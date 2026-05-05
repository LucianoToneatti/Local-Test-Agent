"""
Generador de reporte de resultados de tests.

Consume el dict final producido por autocorrector.autocorrect() y escribe
reporte.md en la raíz del agente con un resumen de passed/failed/sin_resolver
y el tiempo total de ejecución.
"""

import datetime
import pathlib

_OUTPUT_PATH = pathlib.Path(__file__).parent.parent / "reporte.md"


def generate(results: dict, repo_name: str, elapsed: float) -> None:
    """
    Genera reporte.md en la raíz del agente con resumen de resultados.

    Args:
        results: Dict final producido por autocorrector.autocorrect().
                 Formato: {test_id: {'status': str, 'traceback': str|None, 'attempts': list}}
                 También acepta el dict directo de test_runner.run() (sin campo 'attempts').
        repo_name: Nombre del repositorio analizado (e.g. "examples").
        elapsed: Tiempo total de ejecución en segundos.
    """
    passed = sum(1 for v in results.values() if v["status"] == "passed")
    failed_items = [
        (tid, v) for tid, v in results.items() if v["status"] in ("failed", "error")
    ]
    unresolved_items = [
        (tid, v) for tid, v in results.items() if v["status"] == "sin_resolver"
    ]

    fecha = datetime.date.today().isoformat()
    total = len(results)

    lines = [
        f"# Reporte de tests — {repo_name}",
        "",
        f"**Fecha:** {fecha}",
        f"**Tiempo total:** {elapsed:.1f}s",
        "",
        "## Resumen",
        "",
        "| Estado | Cantidad |",
        "|--------|----------|",
        f"| Passed | {passed} |",
        f"| Failed | {len(failed_items)} |",
        f"| Sin resolver | {len(unresolved_items)} |",
        "",
        f"**Total:** {total} tests",
    ]

    if failed_items:
        lines += [
            "",
            "## Tests fallidos",
            "",
        ]
        for tid, v in failed_items:
            last_line = _last_traceback_line(v.get("traceback"))
            lines.append(f"- `{tid}`")
            lines.append(f"  `{last_line}`")

    if unresolved_items:
        lines += [
            "",
            "## Tests sin resolver",
            "",
        ]
        for tid, v in unresolved_items:
            n_attempts = len(v.get("attempts", []))
            lines.append(f"- `{tid}`")
            lines.append(f"  ({n_attempts} intentos agotados)")

    content = "\n".join(lines) + "\n"
    _OUTPUT_PATH.write_text(content, encoding="utf-8")


def _last_traceback_line(traceback: str | None) -> str:
    """
    Extrae la última línea no vacía de un traceback.

    Args:
        traceback: Texto completo del traceback, o None.

    Returns:
        Última línea no vacía del traceback, o 'sin mensaje de error' si no hay contenido.
    """
    if not traceback:
        return "sin mensaje de error"
    lines = [l for l in traceback.strip().splitlines() if l.strip()]
    return lines[-1] if lines else "sin mensaje de error"
