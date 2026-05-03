"""
Extractor AST para repositorios Python.

Analiza archivos .py con el módulo ast de stdlib y devuelve un dict unificado
con funciones top-level, clases (con sus métodos) e imports del mismo repo.
"""

import ast
import os
from pathlib import Path

FRAGMENT_THRESHOLD = 200  # líneas máximas por fragmento


def extract(files: list[str], repo_path: str) -> dict:
    """
    Extrae funciones, clases e imports de una lista de archivos .py.

    Args:
        files: Lista de rutas relativas al repo_path (output de explore()).
        repo_path: Directorio raíz del repositorio.

    Returns:
        Dict {ruta_relativa: {functions, classes, imports}} para cada archivo.
    """
    root = Path(repo_path).resolve()
    repo_files_set = set(files)
    result = {}
    for rel_path in files:
        abs_path = root / rel_path
        result[rel_path] = _parse_file(abs_path, repo_files_set, root)
    return result


def fragment(file_info: dict, source_lines: list[str]) -> list[dict]:
    """
    Divide el resultado de un archivo en fragmentos de ≤ FRAGMENT_THRESHOLD líneas.

    Nunca parte una función o clase individual entre dos fragmentos. Si una unidad
    supera el umbral sola, forma su propio fragmento.

    Args:
        file_info: Dict con claves 'functions' y 'classes' del resultado de extract().
        source_lines: Código fuente del archivo como lista de líneas.

    Returns:
        Lista de dicts, cada uno con 'functions' y 'classes' (subconjunto del file_info).
    """
    # Combinar funciones y clases, ordenar por línea de inicio
    units = []
    for func in file_info.get('functions', []):
        units.append(('function', func))
    for cls in file_info.get('classes', []):
        units.append(('class', cls))

    units.sort(key=lambda u: u[1].get('_lineno', 0))

    if not units:
        return [{'functions': [], 'classes': []}]

    # Calcular tamaños incluyendo líneas en blanco entre unidades (span hasta la siguiente)
    total_lines = len(source_lines)
    sizes = []
    for i, (_, unit) in enumerate(units):
        if i < len(units) - 1:
            next_start = units[i + 1][1].get('_lineno', 1)
            size = next_start - unit.get('_lineno', 1)
        else:
            size = total_lines - unit.get('_lineno', 1) + 1
        sizes.append(max(size, 1))

    fragments = []
    current_funcs = []
    current_classes = []
    current_size = 0

    for i, (unit_type, unit) in enumerate(units):
        size = sizes[i]
        if current_size + size > FRAGMENT_THRESHOLD and (current_funcs or current_classes):
            fragments.append({'functions': current_funcs, 'classes': current_classes})
            current_funcs = []
            current_classes = []
            current_size = 0

        if unit_type == 'function':
            current_funcs.append(unit)
        else:
            current_classes.append(unit)
        current_size += size

    if current_funcs or current_classes:
        fragments.append({'functions': current_funcs, 'classes': current_classes})

    return fragments if fragments else [{'functions': [], 'classes': []}]


def _parse_file(abs_path: Path, repo_files_set: set, root: Path) -> dict:
    try:
        source = abs_path.read_text(encoding='utf-8')
    except OSError as e:
        return {'functions': [], 'classes': [], 'imports': [], 'parse_error': str(e)}

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {'functions': [], 'classes': [], 'imports': [], 'parse_error': str(e)}

    source_lines = source.splitlines()
    imports = _extract_repo_imports(tree, repo_files_set, root)
    functions = _extract_functions(tree, source_lines)
    classes = _extract_classes(tree, source_lines)

    return {'functions': functions, 'classes': classes, 'imports': imports}


def _extract_functions(tree: ast.AST, source_lines: list[str]) -> list[dict]:
    result = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.append(_function_node_to_dict(node))
    return result


def _extract_classes(tree: ast.AST, source_lines: list[str]) -> list[dict]:
    result = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(_function_node_to_dict(item))
            result.append({
                'name': node.name,
                'type': 'class',
                'docstring': ast.get_docstring(node) or '',
                'methods': methods,
                '_lineno': node.lineno,
                '_end_lineno': getattr(node, 'end_lineno', node.lineno),
            })
    return result


def _function_node_to_dict(node) -> dict:
    params = (
        [arg.arg for arg in node.args.posonlyargs]
        + [arg.arg for arg in node.args.args]
        + [arg.arg for arg in node.args.kwonlyargs]
    )
    return {
        'name': node.name,
        'type': 'function',
        'params': params,
        'docstring': ast.get_docstring(node) or '',
        '_lineno': node.lineno,
        '_end_lineno': getattr(node, 'end_lineno', node.lineno),
    }


def _extract_repo_imports(tree: ast.AST, repo_files_set: set, root: Path) -> list[str]:
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                candidate = alias.name.replace('.', '/') + '.py'
                if candidate in repo_files_set:
                    result.append(candidate)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                candidate = node.module.replace('.', '/') + '.py'
                if candidate in repo_files_set:
                    result.append(candidate)
    return list(dict.fromkeys(result))  # deduplicate preserving order
