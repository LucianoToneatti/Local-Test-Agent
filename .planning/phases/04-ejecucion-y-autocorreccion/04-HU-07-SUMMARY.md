---
phase: 04-ejecucion-y-autocorreccion
plan: HU-07
subsystem: testing
tags: [pytest, subprocess, ast, test-runner, parseo]

requires:
  - phase: 03-generacion-de-tests-de-integracion
    provides: tests generados en tests_generados/ para ejecutar

provides:
  - agent/test_runner.py con función pública run(tests_dir) -> dict
  - Detección de pytest con importlib.util.find_spec antes de subprocess
  - Parseo de stdout de pytest -v con regex (PASSED/FAILED/ERROR)
  - Extracción de tracebacks por bloque de failures
  - 12 tests unitarios en tests/test_test_runner.py

affects: [HU-08-autocorrector, agent.py]

tech-stack:
  added: []
  patterns: [subprocess aislado con lista (anti-injection), parseo regex de CLI stdout]

key-files:
  created:
    - agent/test_runner.py
    - tests/test_test_runner.py
  modified:
    - context/marco_teorico_notas.md

key-decisions:
  - "importlib.util.find_spec para detectar pytest antes de subprocess — mensaje accionable"
  - "sys.executable -m pytest en vez de 'pytest' directo — garantiza entorno correcto"
  - "parseo regex de stdout en vez de pytest JSON/XML — zero deps extra"
  - "subprocess.run recibe lista, no string — previene shell injection"

patterns-established:
  - "Detección de dependencia con find_spec antes de subprocess"
  - "Parseo regex de output de CLI con re.MULTILINE"

requirements-completed:
  - EXEC-01
  - EXEC-02

duration: 15min
completed: 2026-05-04
---

# Phase 4 — HU-07: Runner de Tests

**Runner de pytest con detección explícita, parseo regex de resultados y extracción de tracebacks — 12/12 tests unitarios.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-05-04
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- `agent/test_runner.py` implementado con `run(tests_dir: str) -> dict` como única función pública
- Detección de pytest via `importlib.util.find_spec("pytest")` con mensaje de error claro (`pip install pytest`)
- Parseo completo de stdout de `pytest -v`: extrae test_id, status (passed/failed/error) y tracebacks
- 12 tests unitarios en `tests/test_test_runner.py` — 12/12 passing

## Task Commits

1. **Task 1: Crear agent/test_runner.py** — incluido en commit `f3327e0`
2. **Task 2: Crear tests/test_test_runner.py** — incluido en commit `f3327e0`
3. **Task 3: Actualizar marco teórico y commitear** — commit `f3327e0` (feat: HU-07)

## Files Created/Modified
- `agent/test_runner.py` — runner con detección, ejecución y parseo de pytest
- `tests/test_test_runner.py` — 12 tests unitarios con mock de subprocess y find_spec
- `context/marco_teorico_notas.md` — sección HU-07 con decisiones técnicas

## Self-Check: PASSED

- `python3 -c "from agent.test_runner import run; print('OK')"` → OK
- `python3 -m pytest tests/test_test_runner.py -v` → 12 PASSED, 0 failed
- `grep "pip install pytest" agent/test_runner.py` → confirma mensaje de error claro
- `grep "find_spec" agent/test_runner.py` → confirma detección de pytest
- `grep "subprocess.run" agent/test_runner.py` → usa lista (anti-injection)
