---
phase: 4
plan: HU-07
type: execute
wave: 1
depends_on: []
files_modified:
  - agent/test_runner.py
  - tests/test_test_runner.py
  - context/marco_teorico_notas.md
autonomous: true
requirements:
  - EXEC-01
  - EXEC-02
---

<objective>
Implementar `agent/test_runner.py` con la función pública `run(tests_dir: str) -> dict` que:
1. Verifica que pytest esté instalado antes de continuar — si no está, imprime un mensaje claro y retorna dict vacío (nunca falla silenciosamente).
2. Ejecuta `pytest -v` sobre el directorio indicado como subproceso aislado.
3. Parsea el stdout para extraer el resultado por test_id (`path/archivo.py::nombre_funcion`).
4. Devuelve `{test_id: {'status': 'passed'|'failed'|'error', 'traceback': str|None}}`.

Requisitos cubiertos: EXEC-01, EXEC-02.
</objective>

<threat_model>
**ASVS L1 — Análisis de amenazas para test_runner.py**

| Amenaza | Severidad | Mitigación |
|---------|-----------|------------|
| Subprocess injection vía `tests_dir` | Medium | `subprocess.run` recibe lista (no string), por lo que no hay shell expansion. `tests_dir` es una ruta de directorio interna — no input de red ni usuario externo. |
| Output de pytest contiene rutas absolutas expuestas | Informational | Las rutas se usan solo localmente para armar el dict de resultados. No se persisten ni envían a red. |
| Ejecución de código arbitrario en tests importados por pytest | Low | pytest importa los tests generados por el propio agente. El executor ya confió en ese código al generarlo. |
| `tests_dir` inexistente provoca excepción no controlada | Low | Mitigado verificando existencia del directorio al inicio de `run()` y retornando dict vacío con mensaje. |
| pytest no instalado → falla críptica | Medium | **Mitigado explícitamente** — `run()` detecta la ausencia de pytest con `shutil.which('pytest')` o importlib y muestra `"[ERROR] pytest no está instalado. Ejecutá: pip install pytest"` antes de intentar subprocess. |

**Amenazas HIGH:** ninguna. Módulo local sin auth, sin DB, sin input de red.
</threat_model>

<tasks>

<task id="1">
  <title>Crear `agent/test_runner.py`</title>
  <read_first>
    - agent/test_generator.py (patrón de subprocess.run con sys.executable, validación, escritura)
    - agent/integration_generator.py (patrón general del módulo — función pública única, sin deps externas)
    - .planning/phases/04-ejecucion-y-autocorreccion/04-CONTEXT.md (D-01 a D-04 y Claude's Discretion)
    - CLAUDE.md (convenciones del stack, sin deps pip, función pública única)
  </read_first>
  <action>
    Crear `agent/test_runner.py` con el siguiente diseño completo.

    **Detección de pytest (obligatoria, inicio de `run()`):**
    Usar `importlib.util.find_spec("pytest")` para detectar si pytest está instalado.
    Si no está: imprimir `"[ERROR] pytest no está instalado. Ejecutá: pip install pytest"` y retornar `{}`.

    **Parseo del stdout de pytest -v:**
    - Líneas con ` PASSED` → status `'passed'`, traceback `None`
    - Líneas con ` FAILED` → status `'failed'`, capturar traceback (ver abajo)
    - Líneas con ` ERROR` → status `'error'`, capturar traceback (ver abajo)
    - El test_id es todo lo que precede al espacio antes de PASSED/FAILED/ERROR en esa línea.
      Ejemplo: `tests_generados/unit/test_calculadora.py::test_sumar_happy_path PASSED`
      → test_id = `tests_generados/unit/test_calculadora.py::test_sumar_happy_path`
    - Traceback: todo el texto entre la línea `FAILED path::nombre` (o la sección `=== FAILURES ===`)
      y la siguiente línea de separación (`===` o `---`). En la práctica, el traceback completo
      de pytest -v aparece en el bloque `FAILURES` al final del output. Estrategia simple:
      buscar el bloque que empieza con `_ test_nombre _` o `FAILED` + acumular hasta el próximo `===`.

    **Implementación:**

    ```python
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
        """
        results = {}

        # Extraer líneas de resultado: "ruta::test_nombre PASSED/FAILED/ERROR"
        line_re = re.compile(
            r"^([\w/\\.:-]+::\w+)\s+(PASSED|FAILED|ERROR)", re.MULTILINE
        )
        for match in line_re.finditer(output):
            test_id = match.group(1)
            status = match.group(2).lower()
            results[test_id] = {"status": status, "traceback": None}

        # Extraer tracebacks del bloque FAILURES/ERRORS
        _attach_tracebacks(output, results)

        return results


    def _attach_tracebacks(output: str, results: dict) -> None:
        """
        Busca los bloques de traceback en el output de pytest y los asigna
        al test_id correspondiente en el dict results (modifica in-place).

        pytest -v genera bloques con el patrón:
          _________________________ test_nombre _________________________
          ...traceback...
          ========================= short test summary ===================
        """
        # Dividir por líneas de separación "____" que encabezan cada failure
        block_re = re.compile(r"_{5,}\s+([\w]+)\s+_{5,}")
        sep_re = re.compile(r"^[=_]{5,}", re.MULTILINE)

        segments = sep_re.split(output)
        for segment in segments:
            header = block_re.search(segment)
            if not header:
                continue
            func_name = header.group(1)
            # Buscar el test_id que termina con este nombre de función
            for test_id in results:
                if test_id.endswith(f"::{func_name}"):
                    results[test_id]["traceback"] = segment.strip()
                    break
    ```

    No agregar código fuera de las funciones definidas arriba.
    No importar nada que no esté en stdlib.
  </action>
  <acceptance_criteria>
    - `python3 -c "from agent.test_runner import run; print('OK')"` exits 0
    - `grep -n "def run" agent/test_runner.py` muestra la función pública
    - `grep -n "find_spec" agent/test_runner.py` confirma detección de pytest instalado
    - `grep -n "pip install pytest" agent/test_runner.py` confirma el mensaje de error claro
    - `grep -n "def _parse_output" agent/test_runner.py` confirma función de parseo
    - `grep -n "def _attach_tracebacks" agent/test_runner.py` confirma extracción de tracebacks
    - `grep -n "capture_output=True" agent/test_runner.py` confirma captura de stdout/stderr (EXEC-01)
    - `grep -n "'status'" agent/test_runner.py` confirma registro de status por test_id (EXEC-02)
    - `grep -n "subprocess.run" agent/test_runner.py` usa lista (no string) — evita shell injection
    - `python3 -c "import ast; ast.parse(open('agent/test_runner.py').read()); print('syntax OK')"` exits 0
  </acceptance_criteria>
</task>

<task id="2">
  <title>Crear `tests/test_test_runner.py`</title>
  <read_first>
    - agent/test_runner.py (módulo a testear — leer después del Task 1)
    - tests/test_integration_generator.py (patrón de mock con unittest.mock.patch)
    - tests/test_test_generator.py (patrón de fixtures con MagicMock)
    - CLAUDE.md (tests del agente van en tests/, nunca en tests_generados/)
  </read_first>
  <action>
    Crear `tests/test_test_runner.py`. Usar `unittest.mock.patch` para mockear
    `subprocess.run` y `importlib.util.find_spec`. No hacer llamadas reales a pytest.

    **Tests de `run()` — detección de pytest no instalado:**

    1. `test_run_pytest_not_installed` — mockear `find_spec` para retornar `None`:
       `run("tests_generados/")` retorna `{}` y la llamada imprime el mensaje de error.
       Usar `capsys.readouterr()` para capturar stdout y verificar que contiene
       `"pip install pytest"`.

    **Tests de `run()` — directorio inexistente:**

    2. `test_run_directory_not_found` — con pytest instalado (find_spec retorna mock no-None)
       pero `tests_dir` = `"nonexistent_dir_xyz"`: retorna `{}` y stdout contiene `"no existe"`.

    **Tests de `_parse_output()` — parseo de resultados:**

    3. `test_parse_output_all_passed` — input con 2 líneas PASSED:
       ```
       tests_generados/unit/test_calc.py::test_sumar PASSED
       tests_generados/unit/test_calc.py::test_restar PASSED
       ```
       Resultado: 2 test_ids con status `'passed'` y traceback `None`.

    4. `test_parse_output_mixed_results` — input con PASSED, FAILED, ERROR:
       resultado contiene los 3 test_ids con los status correctos.

    5. `test_parse_output_empty_output` — input vacío: retorna `{}`.

    6. `test_parse_output_failed_has_none_traceback_by_default` — línea FAILED sin bloque
       de traceback en el output: el test_id tiene `traceback=None` (no string vacío).
       Verificar: `assert result[test_id]['traceback'] is None`.

    **Tests de `_attach_tracebacks()` — extracción de tracebacks:**

    7. `test_attach_tracebacks_assigns_to_correct_test` — output con bloque
       `_____ test_sumar _____\nAssertionError: assert 1 == 2`:
       después de `_attach_tracebacks`, el test_id que termina en `::test_sumar`
       tiene un traceback no-None que contiene `"AssertionError"`.

    8. `test_attach_tracebacks_no_failure_block` — output sin bloques `_____`:
       no modifica el dict (tracebacks siguen None).

    **Tests de `run()` — integración con subprocess mockeado:**

    9. `test_run_returns_passed_dict` — mockear `subprocess.run` para retornar
       stdout con 1 línea PASSED:
       `"tests_generados/unit/test_calc.py::test_suma PASSED\n"`.
       Verificar que `run("tests_generados/")` retorna
       `{"tests_generados/unit/test_calc.py::test_suma": {"status": "passed", "traceback": None}}`.

    10. `test_run_returns_failed_dict` — mockear subprocess para retornar FAILED.
        Verificar que result tiene status `'failed'`.

    11. `test_run_subprocess_called_with_list` — verificar que `subprocess.run` fue llamado
        con el primer argumento siendo una lista (no un string) — previene shell injection.
        `assert isinstance(call_args[0][0], list)`.

    12. `test_run_captures_stderr` — mockear subprocess para retornar stderr con info de error.
        Verificar que `run()` no lanza excepción (stderr se captura, no propaga).

    Estructura de tests usando tmp_path fixture de pytest para el directorio:
    ```python
    def test_run_returns_passed_dict(tmp_path, monkeypatch):
        import importlib.util
        monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
        # ... mock subprocess.run ...
    ```
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_test_runner.py -v` exits 0
    - Todos los 12 tests pasan (12 PASSED)
    - `grep -c "def test_" tests/test_test_runner.py` imprime al menos 12
    - `grep "pip install pytest" tests/test_test_runner.py` confirma test del mensaje de error claro
    - `grep "find_spec" tests/test_test_runner.py` confirma test de detección de pytest
    - `grep "isinstance.*list" tests/test_test_runner.py` confirma test anti-injection
    - `grep "traceback.*None" tests/test_test_runner.py` confirma test de traceback None
    - `python3 -m pytest tests/ -v` exits 0 (suite completa del agente incluyendo tests anteriores)
  </acceptance_criteria>
</task>

<task id="3">
  <title>Actualizar `context/marco_teorico_notas.md` con HU-07 y commitear</title>
  <read_first>
    - context/marco_teorico_notas.md (ver formato de secciones HU-01 a HU-06)
    - agent/test_runner.py (módulo recién implementado)
  </read_first>
  <action>
    Agregar la sección `### HU-07: Runner de Tests` al final de `context/marco_teorico_notas.md`:

    ```markdown
    ### HU-07: Runner de Tests

    - **Qué se hizo:** se creó `agent/test_runner.py` con la función pública
      `run(tests_dir: str) -> dict` que verifica la disponibilidad de pytest con
      `importlib.util.find_spec("pytest")`, ejecuta `pytest -v` como subproceso aislado
      con `subprocess.run([sys.executable, '-m', 'pytest', '-v', ...], capture_output=True, text=True)`,
      y parsea el stdout para retornar `{test_id: {'status': 'passed'|'failed'|'error', 'traceback': str|None}}`.
      Si pytest no está instalado, imprime `"[ERROR] pytest no está instalado. Ejecutá: pip install pytest"`
      y retorna `{}` sin lanzar excepción.

    - **Por qué detectar pytest explícitamente antes de subprocess:**
      Ejecutar `subprocess.run([sys.executable, '-m', 'pytest', ...])` cuando pytest no está instalado
      produce un `No module named pytest` en stderr con exit code 1 — un error críptico que el usuario
      no puede diagnosticar fácilmente. La verificación previa con `importlib.util.find_spec("pytest")`
      (que retorna `None` si el módulo no existe en el entorno) permite dar un mensaje accionable
      antes de intentar ejecutar el subproceso. Esta decisión prioriza la experiencia del usuario
      sobre la simplicidad de implementación.

    - **Por qué sys.executable en vez de "pytest" directo:**
      Usar `sys.executable + '-m pytest'` garantiza que se ejecuta pytest del mismo entorno Python
      que el agente. Si el usuario tiene múltiples entornos virtuales, `pytest` en PATH puede
      apuntar al entorno equivocado; `sys.executable -m pytest` siempre usa el entorno activo.

    - **Por qué parseo regex en vez de pytest JSON/XML:**
      El formato JSON (`pytest --json-report`) requiere un plugin externo — viola la restricción
      de zero deps del proyecto. El formato JUnit XML (pytest --junit-xml) requiere escribir
      un archivo temporal. El parseo del stdout de `pytest -v` es suficiente para extraer
      test_ids y status con un regex simple, y el traceback está presente en el mismo stdout.

    - **Conceptos teóricos que aplican:** subproceso vs. subprocess (aislamiento del estado Python),
      test discovery de pytest (convención `test_*.py::test_*`), captura de stdout/stderr,
      regex sobre output de CLI, `importlib.util.find_spec` para detección de módulos sin importar.
    ```

    Luego verificar suite y commitear:
    ```bash
    python3 -m pytest tests/ -v
    git add agent/test_runner.py tests/test_test_runner.py context/marco_teorico_notas.md
    git commit -m "feat: HU-07 - Runner de tests con detección de pytest y parseo de resultados"
    ```
  </action>
  <acceptance_criteria>
    - `grep "HU-07" context/marco_teorico_notas.md` encuentra la sección
    - `grep "find_spec" context/marco_teorico_notas.md` explica la decisión de detección de pytest
    - `grep "sys.executable" context/marco_teorico_notas.md` menciona la razón de usar sys.executable
    - `python3 -m pytest tests/ -v` exits 0 antes del commit
    - `git log --oneline -1` muestra `feat: HU-07 - Runner de tests con detección de pytest y parseo de resultados`
    - `git show --name-only HEAD` lista: agent/test_runner.py, tests/test_test_runner.py, context/marco_teorico_notas.md
  </acceptance_criteria>
</task>

</tasks>

<verification>
Verificación completa de HU-07:

```bash
# 1. Imports OK
python3 -c "from agent.test_runner import run; print('import OK')"

# 2. Detección de pytest instalado
python3 -c "
from agent.test_runner import run
import importlib.util
spec = importlib.util.find_spec('pytest')
print('pytest disponible:', spec is not None)
"

# 3. Suite del agente completa (NO tests_generados/)
python3 -m pytest tests/ -v

# 4. Test de parseo en aislamiento
python3 -c "
from agent.test_runner import _parse_output
output = '''tests_generados/unit/test_calc.py::test_suma PASSED
tests_generados/unit/test_calc.py::test_div FAILED
'''
result = _parse_output(output)
assert result['tests_generados/unit/test_calc.py::test_suma']['status'] == 'passed'
assert result['tests_generados/unit/test_calc.py::test_div']['status'] == 'failed'
print('parseo OK:', result)
"

# 5. Verificar commit
git log --oneline -3
```
</verification>

<must_haves>
<truths>
  - `run(tests_dir: str) -> dict` es la única función pública de test_runner.py
  - La detección de pytest usa `importlib.util.find_spec("pytest")` al inicio de `run()` — ANTES de subprocess
  - Si pytest no está instalado, `run()` imprime `"[ERROR] pytest no está instalado. Ejecutá: pip install pytest"` y retorna `{}`
  - El formato de retorno es `{test_id: {'status': 'passed'|'failed'|'error', 'traceback': str|None}}`
  - traceback ausente es `None`, no string vacío
  - `subprocess.run` recibe una lista como primer argumento (no un string) — previene shell injection
  - Solo stdlib: `importlib.util`, `re`, `subprocess`, `sys`, `pathlib`
  - Los tests del agente van en `tests/`, nunca en `tests_generados/`
  - Commit con formato `feat: HU-07 - <desc>` (CLAUDE.md)
</truths>
</must_haves>

<success_criteria>
1. `python3 -c "from agent.test_runner import run; print('OK')"` exits 0
2. `python3 -m pytest tests/test_test_runner.py -v` — 12 tests PASSED, 0 failed
3. `python3 -m pytest tests/ -v` — suite completa del agente PASSED
4. `grep "pip install pytest" agent/test_runner.py` encuentra el mensaje de error claro
5. `git log --oneline -1` muestra commit feat: HU-07
</success_criteria>
