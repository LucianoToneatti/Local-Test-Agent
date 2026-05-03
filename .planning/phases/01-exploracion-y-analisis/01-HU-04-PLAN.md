---
phase: 1
plan: HU-04
type: execute
wave: 2
depends_on:
  - HU-03
files_modified:
  - agent/ast_extractor.py
  - tests/test_ast_extractor.py
  - context/marco_teorico_notas.md
autonomous: true
requirements:
  - ANLS-01
  - ANLS-02
  - ANLS-03
  - EXPL-03
---

<objective>
Implementar `agent/ast_extractor.py` con la función `extract(files, repo_path)` que analiza cada
archivo `.py` listado usando el módulo `ast` de stdlib. Para cada archivo produce un dict con las
funciones top-level, las clases (con sus métodos) y los imports de módulos del mismo repositorio.
Archivos de más de 200 líneas se fragmentan agrupando unidades sintácticas completas (funciones/clases)
sin cortar ninguna a la mitad. El dict unificado devuelto es el contrato que `test_generator.py`
(HU-05) consumirá directamente.
</objective>

<tasks>

<task id="1">
  <title>Crear agent/ast_extractor.py</title>
  <read_first>
    - agent/llm_client.py (patrón de módulo: docstring de módulo, constantes, clase/función pública)
    - .planning/phases/01-exploracion-y-analisis/01-CONTEXT.md (D-01 a D-08 — estructura de datos obligatoria)
    - examples/calculadora.py (archivo de referencia: 5 funciones top-level, sin clases, &lt;200 líneas)
    - CLAUDE.md (reglas del stack: solo stdlib, fragmentación &gt;200 líneas)
  </read_first>
  <action>
    Crear `agent/ast_extractor.py` con el siguiente diseño:

    **Constantes:**
    ```python
    FRAGMENT_THRESHOLD = 200  # líneas máximas por fragmento
    ```

    **Estructura de datos de retorno por archivo:**
    ```python
    # Para cada archivo en el dict resultado:
    {
      'path/to/file.py': {
        'functions': [
          {'name': 'func_name', 'type': 'function', 'params': ['a', 'b'], 'docstring': ''}
        ],
        'classes': [
          {
            'name': 'MyClass',
            'type': 'class',
            'docstring': '',
            'methods': [
              {'name': 'method', 'params': ['self', 'x'], 'docstring': ''}
            ]
          }
        ],
        'imports': ['pkg/other_module'],  # solo módulos del mismo repo, como rutas relativas
        # Opcional si parse falla:
        # 'parse_error': 'SyntaxError: ...'
      }
    }
    ```

    **Funciones a implementar:**

    ```python
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
        repo_files_set = set(files)  # para filtrar imports cruzados
        result = {}
        for rel_path in files:
            abs_path = root / rel_path
            result[rel_path] = _parse_file(abs_path, repo_files_set, root)
        return result
    ```

    **Función interna `_parse_file`:**
    - Lee el archivo con `read_text(encoding='utf-8')`
    - Hace `ast.parse(source)` con manejo de `SyntaxError` → devuelve `{'functions': [], 'classes': [], 'imports': [], 'parse_error': str(e)}`
    - Extrae imports de módulos del mismo repo con `_extract_repo_imports(tree, repo_files_set, root)`
    - Extrae funciones top-level con `_extract_functions(tree, source_lines)`
    - Extrae clases con `_extract_classes(tree, source_lines)`
    - Devuelve `{'functions': [...], 'classes': [...], 'imports': [...]}`

    **Función interna `_extract_functions(tree, source_lines) -> list[dict]`:**
    - Itera `tree.body` buscando nodos `ast.FunctionDef` y `ast.AsyncFunctionDef`
    - Para cada uno extrae:
      - `name`: `node.name`
      - `type`: `'function'`
      - `params`: lista de nombres de parámetros desde `node.args` (args + posonlyargs + kwonlyargs)
      - `docstring`: `ast.get_docstring(node) or ''`
    - Devuelve lista de dicts

    **Función interna `_extract_classes(tree, source_lines) -> list[dict]`:**
    - Itera `tree.body` buscando nodos `ast.ClassDef`
    - Para cada clase extrae:
      - `name`: `node.name`
      - `type`: `'class'`
      - `docstring`: `ast.get_docstring(node) or ''`
      - `methods`: lista de dicts de métodos (misma estructura que funciones, solo `ast.FunctionDef` dentro del cuerpo de la clase)
    - Devuelve lista de dicts

    **Función interna `_extract_repo_imports(tree, repo_files_set, root) -> list[str]`:**
    - Itera todos los nodos del AST buscando `ast.Import` y `ast.ImportFrom`
    - Para cada import, convierte el nombre del módulo a una ruta relativa potencial:
      - `import pkg.mod` → `pkg/mod.py`
      - `from pkg.sub import x` → `pkg/sub.py`
    - Si esa ruta relativa está en `repo_files_set`, la incluye en el resultado
    - Devuelve lista de rutas relativas (solo módulos del mismo repo)

    **Función `fragment(file_info: dict, source_lines: list[str]) -> list[dict]`:**
    - Toma el dict de un archivo y el código fuente como lista de líneas
    - Agrupa las funciones y clases en "fragmentos" donde cada fragmento tiene ≤ FRAGMENT_THRESHOLD líneas
    - Usa `node.lineno` y `node.end_lineno` (del AST) para calcular tamaños
    - Nunca parte una función/clase individual en dos fragmentos; si una unidad supera el umbral sola, forma su propio fragmento
    - Devuelve lista de dicts, cada uno con `{'functions': [...], 'classes': [...]}` (subconjunto del file_info)
    - Esta función es auxiliar para el generador de tests (HU-05); no se llama internamente en extract()

    Nota: el dict retornado por `extract()` NO incluye `fragments` — eso es responsabilidad del
    generador de tests en HU-05 cuando necesite enviar código al LLM en porciones.
    `fragment()` se exporta como utilidad pública.
  </action>
  <acceptance_criteria>
    - `grep -n "def extract" agent/ast_extractor.py` encuentra la función pública
    - `grep -n "def fragment" agent/ast_extractor.py` encuentra la función de fragmentación
    - `grep -n "FRAGMENT_THRESHOLD" agent/ast_extractor.py` encuentra la constante con valor 200
    - `python3 -c "from agent.ast_extractor import extract; print('OK')"` exits 0
    - Validar con calculadora.py:
      ```
      python3 -c "
      from agent.repo_explorer import explore
      from agent.ast_extractor import extract
      files = explore('examples')
      result = extract(files, 'examples')
      entry = result.get('calculadora.py', {})
      funcs = entry.get('functions', [])
      names = [f['name'] for f in funcs]
      assert 'sumar' in names, names
      assert 'dividir' in names, names
      assert len(funcs) == 5, len(funcs)
      print('ANLS-01/02 OK:', names)
      "
      ```
    - `grep -n "parse_error" agent/ast_extractor.py` confirma manejo de SyntaxError
    - `grep -n "repo_files_set" agent/ast_extractor.py` confirma filtrado de imports al mismo repo
    - `grep -n "ast.get_docstring" agent/ast_extractor.py` confirma extracción de docstrings
  </acceptance_criteria>
</task>

<task id="2">
  <title>Crear tests/test_ast_extractor.py</title>
  <read_first>
    - agent/ast_extractor.py (funciones a testear)
    - examples/calculadora.py (fixture real disponible)
    - .planning/phases/01-exploracion-y-analisis/01-CONTEXT.md (D-03 a D-08 — estructura esperada)
  </read_first>
  <action>
    Crear `tests/test_ast_extractor.py` con los siguientes tests. Usar `tmp_path` para repos
    temporales y código Python en strings para fixtures sintéticas.

    **Tests de extracción básica (ANLS-01, ANLS-02):**
    1. `test_extract_functions_from_calculadora` — extrae las 5 funciones de examples/calculadora.py,
       verifica nombres: sumar, restar, multiplicar, dividir, potencia
    2. `test_extract_function_params` — verifica que params de `sumar` son `['a', 'b']`
    3. `test_extract_function_docstring` — usa un archivo con docstring, verifica que se extrae
    4. `test_extract_class_with_methods` — archivo con clase que tiene métodos, verifica estructura
       `classes[0]['methods']` con nombre, params y docstring
    5. `test_extract_returns_empty_for_empty_file` — archivo .py vacío devuelve functions=[], classes=[], imports=[]
    6. `test_extract_syntax_error_handled` — archivo con SyntaxError no lanza excepción; devuelve parse_error

    **Tests de imports (EXPL-03):**
    7. `test_extract_same_repo_imports` — repo con mod_a.py que importa mod_b.py; verifica que
       imports de mod_a contiene 'mod_b.py' (o la ruta relativa correcta)
    8. `test_extract_stdlib_imports_excluded` — `import os, sys, pathlib` no aparece en imports
    9. `test_extract_third_party_imports_excluded` — `import requests, numpy` no aparece en imports

    **Tests de fragmentación (ANLS-03):**
    10. `test_fragment_small_file_returns_one_fragment` — archivo con 3 funciones cortas (total <200 líneas)
        → fragment() devuelve exactamente 1 fragmento
    11. `test_fragment_large_file_returns_multiple_fragments` — generar programáticamente un string
        con 20 funciones de 15 líneas cada una (300 líneas total) → fragment() devuelve ≥2 fragmentos
    12. `test_fragment_never_splits_single_large_function` — una función de 250 líneas forma su
        propio fragmento de 1 unidad aunque supere el umbral
    13. `test_fragment_each_fragment_parseable` — cada fragmento devuelto contiene funciones/clases
        completas (sus 'functions' y 'classes' son dicts válidos)

    Fixture helper sugerida:
    ```python
    def make_py_file(tmp_path, name, content):
        f = tmp_path / name
        f.write_text(content)
        return str(tmp_path), [name]  # repo_path, files
    ```
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_ast_extractor.py -v` exits 0
    - Todos los 13 tests pasan (13 PASSED)
    - `grep -c "def test_" tests/test_ast_extractor.py` imprime al menos 13
    - `grep "test_fragment_large_file" tests/test_ast_extractor.py` confirma test de fragmentación con archivo grande
    - `grep "parse_error" tests/test_ast_extractor.py` confirma test de manejo de errores de sintaxis
  </acceptance_criteria>
</task>

<task id="3">
  <title>Validar criterio de éxito #2 del roadmap (integración)</title>
  <read_first>
    - .planning/ROADMAP.md §Fase 1 criterios de éxito #1, #2, #3, #4
    - agent/repo_explorer.py
    - agent/ast_extractor.py
  </read_first>
  <action>
    Ejecutar los siguientes comandos de validación para confirmar los criterios de éxito del roadmap:

    **Criterio #1** — `examples/calculadora.py` aparece sin incluir dirs del sistema:
    ```bash
    python3 -c "
    from agent.repo_explorer import explore
    result = explore('.')
    # Solo interesa que calculadora.py aparece (como 'examples/calculadora.py')
    assert any('calculadora' in p for p in result), result
    assert not any('__pycache__' in p for p in result), result
    print('Criterio #1 OK')
    "
    ```

    **Criterio #2** — Dict con estructura correcta para calculadora.py:
    ```bash
    python3 -c "
    from agent.repo_explorer import explore
    from agent.ast_extractor import extract
    files = explore('examples')
    result = extract(files, 'examples')
    # La clave puede ser 'calculadora.py' (rutas relativas a 'examples')
    key = 'calculadora.py'
    assert key in result, list(result.keys())
    entry = result[key]
    funcs = entry['functions']
    names = [f['name'] for f in funcs]
    assert 'sumar' in names, names
    assert 'params' in funcs[0], funcs[0]
    print('Criterio #2 OK — estructura:', {k: len(v) for k, v in entry.items()})
    "
    ```

    **Criterio #3** — Fragmentación de archivo >200 líneas:
    ```bash
    python3 -c "
    import tempfile, os
    from agent.ast_extractor import extract, fragment

    # Generar archivo grande con 25 funciones de 10 líneas cada una = 250 líneas
    big_source = ''
    for i in range(25):
        big_source += f'def func_{i}(x):\n'
        for j in range(9):
            big_source += f'    # line {j}\n'
        big_source += f'    return x + {i}\n\n'

    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, 'big.py')
        with open(py_file, 'w') as f:
            f.write(big_source)

        result = extract(['big.py'], tmpdir)
        file_info = result['big.py']
        frags = fragment(file_info, big_source.splitlines())
        assert len(frags) > 1, f'Se esperaban múltiples fragmentos, se obtuvo: {len(frags)}'
        print(f'Criterio #3 OK — {len(frags)} fragmentos para archivo de 250 líneas')
    "
    ```

    Si alguno falla, corregir `ast_extractor.py` antes de continuar.
  </action>
  <acceptance_criteria>
    - Los tres scripts de validación de criterios del roadmap exits 0
    - Output de criterio #2 muestra `{'functions': 5, 'classes': 0, 'imports': 0}` o equivalente
    - Output de criterio #3 muestra ≥2 fragmentos
  </acceptance_criteria>
</task>

<task id="4">
  <title>Actualizar context/marco_teorico_notas.md con HU-04</title>
  <read_first>
    - context/marco_teorico_notas.md (ver formato de secciones HU-01, HU-02, HU-03)
    - agent/ast_extractor.py (módulo recién implementado)
  </read_first>
  <action>
    Agregar una sección `### HU-04: Extractor AST` al final de `context/marco_teorico_notas.md`:

    ```markdown
    ### HU-04: Extractor AST

    - **Qué se hizo:** se creó `agent/ast_extractor.py` con la función pública `extract(files, repo_path)`
      que analiza cada archivo `.py` usando el módulo `ast` de stdlib y devuelve un dict unificado
      `{ruta: {functions, classes, imports}}`. Incluye detección de imports cruzados entre módulos del
      mismo repositorio y la función `fragment()` para dividir archivos grandes en porciones ≤200 líneas
      sin cortar unidades sintácticas a la mitad.

    - **Por qué `ast` en lugar de regex o lectura de texto:**
      El módulo `ast` de Python stdlib convierte el código fuente en un Árbol de Sintaxis Abstracta (AST),
      una representación estructurada exacta de la gramática del lenguaje. A diferencia de regex, el AST
      entiende la jerarquía del código (qué es un cuerpo de clase, qué es un parámetro de función, qué
      es un decorador). `ast.parse()` lanza `SyntaxError` si el archivo tiene código inválido, lo que
      permite detectar y registrar errores de parsing sin abortar el flujo. `ast.get_docstring()` extrae
      la docstring limpia (sin comillas) de cualquier nodo con cuerpo.

    - **Cómo funciona la fragmentación inteligente:**
      Cada función y clase tiene `node.lineno` y `node.end_lineno` en el AST. La función `fragment()`
      agrupa las unidades en lotes usando un algoritmo greedy: agrega unidades al fragmento actual mientras
      la suma de líneas sea ≤ FRAGMENT_THRESHOLD (200). Si una unidad individual supera el umbral, forma
      su propio fragmento (garantía de nunca partir una unidad). Este mecanismo asegura que cada fragmento
      enviado al LLM sea autocontenido y parseable de forma independiente.

    - **Cómo se detectan los imports del mismo repositorio:**
      `_extract_repo_imports()` convierte los nombres de módulos importados (ej. `pkg.mod`) a rutas
      relativas (ej. `pkg/mod.py`) y verifica si esa ruta está en el conjunto de archivos conocidos del
      repositorio. Solo imports que existen en el repo quedan registrados; stdlib y third-party se filtran.

    - **Conceptos teóricos que aplican:** Árbol de Sintaxis Abstracta (AST), algoritmo greedy de
      particionado, patrón de diccionario unificado como contrato de datos entre módulos, manejo
      defensivo de errores de parsing.

    - **Deuda técnica / pendientes:** soporte para `async def` en métodos de clase (parcialmente cubierto),
      extracción de type hints de parámetros para prompts más ricos (v2), caché de resultados para repos
      grandes (v2 QUAL-01).
    ```
  </action>
  <acceptance_criteria>
    - `grep "HU-04" context/marco_teorico_notas.md` encuentra la sección
    - `grep "ast.parse" context/marco_teorico_notas.md` menciona el mecanismo central
    - `grep "fragment" context/marco_teorico_notas.md` explica la fragmentación
    - `grep "lineno" context/marco_teorico_notas.md` menciona el uso de atributos del AST
  </acceptance_criteria>
</task>

<task id="5">
  <title>Commit HU-04</title>
  <read_first>
    - agent/ast_extractor.py
    - tests/test_ast_extractor.py
    - context/marco_teorico_notas.md
  </read_first>
  <action>
    Verificar que todos los tests pasan, luego commitear:
    ```bash
    python3 -m pytest tests/ -v
    git add agent/ast_extractor.py tests/test_ast_extractor.py context/marco_teorico_notas.md
    git commit -m "feat: HU-04 - Extractor AST"
    ```
    El mensaje DEBE seguir el formato `feat: HU-0X - <descripción breve>` de CLAUDE.md.
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/ -v` exits 0 antes del commit (todos los tests pasan)
    - `git log --oneline -1` muestra `feat: HU-04 - Extractor AST`
    - `git show --name-only HEAD` lista ast_extractor.py, test_ast_extractor.py, marco_teorico_notas.md
  </acceptance_criteria>
</task>

</tasks>

<verification>
Verificación completa de la Fase 1 al terminar HU-04:

```bash
# 1. Todos los tests pasan
python3 -m pytest tests/ -v

# 2. Criterio de éxito #1: exploración sin dirs del sistema
python3 -c "
from agent.repo_explorer import explore
result = explore('.')
assert any('calculadora' in p for p in result)
assert not any('__pycache__' in p for p in result)
print('Criterio #1 OK:', [p for p in result if 'calculadora' in p])
"

# 3. Criterio de éxito #2: estructura de datos correcta
python3 -c "
from agent.repo_explorer import explore
from agent.ast_extractor import extract
files = explore('examples')
result = extract(files, 'examples')
key = 'calculadora.py'
assert key in result
entry = result[key]
assert len(entry['functions']) == 5
assert all('name' in f and 'params' in f and 'docstring' in f for f in entry['functions'])
print('Criterio #2 OK — funciones:', [f['name'] for f in entry['functions']])
"

# 4. Criterio de éxito #3: fragmentación
python3 -c "
import tempfile, os
from agent.ast_extractor import extract, fragment
big = '\n'.join(f'def f{i}(x):\n    return x+{i}\n' for i in range(100))
with tempfile.TemporaryDirectory() as d:
    open(f'{d}/big.py', 'w').write(big)
    info = extract(['big.py'], d)['big.py']
    frags = fragment(info, big.splitlines())
    assert len(frags) > 1, frags
    print(f'Criterio #3 OK — {len(frags)} fragmentos')
"

# 5. Verificar commits
git log --oneline -5
```
</verification>

<must_haves>
<truths>
  - extract() devuelve el dict exactamente con claves 'functions', 'classes', 'imports' por archivo
  - functions son funciones top-level (no métodos); classes tienen sub-lista 'methods'
  - imports contiene solo rutas de módulos del mismo repositorio (no stdlib, no third-party)
  - Archivos con SyntaxError devuelven parse_error en lugar de lanzar excepción
  - fragment() nunca parte una función o clase individual entre dos fragmentos
  - Cada fragmento retornado por fragment() es un dict con 'functions' y 'classes'
  - Sin dependencias externas: solo ast, os, pathlib de stdlib
</truths>
</must_haves>

<success_criteria>
1. `python3 -m pytest tests/test_ast_extractor.py` — 13 tests PASSED, 0 failed
2. La estructura retornada por extract('calculadora.py') tiene 5 functions con name, params, docstring, type
3. Archivo de 250+ líneas (con 25+ funciones) produce ≥2 fragmentos sin error
4. `git log --oneline -1` muestra `feat: HU-04 - Extractor AST`
5. `grep "HU-04" context/marco_teorico_notas.md` encuentra la sección de notas
</success_criteria>
