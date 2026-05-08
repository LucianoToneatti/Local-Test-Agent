"""
Punto de entrada del agente local de generación de tests.

Uso:
    python3 agent.py --repo ./examples
"""

import argparse
import pathlib
import sys
import time

from agent import report_generator
from agent.ast_extractor import extract
from agent.autocorrector import autocorrect
from agent.integration_generator import generate as generate_integration
from agent.llm_client import LLMClient, OllamaConnectionError
from agent.repo_explorer import explore
from agent.test_generator import generate as generate_unit
from agent.test_runner import run as run_tests


def main() -> None:
    start = time.time()

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

    client = LLMClient()
    if not client.is_available():
        print(f"[!] Ollama no disponible o modelo '{client.model}' no encontrado.")
        print("    Ejecutá: ollama serve && ollama pull deepseek-coder:6.7b")
        sys.exit(1)

    print(f"[*] Analizando repositorio '{repo.name}'...")
    ast_result = extract(explore(str(repo)), str(repo))

    print("[*] Generando tests unitarios...")
    generate_unit(str(repo), ast_result)
    print(f"[OK] tests_generados/unit/\n")

    print("[*] Generando tests de integración...")
    generate_integration(str(repo), ast_result)
    print(f"[OK] tests_generados/integration/\n")

    print("[*] Ejecutando tests generados...")
    tests_dir = str(pathlib.Path(__file__).parent / "tests_generados")
    results = run_tests(tests_dir)

    if results:
        passed = sum(1 for v in results.values() if v["status"] == "passed")
        failed = sum(1 for v in results.values() if v["status"] in ("failed", "error"))
        print(f"[*] Resultados: {passed} passed, {failed} failed/error")

        if failed > 0:
            print("[*] Autocorrigiendo tests fallidos (hasta 3 intentos por test)...")
            final = autocorrect(results, str(repo))
            resolved = sum(1 for v in final.values() if v["status"] == "passed")
            unresolved = sum(1 for v in final.values() if v["status"] == "sin_resolver")
            print(f"[OK] Autocorrección: {resolved} resueltos, {unresolved} sin resolver\n")
        else:
            final = results
            print("[OK] Todos los tests pasaron\n")
    else:
        final = {}

    elapsed = time.time() - start
    print("[*] Generando reporte...")
    report_generator.generate(final, repo.name, elapsed)
    print("[OK] Reporte generado: reporte.md")


if __name__ == "__main__":
    main()
