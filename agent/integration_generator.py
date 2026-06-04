"""
Generador de tests de integración para repositorios Python, JavaScript/TypeScript y Java.

Recibe el dict producido por ast_extractor.extract(), detecta pares de módulos/clases
relacionados, llama al LLM una vez por par y escribe los tests.

Python: valida con ast.parse() y reintenta una vez si el código no es válido.
JS/TS: valida presencia de bloques test/describe y reintenta una vez si no los hay.
Java: detecta pares por uso directo en el código fuente (no por imports), valida
      presencia de @Test y reintenta una vez. Escribe estructura Maven compatible.
"""

import ast
import re
import shutil
from pathlib import Path
from typing import Optional

from agent.llm_client import LLMClient
from agent.test_generator import _compile_and_fix_java
from prompts.prompt_builder import (
    IntegrationPromptTemplate,
    JavaIntegrationPromptTemplate,
    JsIntegrationPromptTemplate,
    clean_response,
)

OUTPUT_DIR = Path("tests_generados/integration")
_JAVA_INT_TEST_DIR = OUTPUT_DIR / "src" / "test" / "java"
_JAVA_INT_MAIN_DIR = OUTPUT_DIR / "src" / "main" / "java"

_TEMPLATE = IntegrationPromptTemplate()
_JS_TEMPLATE = JsIntegrationPromptTemplate()
_JAVA_INT_TEMPLATE = JavaIntegrationPromptTemplate()

_JS_EXTENSIONS = {".js", ".ts", ".mjs"}


def generate(repo_path: str, ast_result: dict, progress_callback=None, client=None) -> None:
    """
    Genera tests de integración para todos los pares de módulos relacionados.

    Args:
        repo_path: Ruta al repositorio analizado (absoluta o relativa al cwd).
        ast_result: Dict producido por ast_extractor.extract().
                    Estructura: {rel_path: {functions, classes, imports}}
        progress_callback: Callable opcional con firma (current, total, label).
                           Se llama despues de procesar cada par de modulos.
        client: Cliente LLM a usar. Si es None crea OllamaClient() por defecto.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if client is None:
        client = LLMClient()
    repo = Path(repo_path).expanduser().resolve()

    pairs = _find_pairs(ast_result)
    js_pairs = _find_js_pairs(ast_result)
    java_pairs = _find_java_pairs(ast_result, repo)
    total = len(pairs) + len(js_pairs) + len(java_pairs)
    idx = 0

    for (a_path, b_path) in pairs:
        idx += 1
        code = _generate_pair_test(client, repo, a_path, b_path, ast_result)
        stem_a = Path(a_path).stem
        stem_b = Path(b_path).stem
        out_file = OUTPUT_DIR / f"test_{stem_a}_{stem_b}.py"
        out_file.write_text(code + "\n")
        if progress_callback:
            progress_callback(idx, total, f"{stem_a}+{stem_b}")

    _write_conftest(repo)

    for (a_path, b_path) in js_pairs:
        idx += 1
        code = _generate_js_pair_test(client, repo, a_path, b_path, ast_result)
        stem_a = Path(a_path).stem
        stem_b = Path(b_path).stem
        out_file = OUTPUT_DIR / f"{stem_a}_{stem_b}.test.js"
        out_file.write_text(code + "\n")
        if progress_callback:
            progress_callback(idx, total, f"{stem_a}+{stem_b}")

    if js_pairs:
        _write_js_jest_config(repo)

    for (a_path, b_path) in java_pairs:
        idx += 1
        class_a = _get_java_class_name(ast_result, a_path)
        class_b = _get_java_class_name(ast_result, b_path)
        code = _generate_java_pair_test(client, repo, a_path, b_path, ast_result)
        _JAVA_INT_TEST_DIR.mkdir(parents=True, exist_ok=True)
        out_file = _JAVA_INT_TEST_DIR / f"{class_a}{class_b}IntegrationTest.java"
        out_file.write_text(code)
        if progress_callback:
            progress_callback(idx, total, f"{class_a}+{class_b}")

    if java_pairs:
        _copy_java_sources_for_integration(repo)
        _write_java_integration_pom()
        if shutil.which("mvn"):
            _compile_and_fix_java(client, OUTPUT_DIR)


def _find_js_pairs(ast_result: dict) -> list[tuple[str, str]]:
    """
    Retorna la lista de pares (importer_path, imported_path) para archivos JS/TS.

    Un par (A, B) se incluye cuando el campo `imports` de A contiene la ruta
    relativa de B y B está también presente como key en ast_result.
    """
    pairs = []
    for rel_path, file_info in ast_result.items():
        if Path(rel_path).suffix not in _JS_EXTENSIONS:
            continue
        for imported in file_info.get("imports", []):
            if imported in ast_result and Path(imported).suffix in _JS_EXTENSIONS:
                pairs.append((rel_path, imported))
    return pairs


def _find_pairs(ast_result: dict) -> list[tuple[str, str]]:
    """
    Retorna la lista de pares (importer_path, imported_path) detectados por imports.

    Solo considera archivos .py: IntegrationPromptTemplate genera Python y usa
    ast.parse() para validar, por lo que no aplica a JS/TS.

    Un par (A, B) se incluye cuando el campo `imports` de A contiene la ruta
    relativa de B y B está también presente como key en ast_result.
    """
    pairs = []
    for rel_path, file_info in ast_result.items():
        if not rel_path.endswith(".py"):
            continue
        for imported in file_info.get("imports", []):
            if imported in ast_result and imported.endswith(".py"):
                pairs.append((rel_path, imported))
    return pairs


def _format_signatures(file_info: dict) -> str:
    """
    Formatea las firmas de las funciones top-level de un módulo como string.

    Ejemplo de salida:
        def sumar(a, b): ...
        def multiplicar(a, b): ...
    """
    lines = []
    for func in file_info.get("functions", []):
        params = ", ".join(func.get("params", []))
        lines.append(f"def {func['name']}({params}): ...")
    return "\n".join(lines)


def _generate_pair_test(
    client: LLMClient,
    repo: Path,
    a_path: str,
    b_path: str,
    ast_result: dict,
) -> str:
    """
    Genera el código de tests de integración para el par (a_path importa b_path).
    Reintenta una vez si el output del LLM no es Python válido.
    """
    a_source = _read_source(repo, a_path)
    if a_source is None:
        return f"# ERROR: no se pudo leer {a_path}"

    b_sigs = _format_signatures(ast_result.get(b_path, {}))
    stem_a = Path(a_path).stem
    stem_b = Path(b_path).stem

    for attempt in range(2):
        prompt = _TEMPLATE.build(
            code=a_source,
            module_name=stem_a,
            class_name=stem_b,
            module_b_sigs=b_sigs,
        )
        raw = client.generate(prompt.user, system=prompt.system)
        code = clean_response(raw)
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            if attempt == 0:
                continue

    return f"# ERROR: no se pudo generar test de integración para {stem_a}_{stem_b}"


def _read_source(repo: Path, rel_path: str) -> Optional[str]:
    """Lee el código fuente completo de un módulo. Retorna None si no se puede leer."""
    try:
        return (repo / rel_path).read_text(encoding="utf-8")
    except OSError:
        return None


def _format_js_signatures(file_info: dict) -> str:
    lines = []
    for func in file_info.get("functions", []):
        params = ", ".join(func.get("params", []))
        lines.append(f"function {func['name']}({params}) {{ ... }}")
    return "\n".join(lines)


def _build_js_require_header(stem_a: str, file_info_a: dict) -> str:
    symbols = [f["name"] for f in file_info_a.get("functions", [])]
    if symbols:
        destructured = ", ".join(symbols)
        return f"const {{ {destructured} }} = require('{stem_a}');"
    return f"const mod = require('{stem_a}');"


def _generate_js_pair_test(
    client: LLMClient,
    repo: Path,
    a_path: str,
    b_path: str,
    ast_result: dict,
) -> str:
    """
    Genera el código de tests de integración Jest para el par (a_path importa b_path).
    Reintenta una vez si el output del LLM no contiene bloques test/describe.
    """
    a_source = _read_source(repo, a_path)
    if a_source is None:
        return f"// ERROR: no se pudo leer {a_path}"

    b_sigs = _format_js_signatures(ast_result.get(b_path, {}))
    stem_a = Path(a_path).stem
    stem_b = Path(b_path).stem
    header = _build_js_require_header(stem_a, ast_result.get(a_path, {}))

    for attempt in range(2):
        prompt = _JS_TEMPLATE.build(
            code=a_source,
            module_name=stem_a,
            class_name=stem_b,
            module_b_sigs=b_sigs,
        )
        raw = client.generate(prompt.user, system=prompt.system)
        code = clean_response(raw, strip_imports=True, language="javascript")
        if "test(" in code or "describe(" in code or "it(" in code:
            return header + "\n\n" + code
        if attempt == 0:
            continue

    return f"// ERROR: no se pudo generar test de integración para {stem_a}_{stem_b}"


def _write_js_jest_config(repo: Path) -> None:
    """Escribe jest.config.js en el directorio de integración con modulePaths al repo."""
    config = (
        "module.exports = {\n"
        "  rootDir: '.',\n"
        f"  modulePaths: ['{repo}'],\n"
        "};\n"
    )
    (OUTPUT_DIR / "jest.config.js").write_text(config)


def _write_conftest(repo: Path) -> None:
    """Escribe conftest.py con la ruta absoluta del repo analizado en sys.path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    content = (
        "import sys\n"
        "import pathlib\n"
        "\n"
        f'sys.path.insert(0, "{repo}")\n'
    )
    (OUTPUT_DIR / "conftest.py").write_text(content)


def _find_java_pairs(ast_result: dict, repo: Path) -> list[tuple[str, str]]:
    """
    Detecta pares (a_path, b_path) de archivos Java donde A usa la clase de B.

    En Java, las clases del mismo paquete no necesitan imports entre sí. La relación
    se detecta buscando el nombre de ClaseB como palabra completa en el código de ClaseA.
    Cubre: instanciación (new ClaseB()), declaraciones de tipo (ClaseB var =) y
    llamadas estáticas (ClaseB.metodo()).
    """
    java_files = {
        rel: info
        for rel, info in ast_result.items()
        if rel.endswith(".java")
    }
    class_names: dict[str, str] = {}
    for rel, info in java_files.items():
        classes = info.get("classes", [])
        if classes:
            class_names[rel] = classes[0]["name"]

    pairs = []
    for a_path, class_a in class_names.items():
        source = _read_source(repo, a_path)
        if source is None:
            continue
        for b_path, class_b in class_names.items():
            if a_path == b_path:
                continue
            if re.search(rf"\b{re.escape(class_b)}\b", source):
                pairs.append((a_path, b_path))
    return pairs


def _get_java_class_name(ast_result: dict, rel_path: str) -> str:
    """Retorna el nombre de la primera clase del archivo, o el stem del path."""
    classes = ast_result.get(rel_path, {}).get("classes", [])
    if classes:
        return classes[0]["name"]
    return Path(rel_path).stem


def _format_java_method_sigs(file_info: dict) -> str:
    """Formatea las firmas de los métodos públicos de las clases del archivo."""
    lines = []
    for cls in file_info.get("classes", []):
        for method in cls.get("methods", []):
            params = ", ".join(method.get("params", []))
            lines.append(f"public ... {method['name']}({params}) {{ ... }}")
    return "\n".join(lines)


def _generate_java_pair_test(
    client: LLMClient,
    repo: Path,
    a_path: str,
    b_path: str,
    ast_result: dict,
) -> str:
    """
    Genera el código completo del archivo *IntegrationTest.java para el par (A usa B).
    Reintenta una vez si el output del LLM no contiene @Test.
    """
    a_source = _read_source(repo, a_path)
    if a_source is None:
        class_a = _get_java_class_name(ast_result, a_path)
        class_b = _get_java_class_name(ast_result, b_path)
        return f"// ERROR: no se pudo leer {a_path}\n"

    class_a = _get_java_class_name(ast_result, a_path)
    class_b = _get_java_class_name(ast_result, b_path)
    b_sigs = _format_java_method_sigs(ast_result.get(b_path, {}))

    for attempt in range(2):
        prompt = _JAVA_INT_TEMPLATE.build(
            code=a_source,
            module_name=class_a,
            class_name=class_b,
            module_b_sigs=b_sigs,
        )
        raw = client.generate(prompt.user, system=prompt.system)
        methods_block = clean_response(raw, language="java")
        if "@Test" in methods_block and "void" in methods_block:
            return _build_java_integration_test_file(class_a, class_b, methods_block)
        if attempt == 0:
            continue

    return f"// ERROR: no se pudo generar test de integración para {class_a}+{class_b}\n"


def _build_java_integration_test_file(class_a: str, class_b: str, methods_block: str) -> str:
    """Envuelve los métodos @Test generados en una clase JUnit 5 completa."""
    imports = [
        "import org.junit.jupiter.api.Test;",
        "import org.junit.jupiter.api.Assertions;",
        "import static org.junit.jupiter.api.Assertions.*;",
    ]
    if "ArrayList" in methods_block:
        imports.append("import java.util.ArrayList;")
    if "Arrays." in methods_block:
        imports.append("import java.util.Arrays;")
    if re.search(r"\bList[<\s]", methods_block):
        imports.append("import java.util.List;")

    header = "\n".join(imports) + f"\n\nclass {class_a}{class_b}IntegrationTest {{\n"
    indented = "\n".join(
        "    " + line if line.strip() else line
        for line in methods_block.splitlines()
    )
    return header + "\n" + indented + "\n}\n"


def _write_java_integration_pom() -> None:
    """Escribe pom.xml con JUnit 5 en tests_generados/integration/ si no existe."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pom_path = OUTPUT_DIR / "pom.xml"
    if pom_path.exists():
        return
    pom_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0"\n'
        '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        '         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 '
        'http://maven.apache.org/xsd/maven-4.0.0.xsd">\n'
        '    <modelVersion>4.0.0</modelVersion>\n'
        '    <groupId>local.test.agent</groupId>\n'
        '    <artifactId>generated-integration-tests</artifactId>\n'
        '    <version>1.0-SNAPSHOT</version>\n'
        '    <properties>\n'
        '        <maven.compiler.source>11</maven.compiler.source>\n'
        '        <maven.compiler.target>11</maven.compiler.target>\n'
        '        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>\n'
        '    </properties>\n'
        '    <dependencies>\n'
        '        <dependency>\n'
        '            <groupId>org.junit.jupiter</groupId>\n'
        '            <artifactId>junit-jupiter</artifactId>\n'
        '            <version>5.10.0</version>\n'
        '            <scope>test</scope>\n'
        '        </dependency>\n'
        '    </dependencies>\n'
        '    <build>\n'
        '        <plugins>\n'
        '            <plugin>\n'
        '                <groupId>org.apache.maven.plugins</groupId>\n'
        '                <artifactId>maven-surefire-plugin</artifactId>\n'
        '                <version>3.1.2</version>\n'
        '            </plugin>\n'
        '        </plugins>\n'
        '    </build>\n'
        '</project>\n'
    )
    pom_path.write_text(pom_content)


def _copy_java_sources_for_integration(repo: Path) -> None:
    """Copia los .java del repo a src/main/java/ para que Maven los compile."""
    _JAVA_INT_MAIN_DIR.mkdir(parents=True, exist_ok=True)
    for java_file in repo.rglob("*.java"):
        dest = _JAVA_INT_MAIN_DIR / java_file.name
        shutil.copy2(java_file, dest)


if __name__ == "__main__":
    import sys as _sys
    from agent.repo_explorer import explore
    from agent.ast_extractor import extract

    if len(_sys.argv) < 2:
        print("Uso: python3 -m agent.integration_generator <repo_path>")
        _sys.exit(1)

    repo_path = _sys.argv[1]
    files = explore(repo_path)
    ast_result = extract(files, repo_path)
    generate(repo_path, ast_result)
    print(f"Tests de integración generados en {OUTPUT_DIR}/")
