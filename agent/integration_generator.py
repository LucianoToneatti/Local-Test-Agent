"""
Generador de tests de integración para repositorios Python.

Recibe el dict producido por ast_extractor.extract(), detecta pares de módulos
relacionados por imports, llama al LLM una vez por par, valida el output con
ast.parse() y reintenta una vez si el código generado no es válido.
"""

import ast
from pathlib import Path
from typing import Optional

from agent.llm_client import LLMClient
from prompts.prompt_builder import IntegrationPromptTemplate, clean_response

OUTPUT_DIR = Path("tests_generados/integration")
_TEMPLATE = IntegrationPromptTemplate()


def generate(repo_path: str, ast_result: dict) -> None:
    """
    Genera tests de integración para todos los pares de módulos relacionados.

    Args:
        repo_path: Ruta al repositorio analizado (absoluta o relativa al cwd).
        ast_result: Dict producido por ast_extractor.extract().
                    Estructura: {rel_path: {functions, classes, imports}}
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = LLMClient()
    repo = Path(repo_path).resolve()

    pairs = _find_pairs(ast_result)
    for (a_path, b_path) in pairs:
        code = _generate_pair_test(client, repo, a_path, b_path, ast_result)
        stem_a = Path(a_path).stem
        stem_b = Path(b_path).stem
        out_file = OUTPUT_DIR / f"test_{stem_a}_{stem_b}.py"
        out_file.write_text(code + "\n")

    _write_conftest(repo)


def _find_pairs(ast_result: dict) -> list[tuple[str, str]]:
    """
    Retorna la lista de pares (importer_path, imported_path) detectados por imports.

    Un par (A, B) se incluye cuando el campo `imports` de A contiene la ruta relativa de B
    y B está también presente como key en ast_result.
    """
    pairs = []
    for rel_path, file_info in ast_result.items():
        for imported in file_info.get("imports", []):
            if imported in ast_result:
                pairs.append((rel_path, imported))
    return pairs


def _format_signatures(file_info: dict) -> str:
    """
    Formatea las firmas de las funciones top-level de un módulo como string.

    Ejemplo de salida:
        def sumar(a, b): ...
        def multiplicar(a, b): ...
    """
    lines = []
    for func in file_info.get("functions", []):
        params = ", ".join(func.get("params", []))
        lines.append(f"def {func['name']}({params}): ...")
    return "\n".join(lines)


def _generate_pair_test(
    client: LLMClient,
    repo: Path,
    a_path: str,
    b_path: str,
    ast_result: dict,
) -> str:
    """
    Genera el código de tests de integración para el par (a_path importa b_path).
    Reintenta una vez si el output del LLM no es Python válido.
    """
    a_source = _read_source(repo, a_path)
    if a_source is None:
        return f"# ERROR: no se pudo leer {a_path}"

    b_sigs = _format_signatures(ast_result.get(b_path, {}))
    stem_a = Path(a_path).stem
    stem_b = Path(b_path).stem

    for attempt in range(2):
        prompt = _TEMPLATE.build(
            code=a_source,
            module_name=stem_a,
            class_name=stem_b,
            module_b_sigs=b_sigs,
        )
        raw = client.generate(prompt.user, system=prompt.system)
        code = clean_response(raw)
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            if attempt == 0:
                continue

    return f"# ERROR: no se pudo generar test de integración para {stem_a}_{stem_b}"


def _read_source(repo: Path, rel_path: str) -> Optional[str]:
    """Lee el código fuente completo de un módulo. Retorna None si no se puede leer."""
    try:
        return (repo / rel_path).read_text(encoding="utf-8")
    except OSError:
        return None


def _write_conftest(repo: Path) -> None:
    """Escribe conftest.py con la ruta absoluta del repo analizado en sys.path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    content = (
        "import sys\n"
        "import pathlib\n"
        "\n"
        f'sys.path.insert(0, "{repo}")\n'
    )
    (OUTPUT_DIR / "conftest.py").write_text(content)


if __name__ == "__main__":
    import sys as _sys
    from agent.repo_explorer import explore
    from agent.ast_extractor import extract

    if len(_sys.argv) < 2:
        print("Uso: python3 -m agent.integration_generator <repo_path>")
        _sys.exit(1)

    repo_path = _sys.argv[1]
    files = explore(repo_path)
    ast_result = extract(files, repo_path)
    generate(repo_path, ast_result)
    print(f"Tests de integración generados en {OUTPUT_DIR}/")
