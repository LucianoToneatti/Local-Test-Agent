"""
Runner de tests para Python (pytest), JavaScript/TypeScript (Jest) y Java (Maven).

Detecta automaticamente que tipos de tests hay en el directorio y ejecuta
pytest, Jest y/o Maven segun corresponda. Los resultados se combinan en el mismo
formato {test_id: {status, traceback}}.

Prerequisitos:
- Python: pytest instalado en el entorno activo.
- JavaScript: Node.js y Jest instalados.
- Java: Maven (mvn) instalado. Si no está disponible, el agente lo indica claramente.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def run(tests_dir: str, repo_path: str = "") -> tuple[dict, float | None]:
    """
    Ejecuta pytest y/o Jest sobre tests_dir y devuelve resultados y cobertura.

    Args:
        tests_dir: Ruta al directorio con los tests generados.
        repo_path: Ruta al repositorio analizado. Si se provee y pytest-cov
                   esta instalado, se agrega --cov al comando de pytest.

    Returns:
        Tupla (results, coverage_pct) donde results es un dict con formato
        {test_id: {'status': str, 'traceback': str|None}} y coverage_pct es
        el porcentaje de cobertura como float, o None si no esta disponible.
    """
    py_results, coverage_pct = _run_pytest(tests_dir, repo_path)
    js_results = _run_jest(tests_dir)
    java_results = _run_maven(tests_dir)
    return {**py_results, **js_results, **java_results}, coverage_pct


def _run_pytest(tests_dir: str, repo_path: str = "") -> tuple[dict, float | None]:
    """Ejecuta pytest -v sobre tests_dir y devuelve (resultados, cobertura)."""
    if importlib.util.find_spec("pytest") is None:
        print("[ERROR] pytest no esta instalado. Ejecuta: pip install pytest")
        return {}, None

    tests_path = Path(tests_dir)
    if not tests_path.exists():
        print(f"[ERROR] El directorio de tests no existe: {tests_dir}")
        return {}, None

    cmd = [
        sys.executable, "-m", "pytest", "-v",
        "--continue-on-collection-errors",
        str(tests_path),
    ]

    has_cov = importlib.util.find_spec("pytest_cov") is not None
    if repo_path and has_cov:
        cmd += [f"--cov={repo_path}", "--cov-report=term-missing"]

    result = subprocess.run(cmd, capture_output=True, text=True)

    output = result.stdout + result.stderr
    coverage_pct = _parse_coverage(output) if (repo_path and has_cov) else None
    return _parse_output(output), coverage_pct


def _parse_coverage(output: str) -> float | None:
    """
    Extrae el porcentaje total de cobertura del output de pytest-cov.

    pytest-cov imprime una linea al final del estilo:
      TOTAL   120   30   75%
    """
    match = re.search(r"^TOTAL(?:\s+\d+)+\s+(\d+)%", output, re.MULTILINE)
    if match:
        return float(match.group(1))
    return None


def _run_jest(tests_dir: str) -> dict:
    """
    Ejecuta Jest sobre *.test.js y *.test.ts en tests_dir si los hay.

    Corre Jest una vez por cada subdirectorio que tenga su propio jest.config.js,
    para que unit/ e integration/ puedan tener configuraciones independientes.
    """
    tests_path = Path(tests_dir)
    if not tests_path.exists():
        return {}

    js_files = list(tests_path.rglob("*.test.js")) + list(tests_path.rglob("*.test.ts"))
    if not js_files:
        return {}

    if not shutil.which("node"):
        print("[ERROR] Node.js no esta instalado. Jest requiere Node.js para ejecutar tests JavaScript.")
        print("    Instala Node.js desde https://nodejs.org")
        return {}

    # Recolectar los directorios con jest.config.js, en orden de aparicion
    config_dirs: list[Path] = []
    seen: set[Path] = set()
    for f in js_files:
        d = f.parent
        if d not in seen and (d / "jest.config.js").exists():
            config_dirs.append(d)
            seen.add(d)

    if not config_dirs:
        config_dirs = [js_files[0].parent]

    results = {}
    for cwd in config_dirs:
        result = subprocess.run(
            ["npx", "jest", "--json", "--no-coverage"],
            capture_output=True,
            text=True,
            cwd=str(cwd),
        )
        results.update(_parse_jest_output(result.stdout))

    return results


def _run_maven(tests_dir: str) -> dict:
    """
    Ejecuta mvn test sobre proyectos Maven encontrados dentro de tests_dir.

    Busca *Test.java recursivamente (no solo en src/test/java/ directo) para
    soportar el caso en que tests_dir sea el directorio raíz de salida
    (tests_generados/) y el proyecto Maven esté en un subdirectorio (unit/).
    Para cada pom.xml encontrado corre Maven y parsea los XMLs de Surefire.
    """
    tests_path = Path(tests_dir).resolve()

    java_files = list(tests_path.rglob("*Test.java"))
    if not java_files:
        return {}

    if not shutil.which("mvn"):
        print("[INFO] Maven (mvn) no está instalado.")
        print("    Los tests Java fueron generados pero no se pueden ejecutar.")
        print("    Para instalar Maven:")
        print("    sudo apt install maven")
        pom_files = list(tests_path.rglob("pom.xml"))
        if pom_files:
            print("    Una vez instalado, ejecutá:")
            print(f"    cd {pom_files[0].parent} && mvn test")
        return {}

    pom_files = list(tests_path.rglob("pom.xml"))
    if not pom_files:
        print("[ERROR] pom.xml no encontrado. Regenerá los tests.")
        return {}

    results = {}
    for pom_path in pom_files:
        maven_root = pom_path.parent
        subprocess.run(
            ["mvn", "test", "--batch-mode"],
            capture_output=True,
            text=True,
            cwd=str(maven_root),
        )
        results.update(_parse_surefire_reports(maven_root / "target" / "surefire-reports"))

    return results


def _parse_surefire_reports(reports_dir: Path) -> dict:
    """Parsea los XMLs de Surefire y devuelve {test_id: {status, traceback}}."""
    results = {}
    if not reports_dir.exists():
        return results

    for xml_file in reports_dir.glob("TEST-*.xml"):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            suite_name = root.get("name", xml_file.stem)
            for testcase in root.findall("testcase"):
                method_name = testcase.get("name", "unknown")
                test_id = f"{suite_name}::{method_name}"
                failure = testcase.find("failure")
                error = testcase.find("error")
                skipped = testcase.find("skipped")
                if skipped is not None:
                    results[test_id] = {"status": "skipped", "traceback": None}
                elif failure is not None:
                    results[test_id] = {
                        "status": "failed",
                        "traceback": failure.get("message", failure.text or ""),
                    }
                elif error is not None:
                    results[test_id] = {
                        "status": "error",
                        "traceback": error.get("message", error.text or ""),
                    }
                else:
                    results[test_id] = {"status": "passed", "traceback": None}
        except ET.ParseError:
            pass

    return results


def _parse_jest_output(stdout: str) -> dict:
    """
    Parsea el JSON de `jest --json` y devuelve {test_id: {status, traceback}}.

    Jest usa la clave 'assertionResults' (no 'testResults') para los tests
    individuales dentro de cada suite.
    """
    json_start = stdout.find('{')
    if json_start == -1:
        return {}
    try:
        data = json.loads(stdout[json_start:])
    except (json.JSONDecodeError, ValueError):
        return {}

    results = {}
    cwd = Path.cwd()

    for suite in data.get("testResults", []):
        abs_file = suite.get("testFilePath", "")
        try:
            rel_path = str(Path(abs_file).relative_to(cwd))
        except ValueError:
            rel_path = abs_file

        for test in suite.get("assertionResults", []):
            title = test.get("title", "unknown")
            status_raw = test.get("status", "failed")
            status = "passed" if status_raw == "passed" else "failed"
            failure_msgs = test.get("failureMessages", [])
            traceback = "\n".join(failure_msgs) if failure_msgs else None
            test_id = f"{rel_path}::{title}"
            results[test_id] = {"status": status, "traceback": traceback}

    return results


def _parse_output(output: str) -> dict:
    """
    Parsea el stdout de pytest -v y extrae resultados por test_id.

    El formato de una linea de resultado en pytest -v es:
      path/test_file.py::test_nombre STATUS
    donde STATUS es PASSED, FAILED o ERROR.

    Tambien captura collection errors (ImportError, ModuleNotFoundError al
    importar el modulo de test), que pytest reporta como:
      ERROR path/test_file.py
    sin ::nombre de funcion. Estos se registran con el path del archivo como key.
    """
    results = {}

    line_re = re.compile(
        r"^([\w/\\.:-]+::\w+)\s+(PASSED|FAILED|ERROR)", re.MULTILINE
    )
    for match in line_re.finditer(output):
        test_id = match.group(1)
        status = match.group(2).lower()
        results[test_id] = {"status": status, "traceback": None}

    # Collection errors: el archivo no pudo importarse; pytest no llega a
    # enumerar tests individuales. El key es la ruta del archivo (sin ::nombre).
    coll_re = re.compile(r"^ERROR\s+([\w/\\. :-]+\.py)", re.MULTILINE)
    for match in coll_re.finditer(output):
        file_path = match.group(1)
        if file_path not in results:
            results[file_path] = {"status": "error", "traceback": None}

    _attach_tracebacks(output, results)
    _attach_collection_tracebacks(output, results)

    return results


def _attach_collection_tracebacks(output: str, results: dict) -> None:
    """
    Captura bloques de error de coleccion (ERROR collecting path/file.py)
    y los adjunta al test_id correspondiente (ruta del archivo, sin ::nombre).
    """
    block_re = re.compile(
        r"_{5,}\s+ERROR collecting\s+([\w/\\. :-]+\.py)\s+_{5,}\n(.*?)(?=_{5,}|={5,}|\Z)",
        re.DOTALL,
    )
    for match in block_re.finditer(output):
        file_path = match.group(1)
        traceback_text = match.group(2).strip()
        if file_path in results:
            results[file_path]["traceback"] = traceback_text


def _attach_tracebacks(output: str, results: dict) -> None:
    """
    Busca los bloques de traceback en el output de pytest y los asigna
    al test_id correspondiente en el dict results (modifica in-place).

    pytest -v genera bloques con el patron:
      _________________________ test_nombre _________________________
      ...traceback...
      ========================= short test summary ===================
    """
    # Captura: header _____func_____ seguido del cuerpo hasta el proximo separador
    block_re = re.compile(
        r"_{5,}\s+(\w+)\s+_{5,}\n(.*?)(?=_{5,}|={5,}|\Z)",
        re.DOTALL,
    )
    for match in block_re.finditer(output):
        func_name = match.group(1)
        traceback_text = match.group(2).strip()
        for test_id in results:
            if test_id.endswith(f"::{func_name}"):
                results[test_id]["traceback"] = traceback_text
                break
