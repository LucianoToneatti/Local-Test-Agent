# Roadmap: Local-Test-Agent

**Fases:** 5 | **Requisitos mapeados:** 20/20 ✓ | **Granularidad:** Standard

---

## Resumen de Fases

| # | Fase | Goal | Requisitos | Criterios de éxito |
|---|------|------|------------|--------------------|
| 1 | Exploración y Análisis | Parsear cualquier repo Python en una estructura de datos usable | EXPL-01, EXPL-02, EXPL-03, ANLS-01, ANLS-02, ANLS-03 | 6 |
| 2 | Generación de Tests Unitarios | Generar tests unitarios válidos para todas las funciones extraídas | TGEN-01, TGEN-02, TGEN-03 | 4 |
| 3 | Generación de Tests de Integración | Detectar relaciones entre módulos y generar tests de integración | INTG-01, INTG-02, INTG-03 | 3 |
| 4 | Ejecución y Autocorrección | Correr pytest y corregir tests fallidos automáticamente | EXEC-01, EXEC-02, EXEC-03, EXEC-04 | 5 |
| 5 | Reporte y CLI completa | Flujo end-to-end desde un solo comando con reporte final | REPO-01, REPO-02, CLI-01, CLI-02 | 4 |

---

## Fase 1: Exploración y Análisis

**HUs:** HU-03, HU-04
**Rama activa:** `feature/HU-03-HU-04-repo-explorer`

**Goal:** El agente puede parsear cualquier repositorio Python en una estructura de datos usable por el generador de tests.

**Requisitos:**
- EXPL-01: Lista recursiva de `.py` ignorando dirs del sistema
- EXPL-02: Rutas relativas al repositorio
- EXPL-03: Detección de imports entre módulos
- ANLS-01: Extracción de funciones/clases con AST
- ANLS-02: Diccionario `{ archivo: [funciones/clases] }`
- ANLS-03: Fragmentación de archivos >200 líneas

**Planes:**

**Wave 1**
1. `HU-03` — Explorador de repositorio (`agent/repo_explorer.py`) — EXPL-01, EXPL-02 ✅ 2026-05-02

**Wave 2**
2. `HU-04` — Extractor AST (`agent/ast_extractor.py`) — ANLS-01, ANLS-02, ANLS-03, EXPL-03 ✅ 2026-05-02

**Cross-cutting constraints:**
- Solo stdlib de Python (ast, os, pathlib) — sin dependencias pip
- Commit por HU con formato `feat: HU-0X - <desc>` + update de marco_teorico_notas.md

**Criterios de éxito:**
1. `agent.py --repo ./examples` lista `examples/calculadora.py` sin incluir `__pycache__`, `.git` ni `venv`
2. El extractor devuelve `{ "examples/calculadora.py": [{"name": "sumar", "params": [...], "docstring": "..."}, ...] }` para el archivo de ejemplo
3. Un archivo Python de más de 200 líneas se procesa en fragmentos sin error
4. Los imports entre módulos del mismo repositorio quedan registrados en la estructura devuelta
5. Se commiteó con mensaje HU-03 y se actualizó `context/marco_teorico_notas.md`
6. Se commiteó con mensaje HU-04 y se actualizó `context/marco_teorico_notas.md`

**UI hint:** no

---

## Fase 2: Generación de Tests Unitarios

**HUs:** HU-05
**Rama sugerida:** `feature/HU-05-unit-test-generator`

**Goal:** Para cada función extraída en Fase 1, el agente genera archivos de test unitario válidos y ejecutables con pytest.

**Requisitos:**
- TGEN-01: Mínimo 2 casos por función (happy path + edge case)
- TGEN-02: Archivos pytest válidos en `tests_generados/unit/`
- TGEN-03: `conftest.py` con `sys.path` configurado

**Planes:**
1. `HU-05` — Generador de tests unitarios (`agent/test_generator.py`)

**Criterios de éxito:**
1. Sobre `examples/calculadora.py`, el generador produce `tests_generados/unit/test_calculadora.py` con al menos 10 funciones de test (2 por función × 5 funciones)
2. `pytest tests_generados/unit/test_calculadora.py` corre sin errores de importación
3. Cada función de la calculadora tiene al menos un test happy path y un test edge case identificables por nombre
4. El `conftest.py` generado en `tests_generados/unit/` agrega el directorio analizado al `sys.path`

**UI hint:** no

---

## Fase 3: Generación de Tests de Integración

**HUs:** HU-06
**Rama sugerida:** `feature/HU-06-integration-test-generator`

**Goal:** El agente detecta qué módulos del repositorio se importan entre sí y genera al menos un test de integración por par relacionado.

**Requisitos:**
- INTG-01: Identificación de pares de módulos relacionados por imports
- INTG-02: Mínimo 1 test de integración por par
- INTG-03: Tests guardados en `tests_generados/integration/`

**Planes:**
1. `HU-06` — Generador de tests de integración (`agent/integration_generator.py`)

**Criterios de éxito:**
1. El agente identifica correctamente los pares de módulos que se importan entre sí en un repositorio multi-archivo
2. Para cada par detectado, existe un archivo en `tests_generados/integration/`
3. Los tests de integración generados se pueden correr con `pytest` sin errores de importación

**UI hint:** no

---

## Fase 4: Ejecución y Autocorrección

**HUs:** HU-07, HU-08
**Rama sugerida:** `feature/HU-07-HU-08-execution-autocorrection`

**Goal:** El agente corre todos los tests generados y corrige automáticamente los que fallan, hasta 3 intentos por test.

**Requisitos:**
- EXEC-01: Ejecución de pytest con captura de stdout/stderr
- EXEC-02: Registro de passed / failed / error por test
- EXEC-03: Envío de test fallido + error al LLM para corrección
- EXEC-04: Máximo 3 intentos; si falla → "sin resolver"

**Planes:**
1. `HU-07` — Runner de tests (`agent/test_runner.py`)
2. `HU-08` — Autocorrector (`agent/autocorrector.py`)

**Criterios de éxito:**
1. El runner ejecuta `pytest` sobre `tests_generados/` y devuelve un diccionario con el resultado de cada test
2. Un test que falla llega al autocorrector con el traceback completo como contexto
3. Si el LLM corrige el test y ahora pasa, queda marcado como "passed" en la siguiente ejecución
4. Un test que sigue fallando tras 3 intentos queda marcado como "sin resolver" y no bloquea el flujo
5. Se commiteó con mensaje HU-07 y se actualizó `context/marco_teorico_notas.md`

**UI hint:** no

---

## Fase 5: Reporte y CLI Completa

**HUs:** HU-09, HU-10
**Rama sugerida:** `feature/HU-09-HU-10-report-cli`

**Goal:** El flujo completo funciona con un solo comando y produce un reporte legible al finalizar.

**Requisitos:**
- REPO-01: `reporte.md` con resumen passed/failed/sin resolver
- REPO-02: Tiempo total de ejecución en el reporte
- CLI-01: `python3 agent.py --repo ./path` ejecuta todo el flujo
- CLI-02: Progreso visible en terminal durante la ejecución

**Planes:**
1. `HU-09` — Generador de reporte (`agent/report_generator.py`)
2. `HU-10` — CLI completa (refactor de `agent.py`)

**Criterios de éxito:**
1. `python3 agent.py --repo ./examples` corre sin parámetros adicionales y completa el flujo end-to-end
2. Al finalizar, existe `reporte.md` con conteo de passed, failed y sin resolver
3. El reporte incluye el tiempo total de ejecución en segundos
4. Durante la ejecución, el usuario ve mensajes de progreso (ej: "Analizando calculadora.py...", "Generando tests...", "Ejecutando pytest...")

**UI hint:** no

---

## Trazabilidad Completa

| Requisito | Fase | Estado |
|-----------|------|--------|
| EXPL-01 | Fase 1 | Complete ✅ |
| EXPL-02 | Fase 1 | Complete ✅ |
| EXPL-03 | Fase 1 | Complete ✅ |
| ANLS-01 | Fase 1 | Complete ✅ |
| ANLS-02 | Fase 1 | Complete ✅ |
| ANLS-03 | Fase 1 | Complete ✅ |
| TGEN-01 | Fase 2 | Pending |
| TGEN-02 | Fase 2 | Pending |
| TGEN-03 | Fase 2 | Pending |
| INTG-01 | Fase 3 | Pending |
| INTG-02 | Fase 3 | Pending |
| INTG-03 | Fase 3 | Pending |
| EXEC-01 | Fase 4 | Pending |
| EXEC-02 | Fase 4 | Pending |
| EXEC-03 | Fase 4 | Pending |
| EXEC-04 | Fase 4 | Pending |
| REPO-01 | Fase 5 | Pending |
| REPO-02 | Fase 5 | Pending |
| CLI-01 | Fase 5 | Pending |
| CLI-02 | Fase 5 | Pending |

**Cobertura:** 20/20 requisitos v1 mapeados ✓

---
*Roadmap creado: 2026-05-02*
