import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.autocorrector import (
    autocorrect,
    _correct_test,
    _extract_function,
    _replace_function,
    _rerun_test,
    _split_test_id,
)


def _make_test_file(tmp_path, content):
    f = tmp_path / "test_calc.py"
    f.write_text(content)
    return f


# ---------------------------------------------------------------------------
# Tests de _split_test_id
# ---------------------------------------------------------------------------

def test_split_test_id_valid(tmp_path):
    f = tmp_path / "test_calc.py"
    f.write_text("def test_suma(): pass\n")
    test_id = f"{f}::test_suma"
    result_file, result_func = _split_test_id(test_id)
    assert result_file == f
    assert result_func == "test_suma"


def test_split_test_id_no_separator():
    file_part, func_name = _split_test_id("tests/test_calc.py")
    assert file_part is None
    assert func_name is None


def test_split_test_id_file_not_exists():
    file_part, func_name = _split_test_id("nonexistent_xyz/test_calc.py::test_suma")
    assert file_part is None
    assert func_name is None


# ---------------------------------------------------------------------------
# Tests de _extract_function
# ---------------------------------------------------------------------------

def test_extract_function_found(tmp_path):
    f = _make_test_file(tmp_path, "def test_suma():\n    assert 1 + 1 == 2\n")
    result = _extract_function(f, "test_suma")
    assert result is not None
    assert "def test_suma" in result


def test_extract_function_not_found(tmp_path):
    f = _make_test_file(tmp_path, "def test_suma(): pass\n")
    result = _extract_function(f, "test_inexistente")
    assert result is None


def test_extract_function_invalid_syntax(tmp_path):
    f = _make_test_file(tmp_path, "def test_f(: INVALID SYNTAX\n")
    result = _extract_function(f, "test_f")
    assert result is None


# ---------------------------------------------------------------------------
# Tests de _replace_function
# ---------------------------------------------------------------------------

def test_replace_function_replaces_only_target(tmp_path):
    content = (
        "def test_suma():\n"
        "    assert 1 + 1 == 3\n"
        "\n"
        "def test_resta():\n"
        "    assert 2 - 1 == 1\n"
    )
    f = _make_test_file(tmp_path, content)
    new_code = "def test_suma():\n    assert 1 + 1 == 2"
    _replace_function(f, "test_suma", new_code)
    result = f.read_text()
    assert "assert 1 + 1 == 2" in result
    assert "def test_resta" in result


def test_replace_function_invalid_file(tmp_path):
    nonexistent = tmp_path / "nonexistent.py"
    _replace_function(nonexistent, "test_f", "def test_f(): pass")
    # No debe lanzar excepción


# ---------------------------------------------------------------------------
# Tests de _rerun_test (subprocess mockeado)
# ---------------------------------------------------------------------------

def test_rerun_test_passed(tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch("agent.autocorrector.subprocess.run", return_value=mock_result):
        result = _rerun_test("path/test_calc.py::test_suma")
    assert result == "passed"


def test_rerun_test_failed(tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = "FAILED test_suma"
    mock_result.stderr = ""
    with patch("agent.autocorrector.subprocess.run", return_value=mock_result):
        result = _rerun_test("path/test_calc.py::test_suma")
    assert result == "failed"


# ---------------------------------------------------------------------------
# Tests de autocorrect (integración con LLMClient mockeado)
# ---------------------------------------------------------------------------

def test_autocorrect_passes_already_passing():
    results = {
        "tests/test_calc.py::test_suma": {"status": "passed", "traceback": None},
        "tests/test_calc.py::test_resta": {"status": "passed", "traceback": None},
    }
    with patch("agent.autocorrector.LLMClient") as MockLLM:
        mock_client = MagicMock()
        MockLLM.return_value = mock_client
        final = autocorrect(results, "/fake/repo")
    mock_client.generate.assert_not_called()
    assert final["tests/test_calc.py::test_suma"]["status"] == "passed"


def test_autocorrect_corrects_failing_test(tmp_path):
    test_content = "def test_suma():\n    assert 1 + 1 == 3\n"
    f = _make_test_file(tmp_path, test_content)
    test_id = f"{f}::test_suma"

    results = {test_id: {"status": "failed", "traceback": "AssertionError"}}

    fixed_code = "def test_suma():\n    assert 1 + 1 == 2"
    mock_run_result = MagicMock()
    mock_run_result.returncode = 0
    mock_run_result.stdout = ""
    mock_run_result.stderr = ""

    with patch("agent.autocorrector.LLMClient") as MockLLM, \
         patch("agent.autocorrector.subprocess.run", return_value=mock_run_result):
        mock_client = MagicMock()
        mock_client.generate.return_value = fixed_code
        MockLLM.return_value = mock_client
        final = autocorrect(results, str(tmp_path))

    assert final[test_id]["status"] == "passed"
    assert len(final[test_id]["attempts"]) == 1
    assert final[test_id]["attempts"][0]["generated_code"] == fixed_code


def test_autocorrect_marks_unresolved_after_3_attempts(tmp_path):
    test_content = "def test_suma():\n    assert 1 + 1 == 3\n"
    f = _make_test_file(tmp_path, test_content)
    test_id = f"{f}::test_suma"

    results = {test_id: {"status": "failed", "traceback": "AssertionError"}}

    fixed_code = "def test_suma():\n    assert 1 + 1 == 2"
    mock_run_result = MagicMock()
    mock_run_result.returncode = 1
    mock_run_result.stdout = "FAILED"
    mock_run_result.stderr = ""

    with patch("agent.autocorrector.LLMClient") as MockLLM, \
         patch("agent.autocorrector.subprocess.run", return_value=mock_run_result):
        mock_client = MagicMock()
        mock_client.generate.return_value = fixed_code
        MockLLM.return_value = mock_client
        final = autocorrect(results, str(tmp_path))

    assert final[test_id]["status"] == "sin_resolver"
    assert mock_client.generate.call_count == 3
    assert len(final[test_id]["attempts"]) == 3


def test_autocorrect_skips_invalid_llm_output(tmp_path):
    test_content = "def test_suma():\n    assert 1 + 1 == 3\n"
    f = _make_test_file(tmp_path, test_content)
    test_id = f"{f}::test_suma"

    results = {test_id: {"status": "failed", "traceback": "AssertionError"}}

    invalid_code = "def test_f(: SYNTAX ERROR"

    with patch("agent.autocorrector.LLMClient") as MockLLM:
        mock_client = MagicMock()
        mock_client.generate.return_value = invalid_code
        MockLLM.return_value = mock_client
        # No debe lanzar excepción
        final = autocorrect(results, str(tmp_path))

    assert final[test_id]["status"] == "sin_resolver"


def test_autocorrect_returns_same_format_as_runner(tmp_path):
    test_content = "def test_suma():\n    assert 1 + 1 == 3\n"
    f = _make_test_file(tmp_path, test_content)
    test_id = f"{f}::test_suma"

    results = {test_id: {"status": "failed", "traceback": "AssertionError"}}

    with patch("agent.autocorrector.LLMClient") as MockLLM:
        mock_client = MagicMock()
        mock_client.generate.return_value = "def test_f(: INVALID"
        MockLLM.return_value = mock_client
        final = autocorrect(results, str(tmp_path))

    for tid, info in final.items():
        assert "status" in info
        assert "traceback" in info
        assert "attempts" in info
        assert isinstance(info["attempts"], list)


def test_autocorrect_attempts_record_traceback_and_code(tmp_path):
    test_content = "def test_suma():\n    assert 1 + 1 == 3\n"
    f = _make_test_file(tmp_path, test_content)
    test_id = f"{f}::test_suma"

    results = {test_id: {"status": "failed", "traceback": "AssertionError: assert 2 == 3"}}

    generated = "def test_suma():\n    assert 1 + 1 == 2"
    mock_run_result = MagicMock()
    mock_run_result.returncode = 1
    mock_run_result.stdout = "FAILED"
    mock_run_result.stderr = ""

    with patch("agent.autocorrector.LLMClient") as MockLLM, \
         patch("agent.autocorrector.subprocess.run", return_value=mock_run_result):
        mock_client = MagicMock()
        mock_client.generate.return_value = generated
        MockLLM.return_value = mock_client
        final = autocorrect(results, str(tmp_path))

    entry = final[test_id]["attempts"][0]
    assert entry["traceback"] == "AssertionError: assert 2 == 3"
    assert entry["generated_code"] == generated
    assert "traceback" in entry
    assert "generated_code" in entry
