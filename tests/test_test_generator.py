import ast
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.test_generator import (
    generate,
    _slice_source,
    _generate_block,
    _write_conftest,
    OUTPUT_DIR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ast_result(functions):
    return {
        "calc.py": {
            "functions": [
                {"name": f, "params": ["x"], "_lineno": i * 3 + 1, "_end_lineno": i * 3 + 2}
                for i, f in enumerate(functions)
            ],
            "classes": [],
            "imports": [],
        }
    }


# ---------------------------------------------------------------------------
# Tests de _slice_source
# ---------------------------------------------------------------------------

def test_slice_source_basic():
    lines = ["def f():", "    return 1", ""]
    unit = {"_lineno": 1, "_end_lineno": 2}
    result = _slice_source(lines, unit)
    assert result == "def f():\n    return 1"


def test_slice_source_single_line():
    lines = ["x = 1", "y = 2"]
    unit = {"_lineno": 1, "_end_lineno": 1}
    result = _slice_source(lines, unit)
    assert result == "x = 1"


# ---------------------------------------------------------------------------
# Tests de _write_conftest
# ---------------------------------------------------------------------------

def test_write_conftest_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = Path("/some/repo")
    _write_conftest(repo)
    conftest = tmp_path / "tests_generados" / "unit" / "conftest.py"
    assert conftest.exists()
    content = conftest.read_text()
    assert 'sys.path.insert(0, "/some/repo")' in content


def test_write_conftest_content_format(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = Path("/my/project")
    _write_conftest(repo)
    content = (tmp_path / "tests_generados" / "unit" / "conftest.py").read_text()
    assert "import sys" in content
    assert "import pathlib" in content
    assert "/my/project" in content


# ---------------------------------------------------------------------------
# Tests de _generate_block (con mock de LLMClient)
# ---------------------------------------------------------------------------

VALID_CODE = "import pytest\ndef test_f():\n    assert True\n"
INVALID_CODE = "esto no es python @@##"


def _make_unit(name="f"):
    return {"name": name, "params": [], "_lineno": 1, "_end_lineno": 1}


def test_generate_block_valid_output():
    source_lines = ["def f(): pass"]
    with patch("agent.test_generator.LLMClient") as MockClient:
        client = MockClient.return_value
        client.generate.return_value = VALID_CODE
        result = _generate_block(client, source_lines, _make_unit(), "mymod", None)
    assert not result.startswith("# ERROR")


def test_generate_block_invalid_then_valid():
    source_lines = ["def f(): pass"]
    with patch("agent.test_generator.LLMClient") as MockClient:
        client = MockClient.return_value
        client.generate.side_effect = [INVALID_CODE, VALID_CODE]
        result = _generate_block(client, source_lines, _make_unit(), "mymod", None)
    assert not result.startswith("# ERROR")
    assert client.generate.call_count == 2


def test_generate_block_both_attempts_fail():
    source_lines = ["def f(): pass"]
    with patch("agent.test_generator.LLMClient") as MockClient:
        client = MockClient.return_value
        client.generate.return_value = INVALID_CODE
        result = _generate_block(client, source_lines, _make_unit("bad"), "mymod", None)
    assert result.startswith("# ERROR: no se pudo generar tests para")


def test_generate_block_with_class_name():
    source_lines = ["def method(self): pass"]
    captured_prompts = []

    def fake_generate(user, system=None):
        captured_prompts.append(user)
        return VALID_CODE

    with patch("agent.test_generator.LLMClient") as MockClient:
        client = MockClient.return_value
        client.generate.side_effect = fake_generate
        _generate_block(client, source_lines, _make_unit("method"), "mymod", "MyClass")

    assert len(captured_prompts) >= 1
    assert "MyClass" in captured_prompts[0]


# ---------------------------------------------------------------------------
# Tests de generate (integración con mock, usando tmp_path)
# ---------------------------------------------------------------------------

def _make_repo_with_calc(tmp_path):
    """Crea un repo temporal con un archivo calc.py de 3 funciones simples."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    calc = tmp_path / "calc.py"
    calc.write_text(
        "def add(a, b):\n    return a + b\n\n"
        "def sub(a, b):\n    return a - b\n\n"
        "def mul(a, b):\n    return a * b\n"
    )
    return str(tmp_path)


def _make_ast_result_for_calc():
    return {
        "calc.py": {
            "functions": [
                {"name": "add", "params": ["a", "b"], "_lineno": 1, "_end_lineno": 2},
                {"name": "sub", "params": ["a", "b"], "_lineno": 4, "_end_lineno": 5},
                {"name": "mul", "params": ["a", "b"], "_lineno": 7, "_end_lineno": 8},
            ],
            "classes": [],
            "imports": [],
        }
    }


def test_generate_creates_output_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_calc(tmp_path / "repo")
    ast_result = _make_ast_result_for_calc()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_CODE
        generate(repo, ast_result)

    assert (tmp_path / "tests_generados" / "unit" / "test_calc.py").exists()


def test_generate_creates_conftest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_calc(tmp_path / "repo")
    ast_result = _make_ast_result_for_calc()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_CODE
        generate(repo, ast_result)

    conftest = tmp_path / "tests_generados" / "unit" / "conftest.py"
    assert conftest.exists()
    content = conftest.read_text()
    assert "sys.path.insert" in content
    assert str(Path(repo).resolve()) in content


def test_generate_calls_llm_once_per_function(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_calc(tmp_path / "repo")
    ast_result = _make_ast_result_for_calc()

    with patch("agent.test_generator.LLMClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.generate.return_value = VALID_CODE
        generate(repo, ast_result)

    assert mock_instance.generate.call_count == 3


def test_generate_skips_file_with_no_functions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = str(tmp_path / "repo")
    (tmp_path / "repo").mkdir()
    ast_result = {
        "empty.py": {
            "functions": [],
            "classes": [],
            "imports": [],
        }
    }

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_CODE
        generate(repo, ast_result)

    assert not (tmp_path / "tests_generados" / "unit" / "test_empty.py").exists()
