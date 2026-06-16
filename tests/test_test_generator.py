import ast
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.test_generator import (
    generate,
    _slice_source,
    _generate_block,
    _build_import_header,
    _build_js_import_header,
    _build_java_test_file,
    _detect_language,
    _has_balanced_braces,
    _is_embeddable_java_block,
    _write_conftest,
    _write_java_pom,
    OUTPUT_DIR,
)
from prompts.prompt_builder import clean_response


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

VALID_CODE = "def test_f():\n    assert True\n"
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
# Tests de clean_response con strip_imports
# ---------------------------------------------------------------------------

def test_clean_response_strip_imports_removes_import_lines():
    raw = "import pytest\nfrom calc import add\ndef test_add():\n    assert add(1, 2) == 3\n"
    result = clean_response(raw, strip_imports=True)
    assert "import pytest" not in result
    assert "from calc import add" not in result
    assert "def test_add" in result


def test_clean_response_strip_imports_removes_mid_file_imports():
    raw = (
        "def test_a():\n    assert True\n\n"
        "from calc import sub\n\n"
        "def test_b():\n    assert True\n"
    )
    result = clean_response(raw, strip_imports=True)
    assert "from calc import sub" not in result
    assert "def test_a" in result
    assert "def test_b" in result


def test_clean_response_strip_imports_false_preserves_imports():
    raw = "import pytest\nfrom calc import add\ndef test_add():\n    assert True\n"
    result = clean_response(raw, strip_imports=False)
    assert "import pytest" in result
    assert "from calc import add" in result


# Tests de clean_response para Java (HU-14)

def test_clean_response_java_extracts_methods_from_class_wrapper():
    raw = (
        "public class FooTests {\n"
        "    @Test\n"
        "    void testA() {\n"
        "        assertEquals(1, 1);\n"
        "    }\n"
        "}"
    )
    result = clean_response(raw, strip_imports=True, language="java")
    assert "@Test" in result
    assert "void testA()" in result
    assert "class FooTests" not in result


def test_clean_response_java_skips_standalone_java_word():
    raw = "java\n\n@Test\nvoid testA() {\n    assertEquals(1, 1);\n}"
    result = clean_response(raw, strip_imports=True, language="java")
    assert result.strip().startswith("@Test")
    assert "java" not in result.splitlines()[0]


def test_clean_response_java_strips_deepseek_bos_token():
    raw = "@Test\nvoid testA() {\n    int x = Integer<｜begin｜>.MAX_VALUE;\n    assertEquals(1, 1);\n}"
    result = clean_response(raw, language="java")
    assert "｜" not in result
    assert "@Test" in result


def test_clean_response_java_normalizes_indentation():
    # @Test con 4 espacios de base: el cuerpo queda a 4 espacios relativos
    raw = "    @Test\n    void testA() {\n        assertEquals(1, 1);\n    }"
    result = clean_response(raw, language="java")
    assert result.startswith("@Test")
    assert "    assertEquals" in result  # 4 espacios relativos al método


def test_clean_response_java_multiple_methods_from_class():
    raw = (
        "class Tests {\n"
        "    @Test\n"
        "    void testA() { assertEquals(1, 1); }\n"
        "\n"
        "    @Test\n"
        "    void testB() { assertEquals(2, 2); }\n"
        "}"
    )
    result = clean_response(raw, language="java")
    assert "void testA()" in result
    assert "void testB()" in result
    assert "class Tests" not in result


# ---------------------------------------------------------------------------
# Tests de _build_import_header
# ---------------------------------------------------------------------------

def test_build_import_header_functions():
    file_info = {
        "functions": [{"name": "add"}, {"name": "sub"}],
        "classes": [],
    }
    header = _build_import_header("calc", file_info)
    lines = header.splitlines()
    assert lines[0] == "import pytest"
    assert "from calc import add" in lines
    assert "from calc import sub" in lines


def test_build_import_header_class_deduplication():
    file_info = {
        "functions": [],
        "classes": [
            {"name": "Calc", "methods": [{"name": "add"}, {"name": "sub"}]},
        ],
    }
    header = _build_import_header("calc", file_info)
    assert header.count("from calc import Calc") == 1


def test_build_import_header_no_repeated_pytest():
    file_info = {
        "functions": [{"name": "f1"}, {"name": "f2"}],
        "classes": [],
    }
    header = _build_import_header("mod", file_info)
    assert header.count("import pytest") == 1


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


def test_generate_imports_appear_once_at_top(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_calc(tmp_path / "repo")
    ast_result = _make_ast_result_for_calc()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_CODE
        generate(repo, ast_result)

    content = (tmp_path / "tests_generados" / "unit" / "test_calc.py").read_text()
    assert content.count("import pytest") == 1
    assert content.count("from calc import add") == 1
    assert content.count("from calc import sub") == 1
    assert content.count("from calc import mul") == 1
    # El header de imports debe estar al principio del archivo
    first_line = content.splitlines()[0]
    assert first_line == "import pytest"


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


# ---------------------------------------------------------------------------
# Tests de _detect_language (HU-11)
# ---------------------------------------------------------------------------

def test_detect_language_py():
    assert _detect_language("module.py") == "python"


def test_detect_language_js():
    assert _detect_language("app.js") == "javascript"


def test_detect_language_ts():
    assert _detect_language("utils.ts") == "javascript"


def test_detect_language_nested_js():
    assert _detect_language("src/components/Button.js") == "javascript"


# ---------------------------------------------------------------------------
# Tests de _build_js_import_header (HU-11)
# ---------------------------------------------------------------------------

def test_build_js_import_header_functions():
    file_info = {"functions": [{"name": "add"}, {"name": "sub"}], "classes": []}
    header = _build_js_import_header("calc", file_info)
    assert "require('calc')" in header
    assert "add" in header
    assert "sub" in header


def test_build_js_import_header_class():
    file_info = {"functions": [], "classes": [{"name": "Calculator", "methods": []}]}
    header = _build_js_import_header("calc", file_info)
    assert "Calculator" in header
    assert "require('calc')" in header


def test_build_js_import_header_class_deduplication():
    file_info = {
        "functions": [],
        "classes": [
            {"name": "Calc", "methods": [{"name": "add"}, {"name": "sub"}]},
        ],
    }
    header = _build_js_import_header("calc", file_info)
    assert header.count("Calc") == 1


def test_build_js_import_header_empty():
    file_info = {"functions": [], "classes": []}
    header = _build_js_import_header("calc", file_info)
    assert "require('calc')" in header


# ---------------------------------------------------------------------------
# Tests de generate() con archivos JS (HU-11)
# ---------------------------------------------------------------------------

VALID_JS_CODE = "test('adds', () => {\n  expect(add(1, 2)).toBe(3);\n});\n"
INVALID_JS_CODE = "esto no es javascript @@@"


def _make_js_ast_result():
    return {
        "calc.js": {
            "functions": [
                {"name": "add", "params": ["a", "b"], "_lineno": 1, "_end_lineno": 3},
            ],
            "classes": [],
            "imports": [],
        }
    }


def _make_repo_with_js_calc(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    calc = tmp_path / "calc.js"
    calc.write_text("function add(a, b) {\n  return a + b;\n}\n")
    return str(tmp_path)


def test_generate_js_creates_test_js_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_js_calc(tmp_path / "repo")
    ast_result = _make_js_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JS_CODE
        generate(repo, ast_result)

    assert (tmp_path / "tests_generados" / "unit" / "calc.test.js").exists()


def test_generate_js_does_not_create_py_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_js_calc(tmp_path / "repo")
    ast_result = _make_js_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JS_CODE
        generate(repo, ast_result)

    assert not (tmp_path / "tests_generados" / "unit" / "test_calc.py").exists()


def test_generate_js_does_not_create_conftest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_js_calc(tmp_path / "repo")
    ast_result = _make_js_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JS_CODE
        generate(repo, ast_result)

    assert not (tmp_path / "tests_generados" / "unit" / "conftest.py").exists()


def test_generate_js_header_contains_require(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_js_calc(tmp_path / "repo")
    ast_result = _make_js_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JS_CODE
        generate(repo, ast_result)

    content = (tmp_path / "tests_generados" / "unit" / "calc.test.js").read_text()
    assert "require('calc')" in content


def test_generate_js_creates_jest_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_js_calc(tmp_path / "repo")
    ast_result = _make_js_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JS_CODE
        generate(repo, ast_result)

    jest_config = tmp_path / "tests_generados" / "unit" / "jest.config.js"
    assert jest_config.exists()
    content = jest_config.read_text()
    assert "rootDir: '../..'" in content
    assert "modulePaths" in content


def test_generate_block_js_valid_output():
    source_lines = ["function add(a, b) {", "  return a + b;", "}"]
    with patch("agent.test_generator.LLMClient") as MockClient:
        client = MockClient.return_value
        client.generate.return_value = VALID_JS_CODE
        result = _generate_block(
            client, source_lines, _make_unit("add"), "calc", None, language="javascript"
        )
    assert not result.startswith("# ERROR")


def test_generate_block_js_invalid_output_falls_back_to_error():
    source_lines = ["function add(a, b) { return a + b; }"]
    with patch("agent.test_generator.LLMClient") as MockClient:
        client = MockClient.return_value
        client.generate.return_value = INVALID_JS_CODE
        result = _generate_block(
            client, source_lines, _make_unit("add"), "calc", None, language="javascript"
        )
    assert result.startswith("# ERROR: no se pudo generar tests para")


# ---------------------------------------------------------------------------
# Tests de _detect_language para Java (HU-14)
# ---------------------------------------------------------------------------

def test_detect_language_java():
    assert _detect_language("Calculadora.java") == "java"


def test_detect_language_java_nested():
    assert _detect_language("src/Calculadora.java") == "java"


# ---------------------------------------------------------------------------
# Tests de _has_balanced_braces (HU-14)
# ---------------------------------------------------------------------------

def test_has_balanced_braces_valid_method():
    code = "@Test\nvoid testA() {\n    assertEquals(1, 1);\n}"
    assert _has_balanced_braces(code) is True


def test_has_balanced_braces_missing_closing():
    code = "@Test\nvoid testA() {\n    assertEquals(1, 1);\n"  # sin }
    assert _has_balanced_braces(code) is False


def test_has_balanced_braces_extra_closing():
    code = "@Test\nvoid testA() {\n    assertEquals(1, 1);\n}}"
    assert _has_balanced_braces(code) is False


def test_has_balanced_braces_nested_valid():
    code = "@Test\nvoid testA() {\n    assertThrows(E.class, () -> {\n        obj.m();\n    });\n}"
    assert _has_balanced_braces(code) is True


def test_is_embeddable_java_block_valid():
    assert _is_embeddable_java_block(VALID_JAVA_BLOCK) is True


def test_is_embeddable_java_block_rejects_import():
    code = "import static org.junit.jupiter.api.Assertions.*;\n@Test\nvoid testA() { assertEquals(1,1); }"
    assert _is_embeddable_java_block(code) is False


def test_is_embeddable_java_block_rejects_class_declaration():
    code = "class TestFoo {\n    @Test\n    void testA() { assertEquals(1,1); }\n}"
    assert _is_embeddable_java_block(code) is False


def test_is_embeddable_java_block_rejects_unbalanced():
    code = "@Test\nvoid testA() {\n    assertEquals(1, 1);\n"
    assert _is_embeddable_java_block(code) is False


def test_clean_response_java_recognizes_fully_qualified_test_annotation():
    raw = (
        "@org.junit.jupiter.api.Test\n"
        "void testA() {\n"
        "    Pedido obj = new Pedido();\n"
        "    assertEquals(0, obj.cantidadItems());\n"
        "}"
    )
    result = clean_response(raw, language="java")
    assert "void testA()" in result
    assert "assertEquals" in result


def test_clean_response_java_discards_method_with_nested_at_test():
    # El LLM deja un método sin cerrar y empieza el siguiente @Test adentro
    raw = (
        "@Test\n"
        "void testCalc_ok() {\n"
        "    assertEquals(1, obj.calc());\n"
        "}\n"
        "\n"
        "@Test\n"
        "void testCalc_zero() {\n"
        "    Pedido obj = new Pedido();\n"
        "    // método sin cerrar...\n"
        "\n"
        "@Test\n"
        "void testCalc_neg() {\n"
        "    assertTrue(true);\n"
        "}\n"
    )
    result = clean_response(raw, language="java")
    assert "void testCalc_ok()" in result
    assert "void testCalc_neg()" in result
    # testCalc_zero debe descartarse porque sus llaves no cierran antes del @Test
    assert "void testCalc_zero()" not in result


# ---------------------------------------------------------------------------
# Tests de _build_java_test_file (HU-14)
# ---------------------------------------------------------------------------

VALID_JAVA_BLOCK = "@Test\nvoid testSuma_happyPath() {\n    assertEquals(5, obj.suma(2, 3));\n}"


def test_build_java_test_file_contains_class_wrapper():
    result = _build_java_test_file("Calculadora", [VALID_JAVA_BLOCK])
    assert "class CalculadoraTest {" in result
    assert result.strip().endswith("}")


def test_build_java_test_file_contains_junit_imports():
    result = _build_java_test_file("Calculadora", [VALID_JAVA_BLOCK])
    assert "import org.junit.jupiter.api.Test;" in result
    assert "import static org.junit.jupiter.api.Assertions.*;" in result
    assert "import org.junit.jupiter.api.Assertions;" in result


def test_build_java_test_file_adds_before_each_import_when_needed():
    block_with_setup = "@BeforeEach\nvoid setUp() {}\n\n" + VALID_JAVA_BLOCK
    result = _build_java_test_file("Calc", [block_with_setup])
    assert "import org.junit.jupiter.api.BeforeEach;" in result


def test_build_java_test_file_adds_arraylist_import_when_needed():
    block = "@Test\nvoid testA() {\n    ArrayList<String> list = new ArrayList<>();\n}"
    result = _build_java_test_file("Calc", [block])
    assert "import java.util.ArrayList;" in result


def test_build_java_test_file_adds_arrays_import_when_needed():
    block = "@Test\nvoid testA() {\n    List<String> l = Arrays.asList(\"a\");\n}"
    result = _build_java_test_file("Calc", [block])
    assert "import java.util.Arrays;" in result


def test_build_java_test_file_indents_blocks():
    result = _build_java_test_file("Calc", [VALID_JAVA_BLOCK])
    lines = result.splitlines()
    test_line = next(l for l in lines if "@Test" in l)
    assert test_line.startswith("    ")


def test_build_java_test_file_multiple_blocks():
    block2 = "@Test\nvoid testResta_happyPath() {\n    assertEquals(1, obj.resta(3, 2));\n}"
    result = _build_java_test_file("Calc", [VALID_JAVA_BLOCK, block2])
    assert "testSuma_happyPath" in result
    assert "testResta_happyPath" in result


# ---------------------------------------------------------------------------
# Tests de _write_java_pom (HU-14)
# ---------------------------------------------------------------------------

def test_write_java_pom_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_java_pom()
    pom = tmp_path / "tests_generados" / "unit" / "pom.xml"
    assert pom.exists()


def test_write_java_pom_contains_junit5(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_java_pom()
    content = (tmp_path / "tests_generados" / "unit" / "pom.xml").read_text()
    assert "junit-jupiter" in content
    assert "5.10.0" in content


def test_write_java_pom_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_java_pom()
    pom = tmp_path / "tests_generados" / "unit" / "pom.xml"
    original = pom.read_text()
    _write_java_pom()  # segunda llamada no debe sobrescribir
    assert pom.read_text() == original


# ---------------------------------------------------------------------------
# Tests de generate() con archivos Java (HU-14)
# ---------------------------------------------------------------------------

def _make_java_ast_result():
    return {
        "Calculadora.java": {
            "functions": [],
            "classes": [
                {
                    "name": "Calculadora",
                    "type": "class",
                    "docstring": "",
                    "methods": [
                        {"name": "suma", "params": ["a", "b"], "_lineno": 2, "_end_lineno": 4},
                    ],
                }
            ],
            "imports": [],
        }
    }


def _make_repo_with_java_calc(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    calc = tmp_path / "Calculadora.java"
    calc.write_text(
        "public class Calculadora {\n"
        "    public int suma(int a, int b) {\n"
        "        return a + b;\n"
        "    }\n"
        "}\n"
    )
    return str(tmp_path)


def test_generate_java_creates_test_java_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_java_calc(tmp_path / "repo")
    ast_result = _make_java_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JAVA_BLOCK
        generate(repo, ast_result)

    java_test = tmp_path / "tests_generados" / "unit" / "src" / "test" / "java" / "CalculadoraTest.java"
    assert java_test.exists()


def test_generate_java_test_file_has_junit_header(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_java_calc(tmp_path / "repo")
    ast_result = _make_java_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient, \
         patch("agent.test_generator.shutil.which", return_value=None):
        MockClient.return_value.generate.return_value = VALID_JAVA_BLOCK
        generate(repo, ast_result)

    content = (
        tmp_path / "tests_generados" / "unit" / "src" / "test" / "java" / "CalculadoraTest.java"
    ).read_text()
    assert "import org.junit.jupiter.api.Test;" in content
    assert "class CalculadoraTest" in content


def test_generate_java_creates_pom(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_java_calc(tmp_path / "repo")
    ast_result = _make_java_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JAVA_BLOCK
        generate(repo, ast_result)

    pom = tmp_path / "tests_generados" / "unit" / "pom.xml"
    assert pom.exists()


def test_generate_java_copies_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _make_repo_with_java_calc(tmp_path / "repo")
    ast_result = _make_java_ast_result()

    with patch("agent.test_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JAVA_BLOCK
        generate(repo, ast_result)

    src_main = tmp_path / "tests_generados" / "unit" / "src" / "main" / "java" / "Calculadora.java"
    assert src_main.exists()


def test_generate_java_block_valid():
    source_lines = [
        "public class Calculadora {",
        "    public int suma(int a, int b) {",
        "        return a + b;",
        "    }",
        "}",
    ]
    with patch("agent.test_generator.LLMClient") as MockClient:
        client = MockClient.return_value
        client.generate.return_value = VALID_JAVA_BLOCK
        result = _generate_block(client, source_lines, _make_unit("suma"), "Calculadora", "Calculadora", language="java")
    assert not result.startswith("# ERROR")
