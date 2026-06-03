import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.test_runner import (
    _attach_collection_tracebacks,
    _attach_tracebacks,
    _parse_coverage,
    _parse_output,
    _parse_jest_output,
    _parse_surefire_reports,
    run,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_subprocess_result(stdout="", stderr="", returncode=0):
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock


# ---------------------------------------------------------------------------
# run() — detección de pytest no instalado
# ---------------------------------------------------------------------------

def test_run_pytest_not_installed(capsys, monkeypatch):
    # _run_pytest verifica pytest ANTES de verificar el directorio, así que
    # una ruta inexistente es suficiente para aislar el check de pytest sin
    # que _run_jest encuentre archivos .test.js reales.
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    results, cov = run("nonexistent_dir_xyz_abc")
    assert results == {}
    assert cov is None
    captured = capsys.readouterr()
    assert "pip install pytest" in captured.out


# ---------------------------------------------------------------------------
# run() — directorio inexistente
# ---------------------------------------------------------------------------

def test_run_directory_not_found(capsys, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    results, cov = run("nonexistent_dir_xyz_abc")
    assert results == {}
    assert cov is None
    captured = capsys.readouterr()
    assert "no existe" in captured.out


# ---------------------------------------------------------------------------
# _parse_output() — parseo de resultados
# ---------------------------------------------------------------------------

def test_parse_output_all_passed():
    output = (
        "tests_generados/unit/test_calc.py::test_sumar PASSED\n"
        "tests_generados/unit/test_calc.py::test_restar PASSED\n"
    )
    result = _parse_output(output)
    assert len(result) == 2
    for test_id, info in result.items():
        assert info["status"] == "passed"
        assert info["traceback"] is None


def test_parse_output_mixed_results():
    output = (
        "tests_generados/unit/test_calc.py::test_suma PASSED\n"
        "tests_generados/unit/test_calc.py::test_div FAILED\n"
        "tests_generados/unit/test_calc.py::test_mod ERROR\n"
    )
    result = _parse_output(output)
    assert result["tests_generados/unit/test_calc.py::test_suma"]["status"] == "passed"
    assert result["tests_generados/unit/test_calc.py::test_div"]["status"] == "failed"
    assert result["tests_generados/unit/test_calc.py::test_mod"]["status"] == "error"


def test_parse_output_empty_output():
    assert _parse_output("") == {}


def test_parse_output_failed_has_none_traceback_by_default():
    output = "tests_generados/unit/test_calc.py::test_div FAILED\n"
    result = _parse_output(output)
    test_id = "tests_generados/unit/test_calc.py::test_div"
    assert result[test_id]["traceback"] is None


# ---------------------------------------------------------------------------
# _attach_tracebacks() — extracción de tracebacks
# ---------------------------------------------------------------------------

def test_attach_tracebacks_assigns_to_correct_test():
    output = (
        "tests_generados/unit/test_calc.py::test_sumar FAILED\n"
        "============================= FAILURES =============================\n"
        "_____________________________ test_sumar ____________________________\n"
        "AssertionError: assert 1 == 2\n"
        "=========================== short test summary ============================\n"
    )
    results = {
        "tests_generados/unit/test_calc.py::test_sumar": {"status": "failed", "traceback": None}
    }
    _attach_tracebacks(output, results)
    tb = results["tests_generados/unit/test_calc.py::test_sumar"]["traceback"]
    assert tb is not None
    assert "AssertionError" in tb


def test_attach_tracebacks_no_failure_block():
    output = "tests_generados/unit/test_calc.py::test_sumar PASSED\n"
    results = {
        "tests_generados/unit/test_calc.py::test_sumar": {"status": "passed", "traceback": None}
    }
    _attach_tracebacks(output, results)
    assert results["tests_generados/unit/test_calc.py::test_sumar"]["traceback"] is None


# ---------------------------------------------------------------------------
# run() — integración con subprocess mockeado
# ---------------------------------------------------------------------------

def test_run_returns_passed_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    stdout = "tests_generados/unit/test_calc.py::test_suma PASSED\n"
    with patch("agent.test_runner.subprocess.run", return_value=_make_subprocess_result(stdout=stdout)):
        results, cov = run(str(tmp_path))
    assert results == {
        "tests_generados/unit/test_calc.py::test_suma": {"status": "passed", "traceback": None}
    }


def test_run_returns_failed_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    stdout = "tests_generados/unit/test_calc.py::test_div FAILED\n"
    with patch("agent.test_runner.subprocess.run", return_value=_make_subprocess_result(stdout=stdout, returncode=1)):
        results, cov = run(str(tmp_path))
    assert results["tests_generados/unit/test_calc.py::test_div"]["status"] == "failed"


def test_run_subprocess_called_with_list(tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    with patch("agent.test_runner.subprocess.run", return_value=_make_subprocess_result()) as mock_run:
        run(str(tmp_path))
    call_args = mock_run.call_args
    assert isinstance(call_args[0][0], list)


# ---------------------------------------------------------------------------
# _parse_output() — collection errors (módulo no importable)
# ---------------------------------------------------------------------------

_COLLECTION_ERROR_OUTPUT = (
    "============================= test session starts ==============================\n"
    "collecting ... collected 0 items / 1 error\n"
    "\n"
    "==================================== ERRORS ====================================\n"
    "_____________ ERROR collecting tests_generados/unit/test_pacman.py _____________\n"
    "ImportError while importing test module '/tmp/test_pacman.py'.\n"
    "tests_generados/unit/test_pacman.py:1: in <module>\n"
    "    from pacman import setupRoomOne\n"
    "E   ModuleNotFoundError: No module named 'pygame'\n"
    "=========================== short test summary info ============================\n"
    "ERROR tests_generados/unit/test_pacman.py\n"
    "!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!\n"
)


def test_parse_output_collection_error_creates_entry():
    result = _parse_output(_COLLECTION_ERROR_OUTPUT)
    assert "tests_generados/unit/test_pacman.py" in result


def test_parse_output_collection_error_status_is_error():
    result = _parse_output(_COLLECTION_ERROR_OUTPUT)
    assert result["tests_generados/unit/test_pacman.py"]["status"] == "error"


def test_parse_output_collection_error_traceback_contains_module_error():
    result = _parse_output(_COLLECTION_ERROR_OUTPUT)
    tb = result["tests_generados/unit/test_pacman.py"]["traceback"]
    assert tb is not None
    assert "ModuleNotFoundError" in tb


def test_attach_collection_tracebacks_assigns_traceback():
    output = (
        "==================================== ERRORS ====================================\n"
        "_____________ ERROR collecting tests_generados/unit/test_foo.py _____________\n"
        "ImportError: No module named 'bar'\n"
        "E   ModuleNotFoundError: No module named 'bar'\n"
        "=========================== short test summary info ============================\n"
    )
    results = {"tests_generados/unit/test_foo.py": {"status": "error", "traceback": None}}
    _attach_collection_tracebacks(output, results)
    tb = results["tests_generados/unit/test_foo.py"]["traceback"]
    assert tb is not None
    assert "ModuleNotFoundError" in tb


def test_attach_collection_tracebacks_no_match_leaves_none():
    output = "no collection errors here\n"
    results = {"tests_generados/unit/test_foo.py": {"status": "error", "traceback": None}}
    _attach_collection_tracebacks(output, results)
    assert results["tests_generados/unit/test_foo.py"]["traceback"] is None


_MIXED_OUTPUT = (
    "============================= test session starts ==============================\n"
    "collecting ... collected 2 items / 1 error\n"
    "\n"
    "tests_generados/unit/test_good.py::test_always_passes PASSED             [ 50%]\n"
    "tests_generados/unit/test_good.py::test_another_pass PASSED              [100%]\n"
    "\n"
    "==================================== ERRORS ====================================\n"
    "_____________ ERROR collecting tests_generados/unit/test_bad.py _____________\n"
    "ImportError while importing test module '/tmp/test_bad.py'.\n"
    "E   ModuleNotFoundError: No module named 'nonexistent_module_xyz'\n"
    "=========================== short test summary info ============================\n"
    "ERROR tests_generados/unit/test_bad.py\n"
    "========================== 2 passed, 1 error in 0.05s ==========================\n"
)


def test_parse_output_mixed_passes_and_collection_error():
    result = _parse_output(_MIXED_OUTPUT)
    assert result["tests_generados/unit/test_good.py::test_always_passes"]["status"] == "passed"
    assert result["tests_generados/unit/test_good.py::test_another_pass"]["status"] == "passed"
    assert result["tests_generados/unit/test_bad.py"]["status"] == "error"


def test_parse_output_mixed_passed_count():
    result = _parse_output(_MIXED_OUTPUT)
    passed = sum(1 for v in result.values() if v["status"] == "passed")
    errors = sum(1 for v in result.values() if v["status"] == "error")
    assert passed == 2
    assert errors == 1


def test_run_subprocess_called_with_continue_on_collection_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    with patch("agent.test_runner.subprocess.run", return_value=_make_subprocess_result()) as mock_run:
        run(str(tmp_path))
    cmd = mock_run.call_args[0][0]
    assert "--continue-on-collection-errors" in cmd


def test_run_captures_stderr(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    with patch(
        "agent.test_runner.subprocess.run",
        return_value=_make_subprocess_result(stderr="some error output", returncode=1),
    ):
        results, cov = run(str(tmp_path))
    assert isinstance(results, dict)


# ---------------------------------------------------------------------------
# _parse_coverage — extracción del porcentaje de cobertura
# ---------------------------------------------------------------------------

_COVERAGE_OUTPUT = (
    "---------- coverage: platform linux, python 3.11.0 ----------\n"
    "Name                Stmts   Miss  Cover\n"
    "----------------------------------------\n"
    "calculadora.py         10      2    80%\n"
    "estadistica.py         15      5    67%\n"
    "----------------------------------------\n"
    "TOTAL                  25      7    72%\n"
)


def test_parse_coverage_extracts_total_percentage():
    assert _parse_coverage(_COVERAGE_OUTPUT) == 72.0


def test_parse_coverage_100_percent():
    output = "TOTAL   50   0   100%\n"
    assert _parse_coverage(output) == 100.0


def test_parse_coverage_no_coverage_info_returns_none():
    assert _parse_coverage("no coverage output here\n") is None


def test_parse_coverage_empty_string_returns_none():
    assert _parse_coverage("") is None


def test_run_cov_flag_added_when_repo_and_pytest_cov_available(tmp_path, monkeypatch):
    monkeypatch.setattr(
        importlib.util, "find_spec",
        lambda name: object()  # simula pytest Y pytest_cov instalados
    )
    with patch("agent.test_runner.subprocess.run", return_value=_make_subprocess_result()) as mock_run:
        run(str(tmp_path), repo_path="/some/repo")
    cmd = mock_run.call_args[0][0]
    assert any("--cov=" in arg for arg in cmd)


def test_run_no_cov_flag_when_no_repo_path(tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    with patch("agent.test_runner.subprocess.run", return_value=_make_subprocess_result()) as mock_run:
        run(str(tmp_path))
    cmd = mock_run.call_args[0][0]
    assert not any("--cov" in arg for arg in cmd)


def test_run_returns_coverage_pct_from_output(tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    stdout = (
        "tests_generados/unit/test_calc.py::test_suma PASSED\n"
        "TOTAL   25   7   72%\n"
    )
    with patch("agent.test_runner.subprocess.run", return_value=_make_subprocess_result(stdout=stdout)):
        results, cov = run(str(tmp_path), repo_path="/some/repo")
    assert cov == 72.0


def test_run_returns_none_coverage_without_repo_path(tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    stdout = "tests_generados/unit/test_calc.py::test_suma PASSED\nTOTAL   25   7   72%\n"
    with patch("agent.test_runner.subprocess.run", return_value=_make_subprocess_result(stdout=stdout)):
        results, cov = run(str(tmp_path))
    assert cov is None


# ---------------------------------------------------------------------------
# _parse_jest_output — parseo de resultados Jest JSON (HU-11)
# ---------------------------------------------------------------------------

def _make_jest_json(tests: list[dict], file_path: str = "/tmp/calc.test.js") -> str:
    data = {
        "testResults": [
            {
                "testFilePath": file_path,
                "assertionResults": tests,  # clave real del JSON de Jest
            }
        ]
    }
    return json.dumps(data)


def test_parse_jest_output_passed():
    stdout = _make_jest_json([{"title": "adds two numbers", "status": "passed", "failureMessages": []}])
    result = _parse_jest_output(stdout)
    assert any("adds two numbers" in k for k in result)
    statuses = [v["status"] for v in result.values()]
    assert "passed" in statuses


def test_parse_jest_output_failed():
    stdout = _make_jest_json([
        {"title": "handles zero", "status": "failed", "failureMessages": ["Expected 0 to be 1"]}
    ])
    result = _parse_jest_output(stdout)
    test_id = next(k for k in result if "handles zero" in k)
    assert result[test_id]["status"] == "failed"
    assert result[test_id]["traceback"] is not None
    assert "Expected 0 to be 1" in result[test_id]["traceback"]


def test_parse_jest_output_empty_json():
    assert _parse_jest_output("") == {}


def test_parse_jest_output_invalid_json():
    assert _parse_jest_output("not json at all") == {}


def test_parse_jest_output_multiple_tests():
    stdout = _make_jest_json([
        {"title": "test A", "status": "passed", "failureMessages": []},
        {"title": "test B", "status": "failed", "failureMessages": ["Error"]},
    ])
    result = _parse_jest_output(stdout)
    assert len(result) == 2


def test_parse_jest_output_no_traceback_when_passed():
    stdout = _make_jest_json([{"title": "ok", "status": "passed", "failureMessages": []}])
    result = _parse_jest_output(stdout)
    test_id = next(iter(result))
    assert result[test_id]["traceback"] is None


# ---------------------------------------------------------------------------
# _run_jest — detección de Node.js no instalado (HU-11)
# ---------------------------------------------------------------------------

def test_run_jest_no_node_prints_error(tmp_path, capsys):
    (tmp_path / "calc.test.js").write_text("test('x', () => {})")
    with patch("agent.test_runner.shutil.which", return_value=None):
        from agent.test_runner import _run_jest
        result = _run_jest(str(tmp_path))
    assert result == {}
    captured = capsys.readouterr()
    assert "Node.js" in captured.out


def test_run_jest_no_js_files_returns_empty(tmp_path):
    from agent.test_runner import _run_jest
    result = _run_jest(str(tmp_path))
    assert result == {}


# ---------------------------------------------------------------------------
# Maven / Java (HU-14)
# ---------------------------------------------------------------------------

def test_run_maven_no_java_files_returns_empty(tmp_path):
    from agent.test_runner import _run_maven
    result = _run_maven(str(tmp_path))
    assert result == {}


def test_run_maven_no_mvn_prints_message(tmp_path, capsys):
    java_test_dir = tmp_path / "src" / "test" / "java"
    java_test_dir.mkdir(parents=True)
    (java_test_dir / "CalculadoraTest.java").write_text("class CalculadoraTest {}")

    with patch("agent.test_runner.shutil.which", return_value=None):
        from agent.test_runner import _run_maven
        result = _run_maven(str(tmp_path))

    assert result == {}
    captured = capsys.readouterr()
    assert "Maven" in captured.out
    assert "mvn" in captured.out


def test_run_maven_no_mvn_message_includes_install_hint(tmp_path, capsys):
    java_test_dir = tmp_path / "src" / "test" / "java"
    java_test_dir.mkdir(parents=True)
    (java_test_dir / "CalcTest.java").write_text("class CalcTest {}")

    with patch("agent.test_runner.shutil.which", return_value=None):
        from agent.test_runner import _run_maven
        _run_maven(str(tmp_path))

    captured = capsys.readouterr()
    assert "sudo apt install maven" in captured.out or "install" in captured.out.lower()


def _make_surefire_xml(tmp_path, classname, tests):
    """
    Escribe un XML de Surefire en tmp_path/target/surefire-reports/.
    tests: lista de dict con keys: name, failure (opcional), error (opcional).
    """
    reports = tmp_path / "target" / "surefire-reports"
    reports.mkdir(parents=True)
    lines = [f'<?xml version="1.0" encoding="UTF-8"?>',
             f'<testsuite name="{classname}" tests="{len(tests)}">']
    for t in tests:
        lines.append(f'  <testcase name="{t["name"]}" classname="{classname}">')
        if "failure" in t:
            lines.append(f'    <failure message="{t["failure"]}"/>')
        elif "error" in t:
            lines.append(f'    <error message="{t["error"]}"/>')
        elif "skipped" in t:
            lines.append('    <skipped/>')
        lines.append('  </testcase>')
    lines.append('</testsuite>')
    (reports / f"TEST-{classname}.xml").write_text("\n".join(lines))
    return reports


def test_parse_surefire_reports_passed():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = _make_surefire_xml(Path(tmpdir), "CalculadoraTest", [{"name": "testSuma"}])
        result = _parse_surefire_reports(reports)
    assert "CalculadoraTest::testSuma" in result
    assert result["CalculadoraTest::testSuma"]["status"] == "passed"


def test_parse_surefire_reports_failed():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = _make_surefire_xml(
            Path(tmpdir), "CalculadoraTest",
            [{"name": "testDividir", "failure": "expected 2 but was 3"}]
        )
        result = _parse_surefire_reports(reports)
    assert result["CalculadoraTest::testDividir"]["status"] == "failed"
    assert "expected 2" in result["CalculadoraTest::testDividir"]["traceback"]


def test_parse_surefire_reports_skipped():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = _make_surefire_xml(
            Path(tmpdir), "CalculadoraTest",
            [{"name": "testPendiente", "skipped": True}]
        )
        result = _parse_surefire_reports(reports)
    assert result["CalculadoraTest::testPendiente"]["status"] == "skipped"


def test_parse_surefire_reports_empty_dir_returns_empty(tmp_path):
    result = _parse_surefire_reports(tmp_path / "nonexistent")
    assert result == {}


def test_run_combines_pytest_and_jest_results(tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    (tmp_path / "calc.test.js").write_text("test('x', () => {})")

    jest_json = _make_jest_json(
        [{"title": "js test", "status": "passed", "failureMessages": []}],
        file_path=str(tmp_path / "calc.test.js"),
    )
    pytest_stdout = "tests_generados/unit/test_calc.py::test_py PASSED\n"

    def fake_subprocess(*args, **kwargs):
        cmd = args[0]
        if "jest" in cmd:
            return _make_subprocess_result(stdout=jest_json)
        return _make_subprocess_result(stdout=pytest_stdout)

    with patch("agent.test_runner.subprocess.run", side_effect=fake_subprocess):
        with patch("agent.test_runner.shutil.which", return_value="/usr/bin/node"):
            results, cov = run(str(tmp_path))

    assert any("js test" in k for k in results)
    assert any("test_py" in k for k in results)
