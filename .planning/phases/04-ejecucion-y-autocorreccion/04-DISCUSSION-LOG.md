# Phase 4: Ejecución y Autocorrección - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 4-Ejecución y Autocorrección
**Areas discussed:** Granularidad del resultado, Scope de la corrección, Contexto al LLM, Coordinación runner/autocorrector

---

## Granularidad del resultado

### ¿A qué nivel registra el runner los resultados de pytest?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| Por función de test | Parsea stdout de pytest -v, devuelve {test_id: {status, traceback}}. Granular y preciso para el autocorrector. | ✓ |
| Por archivo de test | El runner registra si el archivo pasó o falló como unidad. Más simple de parsear. | |

**Elección:** Por función de test (test_id = path completo + nombre de función)

### ¿Cómo ejecuta el runner pytest internamente?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| subprocess | subprocess.run([sys.executable, '-m', 'pytest', '-v', ...], capture_output=True). Proceso aislado. | ✓ |
| pytest.main() | Desde el mismo proceso. Puede interferir con el agente. | |

**Elección:** subprocess

### ¿Una invocación o separado por subdirectorio?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| Una sola invocación sobre tests_generados/ | Resultado uniforme, el test_id incluye la ruta para distinguir origen. | ✓ |
| Separado por subdirectorio | Permite ver pass rate por tipo, más complejidad. | |

**Elección:** Una sola invocación

### ¿Qué devuelve run()?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| Dict por test ID | run(tests_dir) -> dict[str, dict]. Keys = test IDs, values = {status, traceback}. | ✓ |
| Objeto RunResult | Con atributos .passed, .failed, .errors. Agrega clase sin reutilización. | |

**Elección:** Dict por test ID

---

## Scope de la corrección

### ¿Qué reescribe el autocorrector cuando un test falla?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| Solo la función fallida | Extrae la función fallida, la corrige, la reemplaza en el archivo. Otros tests intactos. | ✓ |
| El archivo completo | LLM recibe el archivo entero y devuelve versión corregida. Puede modificar tests que ya pasan. | |

**Elección:** Solo la función fallida

### ¿Cómo se extrae la función fallida?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| AST | ast.parse() para ubicar la función por nombre y extraer sus líneas. Robusto. | ✓ |
| Regex / split | Buscar 'def test_nombre'. Frágil con decoradores o strings multilínea. | |

**Elección:** AST

### ¿Los 3 intentos se cuentan por función o por archivo?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| Por función de test | Cada test_id tiene su propio contador. Un archivo con 3 funciones fallidas puede tener hasta 9 llamadas al LLM. | ✓ |
| Por archivo | Todo el archivo comparte el contador de 3 intentos. | |

**Elección:** Por función de test

---

## Contexto al LLM

### ¿Qué información envía el autocorrector al LLM?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| Test + traceback + firmas del módulo | Función fallida + traceback + nombre+params de las funciones del módulo bajo test. Patrón de IntegrationPromptTemplate. | ✓ |
| Test + traceback solamente | Mínimo. LLM puede adivinar mal los nombres/tipos. | |
| Test + traceback + código fuente completo | Máximo contexto. Puede exceder el contexto del modelo para archivos >200 líneas. | |

**Elección:** Test + traceback + firmas del módulo

### ¿Dónde vive el template de corrección?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| En prompt_builder.py (CorrectionPromptTemplate) | Nueva subclase registrada en _REGISTRY. Consistente con el patrón del proyecto. | ✓ |
| Inline en autocorrector.py | Más rápido de implementar pero rompe el patrón. | |

**Elección:** En prompt_builder.py

### ¿Cómo obtiene el autocorrector las firmas del módulo bajo test?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| Re-deriva del archivo fuente | autocorrect() llama a ast_extractor.extract() sobre el archivo fuente relevante. No requiere ast_result como parámetro. | ✓ |
| Recibe ast_result como parámetro | Evita re-extraer pero acopla el autocorrector al formato de ast_extractor. | |

**Elección:** Re-deriva del archivo fuente

---

## Coordinación runner/autocorrector

### ¿Quién orquesta el ciclo corrección?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| autocorrector.py es autónomo | autocorrect(results, repo_path) maneja el ciclo internamente. agent.py hace dos llamadas simples. | ✓ |
| agent.py orquesta el ciclo | agent.py itera runner → filtrar → autocorrect → runner. Autocorrector solo corrige una vez. | |

**Elección:** autocorrector.py es autónomo

### ¿Cómo verifica la corrección?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| Re-corre solo el test corregido | subprocess sobre test_id específico. Rápido y preciso. | ✓ |
| Re-corre todo tests_generados/ | Detecta regressions pero más lento. | |

**Elección:** Re-corre solo el test_id corregido

### ¿Qué devuelve autocorrect()?

| Opción | Descripción | Seleccionada |
|--------|-------------|--------------|
| El mismo dict del runner, con status actualizado | Formato uniforme para el reporte (Fase 5). Tests corregidos → 'passed'. Agotados → 'sin_resolver'. | ✓ |
| Dict separado solo con los tests corregidos | agent.py tiene que mergear con el resultado original. | |

**Elección:** El mismo dict del runner con status actualizado

---

## Claude's Discretion

- Parseo de stdout de pytest -v: regex sobre líneas con `PASSED` / `FAILED` / `ERROR`.
- Valor del campo traceback cuando no aplica: `None` (no string vacío).
- Inferencia del módulo bajo test desde test_id: convención `test_<stem>.py` → `<stem>.py` en repo_path.

## Deferred Ideas

- Re-correr la suite completa al finalizar para detectar regressions → puede incluirse en Fase 5 o reporte.
- Caché de correcciones para evitar reprocesar tests idénticos en ejecuciones sucesivas → QUAL-01 (v2).
- Timeout configurable por test → v2.
