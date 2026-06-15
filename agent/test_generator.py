"""
Generador de tests unitarios para repositorios Python, JavaScript/TypeScript y Java.

Para Python genera archivos pytest en tests_generados/unit/test_<stem>.py.
Para JS/TS genera archivos Jest en tests_generados/unit/<stem>.test.js.
Para Java genera archivos JUnit 5 en tests_generados/unit/src/test/java/<Class>Test.java.

Llama al LLM una vez por función/método, valida el output y reintenta
una vez si el código generado no es válido.
"""

import ast
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from agent.llm_client import LLMClient
from prompts.prompt_builder import PromptBuilder, clean_response

OUTPUT_DIR = Path("tests_generados/unit")
_JAVA_TEST_DIR = OUTPUT_DIR / "src" / "test" / "java"
_JAVA_MAIN_DIR = OUTPUT_DIR / "src" / "main" / "java"

_JS_EXTENSIONS = {'.js', '.ts'}
_JAVA_EXTENSIONS = {'.java'}


def _detect_language(rel_path: str) -> str:
    suffix = Path(rel_path).suffix
    if suffix in _JAVA_EXTENSIONS:
        return "java"
    return "javascript" if suffix in _JS_EXTENSIONS else "python"


def generate(repo_path: str, ast_result: dict, progress_callback=None, client=None) -> None:
    """
    Genera tests unitarios para todas las funciones y métodos del ast_result.

    Args:
        repo_path: Ruta al repositorio analizado (absoluta o relativa al cwd).
        ast_result: Dict producido por ast_extractor.extract().
                    Estructura: {rel_path: {functions, classes, imports}}
        progress_callback: Callable opcional con firma (current, total, label).
                           Se llama despues de procesar cada archivo.
        client: Cliente LLM a usar. Si es None crea OllamaClient() por defecto.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if client is None:
        client = LLMClient()
    repo = Path(repo_path).expanduser().resolve()
    has_python = False
    has_js = False
    has_java = False

    files = list(ast_result.items())
    total = len(files)

    for idx, (rel_path, file_info) in enumerate(files, 1):
        language = _detect_language(rel_path)

        if language == "java":
            has_java = True
            _generate_java_tests(client, repo, rel_path, file_info)
        else:
            if language == "python":
                has_python = True
            else:
                has_js = True

            blocks = _generate_blocks_for_file(client, repo, rel_path, file_info, language)
            if blocks:
                module_name = Path(rel_path).stem
                if language == "javascript":
                    header = _build_js_import_header(module_name, file_info)
                    out_file = OUTPUT_DIR / f"{module_name}.test.js"
                else:
                    header = _build_import_header(module_name, file_info)
                    out_file = OUTPUT_DIR / f"test_{module_name}.py"
                out_file.write_text(header + "\n\n" + "\n\n".join(blocks) + "\n")

        if progress_callback:
            progress_callback(idx, total, Path(rel_path).name)

    if has_python:
        _write_conftest(repo)
    if has_js:
        _write_jest_config(repo)
    if has_java:
        _copy_java_sources(repo)
        _write_java_pom()
        if shutil.which("mvn"):
            _compile_and_fix_java(client, OUTPUT_DIR)


def _build_import_header(module_name: str, file_info: dict) -> str:
    """Construye el bloque de imports del archivo de tests Python: pytest + símbolos del módulo."""
    lines = ["import pytest"]
    for func in file_info.get("functions", []):
        lines.append(f"from {module_name} import {func['name']}")
    seen: set[str] = set()
    for cls in file_info.get("classes", []):
        if cls["name"] not in seen:
            lines.append(f"from {module_name} import {cls['name']}")
            seen.add(cls["name"])
    return "\n".join(lines)


def _build_js_import_header(module_name: str, file_info: dict) -> str:
    """
    Construye el require CommonJS para el archivo de tests Jest.

    Usa nombre bare (sin './') para que Jest lo resuelva vía modulePaths
    configurado en jest.config.js — análogo a sys.path en conftest.py.
    """
    symbols: list[str] = []
    for func in file_info.get("functions", []):
        symbols.append(func["name"])
    seen: set[str] = set()
    for cls in file_info.get("classes", []):
        if cls["name"] not in seen:
            symbols.append(cls["name"])
            seen.add(cls["name"])
    if symbols:
        destructured = ", ".join(symbols)
        return f"const {{ {destructured} }} = require('{module_name}');"
    return f"const mod = require('{module_name}');"


def _write_jest_config(repo: Path) -> None:
    """
    Escribe jest.config.js en el directorio de tests generados.

    rootDir: '../..' apunta al directorio raíz del proyecto (dos niveles arriba
    de tests_generados/unit/). Así Jest puede encontrar los archivos fuente del
    repo y escribir coverage/ en un lugar predecible.
    coverageProvider: 'v8' instrumenta sin Babel, evitando errores con CommonJS.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    root_dir_abs = (OUTPUT_DIR / "../..").resolve()
    repo_relpath = os.path.relpath(repo, root_dir_abs)
    config = (
        "module.exports = {\n"
        "  rootDir: '../..',\n"
        f"  testMatch: ['<rootDir>/tests_generados/unit/**/*.test.{{js,ts}}'],\n"
        f"  modulePaths: ['<rootDir>/{repo_relpath}'],\n"
        "  coverageProvider: 'v8',\n"
        f"  collectCoverageFrom: ['{repo_relpath}/**/*.{{js,ts}}'],\n"
        "};\n"
    )
    (OUTPUT_DIR / "jest.config.js").write_text(config)


def _generate_blocks_for_file(
    client: LLMClient,
    repo: Path,
    rel_path: str,
    file_info: dict,
    language: str = "python",
) -> list[str]:
    """Genera todos los bloques de tests para un archivo fuente."""
    source_lines = _read_source_lines(repo, rel_path)
    if source_lines is None:
        return []

    module_name = Path(rel_path).stem
    blocks = []

    for func in file_info.get("functions", []):
        block = _generate_block(
            client=client,
            source_lines=source_lines,
            unit=func,
            module_name=module_name,
            class_name=None,
            language=language,
        )
        blocks.append(block)

    for cls in file_info.get("classes", []):
        for method in cls.get("methods", []):
            block = _generate_block(
                client=client,
                source_lines=source_lines,
                unit=method,
                module_name=module_name,
                class_name=cls["name"],
                language=language,
            )
            blocks.append(block)

    return blocks


def _generate_block(
    client: LLMClient,
    source_lines: list[str],
    unit: dict,
    module_name: str,
    class_name: Optional[str],
    language: str = "python",
    class_source: str = "",
) -> str:
    """
    Genera un bloque de tests para una función o método.
    Reintenta una vez si el output del LLM no es válido.
    """
    func_source = _slice_source(source_lines, unit)
    func_name = unit["name"]

    for attempt in range(2):
        prompt = PromptBuilder.build(
            code=func_source,
            language=language,
            function_name=func_name,
            module_name=module_name,
            class_name=class_name,
            class_source=class_source,
        )
        raw = client.generate(prompt.user, system=prompt.system)
        code = clean_response(raw, strip_imports=True, language=language)

        if language == "javascript":
            if "test(" in code or "describe(" in code or "it(" in code:
                return code
        elif language == "java":
            if _is_embeddable_java_block(code, class_name):
                return code
        else:
            try:
                ast.parse(code)
                return code
            except SyntaxError:
                pass

        if attempt == 0:
            continue

    label = f"{class_name}.{func_name}" if class_name else func_name
    return f"# ERROR: no se pudo generar tests para {label}"


def _slice_source(source_lines: list[str], unit: dict) -> str:
    """Extrae el código fuente de una función/método usando _lineno y _end_lineno."""
    start = unit.get("_lineno", 1) - 1
    end = unit.get("_end_lineno", start + 1)
    return "\n".join(source_lines[start:end])


def _read_source_lines(repo: Path, rel_path: str) -> Optional[list[str]]:
    """Lee el archivo fuente y devuelve sus líneas. Devuelve None si no se puede leer."""
    try:
        return (repo / rel_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None


def _has_balanced_braces(code: str) -> bool:
    """Devuelve True si el código Java tiene llaves { } correctamente balanceadas."""
    depth = 0
    for ch in code:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        if depth < 0:
            return False
    return depth == 0


def _is_embeddable_java_block(code: str, class_name: Optional[str] = None) -> bool:
    """Valida que el bloque sea seguro para incrustar dentro del cuerpo de una clase Java."""
    if not _has_balanced_braces(code):
        return False
    if re.search(r'\d+L\b', code):
        return False
    # JUnit 4: expected = SomeException.class, tanto suelto como dentro de @Test(expected=...)
    if re.search(r'\bexpected\s*=', code):
        return False
    # Int. es un typo frecuente del LLM; la clase correcta es Integer.
    if re.search(r'\bInt\.', code):
        return False
    # Comentario Python (#) dentro de código Java — el bloque está malformado.
    if re.search(r'^\s*#', code, re.MULTILINE):
        return False
    # El nombre de clase instanciado debe coincidir exactamente con class_name esperado.
    if class_name:
        instantiated = re.findall(r'\bnew\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(', code)
        if instantiated and not all(name == class_name for name in instantiated):
            return False
    # delta/DELTA usado sin haber sido declarado en el mismo bloque.
    if re.search(r'\bDELTA\b|\bdelta\b', code) and not re.search(r'\b(?:double|float)\s+delta\b', code):
        return False
    # null pasado a un método — incompatible con tipos primitivos (int, double, float, etc.)
    if re.search(r'\bnull\b', code):
        return False
    for line in code.splitlines():
        s = line.strip()
        if s.startswith('import '):
            return False
        if re.match(r'(?:(?:public|private|protected|abstract|static|final)\s+)*class\s+\w', s):
            return False
    return True


# Patrón de error javac en output de mvn --batch-mode:
# [ERROR] /abs/path/Foo.java:[25,1] error: <identifier> expected
_JAVAC_ERROR_PAT = re.compile(r'\[ERROR\]\s+(/[^\s:]+\.java):\[(\d+),\d+\]\s+(.*)')


def _parse_javac_errors(output: str) -> dict:
    """Extrae {Path: texto_de_errores} del output de mvn test-compile --batch-mode."""
    errors: dict = {}
    for match in _JAVAC_ERROR_PAT.finditer(output):
        path = Path(match.group(1))
        error = f"line {match.group(2)}: {match.group(3)}"
        errors.setdefault(path, []).append(error)
    return {p: "\n".join(errs) for p, errs in errors.items()}


def _fix_java_file_with_llm(client: LLMClient, content: str, errors: str) -> Optional[str]:
    """Pide al LLM que corrija los errores de compilación en el archivo Java."""
    system = (
        "You are a Java expert. Fix the compilation errors in the Java test file below. "
        "Return ONLY the complete corrected Java file, from the first import to the last closing brace. "
        "No markdown, no backticks, no explanations. "
        "Start your response with the first line of the file (import or class declaration).\n"
        "ABSOLUTE RULES — never break these:\n"
        "- Do NOT add any import statement that is not already present in the original file.\n"
        "- Only use JUnit 5 assertion methods available via "
        "'import static org.junit.jupiter.api.Assertions.*': "
        "assertEquals, assertTrue, assertFalse, assertNull, assertNotNull, assertThrows.\n"
        "- Do NOT use long literals (e.g. 100L). Use int or double literals only.\n"
        "- NEVER use JUnit 4 syntax. For exceptions always use assertThrows(), never @Test(expected=...).\n"
        "- NEVER use Int. — always use Integer. (e.g. Integer.MIN_VALUE, Integer.MAX_VALUE).\n"
        "- Do NOT add any comments inside the test methods. No // lines, no /* */ blocks, no # characters.\n"
        "- Never use DELTA or delta as a variable. "
        "For floating-point comparisons use assertEquals(expected, actual, 0.001) directly.\n"
        "- Never pass null to methods that expect primitive types like int, double, float.\n"
        "- Always use the exact class name as provided. Never instantiate a different class.\n"
        "- Never use variables that are not declared within the same test method.\n"
        "- Instantiate the class under test inside each test method.\n"
        "- NEVER use Double.INFINITY — use Double.POSITIVE_INFINITY or Double.NEGATIVE_INFINITY instead.\n"
        "- NEVER use ExecutableAssert or any variable not declared in the current test method."
    )
    user = (
        f"Fix the following Java compilation errors:\n\n"
        f"ERRORS:\n{errors}\n\n"
        f"FILE:\n{content}"
    )
    raw = client.generate(user, system=system)
    blocks = re.findall(r"```(?:java)?\n?(.*?)```", raw, re.DOTALL)
    fixed = blocks[0].strip() if blocks else raw.strip()
    return fixed or None


def _compile_and_fix_java(client: LLMClient, maven_root: Path) -> None:
    """
    Ciclo de compilación-corrección post-generación.

    Ejecuta mvn test-compile; si falla, manda el error al LLM para que corrija
    el archivo. Repite hasta 3 veces o hasta que compile limpio.
    """
    for attempt in range(3):
        result = subprocess.run(
            ["mvn", "test-compile", "--batch-mode"],
            capture_output=True,
            text=True,
            cwd=str(maven_root),
        )
        if result.returncode == 0:
            return

        errors_by_file = _parse_javac_errors(result.stdout + result.stderr)
        if not errors_by_file:
            return

        for file_path, error_text in errors_by_file.items():
            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError:
                continue
            fixed = _fix_java_file_with_llm(client, content, error_text)
            if fixed:
                file_path.write_text(fixed, encoding="utf-8")


def _generate_java_tests(client: LLMClient, repo: Path, rel_path: str, file_info: dict) -> None:
    """Genera un archivo <ClassName>Test.java por cada clase en el archivo fuente."""
    source_lines = _read_source_lines(repo, rel_path)
    if source_lines is None:
        return

    _JAVA_TEST_DIR.mkdir(parents=True, exist_ok=True)

    for cls in file_info.get("classes", []):
        class_name = cls["name"]
        class_source = "\n".join(source_lines) if source_lines else ""
        blocks = []
        seen_method_names: set[str] = set()
        for method in cls.get("methods", []):
            block = _generate_block(
                client=client,
                source_lines=source_lines,
                unit=method,
                module_name=class_name,
                class_name=class_name,
                language="java",
                class_source=class_source,
            )
            if not _is_embeddable_java_block(block, class_name):
                print(f"[WARN] {class_name}.{method['name']}: bloque descartado")
                continue
            names = re.findall(r'\bvoid\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(', block)
            if any(n in seen_method_names for n in names):
                continue
            seen_method_names.update(names)
            blocks.append(block)

        if blocks:
            out_file = _JAVA_TEST_DIR / f"{class_name}Test.java"
            out_file.write_text(_build_java_test_file(class_name, blocks))


def _build_java_test_file(class_name: str, blocks: list[str]) -> str:
    """Arma el archivo Java completo con imports JUnit 5 y wrapper de clase."""
    combined = "\n".join(blocks)

    imports = [
        "import org.junit.jupiter.api.Test;",
        "import org.junit.jupiter.api.Assertions;",
        "import static org.junit.jupiter.api.Assertions.*;",
    ]
    if "@BeforeEach" in combined:
        imports.append("import org.junit.jupiter.api.BeforeEach;")
    if "ArrayList" in combined:
        imports.append("import java.util.ArrayList;")
    if "Arrays." in combined:
        imports.append("import java.util.Arrays;")
    if re.search(r'\bList[<\s]', combined):
        imports.append("import java.util.List;")

    header = "\n".join(imports) + f"\n\nclass {class_name}Test {{\n"


    indented_blocks = []
    for block in blocks:
        indented = "\n".join(
            "    " + line if line.strip() else line
            for line in block.splitlines()
        )
        indented_blocks.append(indented)
    body = "\n\n".join(indented_blocks)
    return header + "\n" + body + "\n}\n"


def _copy_java_sources(repo: Path) -> None:
    """Copia los .java del repo a src/main/java/ para que Maven pueda compilarlos."""
    _JAVA_MAIN_DIR.mkdir(parents=True, exist_ok=True)
    for java_file in repo.rglob("*.java"):
        dest = _JAVA_MAIN_DIR / java_file.name
        shutil.copy2(java_file, dest)


def _write_java_pom() -> None:
    """Escribe un pom.xml con JUnit 5 y JaCoCo en el directorio de tests generados."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pom_path = OUTPUT_DIR / "pom.xml"
    if pom_path.exists():
        # El pom es idempotente: si ya existe (de un run previo) no se sobreescribe.
        # Para actualizar el pom (ej. agregar plugins nuevos) hay que borrar tests_generados/.
        return
    pom_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<project xmlns="http://maven.apache.org/POM/4.0.0"\n'
        '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        '         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 '
        'http://maven.apache.org/xsd/maven-4.0.0.xsd">\n'
        '    <modelVersion>4.0.0</modelVersion>\n'
        '    <groupId>local.test.agent</groupId>\n'
        '    <artifactId>generated-tests</artifactId>\n'
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
        '            <plugin>\n'
        '                <groupId>org.jacoco</groupId>\n'
        '                <artifactId>jacoco-maven-plugin</artifactId>\n'
        '                <version>0.8.13</version>\n'
        '                <executions>\n'
        '                    <execution>\n'
        '                        <id>prepare-agent</id>\n'
        '                        <goals><goal>prepare-agent</goal></goals>\n'
        '                    </execution>\n'
        '                    <execution>\n'
        '                        <id>report</id>\n'
        '                        <phase>test</phase>\n'
        '                        <goals><goal>report</goal></goals>\n'
        '                    </execution>\n'
        '                </executions>\n'
        '            </plugin>\n'
        '        </plugins>\n'
        '    </build>\n'
        '</project>\n'
    )
    pom_path.write_text(pom_content)


def _write_conftest(repo: Path) -> None:
    """Escribe conftest.py con la ruta absoluta del repo en sys.path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    content = (
        "import sys\n"
        "import pathlib\n"
        "\n"
        f'sys.path.insert(0, "{repo}")\n'
    )
    (OUTPUT_DIR / "conftest.py").write_text(content)


if __name__ == "__main__":
    import sys as _sys
    from agent.repo_explorer import explore
    from agent.ast_extractor import extract

    if len(_sys.argv) < 2:
        print("Uso: python3 -m agent.test_generator <repo_path>")
        _sys.exit(1)

    repo_path = _sys.argv[1]
    files = explore(repo_path)
    ast_result = extract(files, repo_path)
    generate(repo_path, ast_result)
    print(f"Tests generados en {OUTPUT_DIR}/")
