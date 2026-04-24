"""
Punto de entrada del agente local de generación de tests.

Uso:
    python3 agent.py --repo ./examples
"""

import argparse
import ast
import pathlib
import sys

from agent.llm_client import LLMClient, OllamaConnectionError
from prompts.prompt_builder import PromptBuilder, clean_response

_ROOT = pathlib.Path(__file__).parent
OUTPUT_DIR = _ROOT / "tests_generados" / "unit"


def extract_functions(source: str) -> list[tuple[str, str]]:
    """Devuelve lista de (nombre, código_fuente) para cada función de nivel top."""
    tree = ast.parse(source)
    lines = source.splitlines()
    result = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            func_source = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            result.append((node.name, func_source))
    return result


def process_file(py_file: pathlib.Path, client: LLMClient) -> pathlib.Path | None:
    source = py_file.read_text(encoding="utf-8")
    functions = extract_functions(source)

    if not functions:
        print(f"  [!] Sin funciones de nivel top en {py_file.name}, se omite.")
        return None

    blocks: list[str] = []
    for func_name, func_code in functions:
        print(f"  [*] {func_name}()")
        prompt = PromptBuilder.build(func_code, language="python", function_name=func_name)
        try:
            raw = client.generate(prompt.user, system=prompt.system)
        except OllamaConnectionError as e:
            print(f"  [ERROR] {e}")
            sys.exit(1)
        blocks.append(clean_response(raw))

    out_file = OUTPUT_DIR / f"test_{py_file.stem}.py"
    out_file.write_text("\n\n".join(blocks), encoding="utf-8")
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera tests unitarios con un LLM local para los .py del repositorio dado."
    )
    parser.add_argument(
        "--repo",
        required=True,
        metavar="DIR",
        help="Carpeta con los archivos .py a testear.",
    )
    args = parser.parse_args()

    repo = pathlib.Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"[ERROR] '{repo}' no es un directorio válido.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = LLMClient()
    if not client.is_available():
        print(f"[!] Ollama no disponible o modelo '{client.model}' no encontrado.")
        print("    Ejecutá: ollama serve && ollama pull deepseek-coder:6.7b")
        sys.exit(1)

    py_files = sorted(f for f in repo.glob("*.py") if not f.name.startswith("_"))
    if not py_files:
        print(f"[!] No se encontraron archivos .py en '{repo}'.")
        sys.exit(0)

    print(f"[*] {len(py_files)} archivo(s) encontrado(s) en '{repo.name}/'")
    print(f"[*] Salida: {OUTPUT_DIR.relative_to(_ROOT)}/\n")

    for py_file in py_files:
        print(f"[>] {py_file.name}")
        out = process_file(py_file, client)
        if out:
            print(f"  [OK] {out.relative_to(_ROOT)}\n")


if __name__ == "__main__":
    main()
