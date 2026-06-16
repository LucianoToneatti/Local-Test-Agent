"""
Punto de entrada del agente local de generación de tests.

Uso:
    python3 agent.py --repo ./examples
"""

import argparse
import pathlib
import sys
import time

from agent import report_generator, terminal_ui
from agent.ast_extractor import extract
from agent.autocorrector import autocorrect
from agent.integration_generator import generate as generate_integration
from agent.llm_client import OllamaConnectionError, create_client
from agent.repo_explorer import explore
from agent.test_generator import generate as generate_unit
from agent.test_runner import run as run_tests


def main() -> None:
    start = time.time()

    terminal_ui.print_title("Local-Test-Agent", "v1.0")

    parser = argparse.ArgumentParser(
        description="Genera tests unitarios con un LLM para los archivos del repositorio dado."
    )
    parser.add_argument(
        "--repo",
        required=True,
        metavar="DIR",
        help="Carpeta con los archivos a testear.",
    )
    parser.add_argument(
        "--provider",
        choices=["local", "groq"],
        default="local",
        help="Proveedor LLM: 'local' usa Ollama (default), 'groq' usa Groq cloud.",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="NOMBRE",
        help="Nombre del modelo a usar. Default: deepseek-coder:6.7b (local) o llama-3.1-8b-instant (groq).",
    )
    args = parser.parse_args()

    repo = pathlib.Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        terminal_ui.print_error(f"'{repo}' no es un directorio valido.")
        sys.exit(1)

    client = create_client(args.provider, args.model)
    if not client.is_available():
        if args.provider == "groq":
            terminal_ui.print_error(
                "GROQ_API_KEY no encontrada. "
                "Exportá la variable de entorno antes de usar --provider groq."
            )
        else:
            terminal_ui.print_error(
                f"Ollama no disponible o modelo '{client.model}' no encontrado."
            )
            print("    Ejecuta: ollama serve && ollama pull deepseek-coder:6.7b")
        sys.exit(1)

    terminal_ui.print_step(f"Analizando repositorio '{repo.name}'...")
    ast_result = extract(explore(str(repo)), str(repo))

    total_files = len(ast_result)
    terminal_ui.print_step(f"Generando tests unitarios ({total_files} archivo(s))...")
    generate_unit(str(repo), ast_result, progress_callback=terminal_ui.print_progress, client=client)
    terminal_ui.print_ok("tests_generados/unit/\n")

    terminal_ui.print_step("Generando tests de integracion...")
    generate_integration(str(repo), ast_result, progress_callback=terminal_ui.print_progress, client=client)
    terminal_ui.print_ok("tests_generados/integration/\n")

    terminal_ui.print_step("Ejecutando tests generados...")
    tests_dir = str(pathlib.Path(__file__).parent / "tests_generados")
    results, coverage_pct = run_tests(tests_dir, str(repo))

    if results:
        passed = sum(1 for v in results.values() if v["status"] == "passed")
        failed = sum(1 for v in results.values() if v["status"] in ("failed", "error"))

        for test_id, info in results.items():
            terminal_ui.print_result_line(test_id, info["status"])
        print()

        if failed > 0:
            terminal_ui.print_step(f"Autocorrigiendo {failed} test(s) fallido(s) (hasta 3 intentos)...")
            final = autocorrect(results, str(repo), client=client)
            resolved = sum(1 for v in final.values() if v["status"] == "passed")
            unresolved = sum(1 for v in final.values() if v["status"] == "sin_resolver")
            bugs = sum(1 for v in final.values() if v["status"] == "posible_bug")
            terminal_ui.print_ok(
                f"Autocorreccion: {resolved} resuelto(s), {unresolved} sin resolver, {bugs} posible(s) bug\n"
            )
        else:
            final = results
            terminal_ui.print_ok("Todos los tests pasaron\n")
    else:
        final = {}

    elapsed = time.time() - start

    terminal_ui.print_step("Generando reporte...")
    report_generator.generate(final, repo.name, elapsed, coverage_pct=coverage_pct)
    terminal_ui.print_ok("Reporte generado: reporte.md")
    terminal_ui.print_report_preview(final)

    passed_final = sum(1 for v in final.values() if v["status"] == "passed")
    failed_final = sum(1 for v in final.values() if v["status"] in ("failed", "error"))
    unresolved_final = sum(1 for v in final.values() if v["status"] == "sin_resolver")
    possible_bugs_final = sum(1 for v in final.values() if v["status"] == "posible_bug")
    terminal_ui.print_summary(
        passed_final, failed_final, unresolved_final, elapsed, coverage_pct,
        possible_bugs=possible_bugs_final,
    )


if __name__ == "__main__":
    main()
