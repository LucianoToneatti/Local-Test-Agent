---
phase: 04-ejecucion-y-autocorreccion
plan: HU-08
subsystem: testing
tags: [autocorrector, llm, ast, pytest, correction-loop]

requires:
  - phase: 04-ejecucion-y-autocorreccion
    provides: test_runner.run() -> dict con {test_id: {status, traceback}}

provides:
  - CorrectionPromptTemplate en prompts/prompt_builder.py (language="python_correction")
  - agent/autocorrector.py con autocorrect(results, repo_path) -> dict
  - Ciclo de corrección LLM hasta 3 intentos por test_id
  - Reemplazo selectivo de función fallida usando AST (no archivo completo)
  - Re-ejecución individual por test_id (no suite completa)
  - 15 tests unitarios en tests/test_autocorrector.py
  - Integración en agent.py: run_tests → autocorrect

affects: [HU-09-report-generator, agent.py]

tech-stack:
  added: []
  patterns:
    - Ciclo feedback LLM→corrección→verificación con límite de intentos
    - Reemplazo selectivo de función con AST (preserva otras funciones)
    - Re-ejecución individual pytest path::test_nombre (costo O(1) por verificación)

key-files:
  created:
    - agent/autocorrector.py
    - tests/test_autocorrector.py
  modified:
    - prompts/prompt_builder.py
    - agent.py
    - context/marco_teorico_notas.md

key-decisions:
  - "Reemplazar solo función fallida con AST — preserva funciones que ya pasan (D-05)"
  - "Re-correr solo test_id individual con pytest path::nombre — costo O(1) (D-12)"
  - "Firmas re-derivadas dentro de autocorrect() — interfaz simple (D-10)"
  - "Máximo 3 intentos por test_id — evita bucle infinito (EXEC-04)"
  - "ast.parse() valida LLM output antes de escribir — evita syntax errors en disco"

patterns-established:
  - "Ciclo de corrección: extrae función → LLM → valida AST → reemplaza → re-corre"
  - "Status 'sin_resolver' para test_ids que agotaron intentos — no bloquea flujo"

requirements-completed:
  - EXEC-03
  - EXEC-04

duration: 25min
completed: 2026-05-04
---

# Phase 4 — HU-08: Autocorrector de Tests

**Ciclo de corrección LLM con reemplazo selectivo AST, re-ejecución individual y límite de 3 intentos — 15/15 tests, 79/79 suite completa.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-05-04
- **Tasks:** 5
- **Files modified:** 5

## Accomplishments
- `CorrectionPromptTemplate` registrada en `_REGISTRY` con `language="python_correction"`
- `agent/autocorrector.py` con `autocorrect(results, repo_path) -> dict` como única función pública
- Ciclo de corrección LLM: extrae función fallida con AST → genera corrección → valida sintaxis → reemplaza en archivo → re-corre test individual
- Status `'sin_resolver'` para tests que agotaron 3 intentos — no bloquea flujo del agente
- Integración en `agent.py`: `results = run_tests(tests_dir)` → `final = autocorrect(results, str(repo))`
- 15 tests unitarios en `tests/test_autocorrector.py` — 15/15 passing
- Suite completa: 79/79 tests passing (HU-01 a HU-08)

## Task Commits

1. **Task 1: CorrectionPromptTemplate** — `c075348`
2. **Task 2: autocorrector.py** — `44ee368`
3. **Task 3: integración agent.py** — `f44954d`
4. **Task 4: test_autocorrector.py** — `3d2a228`
5. **Task 5: marco teórico + commit final** — `fb8c65e`

## Files Created/Modified
- `prompts/prompt_builder.py` — CorrectionPromptTemplate + registro en _REGISTRY
- `agent/autocorrector.py` — autocorrector con ciclo LLM y reemplazo selectivo AST
- `agent.py` — integración run_tests + autocorrect en main()
- `tests/test_autocorrector.py` — 15 tests unitarios con mock de LLMClient y subprocess
- `context/marco_teorico_notas.md` — sección HU-08 con decisiones técnicas

## Self-Check: PASSED

- `python3 -c "from agent.autocorrector import autocorrect; print('OK')"` → OK
- `python3 -m pytest tests/test_autocorrector.py -v` → 15 PASSED, 0 failed
- `python3 -m pytest tests/ -v` → 79 PASSED, 0 failed
- `grep "sin_resolver" agent/autocorrector.py` → confirma status de agotamiento (EXEC-04)
- `grep "_MAX_ATTEMPTS = 3" agent/autocorrector.py` → confirma límite de 3 intentos
- `grep "run_tests\|autocorrect" agent.py` → confirma integración
