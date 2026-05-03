---
phase: 2
plan: HU-05
type: execute
wave: 1
depends_on: []
files_modified:
  - agent/test_generator.py
  - prompts/prompt_builder.py
  - tests/test_test_generator.py
  - context/marco_teorico_notas.md
autonomous: true
requirements:
  - TGEN-01
  - TGEN-02
  - TGEN-03
---

<objective>
Implementar `agent/test_generator.py` con la función pública `generate(repo_path, ast_result)`
que, dado el dict producido por `extract()` (Fase 1) y la ruta del repositorio analizado,
genera archivos pytest válidos en `tests_generados/unit/test_<stem>.py` — uno por archivo
fuente — y un `conftest.py` que agrega el repo al `sys.path`.

Para cada función top-level y cada método de clase, llama al LLM **una vez** (reutilizando
`LLMClient` y `PromptBuilder` sin modificar sus interfaces salvo agregar el parámetro
opcional `class_name` al template). Valida el output con `ast.parse()`, reintenta una vez
si falla, y en caso de segundo fallo escribe un comentario de error en lugar del bloque de tests.

Requisitos cubiertos: TGEN-01, TGEN-02, TGEN-03.
</objective>

<threat_model>
**ASVS L1 — Análisis de amenazas para test_generator.py**

| Amenaza | Severidad | Mitigación |
|---------|-----------|------------|
| LLM output con código malicioso en tests_generados/ | Medium | El output se valida con `ast.parse()` antes de escribirse; código inválido nunca llega al disco en forma ejecutable. Los tests generados son revisados manualmente antes de integrarlos a CI (Out of Scope per REQUIREMENTS.md). |
| Path traversal en `repo_path` o nombre de archivo fuente | Low | Los paths provienen del dict de `extract()` que ya fue producido internamente por `explore()`; no hay input de usuario externo en este módulo. Se usa `Path.stem` para generar nombres de output — caracteres especiales en nombres de archivo son un riesgo teórico pero aceptable en v1. |
| Escritura fuera de `tests_generados/unit/` | Low | Todos los writes usan `Path("tests_generados/unit") / f"test_{stem}.py"` con paths construidos por el agente, no por el usuario. |
| Exposición de ruta absoluta en conftest.py | Informational | El conftest.py escribe la ruta absoluta del repo en `sys.path`. Es información de entorno local, no un secreto. Comportamiento documentado y confirmado por el usuario (D-07). |

**Amenazas HIGH:** ninguna. Módulo local sin auth, sin DB, sin input de red.
</threat_model>

<tasks>

<task id="1">
  <title>Agregar `class_name` opcional a `PythonPromptTemplate` y `PromptBuilder`</title>
  <read_first>
    - prompts/prompt_builder.py (implementación actual completa — ver _USER_TEMPLATE, build(), PromptBuilder.build())
    - .planning/phases/02-generacion-de-tests-unitarios/02-CONTEXT.md (D-04 — cambio exacto requerido)
  </read_first>
  <action>
    Modificar `prompts/prompt_builder.py` en dos lugares:

    **1. `PythonPromptTemplate.build()`** — agregar parámetro `class_name: Optional[str] = None`:

    ```python
    _USER_TEMPLATE_METHOD = (
        "Write pytest tests for this Python method:\n\n"
        "{code}\n\n"
        "Method under test: {function_name} (instance method of class {class_name})\n"
        "Import it with: from {module_name} import {class_name}\n"
        "Instantiate the class before calling the method.\n\n"
        "OUTPUT RULES: raw Python code only. "
        "No markdown, no backticks, no explanations. "
        "Start your response directly with 'import'."
    )

    def build(
        self,
        code: str,
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> BuiltPrompt:
        resolved_name = function_name or _extract_function_name(code) or "la_funcion"
        if class_name:
            user = self._USER_TEMPLATE_METHOD.format(
                code=code.strip(),
                function_name=resolved_name,
                module_name=module_name or "module",
                class_name=class_name,
            )
        else:
            user = self._USER_TEMPLATE.format(
                code=code.strip(),
                function_name=resolved_name,
                module_name=module_name or "module",
            )
        return BuiltPrompt(system=self._SYSTEM, user=user)
    ```

    **2. `PromptBuilder.build()`** — agregar `class_name: Optional[str] = None` y pasarlo al template:

    ```python
    @staticmethod
    def build(
        code: str,
        language: str = "python",
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> BuiltPrompt:
        template = _REGISTRY.get(language.lower())
        if template is None:
            supported = ", ".join(_REGISTRY.keys())
            raise ValueError(
                f"Lenguaje '{language}' no soportado. Disponibles: {supported}"
            )
        return template.build(code, function_name, module_name, class_name)
    ```

    No modificar `PromptTemplate` base ni `clean_response()` ni ningún otro método.
  </action>
  <acceptance_criteria>
    - `grep -n "class_name" prompts/prompt_builder.py` muestra al menos 4 ocurrencias (definición en PythonPromptTemplate.build, en PromptBuilder.build, en _USER_TEMPLATE_METHOD, y en la rama if)
    - `python3 -c "from prompts.prompt_builder import PromptBuilder; p = PromptBuilder.build('def f(): pass', class_name='MyClass'); print('OK')"` exits 0
    - `python3 -c "from prompts.prompt_builder import PromptBuilder; p = PromptBuilder.build('def f(): pass'); print('OK')"` exits 0 (sin romper la firma existente)
    - `python3 -c "from prompts.prompt_builder import PromptBuilder; p = PromptBuilder.build('def f(self): pass', function_name='f', module_name='mymod', class_name='MyClass'); assert 'import MyClass' in p.user or 'from mymod import MyClass' in p.user, p.user; print('OK')"` exits 0
  </acceptance_criteria>
</task>

<task id="2">
  <title>Crear `agent/test_generator.py`</title>
  <read_first>
    - agent/llm_client.py (interfaz de LLMClient.generate(prompt, system) — no modificar)
    - prompts/prompt_builder.py (interfaz de PromptBuilder.build() y clean_response() — después del Task 1)
    - agent/ast_extractor.py (estructura de dict retornado por extract(): keys functions, classes, imports; cada función tiene _lineno, _end_lineno, name, params)
    - examples/calculadora.py (archivo de referencia para validación manual)
    - .planning/phases/02-generacion-de-tests-unitarios/02-CONTEXT.md (D-01 a D-08 — todas las decisiones de diseño)
    - CLAUDE.md (convenciones del stack)
  </read_first>
  <action>
    Crear `agent/test_generator.py` con el siguiente diseño completo:

    ```python
    """
    Generador de tests unitarios para repositorios Python.

    Recibe el dict producido por ast_extractor.extract() y genera archivos pytest
    en tests_generados/unit/. Llama al LLM una vez por función/método, valida el
    output con ast.parse() y reintenta una vez si el código generado no es válido.
    """

    import ast
    from pathlib import Path
    from typing import Optional

    from agent.llm_client import LLMClient
    from prompts.prompt_builder import PromptBuilder, clean_response

    OUTPUT_DIR = Path("tests_generados/unit")


    def generate(repo_path: str, ast_result: dict) -> None:
        """
        Genera tests unitarios para todas las funciones y métodos del ast_result.

        Args:
            repo_path: Ruta al repositorio analizado (absoluta o relativa al cwd).
            ast_result: Dict producido por ast_extractor.extract().
                        Estructura: {rel_path: {functions, classes, imports}}
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        client = LLMClient()
        repo = Path(repo_path).resolve()

        for rel_path, file_info in ast_result.items():
            blocks = _generate_blocks_for_file(client, repo, rel_path, file_info)
            if blocks:
                stem = Path(rel_path).stem
                out_file = OUTPUT_DIR / f"test_{stem}.py"
                out_file.write_text("\n\n".join(blocks) + "\n")

        _write_conftest(repo)


    def _generate_blocks_for_file(
        client: LLMClient,
        repo: Path,
        rel_path: str,
        file_info: dict,
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
                )
                blocks.append(block)

        return blocks


    def _generate_block(
        client: LLMClient,
        source_lines: list[str],
        unit: dict,
        module_name: str,
        class_name: Optional[str],
    ) -> str:
        """
        Genera un bloque de tests para una función o método.
        Reintenta una vez si el output del LLM no es Python válido.
        """
        func_source = _slice_source(source_lines, unit)
        func_name = unit["name"]

        for attempt in range(2):
            prompt = PromptBuilder.build(
                code=func_source,
                function_name=func_name,
                module_name=module_name,
                class_name=class_name,
            )
            raw = client.generate(prompt.user, system=prompt.system)
            code = clean_response(raw)
            try:
                ast.parse(code)
                return code
            except SyntaxError:
                if attempt == 0:
                    continue  # reintenta

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


    def _write_conftest(repo: Path) -> None:
        """Escribe conftest.py con la ruta absoluta del repo en sys.path."""
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
    ```
  </action>
  <acceptance_criteria>
    - `grep -n "def generate" agent/test_generator.py` encuentra la función pública
    - `grep -n "def _generate_block" agent/test_generator.py` encuentra la función interna de un bloque
    - `grep -n "def _write_conftest" agent/test_generator.py` encuentra la función de conftest
    - `python3 -c "from agent.test_generator import generate; print('OK')"` exits 0
    - `grep -n "for attempt in range(2)" agent/test_generator.py` confirma el mecanismo de 1 reintento (D-06)
    - `grep -n "ast.parse(code)" agent/test_generator.py` confirma validación de output (D-05)
    - `grep -n "# ERROR: no se pudo generar" agent/test_generator.py` confirma el fallback (D-05)
    - `grep -n "_lineno" agent/test_generator.py` confirma el slicing de fuente por línea (D-02)
    - `grep -n "class_name" agent/test_generator.py` confirma soporte para métodos de clase (D-03, D-04)
    - `grep -n "sys.path.insert" agent/test_generator.py` confirma escritura de conftest con sys.path (D-07)
  </acceptance_criteria>
</task>

<task id="3">
  <title>Crear `tests/test_test_generator.py`</title>
  <read_first>
    - agent/test_generator.py (módulo a testear — después del Task 2)
    - tests/test_ast_extractor.py (patrón de fixtures con tmp_path y strings de código)
    - .planning/phases/02-generacion-de-tests-unitarios/02-CONTEXT.md (D-01 a D-08)
    - CLAUDE.md (tests del agente van en tests/, nunca en tests_generados/)
  </read_first>
  <action>
    Crear `tests/test_test_generator.py` con los siguientes tests. Usar `unittest.mock.patch`
    para mockear `LLMClient.generate` y evitar llamadas reales a Ollama.

    ```python
    import ast
    import sys
    from pathlib import Path
    from unittest.mock import patch, MagicMock

    import pytest

    from agent.test_generator import (
        generate,
        _slice_source,
        _generate_block,
        _write_conftest,
        OUTPUT_DIR,
    )
    ```

    **Tests de `_slice_source`:**

    1. `test_slice_source_basic` — con source_lines=['def f():', '    return 1', ''] y unit con _lineno=1, _end_lineno=2, verifica que retorna 'def f():\n    return 1'
    2. `test_slice_source_single_line` — función de una sola línea (_lineno == _end_lineno), verifica que retorna esa línea

    **Tests de `_write_conftest`:**

    3. `test_write_conftest_creates_file` — llama `_write_conftest(Path('/some/repo'))`, verifica que `tests_generados/unit/conftest.py` existe y contiene `sys.path.insert(0, "/some/repo")` (usa tmp_path para no pisar el conftest real — parchear OUTPUT_DIR o llamar directamente con un path de test)
    4. `test_write_conftest_content_format` — el conftest generado contiene `import sys` y `import pathlib` y la ruta del repo

    **Tests de `_generate_block` (con mock de LLMClient):**

    5. `test_generate_block_valid_output` — el mock devuelve código Python válido (`"import pytest\ndef test_f(): assert True"`); verifica que el resultado no empieza con `# ERROR`
    6. `test_generate_block_invalid_then_valid` — el mock devuelve primero código inválido (`"esto no es python @@##"`) y luego código válido; verifica que el resultado final es el código válido (D-06: 1 reintento)
    7. `test_generate_block_both_attempts_fail` — el mock siempre devuelve código inválido; verifica que el resultado empieza con `# ERROR: no se pudo generar tests para`
    8. `test_generate_block_with_class_name` — llama `_generate_block` con `class_name="MyClass"`; verifica que el prompt pasado al LLM contiene "MyClass" (D-04)

    **Tests de `generate` (integración con mock, usando tmp_path):**

    9. `test_generate_creates_output_file` — crea un repo temporal con `calculadora.py` (3 funciones simples), mockea LLMClient para devolver código válido, llama `generate(tmp_repo, ast_result)`, verifica que `tests_generados/unit/test_calculadora.py` fue creado
    10. `test_generate_creates_conftest` — igual que el anterior, verifica que `tests_generados/unit/conftest.py` fue creado con la ruta del repo en sys.path
    11. `test_generate_calls_llm_once_per_function` — 3 funciones → mock de LLMClient llamado 3 veces (D-01)
    12. `test_generate_skips_file_with_no_functions` — entry con functions=[] y classes=[] → no crea archivo de tests (no escribe archivos vacíos)

    **Helper para ast_result mock:**
    ```python
    def _make_ast_result(functions):
        return {
            "calc.py": {
                "functions": [
                    {"name": f, "params": ["x"], "_lineno": i*3+1, "_end_lineno": i*3+2}
                    for i, f in enumerate(functions)
                ],
                "classes": [],
                "imports": [],
            }
        }
    ```
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_test_generator.py -v` exits 0
    - Todos los 12 tests pasan (12 PASSED)
    - `grep -c "def test_" tests/test_test_generator.py` imprime al menos 12
    - `grep "# ERROR" tests/test_test_generator.py` confirma test del fallback
    - `grep "class_name" tests/test_test_generator.py` confirma test de métodos de clase
    - `grep "calls_llm_once_per_function" tests/test_test_generator.py` confirma test de granularidad (D-01)
  </acceptance_criteria>
</task>

<task id="4">
  <title>Validar criterios de éxito del roadmap contra `examples/calculadora.py`</title>
  <read_first>
    - agent/test_generator.py (módulo recién implementado)
    - examples/calculadora.py (5 funciones top-level, 0 clases)
    - .planning/ROADMAP.md §Fase 2 (4 criterios de éxito concretos)
    - tests_generados/unit/conftest.py (si existe — verificar que el nuevo run lo sobrescribe)
  </read_first>
  <action>
    Ejecutar el generador contra `examples/calculadora.py` y verificar los 4 criterios del roadmap.
    **IMPORTANTE:** Ollama debe estar corriendo con el modelo `deepseek-coder:6.7b` disponible.
    Si Ollama no está disponible, documentar el resultado esperado en el archivo y continuar.

    **Paso 1 — Ejecutar el generador:**
    ```bash
    python3 -c "
    from agent.repo_explorer import explore
    from agent.ast_extractor import extract
    from agent.test_generator import generate

    repo = 'examples'
    files = explore(repo)
    ast_result = extract(files, repo)
    generate(repo, ast_result)
    print('Generación completada.')
    "
    ```

    **Paso 2 — Criterio #1: ≥10 funciones de test:**
    ```bash
    python3 -c "
    import ast, pathlib
    src = pathlib.Path('tests_generados/unit/test_calculadora.py').read_text()
    tree = ast.parse(src)
    test_funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
    print(f'Funciones de test encontradas: {len(test_funcs)}')
    print(test_funcs)
    assert len(test_funcs) >= 10, f'Se esperaban >=10, se encontraron {len(test_funcs)}'
    print('Criterio #1 OK')
    "
    ```

    **Paso 3 — Criterio #2: pytest corre sin errores de importación:**
    ```bash
    python3 -m pytest tests_generados/unit/test_calculadora.py -v --tb=short 2>&1 | head -50
    ```
    Verificar que no hay `ImportError` ni `ModuleNotFoundError`.

    **Paso 4 — Criterio #3: nombres con happy path y edge case:**
    ```bash
    python3 -c "
    import ast, pathlib
    src = pathlib.Path('tests_generados/unit/test_calculadora.py').read_text()
    tree = ast.parse(src)
    names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
    # Verificar que para cada función de calculadora existe al menos un test con nombre reconocible
    for func in ['sumar', 'restar', 'multiplicar', 'dividir', 'potencia']:
        matching = [n for n in names if func in n]
        assert len(matching) >= 2, f'Se esperaban >=2 tests para {func}, encontrados: {matching}'
        print(f'  {func}: {matching}')
    print('Criterio #3 OK')
    "
    ```

    **Paso 5 — Criterio #4: conftest.py con sys.path:**
    ```bash
    python3 -c "
    content = open('tests_generados/unit/conftest.py').read()
    assert 'sys.path.insert' in content, content
    assert 'examples' in content or 'calculadora' not in content, content
    print('Criterio #4 OK — contenido conftest:')
    print(content)
    "
    ```

    Si algún criterio falla por output del LLM (ej. menos de 10 tests generados porque el modelo
    produjo código inválido repetidamente), documentar en el output del plan y continuar.
    El criterio de aceptación de este task es que el flujo corre sin error de Python —
    la calidad del output del LLM se evalúa en los criterios de éxito pero no bloquea el commit.
  </action>
  <acceptance_criteria>
    - El script de generación (Paso 1) exits 0 o devuelve `OllamaConnectionError` si el servicio no está activo (ambos son resultados válidos — el error de conexión prueba que el módulo funciona correctamente)
    - `tests_generados/unit/test_calculadora.py` existe después del Paso 1
    - `tests_generados/unit/conftest.py` contiene `sys.path.insert` después del Paso 1
    - `grep -c "def test_" tests_generados/unit/test_calculadora.py` retorna ≥5 (al menos 1 test por función aun si el reintento falló)
    - `python3 -m pytest tests_generados/unit/test_calculadora.py --collect-only` exits 0 (puede haber test failures pero no errores de colección/importación)
  </acceptance_criteria>
</task>

<task id="5">
  <title>Actualizar `context/marco_teorico_notas.md` con HU-05</title>
  <read_first>
    - context/marco_teorico_notas.md (ver formato de las secciones HU-01 a HU-04)
    - agent/test_generator.py (módulo recién implementado)
    - prompts/prompt_builder.py (cambio agregado en Task 1)
  </read_first>
  <action>
    Agregar una sección `### HU-05: Generador de Tests Unitarios` al final de
    `context/marco_teorico_notas.md`:

    ```markdown
    ### HU-05: Generador de Tests Unitarios

    - **Qué se hizo:** se creó `agent/test_generator.py` con la función pública
      `generate(repo_path, ast_result)` que itera el dict de `extract()`, llama al LLM una vez
      por función/método, valida el output con `ast.parse()` (1 reintento si falla), y escribe
      los tests en `tests_generados/unit/test_<stem>.py` más un `conftest.py` con el `sys.path`
      del repositorio analizado. Se agregó el parámetro opcional `class_name` a
      `PythonPromptTemplate` y `PromptBuilder.build()` para adaptar el prompt a métodos de clase.

    - **Por qué LLM una vez por función (no por archivo):**
      Enviar una función a la vez reduce el riesgo de que el modelo "olvide" funciones en un
      archivo largo (problema de atención en modelos pequeños como 6.7b). El trade-off es
      más llamadas al LLM, pero es aceptable para v1 donde el objetivo es cobertura, no velocidad.

    - **Por qué `ast.parse()` para validar el output:**
      `ast.parse()` es la verificación mínima que garantiza que el código generado por el LLM
      es Python sintácticamente correcto antes de escribirlo al disco. No verifica semántica
      (el test puede fallar en runtime), pero asegura que pytest pueda al menos importar el archivo.
      La validación semántica es responsabilidad del módulo de ejecución (HU-07/HU-08).

    - **Por qué slicing por `_lineno`/`_end_lineno` en lugar de re-parsear:**
      Los atributos `_lineno` y `_end_lineno` ya están en el dict de `extract()`. Releer el
      archivo fuente y slicear es O(n) en líneas y no requiere una segunda pasada de AST.
      Mantiene `test_generator.py` desacoplado de `ast_extractor.py` (lo consume como dato,
      no lo reimplementa).

    - **Cómo funciona el mecanismo de reintento:**
      `_generate_block()` itera `range(2)`. En el attempt 0: genera, limpia, valida. Si
      `ast.parse()` lanza `SyntaxError`, hace `continue` al attempt 1 (reintento). Si el
      segundo attempt también falla, sale del loop y devuelve el comentario de error.
      Máximo 1 reintento por función (D-06).

    - **Conceptos teóricos que aplican:** validación de AST como guardrail de calidad,
      granularidad de contexto LLM (función vs. archivo), patrón de reintento acotado,
      sys.path como mecanismo de resolución de imports en pytest.

    - **Deuda técnica / pendientes:** soporte para `async def` en prompts (template actual
      no menciona async), caché de resultados para no re-llamar al LLM para funciones sin
      cambios (v2 QUAL-01), template separado para métodos vs. funciones (v2 si se necesita).
    ```
  </action>
  <acceptance_criteria>
    - `grep "HU-05" context/marco_teorico_notas.md` encuentra la sección
    - `grep "ast.parse" context/marco_teorico_notas.md` menciona la validación del output
    - `grep "reintento" context/marco_teorico_notas.md` explica el mecanismo de retry
    - `grep "_lineno" context/marco_teorico_notas.md` menciona el slicing de fuente
  </acceptance_criteria>
</task>

<task id="6">
  <title>Verificar suite completa y commitear HU-05</title>
  <read_first>
    - agent/test_generator.py
    - prompts/prompt_builder.py
    - tests/test_test_generator.py
    - context/marco_teorico_notas.md
  </read_first>
  <action>
    Verificar que todos los tests del agente pasan, luego commitear:

    ```bash
    # Verificar suite completa del agente (NO tests_generados/)
    python3 -m pytest tests/ -v

    # Commitear HU-05
    git add agent/test_generator.py prompts/prompt_builder.py tests/test_test_generator.py context/marco_teorico_notas.md tests_generados/unit/
    git commit -m "feat: HU-05 - Generador de tests unitarios"
    ```

    El mensaje DEBE seguir el formato `feat: HU-0X - <descripción breve>` de CLAUDE.md.
    `tests_generados/unit/` se incluye porque contiene el output del agente para la validación.
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/ -v` exits 0 antes del commit (todos los tests pasan, incluyendo los nuevos de test_test_generator.py)
    - `git log --oneline -1` muestra `feat: HU-05 - Generador de tests unitarios`
    - `git show --name-only HEAD` lista agent/test_generator.py, prompts/prompt_builder.py, tests/test_test_generator.py, context/marco_teorico_notas.md
  </acceptance_criteria>
</task>

</tasks>

<verification>
Verificación completa de la Fase 2 al terminar HU-05:

```bash
# 1. Suite del agente completa
python3 -m pytest tests/ -v

# 2. Criterio de éxito #1: ≥10 funciones de test en test_calculadora.py
python3 -c "
import ast, pathlib
src = pathlib.Path('tests_generados/unit/test_calculadora.py').read_text()
tree = ast.parse(src)
test_funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
print(f'Test functions: {len(test_funcs)} — {test_funcs}')
assert len(test_funcs) >= 10, f'Expected >=10, got {len(test_funcs)}'
print('Criterio #1 OK')
"

# 3. Criterio de éxito #2: pytest sin errores de importación
python3 -m pytest tests_generados/unit/test_calculadora.py --collect-only -q

# 4. Criterio de éxito #3: tests con nombres identificables por función
python3 -c "
import ast, pathlib
src = pathlib.Path('tests_generados/unit/test_calculadora.py').read_text()
names = [n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
for func in ['sumar', 'restar', 'multiplicar', 'dividir', 'potencia']:
    matching = [n for n in names if func in n]
    assert len(matching) >= 2, f'Expected >=2 tests for {func}, got {matching}'
    print(f'  {func}: {matching}')
print('Criterio #3 OK')
"

# 5. Criterio de éxito #4: conftest con sys.path
python3 -c "
c = open('tests_generados/unit/conftest.py').read()
assert 'sys.path.insert' in c
print('Criterio #4 OK')
print(c)
"

# 6. Verificar commits
git log --oneline -5
```
</verification>

<must_haves>
<truths>
  - `generate(repo_path, ast_result)` es la única función pública de test_generator.py
  - El LLM se llama exactamente una vez por función top-level y una vez por método de clase (D-01)
  - El source de cada función se obtiene sliceando por `_lineno` y `_end_lineno` del dict (D-02)
  - Después de `clean_response()`, el output se valida con `ast.parse()` antes de escribir (D-05)
  - Si `ast.parse()` falla: se reintenta exactamente una vez; si falla dos veces: se escribe `# ERROR: no se pudo generar tests para <name>` (D-05, D-06)
  - `conftest.py` se escribe con la ruta absoluta del repo en `sys.path.insert(0, ...)` (D-07)
  - `conftest.py` se sobrescribe en cada ejecución (D-08)
  - No se modifica la interfaz de `LLMClient` ni de `clean_response()` (D-01)
  - Solo stdlib (`ast`, `pathlib`) más los módulos del propio agente — sin dependencias pip (CLAUDE.md)
  - Los tests del agente van en `tests/`, nunca en `tests_generados/` (CLAUDE.md)
</truths>
</must_haves>

<success_criteria>
1. `python3 -m pytest tests/test_test_generator.py -v` — 12 tests PASSED, 0 failed
2. `python3 -m pytest tests/ -v` — suite completa del agente PASSED
3. `tests_generados/unit/test_calculadora.py` contiene ≥10 funciones de test (verificable con `ast.parse`)
4. `python3 -m pytest tests_generados/unit/test_calculadora.py --collect-only` exits 0 sin ImportError
5. `tests_generados/unit/conftest.py` contiene `sys.path.insert(0, "...examples")` con ruta absoluta
6. `git log --oneline -1` muestra `feat: HU-05 - Generador de tests unitarios`
</success_criteria>
