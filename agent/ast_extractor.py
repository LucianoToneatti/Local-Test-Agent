"""
Extractor AST/regex para repositorios Python, JavaScript/TypeScript y Java.

Para .py usa el módulo ast de stdlib. Para .js/.ts/.java usa regex dado que
no existe un parser de esos lenguajes en la stdlib de Python.

Devuelve en todos los casos un dict unificado con funciones top-level,
clases (con sus métodos) e imports del mismo repo.
"""

import ast
import re
import os
from pathlib import Path

FRAGMENT_THRESHOLD = 200  # líneas máximas por fragmento

_JS_EXTENSIONS = {'.js', '.ts', '.mjs'}
_JAVA_EXTENSIONS = {'.java'}

# ---------------------------------------------------------------------------
# Patrones regex para JS/TS
# ---------------------------------------------------------------------------

_JS_FUNC_DECL = re.compile(
    r'^[ \t]*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*\*?\s*'
    r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^)]*)\)',
    re.MULTILINE,
)

# const/let/var name = [async] (params) =>  o  name = param =>
_JS_ARROW = re.compile(
    r'^[ \t]*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*'
    r'=\s*(?:async\s+)?(?:\(([^)]*)\)|([a-zA-Z_$][a-zA-Z0-9_$]*))\s*=>',
    re.MULTILINE,
)

# const/let/var name = [async] function [name](
_JS_FUNC_EXPR = re.compile(
    r'^[ \t]*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*'
    r'=\s*(?:async\s+)?function\s*\*?\s*(?:[a-zA-Z_$][a-zA-Z0-9_$]*)?\s*\(',
    re.MULTILINE,
)

_JS_CLASS_DECL = re.compile(
    r'^[ \t]*(?:export\s+(?:default\s+)?)?class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)',
    re.MULTILINE,
)

# Métodos de clase: línea con indentación + [modificadores] + nombre(params)
_JS_METHOD = re.compile(
    r'^([ \t]+)'
    r'(?:(?:static|async|get|set|override|abstract|public|private|protected|readonly)\s+)*'
    r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^)]*)\)',
    re.MULTILINE,
)

_JS_IMPORT_PAT = re.compile(r"""(?:from|require)\s*\(?\s*['"](\.[^'"]+)['"]""")

_JS_CONTROL_KEYWORDS = {
    'if', 'for', 'while', 'switch', 'catch', 'return', 'throw', 'new',
    'typeof', 'instanceof', 'await', 'yield', 'delete', 'void', 'super',
    'class', 'import', 'export', 'from', 'const', 'let', 'var', 'function',
}

# ---------------------------------------------------------------------------
# Patrones regex para Java
# ---------------------------------------------------------------------------

_JAVA_CLASS_DECL = re.compile(
    r'^[ \t]*(?:(?:public|private|protected|abstract|final|static)\s+)*'
    r'class\s+([A-Za-z_$][A-Za-z0-9_$]*)',
    re.MULTILINE,
)

# Captura: [modificadores] [tipo_retorno] [nombreMétodo](
# El tipo de retorno debe ir seguido de espacio para distinguirlo del nombre.
_JAVA_METHOD_DECL = re.compile(
    r'^[ \t]+'
    r'(?:(?:public|private|protected|abstract|static|final|synchronized|native)\s+)*'
    r'(?:[A-Za-z_$][A-Za-z0-9_$]*(?:<[^>]*>)?(?:\[\])*\s+)'
    r'([A-Za-z_$][A-Za-z0-9_$]*)\s*\(',
    re.MULTILINE,
)

_JAVA_CONTROL_KEYWORDS = {
    'if', 'for', 'while', 'switch', 'catch', 'return', 'throw', 'new',
    'instanceof', 'assert', 'super', 'this', 'else',
}


def extract(files: list[str], repo_path: str) -> dict:
    """
    Extrae funciones, clases e imports de una lista de archivos .py/.js/.ts.

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
        suffix = Path(rel_path).suffix
        if suffix in _JS_EXTENSIONS:
            result[rel_path] = _parse_js_file(abs_path, repo_files_set, root)
        elif suffix in _JAVA_EXTENSIONS:
            result[rel_path] = _parse_java_file(abs_path)
        else:
            result[rel_path] = _parse_python_file(abs_path, repo_files_set, root)
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


def _parse_python_file(abs_path: Path, repo_files_set: set, root: Path) -> dict:
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


# ---------------------------------------------------------------------------
# Parser JS/TS (regex-based)
# ---------------------------------------------------------------------------

def _lineno_of(source: str, pos: int) -> int:
    return source.count('\n', 0, pos) + 1


def _find_js_end_lineno(lines: list[str], start_lineno: int) -> int:
    """Cuenta llaves para encontrar la línea de cierre de un bloque JS. 1-indexed."""
    depth = 0
    found_opening = False
    for i, line in enumerate(lines[start_lineno - 1:], start=start_lineno):
        depth += line.count('{') - line.count('}')
        if '{' in line:
            found_opening = True
        if found_opening and depth <= 0:
            return i
    return start_lineno  # arrow de una línea sin {}


def _parse_js_params(params_str: str) -> list[str]:
    if not params_str.strip():
        return []
    params = []
    for p in params_str.split(','):
        # Eliminar type annotations TS, valores default y destructuring
        name = p.strip().split(':')[0].split('=')[0].strip().lstrip('.')
        name = name.lstrip('{').lstrip('[')
        if name and re.match(r'^[a-zA-Z_$]', name):
            params.append(name)
    return params


def _extract_js_functions(source: str, lines: list[str], class_ranges: list[tuple]) -> list[dict]:
    """Extrae funciones top-level (excluye las que caen dentro de class bodies)."""
    result = []
    seen: set[int] = set()

    def in_class(lineno: int) -> bool:
        return any(s <= lineno <= e for s, e in class_ranges)

    for pattern in (_JS_FUNC_DECL, _JS_ARROW, _JS_FUNC_EXPR):
        for match in pattern.finditer(source):
            name = match.group(1)
            lineno = _lineno_of(source, match.start())
            if lineno in seen or in_class(lineno):
                continue
            seen.add(lineno)
            end_lineno = _find_js_end_lineno(lines, lineno)

            if pattern is _JS_FUNC_DECL:
                params_str = match.group(2) if match.lastindex >= 2 else ''
            elif pattern is _JS_ARROW:
                # grupo 2 = params entre paréntesis, grupo 3 = param sin paréntesis
                params_str = (match.group(2) or match.group(3)) if match.lastindex >= 2 else ''
            else:
                params_str = ''

            result.append({
                'name': name,
                'type': 'function',
                'params': _parse_js_params(params_str or ''),
                'docstring': '',
                '_lineno': lineno,
                '_end_lineno': end_lineno,
            })

    result.sort(key=lambda f: f['_lineno'])
    return result


def _extract_js_methods(class_source: str, class_lines: list[str], class_start: int) -> list[dict]:
    """Extrae métodos de un bloque de clase JS/TS."""
    methods = []
    seen: set[int] = set()

    for match in _JS_METHOD.finditer(class_source):
        name = match.group(2)
        if name in _JS_CONTROL_KEYWORDS:
            continue

        local_lineno = class_source.count('\n', 0, match.start()) + 1
        if local_lineno in seen:
            continue

        # Verificar que sea una definición (línea termina con { o siguiente con {)
        match_line = class_lines[local_lineno - 1] if local_lineno <= len(class_lines) else ''
        next_line = class_lines[local_lineno] if local_lineno < len(class_lines) else ''
        if '{' not in match_line and not next_line.strip().startswith('{'):
            continue

        seen.add(local_lineno)
        abs_lineno = class_start + local_lineno - 1
        end_lineno = _find_js_end_lineno(class_lines, local_lineno)
        abs_end_lineno = class_start + end_lineno - 1

        methods.append({
            'name': name,
            'type': 'function',
            'params': _parse_js_params(match.group(3)),
            'docstring': '',
            '_lineno': abs_lineno,
            '_end_lineno': abs_end_lineno,
        })

    return methods


def _extract_js_classes(source: str, lines: list[str]) -> list[dict]:
    result = []
    for match in _JS_CLASS_DECL.finditer(source):
        name = match.group(1)
        start_lineno = _lineno_of(source, match.start())
        end_lineno = _find_js_end_lineno(lines, start_lineno)
        class_lines = lines[start_lineno - 1:end_lineno]
        class_source = '\n'.join(class_lines)
        methods = _extract_js_methods(class_source, class_lines, start_lineno)
        result.append({
            'name': name,
            'type': 'class',
            'docstring': '',
            'methods': methods,
            '_lineno': start_lineno,
            '_end_lineno': end_lineno,
        })
    return result


def _extract_js_imports(source: str, abs_path: Path, repo_files_set: set, root: Path) -> list[str]:
    """Detecta imports relativos (./path) que apunten a archivos del mismo repo."""
    result = []
    current_dir = abs_path.parent

    for m in _JS_IMPORT_PAT.finditer(source):
        raw = m.group(1)
        resolved = (current_dir / raw).resolve()

        # Probar con la extensión que ya tiene, y también agregar .js / .ts
        candidates = [resolved]
        if resolved.suffix not in ('.js', '.ts', '.mjs'):
            for ext in ('.js', '.ts'):
                candidates.append(Path(str(resolved) + ext))
                candidates.append(resolved.with_suffix(ext))

        for candidate in candidates:
            try:
                rel = str(candidate.relative_to(root))
                if rel in repo_files_set and rel not in result:
                    result.append(rel)
                    break
            except ValueError:
                pass

    return result


def _parse_js_file(abs_path: Path, repo_files_set: set, root: Path) -> dict:
    try:
        source = abs_path.read_text(encoding='utf-8')
    except OSError as e:
        return {'functions': [], 'classes': [], 'imports': [], 'parse_error': str(e)}

    lines = source.splitlines()
    classes = _extract_js_classes(source, lines)
    class_ranges = [(cls['_lineno'], cls['_end_lineno']) for cls in classes]
    functions = _extract_js_functions(source, lines, class_ranges)
    imports = _extract_js_imports(source, abs_path, repo_files_set, root)

    return {'functions': functions, 'classes': classes, 'imports': imports}


# ---------------------------------------------------------------------------
# Parser Java (regex-based)
# ---------------------------------------------------------------------------

def _extract_java_methods(class_source: str, class_lines: list[str], class_start: int) -> list[dict]:
    """Extrae métodos de un bloque de clase Java usando conteo de llaves."""
    methods = []
    seen: set[int] = set()

    for match in _JAVA_METHOD_DECL.finditer(class_source):
        name = match.group(1)
        if name in _JAVA_CONTROL_KEYWORDS:
            continue

        local_lineno = class_source.count('\n', 0, match.start()) + 1
        if local_lineno in seen:
            continue

        match_line = class_lines[local_lineno - 1] if local_lineno <= len(class_lines) else ''
        next_line = class_lines[local_lineno] if local_lineno < len(class_lines) else ''
        if '{' not in match_line and not next_line.strip().startswith('{'):
            continue

        seen.add(local_lineno)
        abs_lineno = class_start + local_lineno - 1
        end_lineno = _find_js_end_lineno(class_lines, local_lineno)
        abs_end_lineno = class_start + end_lineno - 1

        methods.append({
            'name': name,
            'type': 'function',
            'params': [],
            'docstring': '',
            '_lineno': abs_lineno,
            '_end_lineno': abs_end_lineno,
        })

    return methods


def _extract_java_classes(source: str, lines: list[str]) -> list[dict]:
    result = []
    for match in _JAVA_CLASS_DECL.finditer(source):
        name = match.group(1)
        start_lineno = _lineno_of(source, match.start())
        end_lineno = _find_js_end_lineno(lines, start_lineno)
        class_lines = lines[start_lineno - 1:end_lineno]
        class_source = '\n'.join(class_lines)
        methods = _extract_java_methods(class_source, class_lines, start_lineno)
        result.append({
            'name': name,
            'type': 'class',
            'docstring': '',
            'methods': methods,
            '_lineno': start_lineno,
            '_end_lineno': end_lineno,
        })
    return result


def _parse_java_file(abs_path: Path) -> dict:
    try:
        source = abs_path.read_text(encoding='utf-8')
    except OSError as e:
        return {'functions': [], 'classes': [], 'imports': [], 'parse_error': str(e)}

    lines = source.splitlines()
    classes = _extract_java_classes(source, lines)
    return {'functions': [], 'classes': classes, 'imports': []}


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
