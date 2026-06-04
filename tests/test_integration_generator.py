import ast
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.integration_generator import (
    generate,
    _find_pairs,
    _find_java_pairs,
    _format_signatures,
    _format_java_method_sigs,
    _generate_pair_test,
    _generate_java_pair_test,
    _get_java_class_name,
    _build_java_integration_test_file,
    _write_conftest,
    OUTPUT_DIR,
    _JAVA_INT_TEST_DIR,
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


# ---------------------------------------------------------------------------
# Tests de _find_pairs con archivos JS (HU-11 fix)
# ---------------------------------------------------------------------------

def test_find_pairs_skips_js_files():
    ast_result = _make_ast_result({
        "app.js": {"imports": ["utils.js"]},
        "utils.js": {"imports": []},
    })
    assert _find_pairs(ast_result) == []


def test_find_pairs_skips_js_importer_of_py():
    ast_result = _make_ast_result({
        "app.js": {"imports": ["utils.py"]},
        "utils.py": {"imports": []},
    })
    assert _find_pairs(ast_result) == []


def test_find_pairs_only_py_pairs_in_mixed_repo():
    ast_result = _make_ast_result({
        "a.py": {"imports": ["b.py"]},
        "b.py": {"imports": []},
        "app.js": {"imports": ["utils.js"]},
        "utils.js": {"imports": []},
    })
    pairs = _find_pairs(ast_result)
    assert pairs == [("a.py", "b.py")]


# ---------------------------------------------------------------------------
# Tests de _find_java_pairs
# ---------------------------------------------------------------------------

def _make_java_ast(files: dict) -> dict:
    """
    files: {rel_path: {"class_name": str, "methods": list}}
    Construye un ast_result compatible con el formato de ast_extractor para Java.
    """
    result = {}
    for path, info in files.items():
        class_name = info.get("class_name", Path(path).stem)
        methods = info.get("methods", [])
        result[path] = {
            "functions": [],
            "classes": [{"name": class_name, "methods": methods}],
            "imports": [],
        }
    return result


def test_find_java_pairs_detects_by_instantiation(tmp_path):
    (tmp_path / "Estadistica.java").write_text(
        "public class Estadistica {\n"
        "    private Calculadora calc = new Calculadora();\n"
        "}\n"
    )
    (tmp_path / "Calculadora.java").write_text(
        "public class Calculadora { public int suma(int a, int b) { return a+b; } }\n"
    )
    ast_result = _make_java_ast({
        "Estadistica.java": {"class_name": "Estadistica"},
        "Calculadora.java": {"class_name": "Calculadora"},
    })
    pairs = _find_java_pairs(ast_result, tmp_path)
    assert ("Estadistica.java", "Calculadora.java") in pairs


def test_find_java_pairs_no_reference(tmp_path):
    (tmp_path / "A.java").write_text("public class A { }\n")
    (tmp_path / "B.java").write_text("public class B { }\n")
    ast_result = _make_java_ast({
        "A.java": {"class_name": "A"},
        "B.java": {"class_name": "B"},
    })
    pairs = _find_java_pairs(ast_result, tmp_path)
    assert pairs == []


def test_find_java_pairs_skips_non_java(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "B.java").write_text("public class B { }\n")
    ast_result = {
        "a.py": {"functions": [], "classes": [], "imports": []},
        "B.java": {"functions": [], "classes": [{"name": "B", "methods": []}], "imports": []},
    }
    pairs = _find_java_pairs(ast_result, tmp_path)
    assert pairs == []


def test_find_java_pairs_unidirectional(tmp_path):
    (tmp_path / "Estadistica.java").write_text(
        "public class Estadistica { private Calculadora c = new Calculadora(); }\n"
    )
    (tmp_path / "Calculadora.java").write_text(
        "public class Calculadora { }\n"
    )
    ast_result = _make_java_ast({
        "Estadistica.java": {"class_name": "Estadistica"},
        "Calculadora.java": {"class_name": "Calculadora"},
    })
    pairs = _find_java_pairs(ast_result, tmp_path)
    assert ("Estadistica.java", "Calculadora.java") in pairs
    assert ("Calculadora.java", "Estadistica.java") not in pairs


# ---------------------------------------------------------------------------
# Tests de _get_java_class_name y _format_java_method_sigs
# ---------------------------------------------------------------------------

def test_get_java_class_name_from_ast():
    ast_result = _make_java_ast({"Foo.java": {"class_name": "Foo"}})
    assert _get_java_class_name(ast_result, "Foo.java") == "Foo"


def test_get_java_class_name_fallback_to_stem():
    assert _get_java_class_name({}, "Calculadora.java") == "Calculadora"


def test_format_java_method_sigs_basic():
    file_info = {
        "classes": [{
            "name": "Calculadora",
            "methods": [
                {"name": "suma", "params": ["a", "b"]},
                {"name": "dividir", "params": ["dividendo", "divisor"]},
            ],
        }]
    }
    result = _format_java_method_sigs(file_info)
    assert "suma(a, b)" in result
    assert "dividir(dividendo, divisor)" in result


def test_format_java_method_sigs_empty():
    assert _format_java_method_sigs({"classes": []}) == ""


# ---------------------------------------------------------------------------
# Tests de _build_java_integration_test_file
# ---------------------------------------------------------------------------

def test_build_java_integration_test_file_structure():
    methods = "@Test\nvoid testPromedio() {\n    Estadistica e = new Estadistica();\n    assertEquals(2.0, e.promedio(new int[]{1,2,3}), 0.001);\n}"
    result = _build_java_integration_test_file("Estadistica", "Calculadora", methods)
    assert "class EstadisticaCalculadoraIntegrationTest {" in result
    assert "import org.junit.jupiter.api.Test;" in result
    assert "import static org.junit.jupiter.api.Assertions.*;" in result
    assert "@Test" in result
    assert result.strip().endswith("}")


def test_build_java_integration_test_file_indents_methods():
    methods = "@Test\nvoid testX() {\n    assertTrue(true);\n}"
    result = _build_java_integration_test_file("A", "B", methods)
    lines = result.splitlines()
    test_line = next(l for l in lines if "@Test" in l)
    assert test_line.startswith("    ")


# ---------------------------------------------------------------------------
# Tests de _generate_java_pair_test (con mock de LLMClient)
# ---------------------------------------------------------------------------

VALID_JAVA_BLOCK = (
    "@Test\n"
    "void testPromedio() {\n"
    "    Estadistica obj = new Estadistica();\n"
    "    assertEquals(2.0, obj.promedio(new int[]{1, 2, 3}), 0.001);\n"
    "}"
)

INVALID_JAVA_BLOCK = "respuesta inválida del modelo sin anotaciones de test"


@pytest.fixture
def tmp_java_repo(tmp_path):
    (tmp_path / "Estadistica.java").write_text(
        "public class Estadistica {\n"
        "    private Calculadora calc = new Calculadora();\n"
        "    public double promedio(int[] nums) { return 0; }\n"
        "}\n"
    )
    (tmp_path / "Calculadora.java").write_text(
        "public class Calculadora { public int suma(int a, int b) { return a+b; } }\n"
    )
    return tmp_path


def test_generate_java_pair_valid_output(tmp_java_repo):
    ast_result = _make_java_ast({
        "Estadistica.java": {"class_name": "Estadistica", "methods": [{"name": "promedio", "params": ["nums"]}]},
        "Calculadora.java": {"class_name": "Calculadora", "methods": [{"name": "suma", "params": ["a", "b"]}]},
    })
    with patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JAVA_BLOCK
        result = _generate_java_pair_test(
            MockClient.return_value, tmp_java_repo, "Estadistica.java", "Calculadora.java", ast_result
        )
    assert "EstadisticaCalculadoraIntegrationTest" in result
    assert "@Test" in result
    assert not result.startswith("// ERROR")


def test_generate_java_pair_invalid_then_valid(tmp_java_repo):
    ast_result = _make_java_ast({
        "Estadistica.java": {"class_name": "Estadistica"},
        "Calculadora.java": {"class_name": "Calculadora"},
    })
    with patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.side_effect = [INVALID_JAVA_BLOCK, VALID_JAVA_BLOCK]
        result = _generate_java_pair_test(
            MockClient.return_value, tmp_java_repo, "Estadistica.java", "Calculadora.java", ast_result
        )
    assert "@Test" in result
    assert not result.startswith("// ERROR")


def test_generate_java_pair_both_fail(tmp_java_repo):
    ast_result = _make_java_ast({
        "Estadistica.java": {"class_name": "Estadistica"},
        "Calculadora.java": {"class_name": "Calculadora"},
    })
    with patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = INVALID_JAVA_BLOCK
        result = _generate_java_pair_test(
            MockClient.return_value, tmp_java_repo, "Estadistica.java", "Calculadora.java", ast_result
        )
    assert result.startswith("// ERROR: no se pudo generar")


def test_generate_java_pair_unreadable_source(tmp_java_repo):
    ast_result = _make_java_ast({
        "NoExiste.java": {"class_name": "NoExiste"},
        "Calculadora.java": {"class_name": "Calculadora"},
    })
    with patch("agent.integration_generator.LLMClient") as MockClient:
        result = _generate_java_pair_test(
            MockClient.return_value, tmp_java_repo, "NoExiste.java", "Calculadora.java", ast_result
        )
    assert result.startswith("// ERROR: no se pudo leer")


# ---------------------------------------------------------------------------
# Tests de generate() con pares Java
# ---------------------------------------------------------------------------

def test_generate_creates_java_integration_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Estadistica.java").write_text(
        "public class Estadistica {\n"
        "    private Calculadora calc = new Calculadora();\n"
        "    public double promedio(int[] nums) { return 0; }\n"
        "}\n"
    )
    (repo / "Calculadora.java").write_text(
        "public class Calculadora { public int suma(int a, int b) { return a+b; } }\n"
    )
    ast_result = _make_java_ast({
        "Estadistica.java": {"class_name": "Estadistica", "methods": [{"name": "promedio", "params": ["nums"]}]},
        "Calculadora.java": {"class_name": "Calculadora", "methods": [{"name": "suma", "params": ["a", "b"]}]},
    })
    out_dir = tmp_path / "tests_generados" / "integration"
    java_test_dir = out_dir / "src" / "test" / "java"
    with patch("agent.integration_generator.OUTPUT_DIR", out_dir), \
         patch("agent.integration_generator._JAVA_INT_TEST_DIR", java_test_dir), \
         patch("agent.integration_generator._JAVA_INT_MAIN_DIR", out_dir / "src" / "main" / "java"), \
         patch("agent.integration_generator.shutil.which", return_value=None), \
         patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JAVA_BLOCK
        generate(str(repo), ast_result)
    assert (java_test_dir / "EstadisticaCalculadoraIntegrationTest.java").exists()


def test_generate_creates_java_integration_pom(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Estadistica.java").write_text(
        "public class Estadistica {\n"
        "    private Calculadora calc = new Calculadora();\n"
        "}\n"
    )
    (repo / "Calculadora.java").write_text(
        "public class Calculadora { }\n"
    )
    ast_result = _make_java_ast({
        "Estadistica.java": {"class_name": "Estadistica"},
        "Calculadora.java": {"class_name": "Calculadora"},
    })
    out_dir = tmp_path / "tests_generados" / "integration"
    java_test_dir = out_dir / "src" / "test" / "java"
    with patch("agent.integration_generator.OUTPUT_DIR", out_dir), \
         patch("agent.integration_generator._JAVA_INT_TEST_DIR", java_test_dir), \
         patch("agent.integration_generator._JAVA_INT_MAIN_DIR", out_dir / "src" / "main" / "java"), \
         patch("agent.integration_generator.shutil.which", return_value=None), \
         patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JAVA_BLOCK
        generate(str(repo), ast_result)
    pom = out_dir / "pom.xml"
    assert pom.exists()
    assert "junit-jupiter" in pom.read_text()
    assert "maven-surefire-plugin" in pom.read_text()


def test_generate_copies_java_sources(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Estadistica.java").write_text(
        "public class Estadistica { private Calculadora c = new Calculadora(); }\n"
    )
    (repo / "Calculadora.java").write_text("public class Calculadora { }\n")
    ast_result = _make_java_ast({
        "Estadistica.java": {"class_name": "Estadistica"},
        "Calculadora.java": {"class_name": "Calculadora"},
    })
    out_dir = tmp_path / "tests_generados" / "integration"
    java_test_dir = out_dir / "src" / "test" / "java"
    java_main_dir = out_dir / "src" / "main" / "java"
    with patch("agent.integration_generator.OUTPUT_DIR", out_dir), \
         patch("agent.integration_generator._JAVA_INT_TEST_DIR", java_test_dir), \
         patch("agent.integration_generator._JAVA_INT_MAIN_DIR", java_main_dir), \
         patch("agent.integration_generator.shutil.which", return_value=None), \
         patch("agent.integration_generator.LLMClient") as MockClient:
        MockClient.return_value.generate.return_value = VALID_JAVA_BLOCK
        generate(str(repo), ast_result)
    assert (java_main_dir / "Estadistica.java").exists()
    assert (java_main_dir / "Calculadora.java").exists()


def test_generate_no_java_pairs_no_pom(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "A.java").write_text("public class A { }\n")
    (repo / "B.java").write_text("public class B { }\n")
    ast_result = _make_java_ast({
        "A.java": {"class_name": "A"},
        "B.java": {"class_name": "B"},
    })
    out_dir = tmp_path / "tests_generados" / "integration"
    java_test_dir = out_dir / "src" / "test" / "java"
    with patch("agent.integration_generator.OUTPUT_DIR", out_dir), \
         patch("agent.integration_generator._JAVA_INT_TEST_DIR", java_test_dir), \
         patch("agent.integration_generator._JAVA_INT_MAIN_DIR", out_dir / "src" / "main" / "java"), \
         patch("agent.integration_generator.shutil.which", return_value=None), \
         patch("agent.integration_generator.LLMClient"):
        generate(str(repo), ast_result)
    assert not (out_dir / "pom.xml").exists()
