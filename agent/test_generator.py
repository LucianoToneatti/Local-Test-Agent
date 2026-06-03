"""
Generador de tests unitarios para repositorios Python y JavaScript/TypeScript.

Para Python genera archivos pytest en tests_generados/unit/test_<stem>.py.
Para JS/TS genera archivos Jest en tests_generados/unit/<stem>.test.js.

Llama al LLM una vez por función/método, valida el output y reintenta
una vez si el código generado no es válido.
"""

import ast
from pathlib import Path
from typing import Optional

from agent.llm_client import LLMClient
from prompts.prompt_builder import PromptBuilder, clean_response

OUTPUT_DIR = Path("tests_generados/unit")

_JS_EXTENSIONS = {'.js', '.ts'}


def _detect_language(rel_path: str) -> str:
    return "javascript" if Path(rel_path).suffix in _JS_EXTENSIONS else "python"


def generate(repo_path: str, ast_result: dict, progress_callback=None) -> None:
    """
    Genera tests unitarios para todas las funciones y métodos del ast_result.

    Args:
        repo_path: Ruta al repositorio analizado (absoluta o relativa al cwd).
        ast_result: Dict producido por ast_extractor.extract().
                    Estructura: {rel_path: {functions, classes, imports}}
        progress_callback: Callable opcional con firma (current, total, label).
                           Se llama despues de procesar cada archivo.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = LLMClient()
    repo = Path(repo_path).expanduser().resolve()
    has_python = False
    has_js = False

    files = list(ast_result.items())
    total = len(files)

    for idx, (rel_path, file_info) in enumerate(files, 1):
        language = _detect_language(rel_path)
        if language == "python":
            has_python = True
        else:
            has_js = True

        blocks = _generate_blocks_for_file(client, repo, rel_path, file_info, language)
        if blocks:
            module_name = Path(rel_path).stem
            if language == "javascript":
                header = _build_js_import_header(module_name, file_info)
                out_file = OUTPUT_DIR / f"{module_name}.test.js"
            else:
                header = _build_import_header(module_name, file_info)
                out_file = OUTPUT_DIR / f"test_{module_name}.py"
            out_file.write_text(header + "\n\n" + "\n\n".join(blocks) + "\n")

        if progress_callback:
            progress_callback(idx, total, Path(rel_path).name)

    if has_python:
        _write_conftest(repo)
    if has_js:
        _write_jest_config(repo)


def _build_import_header(module_name: str, file_info: dict) -> str:
    """Construye el bloque de imports del archivo de tests Python: pytest + símbolos del módulo."""
    lines = ["import pytest"]
    for func in file_info.get("functions", []):
        lines.append(f"from {module_name} import {func['name']}")
    seen: set[str] = set()
    for cls in file_info.get("classes", []):
        if cls["name"] not in seen:
            lines.append(f"from {module_name} import {cls['name']}")
            seen.add(cls["name"])
    return "\n".join(lines)


def _build_js_import_header(module_name: str, file_info: dict) -> str:
    """
    Construye el require CommonJS para el archivo de tests Jest.

    Usa nombre bare (sin './') para que Jest lo resuelva vía modulePaths
    configurado en jest.config.js — análogo a sys.path en conftest.py.
    """
    symbols: list[str] = []
    for func in file_info.get("functions", []):
        symbols.append(func["name"])
    seen: set[str] = set()
    for cls in file_info.get("classes", []):
        if cls["name"] not in seen:
            symbols.append(cls["name"])
            seen.add(cls["name"])
    if symbols:
        destructured = ", ".join(symbols)
        return f"const {{ {destructured} }} = require('{module_name}');"
    return f"const mod = require('{module_name}');"


def _write_jest_config(repo: Path) -> None:
    """
    Escribe jest.config.js en el directorio de tests generados.

    rootDir: '.' restringe a Jest a escanear solo ese directorio (evita que
    suba al home buscando package.json y encuentre archivos malformados).
    modulePaths: [repo] permite require('modulo') sin './' — equivalente al
    sys.path.insert de conftest.py para Python.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = (
        "module.exports = {\n"
        "  rootDir: '.',\n"
        f"  modulePaths: ['{repo}'],\n"
        "};\n"
    )
    (OUTPUT_DIR / "jest.config.js").write_text(config)


def _generate_blocks_for_file(
    client: LLMClient,
    repo: Path,
    rel_path: str,
    file_info: dict,
    language: str = "python",
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
            language=language,
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
                language=language,
            )
            blocks.append(block)

    return blocks


def _generate_block(
    client: LLMClient,
    source_lines: list[str],
    unit: dict,
    module_name: str,
    class_name: Optional[str],
    language: str = "python",
) -> str:
    """
    Genera un bloque de tests para una función o método.
    Reintenta una vez si el output del LLM no es válido.
    """
    func_source = _slice_source(source_lines, unit)
    func_name = unit["name"]

    for attempt in range(2):
        prompt = PromptBuilder.build(
            code=func_source,
            language=language,
            function_name=func_name,
            module_name=module_name,
            class_name=class_name,
        )
        raw = client.generate(prompt.user, system=prompt.system)
        code = clean_response(raw, strip_imports=True, language=language)

        if language == "javascript":
            if "test(" in code or "describe(" in code or "it(" in code:
                return code
        else:
            try:
                ast.parse(code)
                return code
            except SyntaxError:
                pass

        if attempt == 0:
            continue

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
