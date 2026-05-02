import pytest
from agent.ast_extractor import extract, fragment


def make_py_file(tmp_path, name, content):
    f = tmp_path / name
    f.write_text(content)
    return str(tmp_path), [name]


# --- Tests de extracción básica (ANLS-01, ANLS-02) ---

def test_extract_functions_from_calculadora():
    result = extract(["calculadora.py"], "examples")
    funcs = result["calculadora.py"]["functions"]
    names = [f["name"] for f in funcs]
    assert "sumar" in names
    assert "restar" in names
    assert "multiplicar" in names
    assert "dividir" in names
    assert "potencia" in names
    assert len(funcs) == 5


def test_extract_function_params():
    result = extract(["calculadora.py"], "examples")
    funcs = result["calculadora.py"]["functions"]
    sumar = next(f for f in funcs if f["name"] == "sumar")
    assert sumar["params"] == ["a", "b"]


def test_extract_function_docstring(tmp_path):
    code = 'def greet(name):\n    """Greets someone."""\n    return "hi"\n'
    repo_path, files = make_py_file(tmp_path, "greet.py", code)
    result = extract(files, repo_path)
    funcs = result["greet.py"]["functions"]
    assert funcs[0]["docstring"] == "Greets someone."


def test_extract_class_with_methods(tmp_path):
    code = (
        'class MyCalc:\n'
        '    """A calculator."""\n'
        '    def add(self, x, y):\n'
        '        """Add two numbers."""\n'
        '        return x + y\n'
    )
    repo_path, files = make_py_file(tmp_path, "calc.py", code)
    result = extract(files, repo_path)
    classes = result["calc.py"]["classes"]
    assert len(classes) == 1
    cls = classes[0]
    assert cls["name"] == "MyCalc"
    assert cls["type"] == "class"
    assert cls["docstring"] == "A calculator."
    assert len(cls["methods"]) == 1
    method = cls["methods"][0]
    assert method["name"] == "add"
    assert method["params"] == ["self", "x", "y"]
    assert method["docstring"] == "Add two numbers."


def test_extract_returns_empty_for_empty_file(tmp_path):
    repo_path, files = make_py_file(tmp_path, "empty.py", "")
    result = extract(files, repo_path)
    assert result["empty.py"]["functions"] == []
    assert result["empty.py"]["classes"] == []
    assert result["empty.py"]["imports"] == []


def test_extract_syntax_error_handled(tmp_path):
    repo_path, files = make_py_file(tmp_path, "bad.py", "def broken(:\n    pass\n")
    result = extract(files, repo_path)
    assert "parse_error" in result["bad.py"]
    assert result["bad.py"]["functions"] == []


# --- Tests de imports (EXPL-03) ---

def test_extract_same_repo_imports(tmp_path):
    mod_b = tmp_path / "mod_b.py"
    mod_b.write_text("x = 1\n")
    mod_a = tmp_path / "mod_a.py"
    mod_a.write_text("import mod_b\n\ndef func(): pass\n")
    result = extract(["mod_a.py", "mod_b.py"], str(tmp_path))
    assert "mod_b.py" in result["mod_a.py"]["imports"]


def test_extract_stdlib_imports_excluded(tmp_path):
    code = "import os\nimport sys\nfrom pathlib import Path\n\ndef f(): pass\n"
    repo_path, files = make_py_file(tmp_path, "mod.py", code)
    result = extract(files, repo_path)
    assert result["mod.py"]["imports"] == []


def test_extract_third_party_imports_excluded(tmp_path):
    code = "import requests\nimport numpy as np\n\ndef f(): pass\n"
    repo_path, files = make_py_file(tmp_path, "mod.py", code)
    result = extract(files, repo_path)
    assert result["mod.py"]["imports"] == []


# --- Tests de fragmentación (ANLS-03) ---

def _make_functions_source(count, lines_each):
    """Generate Python source with `count` functions of `lines_each` lines each."""
    parts = []
    for i in range(count):
        body_lines = "\n".join(f"    # line {j}" for j in range(lines_each - 2))
        parts.append(f"def func_{i}(x):\n{body_lines}\n    return x + {i}")
    return "\n\n".join(parts)


def test_fragment_small_file_returns_one_fragment(tmp_path):
    code = "def a(x): return x\ndef b(x): return x\ndef c(x): return x\n"
    repo_path, files = make_py_file(tmp_path, "small.py", code)
    result = extract(files, repo_path)
    file_info = result["small.py"]
    frags = fragment(file_info, code.splitlines())
    assert len(frags) == 1


def test_fragment_large_file_returns_multiple_fragments(tmp_path):
    # 20 functions x 15 lines each = 300 lines total > 200 threshold
    code = _make_functions_source(20, 15)
    repo_path, files = make_py_file(tmp_path, "large.py", code)
    result = extract(files, repo_path)
    file_info = result["large.py"]
    frags = fragment(file_info, code.splitlines())
    assert len(frags) >= 2


def test_fragment_never_splits_single_large_function(tmp_path):
    # One function with 250 lines
    body = "\n".join(f"    x{i} = {i}" for i in range(248))
    code = f"def big_func(x):\n{body}\n    return x\n"
    repo_path, files = make_py_file(tmp_path, "bigfunc.py", code)
    result = extract(files, repo_path)
    file_info = result["bigfunc.py"]
    frags = fragment(file_info, code.splitlines())
    # The single function should form its own fragment (not be split)
    all_func_names = [f["name"] for frag in frags for f in frag["functions"]]
    assert all_func_names.count("big_func") == 1


def test_fragment_each_fragment_parseable(tmp_path):
    code = _make_functions_source(20, 15)
    repo_path, files = make_py_file(tmp_path, "large.py", code)
    result = extract(files, repo_path)
    file_info = result["large.py"]
    frags = fragment(file_info, code.splitlines())
    for frag in frags:
        assert isinstance(frag["functions"], list)
        assert isinstance(frag["classes"], list)
        for f in frag["functions"]:
            assert "name" in f
            assert "params" in f
