import io
import sys

import pytest

from agent.terminal_ui import (
    GREEN, RED, YELLOW, CYAN, BOLD, RESET,
    format_elapsed,
    print_title,
    print_progress,
    print_step,
    print_ok,
    print_error,
    print_result_line,
    print_summary,
)


# ---------------------------------------------------------------------------
# format_elapsed
# ---------------------------------------------------------------------------

def test_format_elapsed_under_60s():
    assert format_elapsed(45.7) == "45s"


def test_format_elapsed_zero():
    assert format_elapsed(0) == "0s"


def test_format_elapsed_exactly_60s():
    assert format_elapsed(60) == "1m 00s"


def test_format_elapsed_90s():
    assert format_elapsed(90) == "1m 30s"


def test_format_elapsed_two_minutes():
    assert format_elapsed(154) == "2m 34s"


def test_format_elapsed_single_digit_seconds_padded():
    assert format_elapsed(65) == "1m 05s"


# ---------------------------------------------------------------------------
# print_title — verifica que imprime borde y contenido
# ---------------------------------------------------------------------------

def test_print_title_contains_agent_name(capsys):
    print_title("MiAgente", "v2.0")
    out = capsys.readouterr().out
    assert "MiAgente" in out
    assert "v2.0" in out


def test_print_title_contains_borders(capsys):
    print_title("X", "v1")
    out = capsys.readouterr().out
    assert "+" in out
    assert "-" in out
    assert "|" in out


def test_print_title_contains_ansi_cyan(capsys):
    print_title("A", "v1")
    out = capsys.readouterr().out
    assert CYAN in out


# ---------------------------------------------------------------------------
# print_step / print_ok / print_error — prefijos y colores
# ---------------------------------------------------------------------------

def test_print_step_prefix(capsys):
    print_step("procesando...")
    out = capsys.readouterr().out
    assert "[*]" in out
    assert "procesando..." in out


def test_print_step_uses_cyan(capsys):
    print_step("msg")
    out = capsys.readouterr().out
    assert CYAN in out


def test_print_ok_prefix(capsys):
    print_ok("listo")
    out = capsys.readouterr().out
    assert "[OK]" in out
    assert "listo" in out


def test_print_ok_uses_green(capsys):
    print_ok("msg")
    out = capsys.readouterr().out
    assert GREEN in out


def test_print_error_prefix(capsys):
    print_error("algo fallo")
    out = capsys.readouterr().out
    assert "[ERROR]" in out
    assert "algo fallo" in out


def test_print_error_uses_red(capsys):
    print_error("msg")
    out = capsys.readouterr().out
    assert RED in out


# ---------------------------------------------------------------------------
# print_result_line — colores segun estado
# ---------------------------------------------------------------------------

def test_print_result_line_passed_is_green(capsys):
    print_result_line("test_foo::test_bar", "passed")
    out = capsys.readouterr().out
    assert GREEN in out
    assert "[PASS]" in out
    assert "test_foo::test_bar" in out


def test_print_result_line_failed_is_red(capsys):
    print_result_line("test_foo::test_bar", "failed")
    out = capsys.readouterr().out
    assert RED in out
    assert "[FAIL]" in out


def test_print_result_line_error_is_red(capsys):
    print_result_line("test_foo::test_bar", "error")
    out = capsys.readouterr().out
    assert RED in out
    assert "[FAIL]" in out


def test_print_result_line_sin_resolver_is_yellow(capsys):
    print_result_line("test_foo::test_bar", "sin_resolver")
    out = capsys.readouterr().out
    assert YELLOW in out
    assert "[WARN]" in out


# ---------------------------------------------------------------------------
# print_progress — barra con porcentaje
# ---------------------------------------------------------------------------

def test_print_progress_shows_100_when_complete(capsys):
    print_progress(5, 5, "done")
    out = capsys.readouterr().out
    assert "100%" in out


def test_print_progress_shows_50_percent(capsys):
    print_progress(1, 2, "")
    out = capsys.readouterr().out
    assert "50%" in out


def test_print_progress_shows_label(capsys):
    print_progress(1, 3, "calculadora.py")
    out = capsys.readouterr().out
    assert "calculadora.py" in out


def test_print_progress_complete_adds_newline(capsys):
    print_progress(3, 3)
    out = capsys.readouterr().out
    assert out.endswith("\n")


def test_print_progress_zero_total_shows_100(capsys):
    print_progress(0, 0)
    out = capsys.readouterr().out
    assert "100%" in out


# ---------------------------------------------------------------------------
# print_summary — resumen final
# ---------------------------------------------------------------------------

def test_print_summary_shows_counts(capsys):
    print_summary(3, 1, 0, 42.0)
    out = capsys.readouterr().out
    assert "3" in out
    assert "1" in out


def test_print_summary_shows_coverage_when_provided(capsys):
    print_summary(5, 0, 0, 10.0, coverage_pct=75.0)
    out = capsys.readouterr().out
    assert "75%" in out


def test_print_summary_no_coverage_line_when_none(capsys):
    print_summary(5, 0, 0, 10.0, coverage_pct=None)
    out = capsys.readouterr().out
    assert "Cobertura" not in out


def test_print_summary_shows_elapsed_formatted(capsys):
    print_summary(1, 0, 0, 90.0)
    out = capsys.readouterr().out
    assert "1m 30s" in out


def test_print_summary_failed_uses_red_when_nonzero(capsys):
    print_summary(0, 2, 0, 5.0)
    out = capsys.readouterr().out
    assert RED in out


def test_print_summary_unresolved_uses_yellow_when_nonzero(capsys):
    print_summary(0, 0, 1, 5.0)
    out = capsys.readouterr().out
    assert YELLOW in out
