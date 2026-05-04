import ast
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.integration_generator import (
    generate,
    _find_pairs,
    _format_signatures,
    _generate_pair_test,
    _write_conftest,
    OUTPUT_DIR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ast_result(files_and_imports):
    """
    files_and_imports: dict {rel_path: {'functions': [...], 'imports': [...]}}
    Cada función: {'name': str, 'params': list, '_lineno': int, '_end_lineno': int}
    """
    result = {}
    for path, info in files_and_imports.items():
        result[path] = {
            "functions": info.get("functions", []),
            "classes": [],
            "imports": info.get("imports", []),
        }
    return result


# ---------------------------------------------------------------------------
# Tests de _find_pairs
# ---------------------------------------------------------------------------

def test_find_pairs_single_import():
    ast_result = _make_ast_result({
        "a.py": {"imports": ["b.py"]},
        "b.py": {"imports": []},
    })
    pairs = _find_pairs(ast_result)
    assert pairs == [("a.py", "b.py")]


def test_find_pairs_no_imports():
    ast_result = _make_ast_result({
        "a.py": {"imports": []},
        "b.py": {"imports": []},
    })
    assert _find_pairs(ast_result) == []


def test_find_pairs_import_outside_repo():
    ast_result = _make_ast_result({
        "a.py": {"imports": ["external.py"]},
        "b.py": {"imports": []},
    })
    assert _find_pairs(ast_result) == []


def test_find_pairs_mutual_imports():
    ast_result = _make_ast_result({
        "a.py": {"imports": ["b.py"]},
        "b.py": {"imports": ["a.py"]},
    })
    pairs = _find_pairs(ast_result)
    assert len(pairs) == 2
    assert ("a.py", "b.py") in pairs
    assert ("b.py", "a.py") in pairs


# ---------------------------------------------------------------------------
# Tests de _format_signatures
# ---------------------------------------------------------------------------

def test_format_signatures_basic():
    file_info = {
        "functions": [
            {"name": "sumar", "params": ["a", "b"]},
            {"name": "restar", "params": ["a", "b"]},
        ]
    }
    result = _format_signatures(file_info)
    assert "def sumar(a, b): ..." in result
    assert "def restar(a, b): ..." in result


def test_format_signatures_no_functions():
    file_info = {"functions": []}
    assert _format_signatures(file_info) == ""


def test_format_signatures_no_params():
    file_info = {"functions": [{"name": "foo", "params": []}]}
    assert _format_signatures(file_info) == "def foo(): ..."


# ---------------------------------------------------------------------------
# Tests de _generate_pair_test (con mock de LLMClient)
# ---------------------------------------------------------------------------

VALID_CODE = "import pytest\ndef test_integ(): assert True"
INVALID_CODE = "def broken(: ..."


@pytest.fixture
def tmp_repo(tmp_path):
    """Crea un repo temporal con a.py y b.py."""
    (tmp_path / "a.py").write_text("from b import foo\ndef use_foo(): return foo()\n")
    (tmp_path / "b.py").write_text("def foo(): return 42\n")
    return tmp_path


def test_generate_pair_valid_output(tmp_repo):
    ast_result = _make_ast_result({
        "a.py": {"imports": ["b.py"], "functions": [{"name": "use_foo", "params": []}]},
        "b.py": {"imports": [], "functions": [{"name": "foo", "params": []}]},
    })
    with patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_CODE
        result = _generate_pair_test(
            MockClient.return_value, tmp_repo, "a.py", "b.py", ast_result
        )
    assert not result.startswith("# ERROR")
    ast.parse(result)


def test_generate_pair_invalid_then_valid(tmp_repo):
    ast_result = _make_ast_result({
        "a.py": {"imports": ["b.py"]},
        "b.py": {"imports": []},
    })
    with patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.side_effect = [INVALID_CODE, VALID_CODE]
        result = _generate_pair_test(
            MockClient.return_value, tmp_repo, "a.py", "b.py", ast_result
        )
    assert not result.startswith("# ERROR")
    ast.parse(result)


def test_generate_pair_both_fail(tmp_repo):
    ast_result = _make_ast_result({
        "a.py": {"imports": ["b.py"]},
        "b.py": {"imports": []},
    })
    with patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = INVALID_CODE
        result = _generate_pair_test(
            MockClient.return_value, tmp_repo, "a.py", "b.py", ast_result
        )
    assert result.startswith("# ERROR: no se pudo generar test de integración para")


def test_generate_pair_unreadable_source(tmp_repo):
    ast_result = _make_ast_result({
        "nonexistent.py": {"imports": ["b.py"]},
        "b.py": {"imports": []},
    })
    with patch("agent.integration_generator.LLMClient") as MockClient:
        result = _generate_pair_test(
            MockClient.return_value, tmp_repo, "nonexistent.py", "b.py", ast_result
        )
    assert result.startswith("# ERROR: no se pudo leer nonexistent.py")


# ---------------------------------------------------------------------------
# Tests de _write_conftest
# ---------------------------------------------------------------------------

def test_write_conftest_creates_file(tmp_path):
    out = tmp_path / "integration"
    out.mkdir()
    with patch("agent.integration_generator.OUTPUT_DIR", out):
        _write_conftest(Path("/test/repo"))
    content = (out / "conftest.py").read_text()
    assert 'sys.path.insert(0, "/test/repo")' in content


def test_write_conftest_contains_imports(tmp_path):
    out = tmp_path / "integration"
    out.mkdir()
    with patch("agent.integration_generator.OUTPUT_DIR", out):
        _write_conftest(Path("/test/repo"))
    content = (out / "conftest.py").read_text()
    assert "import sys" in content
    assert "import pathlib" in content


# ---------------------------------------------------------------------------
# Tests de generate (integración con mock, usando tmp_path)
# ---------------------------------------------------------------------------

def _make_full_ast_result_for_examples(tmp_repo):
    return {
        "estadistica.py": {
            "functions": [
                {"name": "promedio", "params": ["lista"], "_lineno": 1, "_end_lineno": 8},
                {"name": "varianza", "params": ["lista"], "_lineno": 11, "_end_lineno": 18},
            ],
            "classes": [],
            "imports": ["calculadora.py"],
        },
        "calculadora.py": {
            "functions": [
                {"name": "sumar", "params": ["a", "b"]},
                {"name": "multiplicar", "params": ["a", "b"]},
            ],
            "classes": [],
            "imports": [],
        },
    }


def test_generate_creates_pair_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "estadistica.py").write_text(
        "from calculadora import sumar\ndef promedio(lista): return sum(lista)/len(lista)\n"
    )
    (repo / "calculadora.py").write_text("def sumar(a, b): return a + b\n")
    ast_result = _make_full_ast_result_for_examples(repo)
    out_dir = tmp_path / "tests_generados" / "integration"
    with patch("agent.integration_generator.OUTPUT_DIR", out_dir), \
         patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_CODE
        generate(str(repo), ast_result)
    assert (out_dir / "test_estadistica_calculadora.py").exists()


def test_generate_creates_conftest(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "estadistica.py").write_text(
        "from calculadora import sumar\ndef promedio(lista): return sum(lista)/len(lista)\n"
    )
    (repo / "calculadora.py").write_text("def sumar(a, b): return a + b\n")
    ast_result = _make_full_ast_result_for_examples(repo)
    out_dir = tmp_path / "tests_generados" / "integration"
    with patch("agent.integration_generator.OUTPUT_DIR", out_dir), \
         patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_CODE
        generate(str(repo), ast_result)
    assert (out_dir / "conftest.py").exists()
    assert "sys.path.insert" in (out_dir / "conftest.py").read_text()


def test_generate_no_pairs_no_output(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def foo(): pass\n")
    ast_result = _make_ast_result({"a.py": {"imports": []}})
    out_dir = tmp_path / "tests_generados" / "integration"
    with patch("agent.integration_generator.OUTPUT_DIR", out_dir), \
         patch("agent.integration_generator.LLMClient"):
        generate(str(repo), ast_result)
    test_files = list(out_dir.glob("test_*.py")) if out_dir.exists() else []
    assert test_files == []


def test_generate_calls_llm_once_per_pair(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("from b import f\ndef use_f(): return f()\n")
    (repo / "b.py").write_text("def f(): return 1\n")
    (repo / "c.py").write_text("from b import f\ndef use_f2(): return f()+1\n")
    ast_result = _make_ast_result({
        "a.py": {"imports": ["b.py"]},
        "b.py": {"imports": []},
        "c.py": {"imports": ["b.py"]},
    })
    out_dir = tmp_path / "tests_generados" / "integration"
    with patch("agent.integration_generator.OUTPUT_DIR", out_dir), \
         patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_CODE
        generate(str(repo), ast_result)
    assert MockClient.return_value.generate.call_count == 2
