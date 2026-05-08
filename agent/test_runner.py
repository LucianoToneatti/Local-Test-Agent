"""
Runner de tests para repositorios Python.

Ejecuta pytest sobre el directorio de tests generados como subproceso aislado
y devuelve un diccionario con el resultado por test_id.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path


def run(tests_dir: str) -> dict:
    """
    Ejecuta pytest -v sobre tests_dir y devuelve resultados por test_id.

    Args:
        tests_dir: Ruta al directorio con los tests generados (e.g. "tests_generados/").

    Returns:
        Dict con formato {test_id: {'status': str, 'traceback': str|None}}.
        'status' es 'passed', 'failed' o 'error'.
        Retorna {} si pytest no está instalado o el directorio no existe.
    """
    if importlib.util.find_spec("pytest") is None:
        print("[ERROR] pytest no está instalado. Ejecutá: pip install pytest")
        return {}

    tests_path = Path(tests_dir)
    if not tests_path.exists():
        print(f"[ERROR] El directorio de tests no existe: {tests_dir}")
        return {}

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", str(tests_path)],
        capture_output=True,
        text=True,
    )

    return _parse_output(result.stdout + result.stderr)


def _parse_output(output: str) -> dict:
    """
    Parsea el stdout de pytest -v y extrae resultados por test_id.

    El formato de una línea de resultado en pytest -v es:
      path/test_file.py::test_nombre STATUS
    donde STATUS es PASSED, FAILED o ERROR.

    También captura collection errors (ImportError, ModuleNotFoundError al
    importar el módulo de test), que pytest reporta como:
      ERROR path/test_file.py
    sin ::nombre de función. Estos se registran con el path del archivo como key.
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
    Captura bloques de error de colección (ERROR collecting path/file.py)
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

    pytest -v genera bloques con el patrón:
      _________________________ test_nombre _________________________
      ...traceback...
      ========================= short test summary ===================
    """
    # Captura: header _____func_____ seguido del cuerpo hasta el próximo separador
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
