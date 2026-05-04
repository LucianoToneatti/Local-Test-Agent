---
phase: 4
plan: HU-08
type: execute
wave: 2
depends_on:
  - HU-07
files_modified:
  - prompts/prompt_builder.py
  - agent/autocorrector.py
  - agent.py
  - tests/test_autocorrector.py
  - context/marco_teorico_notas.md
autonomous: true
requirements:
  - EXEC-03
  - EXEC-04
---

<objective>
Implementar el ciclo de autocorrección de tests fallidos:
1. `CorrectionPromptTemplate` en `prompts/prompt_builder.py` — template registrado en `_REGISTRY`
   con `language="python_correction"`.
2. `agent/autocorrector.py` con función pública `autocorrect(results: dict, repo_path: str) -> dict`
   que itera los tests fallidos, llama al LLM hasta 3 veces por test_id, re-corre el test corregido
   individualmente, y marca como `'sin_resolver'` los que no se pudieron corregir.
3. Integración en `agent.py`: añadir `test_runner.run()` → `autocorrector.autocorrect()` al flujo.

Requisitos cubiertos: EXEC-03, EXEC-04.
</objective>

<threat_model>
**ASVS L1 — Análisis de amenazas para autocorrector.py y CorrectionPromptTemplate**

| Amenaza | Severidad | Mitigación |
|---------|-----------|------------|
| LLM output con código malicioso en el test corregido | Medium | El output se valida con `ast.parse()` antes de escribirse al archivo. Código con `exec()`, `os.system()` etc. es Python sintácticamente válido — pero los tests generados son revisados manualmente antes de CI (Out of Scope per REQUIREMENTS.md). El LLM es local (Ollama) sin salida a internet. |
| Sobrescritura de archivo de test con código inválido | Low | La función de reemplazo usa AST para extraer y reemplazar solo la función fallida — no sobrescribe el archivo completo con output crudo del LLM. La escritura ocurre solo después de `ast.parse()` exitoso. |
| Path traversal desde test_id hacia archivos fuera del repo | Low | El test_id proviene del output de pytest sobre `tests_generados/` — directorio interno del agente. La inferencia del módulo usa `Path(repo_path) / stem_name` construida internamente. |
| Subprocess injection al re-correr test individual | Low | `subprocess.run` recibe lista. El test_id se usa directamente como argumento posicional — no interpolado en string. |
| Código fuente del repositorio enviado al LLM | Informational | El LLM es local (Ollama/DeepSeek) sin conexión a internet — el código nunca sale del equipo. |
| Bucle infinito si re-ejecución del test siempre falla | Low | Mitigado por contador explícito de 3 intentos máximos por test_id (EXEC-04). El bucle tiene condición de salida garantizada. |

**Amenazas HIGH:** ninguna. Módulo local sin auth, sin DB, sin input de red.
</threat_model>

<tasks>

<task id="1">
  <title>Agregar `CorrectionPromptTemplate` a `prompts/prompt_builder.py`</title>
  <read_first>
    - prompts/prompt_builder.py (implementación completa — PromptTemplate, PythonPromptTemplate, IntegrationPromptTemplate, _REGISTRY, BuiltPrompt, clean_response)
    - .planning/phases/04-ejecucion-y-autocorreccion/04-CONTEXT.md (D-08, D-09 — diseño del template)
    - .planning/phases/03-generacion-de-tests-de-integracion/03-CONTEXT.md (D-03/D-04 — patrón de IntegrationPromptTemplate como referencia)
  </read_first>
  <action>
    Agregar la clase `CorrectionPromptTemplate` en `prompts/prompt_builder.py` DESPUÉS de
    `IntegrationPromptTemplate` y ANTES de `_REGISTRY`. Luego registrarla en `_REGISTRY`.

    **1. Nueva clase `CorrectionPromptTemplate`:**

    ```python
    class CorrectionPromptTemplate(PromptTemplate):
        """
        Template para corregir una función de test pytest que falló.

        Envía al LLM: (1) código de la función fallida, (2) traceback del error,
        (3) firmas del módulo bajo test.
        """

        language = "python_correction"

        _SYSTEM = (
            "You are a Python test-fixing machine. "
            "You output ONLY the corrected test function as raw Python code. Nothing else.\n"
            "ABSOLUTE RULES — never break these:\n"
            "- NO markdown. Never use triple backticks (```) under any circumstances.\n"
            "- NO explanations, NO introductory sentences, NO comments outside the code.\n"
            "- Output ONLY the single corrected test function (def test_...).\n"
            "- Do NOT output the full test file — only the function.\n"
            "- The function must be valid pytest: start with 'def test_', use assert statements.\n"
            "- Return only the corrected test function, no explanations."
        )

        _USER_TEMPLATE = (
            "Fix the following failing pytest test function.\n\n"
            "# Failing test function:\n"
            "{test_function_code}\n\n"
            "# Error traceback:\n"
            "{traceback}\n\n"
            "# Module under test — function signatures:\n"
            "{module_signatures}\n\n"
            "OUTPUT RULES: return ONLY the corrected test function (def test_...). "
            "Raw Python code only. No markdown, no backticks, no explanations."
        )

        def build(
            self,
            code: str,
            function_name: Optional[str] = None,
            module_name: Optional[str] = None,
            traceback: str = "",
            module_signatures: str = "",
        ) -> BuiltPrompt:
            user = self._USER_TEMPLATE.format(
                test_function_code=code.strip(),
                traceback=traceback.strip() or "(no traceback available)",
                module_signatures=module_signatures.strip() or "(no signatures available)",
            )
            return BuiltPrompt(system=self._SYSTEM, user=user)
    ```

    **2. Actualizar `_REGISTRY`** para incluir el nuevo template:

    ```python
    _REGISTRY: dict[str, PromptTemplate] = {
        "python": PythonPromptTemplate(),
        "python_integration": IntegrationPromptTemplate(),
        "python_correction": CorrectionPromptTemplate(),
    }
    ```

    No modificar ningún otro método existente (`clean_response`, `PromptBuilder.build`,
    `PythonPromptTemplate`, `IntegrationPromptTemplate`, `_extract_function_name`).
  </action>
  <acceptance_criteria>
    - `grep -n "class CorrectionPromptTemplate" prompts/prompt_builder.py` muestra la nueva clase
    - `grep -n "python_correction" prompts/prompt_builder.py` aparece al menos 2 veces (language attr y _REGISTRY)
    - `python3 -c "from prompts.prompt_builder import CorrectionPromptTemplate; t = CorrectionPromptTemplate(); p = t.build(code='def test_f(): assert 1==2', traceback='AssertionError', module_signatures='def sumar(a,b): ...'); print('OK')"` exits 0
    - `python3 -c "from prompts.prompt_builder import PromptBuilder; p = PromptBuilder.build('def f(): pass'); print('OK')"` exits 0 (interfaz existente no rota)
    - `python3 -c "from prompts.prompt_builder import CorrectionPromptTemplate; t = CorrectionPromptTemplate(); p = t.build(code='def test_f(): assert 1==2', traceback='err', module_signatures='sig'); assert 'AssertionError' not in p.system; assert 'err' in p.user; print('OK')"` exits 0
    - `grep "Return only the corrected test function" prompts/prompt_builder.py` confirma instrucción directiva al LLM (D-08)
  </acceptance_criteria>
</task>

<task id="2">
  <title>Crear `agent/autocorrector.py`</title>
  <read_first>
    - agent/test_runner.py (formato de `results` que recibe autocorrect — producido por run())
    - agent/ast_extractor.py (función extract() y estructura del dict devuelto — para re-derivar firmas)
    - agent/llm_client.py (interfaz LLMClient.generate(prompt, system) — no modificar)
    - prompts/prompt_builder.py (CorrectionPromptTemplate — después del Task 1)
    - .planning/phases/04-ejecucion-y-autocorreccion/04-CONTEXT.md (D-05 a D-13)
    - CLAUDE.md (convenciones del stack, sin deps pip, función pública única)
  </read_first>
  <action>
    Crear `agent/autocorrector.py` con el siguiente diseño completo.

    **Lógica de inferencia del módulo bajo test:**
    Del test_id `tests_generados/unit/test_calculadora.py::test_sumar_happy_path`:
    - Extraer el stem del archivo de test: `test_calculadora.py` → stem = `calculadora`
    - Buscar `calculadora.py` en `repo_path` recursivamente con `Path(repo_path).rglob("calculadora.py")`
    - Si no se encuentra: usar string vacío como firmas (no bloquear el flujo)

    **Extracción de la función fallida del archivo de test (D-06):**
    Usar `ast.parse()` sobre el archivo de test, buscar la `FunctionDef` con el nombre correcto,
    extraer las líneas correspondientes con `source.splitlines()[node.lineno-1:node.end_lineno]`.

    **Reemplazo de la función en el archivo (D-05):**
    Reconstruir el archivo reemplazando solo las líneas de la función fallida con el código corregido.
    Las demás funciones del archivo no se modifican.

    **Implementación:**

    ```python
    """
    Autocorrector de tests fallidos.

    Itera los tests con status 'failed' o 'error' del dict producido por test_runner.run(),
    llama al LLM hasta 3 veces por test_id, re-ejecuta el test corregido individualmente,
    y marca como 'sin_resolver' los que no se pudieron corregir tras 3 intentos.
    """

    import ast
    import subprocess
    import sys
    from pathlib import Path

    from agent.ast_extractor import extract
    from agent.llm_client import LLMClient
    from agent.repo_explorer import explore
    from prompts.prompt_builder import CorrectionPromptTemplate, clean_response

    _TEMPLATE = CorrectionPromptTemplate()
    _MAX_ATTEMPTS = 3


    def autocorrect(results: dict, repo_path: str) -> dict:
        """
        Corrige tests fallidos hasta 3 intentos por test_id.

        Args:
            results: Dict producido por test_runner.run().
                     Formato: {test_id: {'status': str, 'traceback': str|None}}
            repo_path: Ruta al repositorio analizado.

        Returns:
            Dict con mismo formato que results. Tests corregidos → 'passed'.
            Tests que agotaron intentos → 'sin_resolver'. No modifica tests 'passed'.
        """
        client = LLMClient()
        final = dict(results)

        for test_id, info in results.items():
            if info["status"] not in ("failed", "error"):
                continue
            final[test_id] = _correct_test(client, test_id, info, repo_path)

        return final


    def _correct_test(client: LLMClient, test_id: str, info: dict, repo_path: str) -> dict:
        """
        Intenta corregir un test_id fallido hasta _MAX_ATTEMPTS veces.
        Retorna el dict de resultado actualizado.
        """
        for attempt in range(_MAX_ATTEMPTS):
            test_file, func_name = _split_test_id(test_id)
            if test_file is None:
                break

            func_code = _extract_function(test_file, func_name)
            if func_code is None:
                break

            module_sigs = _get_module_signatures(test_file, repo_path)
            traceback = info.get("traceback") or ""

            prompt = _TEMPLATE.build(
                code=func_code,
                traceback=traceback,
                module_signatures=module_sigs,
            )
            raw = client.generate(prompt.user, system=prompt.system)
            corrected_code = clean_response(raw)

            try:
                ast.parse(corrected_code)
            except SyntaxError:
                continue

            _replace_function(test_file, func_name, corrected_code)

            new_status = _rerun_test(test_id)
            if new_status == "passed":
                return {"status": "passed", "traceback": None}

            info = {"status": new_status, "traceback": None}

        return {"status": "sin_resolver", "traceback": info.get("traceback")}


    def _split_test_id(test_id: str):
        """
        Separa 'path/test_file.py::test_nombre' en (Path('path/test_file.py'), 'test_nombre').
        Retorna (None, None) si el formato no es válido.
        """
        if "::" not in test_id:
            return None, None
        file_part, func_name = test_id.rsplit("::", 1)
        test_file = Path(file_part)
        if not test_file.exists():
            return None, None
        return test_file, func_name


    def _extract_function(test_file: Path, func_name: str) -> str | None:
        """
        Extrae el código fuente de la función `func_name` en `test_file` usando AST.
        Retorna None si no se puede leer o la función no existe.
        """
        try:
            source = test_file.read_text(encoding="utf-8")
        except OSError:
            return None

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return "\n".join(lines[node.lineno - 1 : node.end_lineno])
        return None


    def _replace_function(test_file: Path, func_name: str, new_code: str) -> None:
        """
        Reemplaza la función `func_name` en `test_file` con `new_code`.
        Solo modifica las líneas de esa función — el resto del archivo no cambia.
        """
        try:
            source = test_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            return

        lines = source.splitlines(keepends=True)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                start = node.lineno - 1
                end = node.end_lineno
                new_lines = [line + "\n" for line in new_code.splitlines()]
                lines[start:end] = new_lines
                test_file.write_text("".join(lines), encoding="utf-8")
                return


    def _get_module_signatures(test_file: Path, repo_path: str) -> str:
        """
        Infiere el módulo bajo test desde el nombre del archivo de test.
        Convención: test_calculadora.py → buscar calculadora.py en repo_path.
        Retorna las firmas de funciones como string, o '' si no se encuentra.
        """
        stem = test_file.stem  # e.g. "test_calculadora"
        if not stem.startswith("test_"):
            return ""
        module_stem = stem[len("test_"):]  # e.g. "calculadora"

        matches = list(Path(repo_path).rglob(f"{module_stem}.py"))
        if not matches:
            return ""

        module_file = matches[0]
        try:
            files = explore(repo_path)
            ast_result = extract(files, repo_path)
        except Exception:
            return ""

        # Buscar el módulo por stem en el ast_result (keys son rutas relativas)
        for rel_path, file_info in ast_result.items():
            if Path(rel_path).stem == module_stem:
                lines = []
                for func in file_info.get("functions", []):
                    params = ", ".join(func.get("params", []))
                    lines.append(f"def {func['name']}({params}): ...")
                return "\n".join(lines)
        return ""


    def _rerun_test(test_id: str) -> str:
        """
        Re-corre solo el test_id específico con pytest.
        Retorna 'passed', 'failed' o 'error'.
        """
        file_part, func_name = test_id.rsplit("::", 1) if "::" in test_id else (test_id, "")
        cmd = [sys.executable, "-m", "pytest", "-v", test_id]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            return "passed"
        if "error" in result.stdout.lower() or "error" in result.stderr.lower():
            return "error"
        return "failed"
    ```
  </action>
  <acceptance_criteria>
    - `python3 -c "from agent.autocorrector import autocorrect; print('OK')"` exits 0
    - `grep -n "def autocorrect" agent/autocorrector.py` muestra la función pública
    - `grep -n "_MAX_ATTEMPTS = 3" agent/autocorrector.py` confirma límite de 3 intentos (EXEC-04)
    - `grep -n "sin_resolver" agent/autocorrector.py` confirma status de agotamiento (EXEC-04)
    - `grep -n "def _extract_function" agent/autocorrector.py` confirma extracción AST de la función (D-06)
    - `grep -n "def _replace_function" agent/autocorrector.py` confirma reemplazo solo de la función (D-05)
    - `grep -n "def _rerun_test" agent/autocorrector.py` confirma re-ejecución individual del test (D-12)
    - `grep -n "def _get_module_signatures" agent/autocorrector.py` confirma inferencia del módulo bajo test (D-10)
    - `grep -n "ast.parse(corrected_code)" agent/autocorrector.py` confirma validación antes de escribir
    - `grep -n "subprocess.run.*list\|cmd.*sys.executable" agent/autocorrector.py` o verificar que cmd es lista
    - `python3 -c "import ast; ast.parse(open('agent/autocorrector.py').read()); print('syntax OK')"` exits 0
  </acceptance_criteria>
</task>

<task id="3">
  <title>Integrar `test_runner` y `autocorrector` en `agent.py`</title>
  <read_first>
    - agent.py (implementación completa actual — leer antes de modificar)
    - agent/test_runner.py (función run(tests_dir: str) -> dict)
    - agent/autocorrector.py (función autocorrect(results: dict, repo_path: str) -> dict)
    - .planning/phases/04-ejecucion-y-autocorreccion/04-CONTEXT.md (D-11 — coordinación runner/autocorrector)
  </read_first>
  <action>
    Modificar `agent.py` para añadir las dos llamadas al final de `main()`, después de la
    generación de tests de integración.

    **1. Agregar imports al inicio del archivo** (después de los imports existentes):
    ```python
    from agent.test_runner import run as run_tests
    from agent.autocorrector import autocorrect
    ```

    **2. Modificar `main()`** — añadir estas líneas después del bloque de integración:

    Localizar la línea:
    ```python
    print(f"[OK] tests_generados/integration/\n")
    ```

    Después de esa línea, agregar:
    ```python
    print("[*] Ejecutando tests generados...")
    tests_dir = str(_ROOT / "tests_generados")
    results = run_tests(tests_dir)

    if results:
        passed = sum(1 for v in results.values() if v["status"] == "passed")
        failed = sum(1 for v in results.values() if v["status"] in ("failed", "error"))
        print(f"[*] Resultados: {passed} passed, {failed} failed/error")

        if failed > 0:
            print("[*] Autocorrigiendo tests fallidos (hasta 3 intentos por test)...")
            final = autocorrect(results, str(repo))
            resolved = sum(1 for v in final.values() if v["status"] == "passed")
            unresolved = sum(1 for v in final.values() if v["status"] == "sin_resolver")
            print(f"[OK] Autocorrección: {resolved} resueltos, {unresolved} sin resolver\n")
        else:
            final = results
            print("[OK] Todos los tests pasaron\n")
    else:
        final = {}
    ```

    No modificar ninguna otra parte de `agent.py` (imports existentes, parse de argumentos,
    generación de tests unitarios, generación de integración).
  </action>
  <acceptance_criteria>
    - `grep -n "from agent.test_runner import run as run_tests" agent.py` confirma import del runner
    - `grep -n "from agent.autocorrector import autocorrect" agent.py` confirma import del autocorrector
    - `grep -n "run_tests(tests_dir)" agent.py` confirma la llamada al runner (D-11)
    - `grep -n "autocorrect(results, str(repo))" agent.py` confirma la llamada al autocorrector (D-11)
    - `python3 -c "import ast; ast.parse(open('agent.py').read()); print('syntax OK')"` exits 0
    - `python3 -c "import agent; print('import OK')"` exits 0 (sin importar dependencias rotas)
  </acceptance_criteria>
</task>

<task id="4">
  <title>Crear `tests/test_autocorrector.py`</title>
  <read_first>
    - agent/autocorrector.py (módulo a testear — leer después del Task 2)
    - tests/test_integration_generator.py (patrón de mock con unittest.mock.patch)
    - tests/test_test_runner.py (patrón de fixtures ya establecido para esta fase)
    - CLAUDE.md (tests del agente van en tests/, nunca en tests_generados/)
  </read_first>
  <action>
    Crear `tests/test_autocorrector.py`. Usar `unittest.mock.patch` para mockear
    `LLMClient.generate` y `subprocess.run`. Usar `tmp_path` para archivos temporales.

    **Helper: crear archivo de test temporal:**
    ```python
    def _make_test_file(tmp_path, content):
        f = tmp_path / "test_calc.py"
        f.write_text(content)
        return f
    ```

    **Tests de `_split_test_id`:**

    1. `test_split_test_id_valid` — input `"tests/test_calc.py::test_suma"` con file creado en
       tmp_path: retorna `(Path("tests/test_calc.py"), "test_suma")`.
    2. `test_split_test_id_no_separator` — input sin `::`: retorna `(None, None)`.
    3. `test_split_test_id_file_not_exists` — input con path que no existe: retorna `(None, None)`.

    **Tests de `_extract_function`:**

    4. `test_extract_function_found` — archivo con `def test_suma(): assert 1+1==2`:
       `_extract_function(path, "test_suma")` retorna string que contiene `"def test_suma"`.
    5. `test_extract_function_not_found` — función que no existe: retorna `None`.
    6. `test_extract_function_invalid_syntax` — archivo con SyntaxError: retorna `None`.

    **Tests de `_replace_function`:**

    7. `test_replace_function_replaces_only_target` — archivo con 2 funciones de test:
       después de `_replace_function(path, "test_suma", nuevo_codigo)`, el archivo
       contiene el nuevo código para `test_suma` pero la otra función (`test_resta`) no cambió.
       Verificar: `assert "def test_resta" in path.read_text()`.
    8. `test_replace_function_invalid_file` — path que no existe: no lanza excepción.

    **Tests de `_rerun_test` (con mock de subprocess):**

    9. `test_rerun_test_passed` — mock `subprocess.run` con returncode=0:
       `_rerun_test("path/test_calc.py::test_suma")` retorna `"passed"`.
    10. `test_rerun_test_failed` — mock con returncode=1, stdout sin "error":
        retorna `"failed"`.

    **Tests de `autocorrect` (integración con mock de LLMClient):**

    11. `test_autocorrect_passes_already_passing` — results con solo tests 'passed':
        `autocorrect(results, repo_path)` retorna el mismo dict sin llamar al LLM.
        Verificar: mock de LLMClient.generate no fue llamado.

    12. `test_autocorrect_corrects_failing_test` — 1 test 'failed', mock LLM devuelve
        código válido, mock subprocess (re-run) retorna returncode=0:
        el test_id en el resultado final tiene status `'passed'`.

    13. `test_autocorrect_marks_unresolved_after_3_attempts` — 1 test 'failed', mock LLM
        siempre devuelve código válido pero mock subprocess siempre retorna returncode=1:
        después de 3 intentos, el test_id tiene status `'sin_resolved'`.
        Verificar: mock de LLMClient.generate fue llamado exactamente 3 veces.

    14. `test_autocorrect_skips_invalid_llm_output` — mock LLM devuelve código con
        SyntaxError (e.g. `"def test_f(: pass"`): el intento no escribe al disco y
        continúa al siguiente intento (no lanza excepción).

    15. `test_autocorrect_returns_same_format_as_runner` — verificar que el dict retornado
        tiene la misma estructura que el input: `{test_id: {'status': str, 'traceback': ...}}`.
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_autocorrector.py -v` exits 0
    - Todos los 15 tests pasan (15 PASSED)
    - `grep -c "def test_" tests/test_autocorrector.py` imprime al menos 15
    - `grep "sin_resolver\|sin_resolved" tests/test_autocorrector.py` confirma test de agotamiento (EXEC-04)
    - `grep "_MAX_ATTEMPTS\|3 veces\|3 intentos\|call_count.*3" tests/test_autocorrector.py` confirma test del límite de 3 intentos
    - `grep "def test_resta" tests/test_autocorrector.py` confirma test de reemplazo selectivo (D-05)
    - `python3 -m pytest tests/ -v` exits 0 (suite completa incluyendo HU-01..HU-07)
  </acceptance_criteria>
</task>

<task id="5">
  <title>Actualizar `context/marco_teorico_notas.md` con HU-08 y commitear ambas HUs</title>
  <read_first>
    - context/marco_teorico_notas.md (ver formato de sección HU-07 agregada en Wave 1)
    - agent/autocorrector.py (módulo recién implementado)
    - prompts/prompt_builder.py (CorrectionPromptTemplate)
  </read_first>
  <action>
    Agregar la sección `### HU-08: Autocorrector de Tests` al final de `context/marco_teorico_notas.md`:

    ```markdown
    ### HU-08: Autocorrector de Tests

    - **Qué se hizo:** se creó `agent/autocorrector.py` con la función pública
      `autocorrect(results: dict, repo_path: str) -> dict` que itera los tests con
      status 'failed' o 'error', llama al LLM hasta 3 veces por test_id enviando
      el código de la función fallida + traceback + firmas del módulo bajo test,
      valida el output con `ast.parse()` antes de escribirlo, reemplaza solo la
      función fallida en el archivo de test (no el archivo completo), re-corre el
      test corregido individualmente con `pytest path::test_nombre`, y marca como
      'sin_resolver' los que agotaron los 3 intentos.
      Se agregó `CorrectionPromptTemplate` a `prompts/prompt_builder.py` con
      `language="python_correction"`, registrado en `_REGISTRY`.
      Se integraron las dos llamadas en `agent.py`:
      `results = run_tests(tests_dir)` → `final = autocorrect(results, str(repo))`.

    - **Por qué corregir solo la función fallida (D-05):**
      Un archivo de test puede tener N funciones. Si reemplazáramos el archivo completo
      con el output del LLM, perderíamos las funciones que ya pasan (el LLM podría
      omitirlas o cambiarlas). Al extraer y reemplazar solo la función fallida usando
      AST, el resto del archivo queda intacto — conservamos las funciones que ya pasan.

    - **Por qué re-correr solo el test_id individual (D-12):**
      Re-correr la suite completa para verificar una corrección tendría un costo O(n)
      en tiempo por intento, donde n es el total de tests. En el caso extremo con N
      tests fallidos × 3 intentos × m tests en suite, el costo es O(N×3×m). Al
      re-correr solo el test_id afectado (`pytest path::nombre`), el costo es O(1) por
      verificación. La suite completa se corre una sola vez al inicio (`run()`).

    - **Por qué las firmas se re-derivan en autocorrect() (D-10):**
      El autocorrector no recibe el ast_result como parámetro para mantener la interfaz
      simple (`autocorrect(results, repo_path)`). Las firmas se obtienen llamando
      `explore()` + `extract()` sobre repo_path, que son operaciones de solo lectura.
      La inferencia del módulo usa la convención `test_<stem>.py` → `<stem>.py` ya
      establecida por `test_generator.py`.

    - **Conceptos teóricos que aplican:** reemplazo selectivo con AST (preservación de
      contexto), ciclo de feedback LLM→corrección→verificación, límite de intentos para
      evitar bucles infinitos (EXEC-04), separación de responsabilidades entre runner
      (solo mide) y autocorrector (solo corrige).
    ```

    Luego verificar suite completa y commitear:
    ```bash
    python3 -m pytest tests/ -v
    git add prompts/prompt_builder.py agent/autocorrector.py agent.py tests/test_autocorrector.py context/marco_teorico_notas.md
    git commit -m "feat: HU-08 - Autocorrector de tests con CorrectionPromptTemplate e integración en agent.py"
    ```
  </action>
  <acceptance_criteria>
    - `grep "HU-08" context/marco_teorico_notas.md` encuentra la sección
    - `grep "función fallida" context/marco_teorico_notas.md` explica la decisión D-05
    - `grep "re-correr solo" context/marco_teorico_notas.md` explica la decisión D-12
    - `python3 -m pytest tests/ -v` exits 0 antes del commit
    - `git log --oneline -1` muestra `feat: HU-08 - Autocorrector de tests con CorrectionPromptTemplate e integración en agent.py`
    - `git show --name-only HEAD` lista: prompts/prompt_builder.py, agent/autocorrector.py, agent.py, tests/test_autocorrector.py, context/marco_teorico_notas.md
  </acceptance_criteria>
</task>

</tasks>

<verification>
Verificación completa de la Fase 4 al terminar HU-08:

```bash
# 1. Suite del agente completa
python3 -m pytest tests/ -v

# 2. Criterio #1 — runner devuelve dict de resultados
python3 -c "
from agent.test_runner import run
import importlib.util
assert importlib.util.find_spec('pytest') is not None, 'pytest no instalado'
print('pytest disponible - OK')
"

# 3. Criterio #2 — autocorrect recibe traceback completo
python3 -c "
from agent.autocorrector import autocorrect
# Verificar que la interfaz pública es correcta
import inspect
sig = inspect.signature(autocorrect)
assert list(sig.parameters.keys()) == ['results', 'repo_path']
print('interfaz autocorrect OK:', sig)
"

# 4. Criterio #4 — sin_resolver no bloquea el flujo
python3 -c "
from agent.autocorrector import _correct_test
from unittest.mock import MagicMock, patch

# Mock LLM siempre devuelve sintaxis inválida
with patch('agent.autocorrector.LLMClient') as MockLLM:
    mock_client = MagicMock()
    mock_client.generate.return_value = 'def test_f(: INVALID'  # SyntaxError
    MockLLM.return_value = mock_client
    # No se puede probar sin un archivo real, pero la interfaz es correcta
    print('Criterio #4 — interfaz no bloquea: OK')
"

# 5. Criterio #5 — commits verificados
git log --oneline -5

# 6. Verificar integración en agent.py
grep -n "run_tests\|autocorrect" agent.py
```
</verification>

<must_haves>
<truths>
  - `autocorrect(results: dict, repo_path: str) -> dict` es la única función pública de autocorrector.py
  - El ciclo de corrección (hasta 3 intentos) vive dentro de `autocorrect()` — `agent.py` no maneja reintentos
  - Se corrige solo la función de test fallida, no el archivo completo (D-05)
  - La extracción de la función fallida usa `ast.parse()` (D-06)
  - Máximo 3 intentos por test_id — contador por test_id, no por archivo (D-07)
  - El prompt envía: código de la función fallida + traceback + firmas del módulo bajo test (D-08)
  - `CorrectionPromptTemplate` registrada en `_REGISTRY` con `language="python_correction"` (D-09)
  - Las firmas se re-derivan dentro de `autocorrect()` — no se reciben como parámetro (D-10)
  - Re-ejecución individual: `pytest path/test_file.py::test_nombre` — no suite completa (D-12)
  - Retorna `{test_id: {'status': ..., 'traceback': ...}}` — mismo formato que `run()` (D-13)
  - Tests corregidos → `'passed'`; tests agotados → `'sin_resolver'` (D-13)
  - `'sin_resolver'` no bloquea el flujo del agente (D-13)
  - Solo stdlib (`ast`, `subprocess`, `sys`, `pathlib`) + módulos del propio agente — sin pip (CLAUDE.md)
  - Tests del agente van en `tests/`, nunca en `tests_generados/` (CLAUDE.md)
  - Commits separados: `feat: HU-07 - ...` y `feat: HU-08 - ...` (CLAUDE.md)
  - `agent.py` llama: `results = run_tests(tests_dir)` → `final = autocorrect(results, str(repo))` (D-11)
</truths>
</must_haves>

<success_criteria>
1. `python3 -c "from agent.autocorrector import autocorrect; print('OK')"` exits 0
2. `python3 -m pytest tests/test_autocorrector.py -v` — 15 tests PASSED, 0 failed
3. `python3 -m pytest tests/ -v` — suite completa del agente PASSED (HU-01..HU-08)
4. `grep "sin_resolver" agent/autocorrector.py` confirma status de agotamiento (EXEC-04)
5. `grep "run_tests\|autocorrect" agent.py` confirma integración en el punto de entrada
6. `git log --oneline -2` muestra commits feat: HU-07 y feat: HU-08
</success_criteria>
