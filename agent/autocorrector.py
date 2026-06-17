"""
Autocorrector de tests fallidos.

Itera los tests con status 'failed' o 'error' del dict producido por test_runner.run(),
clasifica cada error como corregible o posible_bug, y para los corregibles llama al LLM
hasta 3 veces por test_id. Los posible_bug se registran sin intentar corrección.

Clasificación:
  posible_bug  — AssertionError con dos valores distintos extraíbles (el test es
                 correcto pero el código falla).
  corregible   — cualquier otro error (sintaxis, imports, NameError, TypeError, etc.)
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

from agent.ast_extractor import extract
from agent.llm_client import LLMClient
from agent.repo_explorer import explore
from prompts.prompt_builder import CorrectionPromptTemplate, clean_response

_TEMPLATE = CorrectionPromptTemplate()
_MAX_ATTEMPTS = 3
_MAX_AUTOCORRECT = 30

# Patrones para detectar comparaciones de valores en AssertionError.
# Grupo 1 = valor izquierdo/esperado, Grupo 2 = valor derecho/obtenido.
_ASSERT_VALUE_PATTERNS = [
    # pytest línea de detalle: "E       assert 12 == 11" (con o sin prefijo "E")
    re.compile(r'^E\s+assert\s+(.+?)\s*==\s*(.+)$', re.MULTILINE),
    # pytest inline: "AssertionError: assert 4 == 5"
    re.compile(r'AssertionError:\s*assert\s+(.+?)\s*==\s*(.+)', re.IGNORECASE),
    # JUnit:   "expected: <4> but was: <5>"
    re.compile(r'expected:\s*<([^>]+)>\s*but was:\s*<([^>]+)>', re.IGNORECASE),
    # pytest approx: "Obtained: 50.0" + "Expected: 25.0"
    re.compile(r'Obtained:\s*(.+?)\n\s*Expected:\s*(.+)', re.IGNORECASE),
    # genérico: "expected 4 but was 5" / "expected 4 got 5"
    re.compile(r'expected:?\s+(.+?)\s+(?:but was|got|actual):?\s+(.+)', re.IGNORECASE),
    # AssertionError con !=: "AssertionError: 4 != 5"
    re.compile(r'AssertionError:\s*(.+?)\s*!=\s*(.+)', re.IGNORECASE),
]


def autocorrect(results: dict, repo_path: str, client=None) -> dict:
    """
    Clasifica y corrige tests fallidos hasta 3 intentos por test_id.

    Args:
        results: Dict producido por test_runner.run().
                 Formato: {test_id: {'status': str, 'traceback': str|None}}
        repo_path: Ruta al repositorio analizado.
        client: Cliente LLM a usar. Si es None crea OllamaClient() por defecto.

    Returns:
        Dict con mismo formato que results. Posibles status finales:
        - 'passed':       corregido exitosamente.
        - 'sin_resolver': agotó 3 intentos sin éxito.
        - 'posible_bug':  AssertionError con valores concretos — no se intenta
                          corrección. Incluye campos 'expected' y 'actual'.
        No modifica tests que ya tenían status 'passed'.
    """
    if client is None:
        client = LLMClient()
    final = dict(results)

    failed_ids = [
        tid for tid, info in results.items()
        if info["status"] in ("failed", "error")
    ]
    to_correct = set(failed_ids[:_MAX_AUTOCORRECT])

    for test_id, info in results.items():
        if info["status"] not in ("failed", "error"):
            continue

        if test_id not in to_correct:
            final[test_id] = {
                "status": "sin_resolver",
                "traceback": info.get("traceback"),
                "reason": "omitido_por_volumen",
            }
        elif _is_import_error(info.get("traceback")):
            final[test_id] = {
                "status": "sin_resolver",
                "traceback": info.get("traceback"),
                "reason": "import_error",
            }
        elif _classify_error(info.get("traceback")) == "posible_bug":
            final[test_id] = _mark_as_possible_bug(info)
        else:
            final[test_id] = _correct_test(client, test_id, info, repo_path)

    return final


_IMPORT_ERROR_PAT = re.compile(r'\b(ModuleNotFoundError|ImportError)\b')

_JUNIT_ASSERT_PAT = re.compile(r'expected:\s*<[^>]+>\s*but was:\s*<[^>]+>', re.IGNORECASE)


def _is_import_error(traceback: str | None) -> bool:
    if not traceback:
        return False
    return bool(_IMPORT_ERROR_PAT.search(traceback))


def _classify_error(traceback: str | None) -> str:
    """
    Clasifica el error como 'posible_bug' o 'corregible'.

    Es 'posible_bug' cuando el traceback indica una discrepancia de valores
    concreta (expected ≠ actual): bien por AssertionError con valores extraíbles,
    bien por el formato JUnit 'expected: <X> but was: <Y>'.
    Cualquier otro error (NameError, TypeError, ImportError, etc.) es 'corregible'.
    """
    if not traceback:
        return "corregible"
    has_assert = "AssertionError" in traceback
    has_junit = bool(_JUNIT_ASSERT_PAT.search(traceback))
    if not has_assert and not has_junit:
        return "corregible"
    expected, actual = _extract_assert_values(traceback)
    if expected is not None and actual is not None and expected != actual:
        return "posible_bug"
    return "corregible"


def _extract_assert_values(traceback: str) -> tuple[str | None, str | None]:
    """
    Intenta extraer (expected, actual) de un traceback con AssertionError.
    Retorna (None, None) si no encuentra el patrón.
    """
    for pattern in _ASSERT_VALUE_PATTERNS:
        m = pattern.search(traceback)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return None, None


def _mark_as_possible_bug(info: dict) -> dict:
    """Construye el dict de resultado para un test clasificado como posible_bug."""
    tb = info.get("traceback") or ""
    expected, actual = _extract_assert_values(tb)
    return {
        "status": "posible_bug",
        "traceback": tb,
        "expected": expected,
        "actual": actual,
    }


def _correct_test(client: LLMClient, test_id: str, info: dict, repo_path: str) -> dict:
    """
    Intenta corregir un test_id fallido hasta _MAX_ATTEMPTS veces.
    Retorna el dict de resultado actualizado con historial de intentos.
    """
    attempts = []

    for attempt in range(_MAX_ATTEMPTS):
        test_file, func_name = _split_test_id(test_id)
        if test_file is None:
            break

        func_code = _extract_function(test_file, func_name)
        if func_code is None:
            break

        module_sigs = _get_module_signatures(test_file, repo_path)
        traceback = info.get("traceback") or ""

        prompt = _TEMPLATE.build(
            code=func_code,
            traceback=traceback,
            module_signatures=module_sigs,
        )
        raw = client.generate(prompt.user, system=prompt.system)
        corrected_code = clean_response(raw, strip_imports=True)

        attempts.append({"traceback": traceback or None, "generated_code": corrected_code})

        try:
            ast.parse(corrected_code)
        except SyntaxError:
            continue

        _replace_function(test_file, func_name, corrected_code)

        new_status = _rerun_test(test_id)
        if new_status == "passed":
            return {"status": "passed", "traceback": None, "attempts": attempts}

        info = {"status": new_status, "traceback": None}

    return {"status": "sin_resolver", "traceback": info.get("traceback"), "attempts": attempts}


def _split_test_id(test_id: str):
    """
    Separa 'path/test_file.py::test_nombre' en (Path('path/test_file.py'), 'test_nombre').
    Retorna (None, None) si el formato no es válido.
    """
    if "::" not in test_id:
        return None, None
    file_part, func_name = test_id.rsplit("::", 1)
    test_file = Path(file_part)
    if not test_file.exists():
        return None, None
    return test_file, func_name


def _extract_function(test_file: Path, func_name: str) -> str | None:
    """
    Extrae el código fuente de la función `func_name` en `test_file` usando AST.
    Retorna None si no se puede leer o la función no existe.
    """
    try:
        source = test_file.read_text(encoding="utf-8")
    except OSError:
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return None


def _replace_function(test_file: Path, func_name: str, new_code: str) -> None:
    """
    Reemplaza la función `func_name` en `test_file` con `new_code`.
    Solo modifica las líneas de esa función — el resto del archivo no cambia.
    """
    try:
        source = test_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return

    lines = source.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            start = node.lineno - 1
            end = node.end_lineno
            new_lines = [line + "\n" for line in new_code.splitlines()]
            lines[start:end] = new_lines
            test_file.write_text("".join(lines), encoding="utf-8")
            return


def _get_module_signatures(test_file: Path, repo_path: str) -> str:
    """
    Infiere el módulo bajo test desde el nombre del archivo de test.
    Convención: test_calculadora.py → buscar calculadora.py en repo_path.
    Retorna las firmas de funciones como string, o '' si no se encuentra.
    """
    stem = test_file.stem  # e.g. "test_calculadora"
    if not stem.startswith("test_"):
        return ""
    module_stem = stem[len("test_"):]  # e.g. "calculadora"

    matches = list(Path(repo_path).rglob(f"{module_stem}.py"))
    if not matches:
        return ""

    try:
        files = explore(repo_path)
        ast_result = extract(files, repo_path)
    except Exception:
        return ""

    for rel_path, file_info in ast_result.items():
        if Path(rel_path).stem == module_stem:
            lines = []
            for func in file_info.get("functions", []):
                params = ", ".join(func.get("params", []))
                lines.append(f"def {func['name']}({params}): ...")
            return "\n".join(lines)
    return ""


def _rerun_test(test_id: str) -> str:
    """
    Re-corre solo el test_id específico con pytest.
    Retorna 'passed', 'failed' o 'error'.
    """
    cmd = [sys.executable, "-m", "pytest", "-v", test_id]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return "passed"
    if "error" in result.stdout.lower() or "error" in result.stderr.lower():
        return "error"
    return "failed"
