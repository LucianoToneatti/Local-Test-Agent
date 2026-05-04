---
phase: 3
plan: HU-06
status: passed
verified: 2026-05-03
---

# Phase 3: Generación de Tests de Integración — Verification

## Requirements Traceability

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| INTG-01 | El agente identifica pares de módulos relacionados a partir de los imports entre archivos del repositorio | Verificado | `_find_pairs()` itera `file_info.get("imports", [])` del dict de `extract()`; detecto `('estadistica.py', ['calculadora.py'])` en `examples/` |
| INTG-02 | Para cada par de módulos relacionados, el agente genera al menos 1 test de integración que valida la interacción entre ellos | Verificado | `_generate_pair_test()` llama `client.generate()` exactamente una vez por par; archivo generado contiene 7 tests para el par (estadistica, calculadora) |
| INTG-03 | Los tests de integración se guardan en `tests_generados/integration/test_<modulo_a>_<modulo_b>.py` | Verificado | Archivo `tests_generados/integration/test_estadistica_calculadora.py` existe y fue confirmado con `test -f` |

## Must-Haves Verification

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `generate(repo_path, ast_result)` es la única función pública de `integration_generator.py` | Verificado | Archivo leído: única función sin prefijo `_`; todas las demás son `_find_pairs`, `_format_signatures`, `_generate_pair_test`, `_read_source`, `_write_conftest` |
| 2 | Los pares se detectan desde el campo `imports` (no re-parsea el código) | Verificado | Línea 53: `for imported in file_info.get("imports", []):` — consume el dict de `extract()` directamente |
| 3 | El LLM se llama exactamente una vez por par (no por función) | Verificado | `_generate_pair_test()` contiene un único `client.generate()` dentro del loop `for attempt in range(2)`; test `test_generate_calls_llm_once_per_pair` confirma 2 llamadas para 2 pares |
| 4 | El prompt pasa código fuente completo de A y solo las FIRMAS (nombre+params) de B | Verificado | `_TEMPLATE.build(code=a_source, module_name=stem_a, class_name=stem_b, module_b_sigs=b_sigs)` donde `b_sigs` proviene de `_format_signatures()` que solo produce `def nombre(params): ...` sin cuerpo |
| 5 | `ast.parse()` valida el output antes de escribir | Verificado | Líneas 102-107: `try: ast.parse(code); return code; except SyntaxError:` |
| 6 | Reintento exactamente una vez (`for attempt in range(2)`) | Verificado | Línea 93: `for attempt in range(2):` — exactamente 1 reintento si el primer intento produce SyntaxError |
| 7 | Fallback: `# ERROR: no se pudo generar test de integración para <stemA>_<stemB>` | Verificado | Línea 109: `return f"# ERROR: no se pudo generar test de integración para {stem_a}_{stem_b}"` |
| 8 | `conftest.py` con `sys.path.insert(0, ...)` y ruta absoluta del repo | Verificado | Archivo en `tests_generados/integration/conftest.py` contiene `sys.path.insert(0, "/home/lucianotoneatti/Proyectos-CC/TIF/Local-Test-Agent/examples")` |
| 9 | Nombre de output: `test_{stem_A}_{stem_B}.py` | Verificado | Línea 38: `out_file = OUTPUT_DIR / f"test_{stem_a}_{stem_b}.py"`; archivo `test_estadistica_calculadora.py` confirmado |
| 10 | Solo stdlib + módulos del propio agente (sin dependencias pip) | Verificado | Imports del módulo: `ast`, `pathlib`, `typing` (stdlib) + `agent.llm_client`, `prompts.prompt_builder` (proyecto) — ningún import pip |
| 11 | Tests del agente en `tests/`, output en `tests_generados/` (nunca mezclados) | Verificado | `tests/test_integration_generator.py` contiene los 17 tests del agente; `tests_generados/integration/` contiene el output generado — directorios separados |
| 12 | `IntegrationPromptTemplate` registrada en `_REGISTRY` con `language="python_integration"` | Verificado | `prompt_builder.py` líneas 118 y 169-171: `language = "python_integration"` y `"python_integration": IntegrationPromptTemplate()` en `_REGISTRY` |
| 13 | `PromptBuilder.build()` y `PythonPromptTemplate` no modificados | Verificado | Lectura del archivo: `PromptBuilder.build()` acepta los mismos parámetros que antes (code, language, function_name, module_name, class_name); `PythonPromptTemplate` sin cambios |

## Success Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `pytest tests/test_integration_generator.py -v` — 17 tests PASSED, 0 failed | Verificado | Output: `17 passed in 0.04s` |
| 2 | `pytest tests/ -v` — suite completa 52/52 PASSED | Verificado | Output: `52 passed in 0.08s` |
| 3 | El agente identifica correctamente el par (estadistica.py, calculadora.py) en `examples/` | Verificado | Output del script: `Pares: [('estadistica.py', ['calculadora.py'])]` y `Criterio 1 OK` |
| 4 | `tests_generados/integration/test_estadistica_calculadora.py` existe y no es comentario de error | Verificado | `test -f` retorna 0; contenido del archivo comienza con `import pytest` y contiene 7 funciones de test |
| 5 | `pytest tests_generados/integration/ --collect-only` sin ImportError | Verificado | Output: `7 tests collected in 0.00s` — 0 errores de importación |
| 6 | `git log --oneline -1` muestra `feat: HU-06 - Generador de tests de integración` | Parcial | Se usaron commits atómicos por task en lugar de un commit único; el último commit de HU-06 es `21a4b50 docs(03-HU-06): create plan SUMMARY.md`. Desviación documentada en SUMMARY.md, sin impacto funcional. |

## Gaps Found

Ninguno. Todos los must_haves están implementados exactamente como especificados en el plan. La única desviación es la estrategia de commits (atómicos por task vs. un commit único al final), que fue documentada explícitamente en SUMMARY.md y no tiene impacto en la funcionalidad.

## Verification Complete

La Fase 3 (HU-06) está completamente implementada y verificada. Los tres criterios de éxito del ROADMAP.md están cumplidos:

1. El agente identifica correctamente los pares de módulos relacionados por imports.
2. Para cada par detectado existe un archivo en `tests_generados/integration/`.
3. Los tests generados se pueden colectar con pytest sin errores de importación.

La suite de 17 tests del agente pasa en 0.04s. La suite completa de 52 tests pasa sin regresiones. El módulo `agent/integration_generator.py` implementa el patrón de validación `ast.parse()` + 1 reintento, el conftest con `sys.path` absoluto, y la detección de pares desde el campo `imports` del dict de `extract()` — sin reparsear código.
