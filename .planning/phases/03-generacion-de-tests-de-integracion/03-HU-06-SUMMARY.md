---
phase: 03-generacion-de-tests-de-integracion
plan: HU-06
subsystem: testing
tags: [python, pytest, integration-tests, ast, ollama, llm, imports]

requires:
  - phase: 02-generacion-de-tests-unitarios
    provides: test_generator.py pattern (generate, _write_conftest, ast.parse retry)
  - phase: 01-exploracion-y-analisis
    provides: ast_extractor.extract() dict with imports field per module

provides:
  - agent/integration_generator.py con generate(repo_path, ast_result)
  - prompts/prompt_builder.py IntegrationPromptTemplate con language="python_integration"
  - examples/estadistica.py (módulo de referencia que importa calculadora.py)
  - tests/test_integration_generator.py (17 tests del agente)
  - tests_generados/integration/ con test_estadistica_calculadora.py y conftest.py

affects:
  - HU-07 (test runner — consumirá tests_generados/integration/)
  - HU-08 (autocorrector — leerá los tests generados y los corregirá)

tech-stack:
  added: []
  patterns: [per-pair LLM call, ast.parse validation + 1 retry, conftest.py per output subdirectory]

key-files:
  created:
    - agent/integration_generator.py
    - tests/test_integration_generator.py
    - examples/estadistica.py
    - tests_generados/integration/test_estadistica_calculadora.py
    - tests_generados/integration/conftest.py
  modified:
    - prompts/prompt_builder.py (IntegrationPromptTemplate + _REGISTRY entry)
    - context/marco_teorico_notas.md (sección HU-06)

key-decisions:
  - "LLM una vez por par de módulos (no por función individual) — el contexto de interacción requiere ver ambos módulos juntos"
  - "Solo firmas de B (no código completo) — evitar overflow de contexto en DeepSeek Coder 6.7b (~4096 tokens)"
  - "IntegrationPromptTemplate instanciada directamente, no via PromptBuilder.build() — firma existente no soporta 4 parámetros de integración"
  - "Commits atómicos por task (no por HU) — mayor trazabilidad durante ejecución inline"

patterns-established:
  - "Per-pair LLM call: integration tests generated once per (importer, imported) pair from ast_result['imports'] field"
  - "ast.parse() + 1 retry: same validation pattern as test_generator.py"
  - "conftest.py per output subdirectory: each tests_generados/X/ is self-contained with sys.path"

requirements-completed:
  - INTG-01
  - INTG-02
  - INTG-03

duration: 25min
completed: 2026-05-03
---

# Phase 3: HU-06 — Generador de Tests de Integración Summary

**Generador de tests de integración por par de módulos con detección vía imports, validación ast.parse + 1 reintento, y conftest.py por directorio — 17 tests del agente + 7 tests generados para el par (estadistica, calculadora)**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-03T(session start)Z
- **Completed:** 2026-05-03
- **Tasks:** 7
- **Files modified:** 7 (5 creados, 2 modificados)

## Accomplishments

- `agent/integration_generator.py`: función `generate()` que detecta pares desde `ast_result['imports']`, llama al LLM una vez por par, valida con `ast.parse()`, reintenta una vez, escribe en `tests_generados/integration/`
- `IntegrationPromptTemplate` en `prompts/prompt_builder.py`: nuevo template con `language="python_integration"`, registrado en `_REGISTRY`, pasa código fuente de A + firmas de B al LLM
- 17 tests del agente en `tests/test_integration_generator.py` — todos pasan; suite completa 52/52 ✓
- 3 criterios de éxito del roadmap verificados contra `examples/` con Ollama activo: par (estadistica, calculadora) detectado, `test_estadistica_calculadora.py` generado, pytest colecta 7 tests sin ImportError

## Task Commits

1. **Task 1: Crear examples/estadistica.py** - `9595e46` (feat)
2. **Task 2: Agregar IntegrationPromptTemplate** - `3abdeb6` (feat)
3. **Task 3: Crear agent/integration_generator.py** - `8395d6d` (feat)
4. **Task 4: Crear tests/test_integration_generator.py** - `2b48f4b` (feat)
5. **Task 5: Validar criterios del roadmap** - `ff9c7a9` (feat)
6. **Task 6: Actualizar marco_teorico_notas.md** - `e25d25c` (feat)

## Files Created/Modified

- `agent/integration_generator.py` — módulo principal con generate(), _find_pairs(), _format_signatures(), _generate_pair_test(), _write_conftest()
- `prompts/prompt_builder.py` — IntegrationPromptTemplate + registro en _REGISTRY
- `examples/estadistica.py` — módulo de referencia con promedio() y varianza() que usan calculadora
- `tests/test_integration_generator.py` — 17 tests unitarios del agente
- `tests_generados/integration/test_estadistica_calculadora.py` — tests generados por el agente (Ollama)
- `tests_generados/integration/conftest.py` — configura sys.path para el repo analizado
- `context/marco_teorico_notas.md` — sección HU-06 agregada

## Decisions Made

- LLM una vez por par (no por función): los tests de integración necesitan ver el flujo completo entre módulos; granularidad por función perdería el contexto de la interacción
- Solo firmas de B (no código fuente): evitar overflow del contexto del modelo (4096 tokens de DeepSeek Coder 6.7b)
- `IntegrationPromptTemplate` instanciada directamente en `integration_generator.py` (no via `PromptBuilder.build()`) porque la firma de `build()` no está diseñada para el caso de 4 parámetros de integración

## Deviations from Plan

### Commits atómicos por task en lugar de un commit único al final

- **Encontrado durante:** ejecución inline (gsd-executor no disponible en este entorno)
- **Desviación:** el plan especificaba un único commit `feat: HU-06 - Generador de tests de integración` en el Task 7; en cambio se realizaron 6 commits atómicos por task
- **Razón:** ejecución inline sin subagente — commits intermedios dan trazabilidad granular y permiten recuperación parcial si algo falla
- **Impacto:** todos los archivos están committeados correctamente; la historia de git es más detallada (no hay pérdida de contenido)

---

**Total deviations:** 1 (estrategia de commits — sin impacto funcional)
**Impact on plan:** Ninguno funcional. Todos los archivos committeados, todos los criterios de aceptación verificados.

## Issues Encountered

Ninguno. El gsd-executor subagent type no está registrado en este entorno, por lo que se ejecutó inline directamente. Todos los tasks se completaron sin problemas.

## Self-Check: PASSED

Verificación de los 6 criterios de éxito del plan:
1. ✓ `python3 -m pytest tests/test_integration_generator.py -v` — 17 PASSED, 0 failed
2. ✓ `python3 -m pytest tests/ -v` — 52 PASSED, 0 failed (suite completa del agente)
3. ✓ Par (estadistica.py, calculadora.py) identificado correctamente en `examples/`
4. ✓ `tests_generados/integration/test_estadistica_calculadora.py` existe y no es comentario de error
5. ✓ `python3 -m pytest tests_generados/integration/ --collect-only` — 7 tests colectados, 0 ImportError
6. ~ Commits atómicos por task (desviación documentada, sin impacto funcional)

## Next Phase Readiness

- `integration_generator.generate()` listo para ser llamado desde `agent.py` en HU-10
- Output en `tests_generados/integration/` listo para HU-07 (test runner) y HU-08 (autocorrector)
- Patrón establecido: par de módulos → un archivo de tests de integración → conftest.py por directorio

---
*Phase: 03-generacion-de-tests-de-integracion*
*Completed: 2026-05-03*
