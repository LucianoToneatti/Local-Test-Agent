"""
Interfaz de usuario en terminal para Local-Test-Agent.
Solo usa codigos ANSI estandar y caracteres ASCII — sin librerias externas.
"""

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_title(agent_name: str, version: str) -> None:
    title = f"  {agent_name} {version}  "
    border = "+" + "-" * len(title) + "+"
    print(f"\n{BOLD}{CYAN}{border}{RESET}")
    print(f"{BOLD}{CYAN}|{title}|{RESET}")
    print(f"{BOLD}{CYAN}{border}{RESET}\n")


def print_progress(current: int, total: int, label: str = "") -> None:
    """Imprime una barra de progreso con porcentaje (sobreescribe la linea actual)."""
    if total == 0:
        pct, filled = 100, 30
    else:
        pct = int(current * 100 / total)
        filled = int(30 * current / total)

    arrow = ">" if filled < 30 else ""
    bar = "=" * filled + arrow + " " * max(0, 30 - filled - len(arrow))
    suffix = f" {label}" if label else ""
    print(f"\r  [{bar}] {pct:3d}%{suffix}   ", end="", flush=True)
    if current >= total:
        print()


def print_step(msg: str) -> None:
    print(f"{CYAN}[*]{RESET} {msg}")


def print_ok(msg: str) -> None:
    print(f"{GREEN}[OK]{RESET} {msg}")


def print_error(msg: str) -> None:
    print(f"{RED}[ERROR]{RESET} {msg}")


def print_result_line(test_id: str, status: str) -> None:
    """Imprime una linea de resultado coloreada segun el estado del test."""
    if status == "passed":
        color, icon = GREEN, "[PASS]"
    elif status == "sin_resolver":
        color, icon = YELLOW, "[WARN]"
    else:
        color, icon = RED, "[FAIL]"
    print(f"  {color}{icon}{RESET} {test_id}")


def print_summary(
    passed: int,
    failed: int,
    unresolved: int,
    elapsed: float,
    coverage_pct: float | None = None,
    possible_bugs: int = 0,
) -> None:
    """Imprime el resumen final con colores y tiempo formateado."""
    total = passed + failed + unresolved + possible_bugs
    print(f"\n{BOLD}+--- Resumen final ---+{RESET}")
    print(f"  {GREEN}Passed:       {passed}{RESET}")
    failed_str = f"{RED}Failed:       {failed}{RESET}" if failed > 0 else f"Failed:       {failed}"
    print(f"  {failed_str}")
    unres_str = f"{YELLOW}Sin resolver: {unresolved}{RESET}" if unresolved > 0 else f"Sin resolver: {unresolved}"
    print(f"  {unres_str}")
    bugs_str = f"{RED}Posible bug:  {possible_bugs}{RESET}" if possible_bugs > 0 else f"Posible bug:  {possible_bugs}"
    print(f"  {bugs_str}")
    print(f"  Total:        {total}")
    if coverage_pct is not None:
        print(f"  Cobertura:    {coverage_pct:.0f}%")
    print(f"  Tiempo:       {format_elapsed(elapsed)}")
    print()


def format_elapsed(seconds: float) -> str:
    """Convierte segundos en '2m 34s' o '45s'."""
    if seconds < 60:
        return f"{int(seconds)}s"
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins}m {secs:02d}s"
