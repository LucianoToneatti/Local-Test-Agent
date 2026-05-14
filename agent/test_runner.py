"""
Runner de tests para Python (pytest) y JavaScript/TypeScript (Jest).

Detecta automáticamente qué tipos de tests hay en el directorio y ejecuta
pytest y/o Jest según corresponda. Los resultados se combinan en el mismo
formato {test_id: {status, traceback}}.

Prerequisitos:
- Python: pytest instalado en el entorno activo.
- JavaScript: Node.js y Jest instalados. El agente asume que los
  desarrolladores JS ya tienen estas herramientas — son parte de su
  entorno habitual, igual que Python/pytest lo son para Python.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(tests_dir: str) -> dict:
    """
    Ejecuta pytest y/o Jest sobre tests_dir y devuelve resultados por test_id.

    Args:
        tests_dir: Ruta al directorio con los tests generados.

    Returns:
        Dict con formato {test_id: {'status': str, 'traceback': str|None}}.
        'status' es 'passed', 'failed' o 'error'.
    """
    py_results = _run_pytest(tests_dir)
    js_results = _run_jest(tests_dir)
    return {**py_results, **js_results}


def _run_pytest(tests_dir: str) -> dict:
    """Ejecuta pytest -v sobre tests_dir y devuelve resultados parseados."""
    if importlib.util.find_spec("pytest") is None:
        print("[ERROR] pytest no está instalado. Ejecutá: pip install pytest")
        return {}

    tests_path = Path(tests_dir)
    if not tests_path.exists():
        print(f"[ERROR] El directorio de tests no existe: {tests_dir}")
        return {}

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--continue-on-collection-errors", str(tests_path)],
        capture_output=True,
        text=True,
    )

    return _parse_output(result.stdout + result.stderr)


def _run_jest(tests_dir: str) -> dict:
    """Ejecuta Jest sobre *.test.js y *.test.ts en tests_dir si los hay."""
    tests_path = Path(tests_dir)
    if not tests_path.exists():
        return {}

    js_files = list(tests_path.rglob("*.test.js")) + list(tests_path.rglob("*.test.ts"))
    if not js_files:
        return {}

    if not shutil.which("node"):
        print("[ERROR] Node.js no está instalado. Jest requiere Node.js para ejecutar tests JavaScript.")
        print("    Instalá Node.js desde https://nodejs.org")
        return {}

    # Correr desde el directorio que contiene jest.config.js, no desde tests_dir.
    # agent.py pasa "tests_generados/" pero jest.config.js vive en "tests_generados/unit/".
    jest_cwd = _find_jest_cwd(js_files, tests_path)

    result = subprocess.run(
        ["npx", "jest", "--json", "--no-coverage"],
        capture_output=True,
        text=True,
        cwd=str(jest_cwd),
    )

    return _parse_jest_output(result.stdout)


def _find_jest_cwd(js_files: list, fallback: Path) -> Path:
    """
    Devuelve el directorio desde donde correr Jest.
    Prefiere el directorio de los archivos de test que tenga jest.config.js.
    Si no hay config, usa el directorio común de los archivos JS.
    """
    for f in js_files:
        candidate = f.parent
        if (candidate / "jest.config.js").exists():
            return candidate
    # Fallback: directorio padre común de los archivos JS encontrados
    return js_files[0].parent if js_files else fallback


def _parse_jest_output(stdout: str) -> dict:
    """
    Parsea el JSON de `jest --json` y devuelve {test_id: {status, traceback}}.

    Jest usa la clave 'assertionResults' (no 'testResults') para los tests
    individuales dentro de cada suite.
    """
    json_start = stdout.find('{')
    if json_start == -1:
        return {}
    try:
        data = json.loads(stdout[json_start:])
    except (json.JSONDecodeError, ValueError):
        return {}

    results = {}
    cwd = Path.cwd()

    for suite in data.get("testResults", []):
        abs_file = suite.get("testFilePath", "")
        try:
            rel_path = str(Path(abs_file).relative_to(cwd))
        except ValueError:
            rel_path = abs_file

        for test in suite.get("assertionResults", []):
            title = test.get("title", "unknown")
            status_raw = test.get("status", "failed")
            status = "passed" if status_raw == "passed" else "failed"
            failure_msgs = test.get("failureMessages", [])
            traceback = "\n".join(failure_msgs) if failure_msgs else None
            test_id = f"{rel_path}::{title}"
            results[test_id] = {"status": status, "traceback": traceback}

    return results


def _parse_output(output: str) -> dict:
    """
    Parsea el stdout de pytest -v y extrae resultados por test_id.

    El formato de una línea de resultado en pytest -v es:
      path/test_file.py::test_nombre STATUS
    donde STATUS es PASSED, FAILED o ERROR.

    También captura collection errors (ImportError, ModuleNotFoundError al
    importar el módulo de test), que pytest reporta como:
      ERROR path/test_file.py
    sin ::nombre de función. Estos se registran con el path del archivo como key.
    """
    results = {}

    line_re = re.compile(
        r"^([\w/\\.:-]+::\w+)\s+(PASSED|FAILED|ERROR)", re.MULTILINE
    )
    for match in line_re.finditer(output):
        test_id = match.group(1)
        status = match.group(2).lower()
        results[test_id] = {"status": status, "traceback": None}

    # Collection errors: el archivo no pudo importarse; pytest no llega a
    # enumerar tests individuales. El key es la ruta del archivo (sin ::nombre).
    coll_re = re.compile(r"^ERROR\s+([\w/\\. :-]+\.py)", re.MULTILINE)
    for match in coll_re.finditer(output):
        file_path = match.group(1)
        if file_path not in results:
            results[file_path] = {"status": "error", "traceback": None}

    _attach_tracebacks(output, results)
    _attach_collection_tracebacks(output, results)

    return results


def _attach_collection_tracebacks(output: str, results: dict) -> None:
    """
    Captura bloques de error de colección (ERROR collecting path/file.py)
    y los adjunta al test_id correspondiente (ruta del archivo, sin ::nombre).
    """
    block_re = re.compile(
        r"_{5,}\s+ERROR collecting\s+([\w/\\. :-]+\.py)\s+_{5,}\n(.*?)(?=_{5,}|={5,}|\Z)",
        re.DOTALL,
    )
    for match in block_re.finditer(output):
        file_path = match.group(1)
        traceback_text = match.group(2).strip()
        if file_path in results:
            results[file_path]["traceback"] = traceback_text


def _attach_tracebacks(output: str, results: dict) -> None:
    """
    Busca los bloques de traceback en el output de pytest y los asigna
    al test_id correspondiente en el dict results (modifica in-place).

    pytest -v genera bloques con el patrón:
      _________________________ test_nombre _________________________
      ...traceback...
      ========================= short test summary ===================
    """
    # Captura: header _____func_____ seguido del cuerpo hasta el próximo separador
    block_re = re.compile(
        r"_{5,}\s+(\w+)\s+_{5,}\n(.*?)(?=_{5,}|={5,}|\Z)",
        re.DOTALL,
    )
    for match in block_re.finditer(output):
        func_name = match.group(1)
        traceback_text = match.group(2).strip()
        for test_id in results:
            if test_id.endswith(f"::{func_name}"):
                results[test_id]["traceback"] = traceback_text
                break
