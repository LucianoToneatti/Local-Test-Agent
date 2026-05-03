"""
Generador de tests unitarios para repositorios Python.

Recibe el dict producido por ast_extractor.extract() y genera archivos pytest
en tests_generados/unit/. Llama al LLM una vez por función/método, valida el
output con ast.parse() y reintenta una vez si el código generado no es válido.
"""

import ast
from pathlib import Path
from typing import Optional

from agent.llm_client import LLMClient
from prompts.prompt_builder import PromptBuilder, clean_response

OUTPUT_DIR = Path("tests_generados/unit")


def generate(repo_path: str, ast_result: dict) -> None:
    """
    Genera tests unitarios para todas las funciones y métodos del ast_result.

    Args:
        repo_path: Ruta al repositorio analizado (absoluta o relativa al cwd).
        ast_result: Dict producido por ast_extractor.extract().
                    Estructura: {rel_path: {functions, classes, imports}}
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = LLMClient()
    repo = Path(repo_path).resolve()

    for rel_path, file_info in ast_result.items():
        blocks = _generate_blocks_for_file(client, repo, rel_path, file_info)
        if blocks:
            stem = Path(rel_path).stem
            out_file = OUTPUT_DIR / f"test_{stem}.py"
            out_file.write_text("\n\n".join(blocks) + "\n")

    _write_conftest(repo)


def _generate_blocks_for_file(
    client: LLMClient,
    repo: Path,
    rel_path: str,
    file_info: dict,
) -> list[str]:
    """Genera todos los bloques de tests para un archivo fuente."""
    source_lines = _read_source_lines(repo, rel_path)
    if source_lines is None:
        return []

    module_name = Path(rel_path).stem
    blocks = []

    for func in file_info.get("functions", []):
        block = _generate_block(
            client=client,
            source_lines=source_lines,
            unit=func,
            module_name=module_name,
            class_name=None,
        )
        blocks.append(block)

    for cls in file_info.get("classes", []):
        for method in cls.get("methods", []):
            block = _generate_block(
                client=client,
                source_lines=source_lines,
                unit=method,
                module_name=module_name,
                class_name=cls["name"],
            )
            blocks.append(block)

    return blocks


def _generate_block(
    client: LLMClient,
    source_lines: list[str],
    unit: dict,
    module_name: str,
    class_name: Optional[str],
) -> str:
    """
    Genera un bloque de tests para una función o método.
    Reintenta una vez si el output del LLM no es Python válido.
    """
    func_source = _slice_source(source_lines, unit)
    func_name = unit["name"]

    for attempt in range(2):
        prompt = PromptBuilder.build(
            code=func_source,
            function_name=func_name,
            module_name=module_name,
            class_name=class_name,
        )
        raw = client.generate(prompt.user, system=prompt.system)
        code = clean_response(raw)
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            if attempt == 0:
                continue  # reintenta

    label = f"{class_name}.{func_name}" if class_name else func_name
    return f"# ERROR: no se pudo generar tests para {label}"


def _slice_source(source_lines: list[str], unit: dict) -> str:
    """Extrae el código fuente de una función/método usando _lineno y _end_lineno."""
    start = unit.get("_lineno", 1) - 1
    end = unit.get("_end_lineno", start + 1)
    return "\n".join(source_lines[start:end])


def _read_source_lines(repo: Path, rel_path: str) -> Optional[list[str]]:
    """Lee el archivo fuente y devuelve sus líneas. Devuelve None si no se puede leer."""
    try:
        return (repo / rel_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None


def _write_conftest(repo: Path) -> None:
    """Escribe conftest.py con la ruta absoluta del repo en sys.path."""
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
        print("Uso: python3 -m agent.test_generator <repo_path>")
        _sys.exit(1)

    repo_path = _sys.argv[1]
    files = explore(repo_path)
    ast_result = extract(files, repo_path)
    generate(repo_path, ast_result)
    print(f"Tests generados en {OUTPUT_DIR}/")
