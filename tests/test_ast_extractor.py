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


# ---------------------------------------------------------------------------
# Tests JS/TS (HU-11)
# ---------------------------------------------------------------------------

def make_js_file(tmp_path, name, content):
    f = tmp_path / name
    f.write_text(content)
    return str(tmp_path), [name]


def test_extract_js_function_declaration(tmp_path):
    code = "function add(a, b) {\n  return a + b;\n}\n"
    repo_path, files = make_js_file(tmp_path, "calc.js", code)
    result = extract(files, repo_path)
    funcs = result["calc.js"]["functions"]
    assert any(f["name"] == "add" for f in funcs)


def test_extract_js_arrow_function(tmp_path):
    code = "const multiply = (a, b) => {\n  return a * b;\n};\n"
    repo_path, files = make_js_file(tmp_path, "calc.js", code)
    result = extract(files, repo_path)
    funcs = result["calc.js"]["functions"]
    assert any(f["name"] == "multiply" for f in funcs)


def test_extract_js_function_expression(tmp_path):
    code = "const divide = function(a, b) {\n  return a / b;\n};\n"
    repo_path, files = make_js_file(tmp_path, "calc.js", code)
    result = extract(files, repo_path)
    funcs = result["calc.js"]["functions"]
    assert any(f["name"] == "divide" for f in funcs)


def test_extract_js_class_with_methods(tmp_path):
    code = (
        "class Calculator {\n"
        "  constructor(base) {\n"
        "    this.base = base;\n"
        "  }\n"
        "  add(x) {\n"
        "    return this.base + x;\n"
        "  }\n"
        "}\n"
    )
    repo_path, files = make_js_file(tmp_path, "calc.js", code)
    result = extract(files, repo_path)
    classes = result["calc.js"]["classes"]
    assert len(classes) == 1
    cls = classes[0]
    assert cls["name"] == "Calculator"
    assert cls["type"] == "class"
    method_names = [m["name"] for m in cls["methods"]]
    assert "add" in method_names
    assert "constructor" in method_names


def test_extract_js_class_methods_not_in_functions(tmp_path):
    code = (
        "class Foo {\n"
        "  bar(x) {\n"
        "    return x;\n"
        "  }\n"
        "}\n"
    )
    repo_path, files = make_js_file(tmp_path, "foo.js", code)
    result = extract(files, repo_path)
    func_names = [f["name"] for f in result["foo.js"]["functions"]]
    assert "bar" not in func_names


def test_extract_js_export_function(tmp_path):
    code = "export function greet(name) {\n  return `Hello ${name}`;\n}\n"
    repo_path, files = make_js_file(tmp_path, "greet.js", code)
    result = extract(files, repo_path)
    funcs = result["greet.js"]["functions"]
    assert any(f["name"] == "greet" for f in funcs)


def test_extract_ts_file(tmp_path):
    code = "function greet(name: string): string {\n  return `Hello ${name}`;\n}\n"
    repo_path, files = make_js_file(tmp_path, "greet.ts", code)
    result = extract(files, repo_path)
    funcs = result["greet.ts"]["functions"]
    assert any(f["name"] == "greet" for f in funcs)


def test_extract_js_empty_file(tmp_path):
    repo_path, files = make_js_file(tmp_path, "empty.js", "")
    result = extract(files, repo_path)
    assert result["empty.js"]["functions"] == []
    assert result["empty.js"]["classes"] == []
    assert result["empty.js"]["imports"] == []


def test_extract_js_read_error(tmp_path):
    repo_path = str(tmp_path)
    result = extract(["nonexistent.js"], repo_path)
    assert "parse_error" in result["nonexistent.js"]


def test_extract_js_function_lineno(tmp_path):
    code = "function foo() {\n  return 1;\n}\n"
    repo_path, files = make_js_file(tmp_path, "foo.js", code)
    result = extract(files, repo_path)
    func = result["foo.js"]["functions"][0]
    assert func["_lineno"] == 1
    assert func["_end_lineno"] == 3


# ---------------------------------------------------------------------------
# Tests Java (HU-14)
# ---------------------------------------------------------------------------

def make_java_file(tmp_path, name, content):
    f = tmp_path / name
    f.write_text(content)
    return str(tmp_path), [name]


def test_extract_java_class(tmp_path):
    code = (
        "public class Calculadora {\n"
        "    public int suma(int a, int b) {\n"
        "        return a + b;\n"
        "    }\n"
        "}\n"
    )
    repo_path, files = make_java_file(tmp_path, "Calculadora.java", code)
    result = extract(files, repo_path)
    classes = result["Calculadora.java"]["classes"]
    assert len(classes) == 1
    assert classes[0]["name"] == "Calculadora"
    assert classes[0]["type"] == "class"


def test_extract_java_methods(tmp_path):
    code = (
        "public class Calculadora {\n"
        "    public int suma(int a, int b) {\n"
        "        return a + b;\n"
        "    }\n"
        "    public int resta(int a, int b) {\n"
        "        return a - b;\n"
        "    }\n"
        "}\n"
    )
    repo_path, files = make_java_file(tmp_path, "Calculadora.java", code)
    result = extract(files, repo_path)
    methods = result["Calculadora.java"]["classes"][0]["methods"]
    method_names = [m["name"] for m in methods]
    assert "suma" in method_names
    assert "resta" in method_names


def test_extract_java_method_params(tmp_path):
    code = (
        "public class Calc {\n"
        "    public double dividir(double dividendo, double divisor) {\n"
        "        return dividendo / divisor;\n"
        "    }\n"
        "}\n"
    )
    repo_path, files = make_java_file(tmp_path, "Calc.java", code)
    result = extract(files, repo_path)
    methods = result["Calc.java"]["classes"][0]["methods"]
    dividir = next(m for m in methods if m["name"] == "dividir")
    assert "dividendo" in dividir["params"]
    assert "divisor" in dividir["params"]


def test_extract_java_no_top_level_functions(tmp_path):
    code = (
        "public class Foo {\n"
        "    public void bar() {\n"
        "        System.out.println(\"hello\");\n"
        "    }\n"
        "}\n"
    )
    repo_path, files = make_java_file(tmp_path, "Foo.java", code)
    result = extract(files, repo_path)
    assert result["Foo.java"]["functions"] == []


def test_extract_java_no_imports_tracked(tmp_path):
    code = (
        "import java.util.List;\n"
        "public class Foo {\n"
        "    public void bar() {}\n"
        "}\n"
    )
    repo_path, files = make_java_file(tmp_path, "Foo.java", code)
    result = extract(files, repo_path)
    assert result["Foo.java"]["imports"] == []


def test_extract_java_empty_class(tmp_path):
    code = "public class Empty {\n}\n"
    repo_path, files = make_java_file(tmp_path, "Empty.java", code)
    result = extract(files, repo_path)
    classes = result["Empty.java"]["classes"]
    assert len(classes) == 1
    assert classes[0]["methods"] == []


def test_extract_java_read_error(tmp_path):
    repo_path = str(tmp_path)
    result = extract(["NonExistent.java"], repo_path)
    assert "parse_error" in result["NonExistent.java"]


def test_extract_java_static_method(tmp_path):
    code = (
        "public class Utils {\n"
        "    public static String mayusculas(String texto) {\n"
        "        return texto.toUpperCase();\n"
        "    }\n"
        "}\n"
    )
    repo_path, files = make_java_file(tmp_path, "Utils.java", code)
    result = extract(files, repo_path)
    methods = result["Utils.java"]["classes"][0]["methods"]
    assert any(m["name"] == "mayusculas" for m in methods)


def test_extract_java_examples(tmp_path):
    code = (
        "public class Calculadora {\n"
        "    public int suma(int a, int b) { return a + b; }\n"
        "    public int resta(int a, int b) { return a - b; }\n"
        "    public double dividir(double dividendo, double divisor) {\n"
        "        if (divisor == 0) throw new IllegalArgumentException(\"cero\");\n"
        "        return dividendo / divisor;\n"
        "    }\n"
        "}\n"
    )
    repo_path, files = make_java_file(tmp_path, "Calculadora.java", code)
    result = extract(files, repo_path)
    classes = result["Calculadora.java"]["classes"]
    assert len(classes) == 1
    method_names = [m["name"] for m in classes[0]["methods"]]
    assert "suma" in method_names
    assert "resta" in method_names
    assert "dividir" in method_names
