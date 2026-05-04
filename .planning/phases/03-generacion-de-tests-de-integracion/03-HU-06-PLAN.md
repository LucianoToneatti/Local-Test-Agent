---
phase: 3
plan: HU-06
type: execute
wave: 1
depends_on: []
files_modified:
  - examples/estadistica.py
  - prompts/prompt_builder.py
  - agent/integration_generator.py
  - tests/test_integration_generator.py
  - context/marco_teorico_notas.md
autonomous: true
requirements:
  - INTG-01
  - INTG-02
  - INTG-03
---

<objective>
Implementar `agent/integration_generator.py` con la función pública `generate(repo_path, ast_result)`
que, dado el dict producido por `extract()`, identifica pares de módulos relacionados por imports
(INTG-01), genera un test de integración por par (INTG-02) y los escribe en
`tests_generados/integration/test_<stemA>_<stemB>.py` más un `conftest.py` con `sys.path`
configurado (INTG-03).

También requiere:
- `examples/estadistica.py`: módulo ejemplo que importa `sumar` y `multiplicar` de `calculadora.py`,
  validando los 3 criterios de éxito del roadmap para la Fase 3.
- `IntegrationPromptTemplate` en `prompts/prompt_builder.py`: nuevo template registrado en `_REGISTRY`
  con `language="python_integration"` que construye el prompt para un par de módulos.

El módulo sigue el mismo patrón de `agent/test_generator.py`: llama al LLM una vez por par,
valida con `ast.parse()`, reintenta una vez si falla, y escribe un comentario de error si ambos
intentos fallan.

Requisitos cubiertos: INTG-01, INTG-02, INTG-03.
</objective>

<threat_model>
**ASVS L1 — Análisis de amenazas para integration_generator.py**

| Amenaza | Severidad | Mitigación |
|---------|-----------|------------|
| LLM output con código malicioso en tests_generados/integration/ | Medium | El output se valida con `ast.parse()` antes de escribirse; código inválido (incluyendo ejecución de comandos) no llega al disco en forma ejecutable. Los tests generados son revisados manualmente antes de integrarlos a CI (Out of Scope per REQUIREMENTS.md). |
| Path traversal en `repo_path` o rutas de los módulos | Low | Los paths provienen del dict de `extract()` producido internamente por `explore()`; no hay input de usuario externo en este módulo. Los nombres de archivo de output se derivan de `Path.stem` de rutas ya validadas. |
| Escritura fuera de `tests_generados/integration/` | Low | Todos los writes usan `Path("tests_generados/integration") / f"test_{stem_a}_{stem_b}.py"` con paths construidos por el agente. |
| Exposición de ruta absoluta en conftest.py | Informational | El conftest escribe la ruta absoluta del repo analizado en `sys.path`. Comportamiento documentado y confirmado (D-07). |
| Código fuente del repositorio analizado enviado al LLM | Informational | El LLM es local (Ollama/DeepSeek) sin conexión a internet — el código fuente nunca sale del equipo. Confirmado por requisito "sin servicios en la nube". |

**Amenazas HIGH:** ninguna. Módulo local sin auth, sin DB, sin input de red.
</threat_model>

<tasks>

<task id="1">
  <title>Crear `examples/estadistica.py`</title>
  <read_first>
    - examples/calculadora.py (módulo B — funciones a usar: sumar, multiplicar)
    - .planning/phases/03-generacion-de-tests-de-integracion/03-CONTEXT.md (D-01, D-02 — diseño del archivo)
    - agent/ast_extractor.py (función _extract_repo_imports — cómo detecta imports: busca `from calculadora import ...`)
  </read_first>
  <action>
    Crear `examples/estadistica.py` con el siguiente contenido exacto. El import debe usar
    `from calculadora import sumar, multiplicar` para que `ast_extractor._extract_repo_imports()`
    lo detecte como un import del mismo repositorio (busca `calculadora.py` en `repo_files_set`).

    ```python
    from calculadora import sumar, multiplicar


    def promedio(lista):
        """Calcula el promedio de una lista de números usando calculadora.sumar."""
        if not lista:
            raise ValueError("La lista no puede estar vacía.")
        total = 0
        for x in lista:
            total = sumar(total, x)
        return total / len(lista)


    def varianza(lista):
        """Calcula la varianza usando calculadora.sumar y calculadora.multiplicar."""
        if not lista:
            raise ValueError("La lista no puede estar vacía.")
        prom = promedio(lista)
        total_sq_diff = 0
        for x in lista:
            diff = x - prom
            total_sq_diff = sumar(total_sq_diff, multiplicar(diff, diff))
        return total_sq_diff / len(lista)
    ```

    Verificar que el archivo importa correctamente corriendo:
    ```bash
    cd examples && python3 -c "from estadistica import promedio, varianza; print(promedio([1,2,3]), varianza([1,2,3]))"
    ```
    Resultado esperado: `2.0 0.6666...`
  </action>
  <acceptance_criteria>
    - `grep "from calculadora import" examples/estadistica.py` encuentra la línea de import (necesario para que INTG-01 funcione)
    - `grep "def promedio" examples/estadistica.py` y `grep "def varianza" examples/estadistica.py` confirman ambas funciones
    - `python3 -c "import sys; sys.path.insert(0,'examples'); from estadistica import promedio; assert promedio([1,2,3]) == 2.0; print('OK')"` exits 0
    - `python3 -c "import sys; sys.path.insert(0,'examples'); from estadistica import varianza; v = varianza([2,4,4,4,5,5,7,9]); print(f'{v:.4f}'); assert abs(v - 4.0) < 0.01; print('OK')"` exits 0
  </acceptance_criteria>
</task>

<task id="2">
  <title>Agregar `IntegrationPromptTemplate` a `prompts/prompt_builder.py`</title>
  <read_first>
    - prompts/prompt_builder.py (implementación completa — ver PromptTemplate, PythonPromptTemplate, _REGISTRY, BuiltPrompt)
    - .planning/phases/03-generacion-de-tests-de-integracion/03-CONTEXT.md (D-03, D-04, D-05, D-06 — diseño del template)
  </read_first>
  <action>
    Agregar la clase `IntegrationPromptTemplate` en `prompts/prompt_builder.py` DESPUÉS de
    `PythonPromptTemplate` y ANTES de `_REGISTRY`. Luego registrarla en `_REGISTRY`.

    **1. Nueva clase `IntegrationPromptTemplate`:**

    ```python
    class IntegrationPromptTemplate(PromptTemplate):
        """
        Template para generar tests de integración entre pares de módulos Python.

        Se llama una vez por par (A importa B). Pasa al LLM:
        (1) código fuente completo de A, (2) firmas de funciones de B, (3) nombres de módulos.
        """

        language = "python_integration"

        _SYSTEM = (
            "You are a Python integration test-writing machine. "
            "You output ONLY raw Python code. Nothing else.\n"
            "ABSOLUTE RULES — never break these:\n"
            "- NO markdown. Never use triple backticks (```) under any circumstances.\n"
            "- NO explanations, NO introductory sentences, NO comments outside the code.\n"
            "- Your entire response must be valid Python that can be saved directly to a .py file.\n"
            "- First line of your response must be an import statement.\n"
            "- Use pytest. Generate integration tests that call functions from module A "
            "(which internally uses module B). Assert with concrete expected values."
        )

        _USER_TEMPLATE = (
            "Write pytest integration tests for these two related Python modules.\n\n"
            "# Module A (the importer): {module_a_name}.py\n"
            "{module_a_source}\n\n"
            "# Module B function signatures (imported by A): {module_b_name}.py\n"
            "{module_b_sigs}\n\n"
            "Generate tests that:\n"
            "1. Import from {module_a_name}: 'from {module_a_name} import <function>'\n"
            "2. Call functions from {module_a_name} that internally use {module_b_name}\n"
            "3. Assert with concrete expected values "
            "(e.g., assert promedio([1, 2, 3]) == 2.0)\n\n"
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
            module_b_sigs: str = "",
        ) -> BuiltPrompt:
            user = self._USER_TEMPLATE.format(
                module_a_name=module_name or "module_a",
                module_a_source=code.strip(),
                module_b_name=class_name or "module_b",
                module_b_sigs=module_b_sigs or "(no signatures available)",
            )
            return BuiltPrompt(system=self._SYSTEM, user=user)
    ```

    **2. Actualizar `_REGISTRY`** para incluir el nuevo template:

    ```python
    _REGISTRY: dict[str, PromptTemplate] = {
        "python": PythonPromptTemplate(),
        "python_integration": IntegrationPromptTemplate(),
    }
    ```

    No modificar ningún otro método existente (`clean_response`, `PromptBuilder.build`,
    `PythonPromptTemplate`, `_extract_function_name`).
  </action>
  <acceptance_criteria>
    - `grep -n "class IntegrationPromptTemplate" prompts/prompt_builder.py` muestra la nueva clase
    - `grep -n "python_integration" prompts/prompt_builder.py` muestra al menos 2 ocurrencias (language attr y _REGISTRY)
    - `python3 -c "from prompts.prompt_builder import IntegrationPromptTemplate; t = IntegrationPromptTemplate(); p = t.build(code='def f(): pass', module_name='mod_a', class_name='mod_b', module_b_sigs='def g(): ...'); print('OK')"` exits 0
    - `python3 -c "from prompts.prompt_builder import PromptBuilder; p = PromptBuilder.build('def f(): pass'); print('OK')"` exits 0 (interfaz existente no rota)
    - `python3 -c "from prompts.prompt_builder import IntegrationPromptTemplate; t = IntegrationPromptTemplate(); p = t.build(code='x=1', module_name='estadistica', class_name='calculadora', module_b_sigs='def sumar(a, b): ...'); assert 'estadistica' in p.user; assert 'calculadora' in p.user; print('OK')"` exits 0
    - El system prompt contiene la instrucción "Assert with concrete expected values" para guiar al LLM
  </acceptance_criteria>
</task>

<task id="3">
  <title>Crear `agent/integration_generator.py`</title>
  <read_first>
    - agent/test_generator.py (patrón exacto a replicar: generate(), _write_conftest(), ast.parse() + 1 reintento)
    - agent/ast_extractor.py (estructura de imports en el dict: {rel_path: {functions, classes, imports: [otras_rel_paths]}})
    - prompts/prompt_builder.py (IntegrationPromptTemplate — después del Task 2)
    - agent/llm_client.py (interfaz LLMClient.generate(prompt, system) — no modificar)
    - .planning/phases/03-generacion-de-tests-de-integracion/03-CONTEXT.md (D-01 a D-08 — todas las decisiones)
    - CLAUDE.md (convenciones del stack)
  </read_first>
  <action>
    Crear `agent/integration_generator.py` con el siguiente diseño completo:

    ```python
    """
    Generador de tests de integración para repositorios Python.

    Recibe el dict producido por ast_extractor.extract(), detecta pares de módulos
    relacionados por imports, llama al LLM una vez por par, valida el output con
    ast.parse() y reintenta una vez si el código generado no es válido.
    """

    import ast
    from pathlib import Path
    from typing import Optional

    from agent.llm_client import LLMClient
    from prompts.prompt_builder import IntegrationPromptTemplate, clean_response

    OUTPUT_DIR = Path("tests_generados/integration")
    _TEMPLATE = IntegrationPromptTemplate()


    def generate(repo_path: str, ast_result: dict) -> None:
        """
        Genera tests de integración para todos los pares de módulos relacionados.

        Args:
            repo_path: Ruta al repositorio analizado (absoluta o relativa al cwd).
            ast_result: Dict producido por ast_extractor.extract().
                        Estructura: {rel_path: {functions, classes, imports}}
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        client = LLMClient()
        repo = Path(repo_path).resolve()

        pairs = _find_pairs(ast_result)
        for (a_path, b_path) in pairs:
            code = _generate_pair_test(client, repo, a_path, b_path, ast_result)
            stem_a = Path(a_path).stem
            stem_b = Path(b_path).stem
            out_file = OUTPUT_DIR / f"test_{stem_a}_{stem_b}.py"
            out_file.write_text(code + "\n")

        _write_conftest(repo)


    def _find_pairs(ast_result: dict) -> list[tuple[str, str]]:
        """
        Retorna la lista de pares (importer_path, imported_path) detectados por imports.

        Un par (A, B) se incluye cuando el campo `imports` de A contiene la ruta relativa de B
        y B está también presente como key en ast_result.
        """
        pairs = []
        for rel_path, file_info in ast_result.items():
            for imported in file_info.get("imports", []):
                if imported in ast_result:
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
    ```
  </action>
  <acceptance_criteria>
    - `grep -n "def generate" agent/integration_generator.py` encuentra la función pública
    - `grep -n "def _find_pairs" agent/integration_generator.py` encuentra la función interna
    - `grep -n "def _format_signatures" agent/integration_generator.py` encuentra la función de firmas
    - `grep -n "def _write_conftest" agent/integration_generator.py` encuentra la función de conftest
    - `python3 -c "from agent.integration_generator import generate; print('OK')"` exits 0
    - `grep -n "for attempt in range(2)" agent/integration_generator.py` confirma mecanismo de 1 reintento (D-08)
    - `grep -n "ast.parse(code)" agent/integration_generator.py` confirma validación de output (D-08)
    - `grep -n "# ERROR: no se pudo generar" agent/integration_generator.py` confirma fallback (D-08)
    - `grep -n "imports" agent/integration_generator.py` confirma que se usa el campo imports del ast_result (INTG-01)
    - `grep -n "sys.path.insert" agent/integration_generator.py` confirma conftest con sys.path (D-07)
  </acceptance_criteria>
</task>

<task id="4">
  <title>Crear `tests/test_integration_generator.py`</title>
  <read_first>
    - agent/integration_generator.py (módulo a testear — después del Task 3)
    - tests/test_test_generator.py (patrón de fixtures con mock de LLMClient)
    - tests/test_ast_extractor.py (patrón de ast_result mock)
    - .planning/phases/03-generacion-de-tests-de-integracion/03-CONTEXT.md (D-01 a D-08)
    - CLAUDE.md (tests del agente van en tests/, nunca en tests_generados/)
  </read_first>
  <action>
    Crear `tests/test_integration_generator.py`. Usar `unittest.mock.patch` para mockear
    `LLMClient.generate` y evitar llamadas reales a Ollama.

    ```python
    import ast
    import sys
    from pathlib import Path
    from unittest.mock import patch, MagicMock

    import pytest

    from agent.integration_generator import (
        generate,
        _find_pairs,
        _format_signatures,
        _generate_pair_test,
        _write_conftest,
        OUTPUT_DIR,
    )
    ```

    **Helper para construir ast_result de prueba:**
    ```python
    def _make_ast_result(files_and_imports):
        """
        files_and_imports: dict {rel_path: {'functions': [...], 'imports': [...]}}
        Cada función: {'name': str, 'params': list, '_lineno': int, '_end_lineno': int}
        """
        result = {}
        for path, info in files_and_imports.items():
            result[path] = {
                'functions': info.get('functions', []),
                'classes': [],
                'imports': info.get('imports', []),
            }
        return result
    ```

    **Tests de `_find_pairs`:**

    1. `test_find_pairs_single_import` — ast_result con A importando B: `_find_pairs` retorna `[('a.py', 'b.py')]`
    2. `test_find_pairs_no_imports` — ast_result sin imports: `_find_pairs` retorna `[]`
    3. `test_find_pairs_import_outside_repo` — A tiene un import que NO está en ast_result (import externo): par no incluido
    4. `test_find_pairs_mutual_imports` — A importa B y B importa A: retorna 2 pares

    **Tests de `_format_signatures`:**

    5. `test_format_signatures_basic` — file_info con 2 funciones (`sumar(a, b)`, `restar(a, b)`): resultado contiene "def sumar(a, b): ..." y "def restar(a, b): ..."
    6. `test_format_signatures_no_functions` — file_info sin functions: retorna string vacío
    7. `test_format_signatures_no_params` — función sin parámetros: retorna "def foo(): ..."

    **Tests de `_generate_pair_test` (con mock de LLMClient):**

    8. `test_generate_pair_valid_output` — mock devuelve código Python válido (`"import pytest\ndef test_integ(): assert True"`): resultado no empieza con `# ERROR`
    9. `test_generate_pair_invalid_then_valid` — mock devuelve primero código inválido y luego válido: resultado es el código válido (D-08: 1 reintento)
    10. `test_generate_pair_both_fail` — mock siempre devuelve código inválido: resultado empieza con `# ERROR: no se pudo generar test de integración para`
    11. `test_generate_pair_unreadable_source` — `a_path` no existe en repo: resultado empieza con `# ERROR: no se pudo leer`

    **Tests de `_write_conftest`:**

    12. `test_write_conftest_creates_file` — llama `_write_conftest(Path('/test/repo'))`, verifica que `tests_generados/integration/conftest.py` contiene `sys.path.insert(0, "/test/repo")`
    13. `test_write_conftest_contains_imports` — el conftest generado contiene `import sys` y `import pathlib`

    **Tests de `generate` (integración con mock, usando tmp_path):**

    14. `test_generate_creates_pair_file` — crea repo temporal con `estadistica.py` importando `calculadora.py`, mockea LLMClient para devolver código válido, llama `generate(tmp_repo, ast_result)`, verifica que `tests_generados/integration/test_estadistica_calculadora.py` fue creado
    15. `test_generate_creates_conftest` — igual que el anterior, verifica que `tests_generados/integration/conftest.py` fue creado
    16. `test_generate_no_pairs_no_output` — ast_result sin imports: `generate()` corre sin error y no crea archivos de tests (solo conftest)
    17. `test_generate_calls_llm_once_per_pair` — ast_result con 2 pares: mock de LLMClient llamado exactamente 2 veces
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_integration_generator.py -v` exits 0
    - Todos los 17 tests pasan (17 PASSED)
    - `grep -c "def test_" tests/test_integration_generator.py` imprime al menos 17
    - `grep "# ERROR" tests/test_integration_generator.py` confirma tests del fallback
    - `grep "_find_pairs" tests/test_integration_generator.py` confirma tests de detección de pares (INTG-01)
    - `grep "_format_signatures" tests/test_integration_generator.py` confirma tests de formato de firmas (D-03)
    - `grep "sys.path" tests/test_integration_generator.py` confirma test del conftest (D-07)
  </acceptance_criteria>
</task>

<task id="5">
  <title>Validar los 3 criterios de éxito del roadmap contra `examples/`</title>
  <read_first>
    - agent/integration_generator.py (módulo recién implementado)
    - examples/calculadora.py (módulo B — importado)
    - examples/estadistica.py (módulo A — importador, creado en Task 1)
    - .planning/ROADMAP.md §Fase 3 (3 criterios de éxito concretos)
  </read_first>
  <action>
    Ejecutar el generador de integración contra `examples/` y verificar los 3 criterios del roadmap.
    **IMPORTANTE:** Ollama debe estar corriendo con el modelo `deepseek-coder:6.7b` disponible.
    Si Ollama no está disponible, documentar el resultado esperado y continuar.

    **Paso 1 — Ejecutar el generador:**
    ```bash
    python3 -c "
    from agent.repo_explorer import explore
    from agent.ast_extractor import extract
    from agent.integration_generator import generate

    repo = 'examples'
    files = explore(repo)
    ast_result = extract(files, repo)
    print('Pares detectados:', [(k, v['imports']) for k, v in ast_result.items() if v['imports']])
    generate(repo, ast_result)
    print('Generación completada.')
    "
    ```

    **Criterio #1 — Identificación correcta de pares:**
    Verificar que el output del Paso 1 lista `estadistica.py` importando `calculadora.py`.
    La línea `Pares detectados:` debe mostrar `('estadistica.py', ['calculadora.py'])`.

    **Criterio #2 — Archivo de test por par:**
    ```bash
    python3 -c "
    from pathlib import Path
    f = Path('tests_generados/integration/test_estadistica_calculadora.py')
    assert f.exists(), f'No encontrado: {f}'
    content = f.read_text()
    assert len(content.strip()) > 0, 'Archivo vacío'
    print('Criterio #2 OK — archivo existe:', f)
    print(content[:300])
    "
    ```

    **Criterio #3 — Tests corren con pytest sin errores de importación:**
    ```bash
    python3 -m pytest tests_generados/integration/ --collect-only -q 2>&1 | head -20
    ```
    Verificar que no hay `ImportError` ni `ModuleNotFoundError` en la salida de colección.

    Si el LLM genera código con valores incorrectos (tests que fallan), documentar en output.
    El criterio de aceptación de este task es que pytest puede importar los tests —
    los failures de runtime se corrigen en Fase 4 (autocorrector).
  </action>
  <acceptance_criteria>
    - El script del Paso 1 exits 0 o devuelve `OllamaConnectionError` (ambos válidos — confirma que el módulo funciona)
    - `tests_generados/integration/test_estadistica_calculadora.py` existe después del Paso 1
    - `tests_generados/integration/conftest.py` contiene `sys.path.insert` con ruta al repo
    - `python3 -m pytest tests_generados/integration/ --collect-only` exits 0 (sin ImportError en colección)
    - `grep -n "estadistica" tests_generados/integration/test_estadistica_calculadora.py` encuentra referencias al módulo A (el test llama funciones de estadistica)
  </acceptance_criteria>
</task>

<task id="6">
  <title>Actualizar `context/marco_teorico_notas.md` con HU-06</title>
  <read_first>
    - context/marco_teorico_notas.md (ver formato de las secciones HU-01 a HU-05)
    - agent/integration_generator.py (módulo recién implementado)
    - prompts/prompt_builder.py (IntegrationPromptTemplate agregado en Task 2)
  </read_first>
  <action>
    Agregar una sección `### HU-06: Generador de Tests de Integración` al final de
    `context/marco_teorico_notas.md`:

    ```markdown
    ### HU-06: Generador de Tests de Integración

    - **Qué se hizo:** se creó `agent/integration_generator.py` con la función pública
      `generate(repo_path, ast_result)` que detecta pares de módulos relacionados por imports
      (campo `imports` del dict de `extract()`), llama al LLM una vez por par, valida el output
      con `ast.parse()` (1 reintento si falla), y escribe los tests en
      `tests_generados/integration/test_<stemA>_<stemB>.py` más un `conftest.py` con `sys.path`.
      Se agregó `IntegrationPromptTemplate` a `prompts/prompt_builder.py` con
      `language="python_integration"`, registrado en `_REGISTRY`.
      Se creó `examples/estadistica.py` como módulo de referencia que importa funciones de
      `calculadora.py` para validar los criterios de éxito de la Fase 3.

    - **Por qué LLM una vez por par (no por función de integración):**
      A diferencia de los tests unitarios (una llamada por función), los tests de integración
      deben validar la INTERACCIÓN entre módulos. Enviar el módulo A completo + las firmas de B
      le permite al LLM entender el flujo de datos entre los dos módulos y generar asserts
      significativos. Si llamáramos por función de A, perderíamos el contexto del módulo importado.

    - **Por qué solo firmas de B (no el código fuente completo):**
      Enviar el cuerpo completo de B junto con el de A puede exceder el contexto del modelo
      (DeepSeek Coder 6.7b tiene límite de ~4096 tokens). Las firmas (nombre + parámetros)
      son suficientes para que el LLM sepa cómo llamar las funciones de B y qué valores esperar.
      Esta decisión (D-03) balancea calidad de prompt vs. tamaño de contexto.

    - **Cómo funciona la detección de pares (INTG-01):**
      `_find_pairs()` itera el dict de `extract()` y para cada archivo busca en su campo `imports`
      (ya calculado por `ast_extractor._extract_repo_imports()`) las rutas de otros módulos del repo.
      Un par (A, B) se incluye solo si B también está como key en el dict — esto excluye imports
      externos (stdlib, pip). La detección es transitiva: si A→B y B→C, se generan pares (A,B)
      y (B,C) pero no (A,C) directamente (v1 solo pares directos, v2 puede agregar triplas).

    - **Por qué IntegrationPromptTemplate no usa PromptBuilder.build():**
      La firma de `PromptBuilder.build()` está diseñada para el caso unitario (función individual).
      El caso de integración requiere pasar 4 datos distintos (fuente de A, firmas de B, nombre A,
      nombre B). En lugar de sobrecargar la firma existente con kwargs opcionales, `integration_generator.py`
      instancia `IntegrationPromptTemplate` directamente. La clase sigue registrada en `_REGISTRY`
      para futura integración con `PromptBuilder.build()` vía kwargs o si se refactoriza la interfaz.

    - **Conceptos teóricos que aplican:** grafos de dependencias entre módulos (pares de imports),
      cobertura de integración vs. unitaria, context window budget en modelos pequeños,
      patrón de reintento acotado (mismo que HU-05), conftest.py por directorio en pytest.

    - **Deuda técnica / pendientes:** deduplicación de pares bidireccionales (A→B y B→A generan
      tests solapados — v2 QUAL-02), triplas de dependencia A→B→C (v2), template separado por tipo
      de interacción clase vs. función libre (v2 si se necesita).
    ```
  </action>
  <acceptance_criteria>
    - `grep "HU-06" context/marco_teorico_notas.md` encuentra la sección
    - `grep "_find_pairs" context/marco_teorico_notas.md` menciona la función de detección de pares
    - `grep "firmas" context/marco_teorico_notas.md` explica la decisión D-03 (solo firmas de B)
    - `grep "IntegrationPromptTemplate" context/marco_teorico_notas.md` menciona el template
  </acceptance_criteria>
</task>

<task id="7">
  <title>Verificar suite completa y commitear HU-06</title>
  <read_first>
    - agent/integration_generator.py
    - prompts/prompt_builder.py
    - tests/test_integration_generator.py
    - context/marco_teorico_notas.md
    - examples/estadistica.py
  </read_first>
  <action>
    Verificar que todos los tests del agente pasan, luego commitear HU-06:

    ```bash
    # Verificar suite completa del agente (NO tests_generados/)
    python3 -m pytest tests/ -v

    # Commitear HU-06
    git add \
      examples/estadistica.py \
      prompts/prompt_builder.py \
      agent/integration_generator.py \
      tests/test_integration_generator.py \
      context/marco_teorico_notas.md \
      tests_generados/integration/
    git commit -m "feat: HU-06 - Generador de tests de integración"
    ```

    El mensaje DEBE seguir el formato `feat: HU-0X - <descripción breve>` de CLAUDE.md.
    `tests_generados/integration/` se incluye porque contiene el output del agente para validación.
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/ -v` exits 0 antes del commit (todos los tests del agente pasan)
    - `git log --oneline -1` muestra `feat: HU-06 - Generador de tests de integración`
    - `git show --name-only HEAD` lista: examples/estadistica.py, prompts/prompt_builder.py, agent/integration_generator.py, tests/test_integration_generator.py, context/marco_teorico_notas.md
  </acceptance_criteria>
</task>

</tasks>

<verification>
Verificación completa de la Fase 3 al terminar HU-06:

```bash
# 1. Suite del agente completa
python3 -m pytest tests/ -v

# 2. Criterio de éxito #1: identificación correcta de pares
python3 -c "
from agent.repo_explorer import explore
from agent.ast_extractor import extract

repo = 'examples'
files = explore(repo)
ast_result = extract(files, repo)
pairs = [(k, v['imports']) for k, v in ast_result.items() if v['imports']]
print('Pares detectados:', pairs)
assert any('estadistica' in k for k, _ in pairs), 'estadistica.py no detectado como importador'
assert any('calculadora' in imp for _, imps in pairs for imp in imps), 'calculadora.py no detectado como importado'
print('Criterio #1 OK — pares de módulos identificados correctamente')
"

# 3. Criterio de éxito #2: archivo de test por par
python3 -c "
from pathlib import Path
f = Path('tests_generados/integration/test_estadistica_calculadora.py')
assert f.exists(), f'No encontrado: {f}'
print('Criterio #2 OK —', f)
"

# 4. Criterio de éxito #3: pytest sin errores de importación
python3 -m pytest tests_generados/integration/ --collect-only -q

# 5. Verificar commits
git log --oneline -5
```
</verification>

<must_haves>
<truths>
  - `generate(repo_path, ast_result)` es la única función pública de integration_generator.py
  - Los pares se detectan desde el campo `imports` del dict de ast_extractor.extract() — no se re-parsea el código (INTG-01)
  - El LLM se llama exactamente una vez por par de módulos (no por función individual) (INTG-02)
  - El prompt pasa el código fuente completo de A y solo las FIRMAS (nombre + params) de B, no el cuerpo de B (D-03)
  - Después de `clean_response()`, el output se valida con `ast.parse()` antes de escribir (D-08)
  - Si `ast.parse()` falla: se reintenta exactamente una vez; si falla dos veces: se escribe `# ERROR: no se pudo generar test de integración para <stemA>_<stemB>` (D-08)
  - `conftest.py` se escribe en `tests_generados/integration/` con la ruta absoluta del repo en `sys.path.insert(0, ...)` (D-07)
  - El archivo de output se llama `test_<stem_A>_<stem_B>.py` donde A es el importador y B el importado
  - Solo stdlib (`ast`, `pathlib`) más módulos del propio agente — sin dependencias pip (CLAUDE.md)
  - Los tests del agente van en `tests/`, nunca en `tests_generados/` (CLAUDE.md)
  - `IntegrationPromptTemplate` se registra en `_REGISTRY` con `language="python_integration"` (D-04)
  - `PromptBuilder.build()` y la interfaz de `PythonPromptTemplate` no se modifican (D-04)
</truths>
</must_haves>

<success_criteria>
1. `python3 -m pytest tests/test_integration_generator.py -v` — 17 tests PASSED, 0 failed
2. `python3 -m pytest tests/ -v` — suite completa del agente PASSED (incluyendo tests previos de HU-01..HU-05)
3. El agente identifica correctamente el par (estadistica.py, calculadora.py) en `examples/`
4. `tests_generados/integration/test_estadistica_calculadora.py` existe y no es un comentario de error
5. `python3 -m pytest tests_generados/integration/ --collect-only` exits 0 sin ImportError
6. `git log --oneline -1` muestra `feat: HU-06 - Generador de tests de integración`
</success_criteria>
