import pathlib

import pytest

import agent.report_generator as rg
from agent.report_generator import _last_traceback_line


# ---------------------------------------------------------------------------
# Tests de _last_traceback_line
# ---------------------------------------------------------------------------

def test_last_traceback_line_none():
    assert _last_traceback_line(None) == "sin mensaje de error"


def test_last_traceback_line_empty_string():
    assert _last_traceback_line("") == "sin mensaje de error"


def test_last_traceback_line_whitespace_only():
    assert _last_traceback_line("   \n  ") == "sin mensaje de error"


def test_last_traceback_line_single_line():
    assert _last_traceback_line("AssertionError: assert 1 == 2") == "AssertionError: assert 1 == 2"


def test_last_traceback_line_multiline():
    tb = (
        "Traceback (most recent call last):\n"
        "  File 'test_calc.py', line 5, in test_div\n"
        "    result = 1 / 0\n"
        "ZeroDivisionError: division by zero"
    )
    assert _last_traceback_line(tb) == "ZeroDivisionError: division by zero"


def test_last_traceback_line_trailing_newlines():
    tb = "AssertionError: assert 0 == 1\n\n\n"
    assert _last_traceback_line(tb) == "AssertionError: assert 0 == 1"


# ---------------------------------------------------------------------------
# Tests de generate() — usando monkeypatch para redirigir _OUTPUT_PATH
# ---------------------------------------------------------------------------

def test_generate_creates_reporte_md(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 5.0)
    assert output_file.exists()


def test_generate_header_contains_repo_name(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 5.0)
    content = output_file.read_text()
    assert "# Reporte de tests — myrepo" in content


def test_generate_elapsed_formatted_one_decimal(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 47.3)
    content = output_file.read_text()
    assert "**Tiempo total:** 47.3s" in content


def test_generate_elapsed_rounds_correctly(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 47.0)
    content = output_file.read_text()
    assert "47.0s" in content


def test_generate_summary_table_counts(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    results = {
        "t1": {"status": "passed", "traceback": None},
        "t2": {"status": "passed", "traceback": None},
        "t3": {"status": "failed", "traceback": "AssertionError"},
        "t4": {"status": "sin_resolver", "traceback": None, "attempts": [1, 2, 3]},
    }
    rg.generate(results, "myrepo", 10.0)
    content = output_file.read_text()
    assert "| Passed | 2 |" in content
    assert "| Failed | 1 |" in content
    assert "| Sin resolver | 1 |" in content
    assert "**Total:** 4 tests" in content


def test_generate_no_failed_section_when_empty(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    results = {
        "t1": {"status": "passed", "traceback": None},
    }
    rg.generate(results, "myrepo", 1.0)
    content = output_file.read_text()
    assert "## Tests fallidos" not in content


def test_generate_no_unresolved_section_when_empty(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    results = {
        "t1": {"status": "passed", "traceback": None},
    }
    rg.generate(results, "myrepo", 1.0)
    content = output_file.read_text()
    assert "## Tests sin resolver" not in content


def test_generate_failed_section_shows_test_id(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    results = {
        "tests/test_calc.py::test_suma": {"status": "failed", "traceback": "AssertionError"},
    }
    rg.generate(results, "myrepo", 1.0)
    content = output_file.read_text()
    assert "`tests/test_calc.py::test_suma`" in content


def test_generate_failed_section_shows_last_traceback_line(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    tb = (
        "Traceback (most recent call last):\n"
        "  File 'test_calc.py', line 5\n"
        "ZeroDivisionError: division by zero"
    )
    results = {
        "tests/test_calc.py::test_div": {"status": "failed", "traceback": tb},
    }
    rg.generate(results, "myrepo", 1.0)
    content = output_file.read_text()
    assert "`ZeroDivisionError: division by zero`" in content


def test_generate_unresolved_section_shows_attempt_count(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    results = {
        "tests/test_calc.py::test_raiz": {
            "status": "sin_resolver",
            "traceback": None,
            "attempts": [{"traceback": None, "generated_code": "a"}, {"traceback": None, "generated_code": "b"}, {"traceback": None, "generated_code": "c"}],
        },
    }
    rg.generate(results, "myrepo", 1.0)
    content = output_file.read_text()
    assert "(3 intentos agotados)" in content


def test_generate_passed_not_listed_individually(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    results = {
        "tests/test_calc.py::test_suma": {"status": "passed", "traceback": None},
    }
    rg.generate(results, "myrepo", 1.0)
    content = output_file.read_text()
    # El test_id no debe aparecer en el cuerpo del reporte (solo cuenta en la tabla)
    assert "tests/test_calc.py::test_suma" not in content


def test_generate_empty_results(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 0.0)
    content = output_file.read_text()
    assert output_file.exists()
    assert "**Total:** 0 tests" in content


def test_generate_unresolved_section_shows_traceback_from_attempts(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    tb = (
        "Traceback (most recent call last):\n"
        "  File 'test_calc.py', line 8\n"
        "AssertionError: expected 4 got 5"
    )
    results = {
        "tests/test_calc.py::test_raiz": {
            "status": "sin_resolver",
            "traceback": None,
            "attempts": [{"traceback": tb, "generated_code": "a"}],
        },
    }
    rg.generate(results, "myrepo", 1.0)
    content = output_file.read_text()
    assert "`AssertionError: expected 4 got 5`" in content


def test_generate_error_status_counts_as_failed(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    results = {
        "tests/test_calc.py::test_suma": {"status": "error", "traceback": "ImportError: no module"},
    }
    rg.generate(results, "myrepo", 1.0)
    content = output_file.read_text()
    assert "| Failed | 1 |" in content
    assert "## Tests fallidos" in content


# ---------------------------------------------------------------------------
# Tests de coverage_pct en generate()
# ---------------------------------------------------------------------------

def test_generate_coverage_shown_when_provided(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 5.0, coverage_pct=78.0)
    content = output_file.read_text()
    assert "78%" in content
    assert "**Cobertura:**" in content


def test_generate_coverage_na_when_none(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 5.0, coverage_pct=None)
    content = output_file.read_text()
    assert "N/A" in content


def test_generate_coverage_in_summary_table(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 5.0, coverage_pct=65.0)
    content = output_file.read_text()
    assert "| Cobertura | 65% |" in content


def test_generate_coverage_default_is_na(tmp_path, monkeypatch):
    output_file = tmp_path / "reporte.md"
    monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)
    rg.generate({}, "myrepo", 5.0)
    content = output_file.read_text()
    assert "| Cobertura | N/A |" in content
