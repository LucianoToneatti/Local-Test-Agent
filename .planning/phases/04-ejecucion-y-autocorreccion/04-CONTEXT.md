# Phase 4: Ejecución y Autocorrección - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

El agente corre todos los tests generados con pytest (subprocess), registra el resultado por función de test (test_id), y corrige automáticamente las funciones fallidas enviando el test + traceback + firmas del módulo al LLM, hasta 3 intentos por test_id.

**Dos módulos nuevos:**
- `agent/test_runner.py` — EXEC-01, EXEC-02
- `agent/autocorrector.py` — EXEC-03, EXEC-04

**Un template nuevo:** `CorrectionPromptTemplate` en `prompts/prompt_builder.py`

**Integración en agent.py:** `results = test_runner.run(tests_dir)` → `final = autocorrector.autocorrect(results, repo_path)`

</domain>

<decisions>
## Implementation Decisions

### Granularidad del resultado del runner (EXEC-01, EXEC-02)
- **D-01:** El runner reporta resultados por test ID (función de test), no por archivo. Formato de retorno: `{test_id: {'status': 'passed'|'failed'|'error', 'traceback': str|None}}`. El test_id es la ruta completa + nombre de función tal como lo reporta pytest: `tests_generados/unit/test_calculadora.py::test_sumar_happy_path`.
- **D-02:** El runner ejecuta pytest con `subprocess.run([sys.executable, '-m', 'pytest', '-v', str(tests_dir)], capture_output=True, text=True)`. Proceso aislado del agente; el stdout se parsea para extraer test IDs y sus resultados.
- **D-03:** Una sola invocación sobre `tests_generados/` completo (no separado por subdirectorio unit/ e integration/). El test_id incluye la ruta relativa completa, que permite distinguir el origen.
- **D-04:** Función pública del runner: `run(tests_dir: str) -> dict`.

### Scope de la corrección (EXEC-03, EXEC-04)
- **D-05:** El autocorrector corrige solo la función de test fallida, no el archivo completo. Los demás tests del mismo archivo no se modifican.
- **D-06:** La extracción de la función fallida del archivo de tests usa AST (`ast.parse()`), igual que `ast_extractor.py`. No se usa regex.
- **D-07:** El contador de 3 intentos máximos (EXEC-04) es por test_id (por función de test), no por archivo. Un archivo con N funciones fallidas puede tener hasta 3×N llamadas al LLM.

### Contexto al LLM para corrección (EXEC-03)
- **D-08:** El prompt de corrección envía al LLM: (1) código de la función de test fallida, (2) traceback completo del error, (3) firmas del módulo bajo test (nombre + parámetros, sin el cuerpo). Mismo patrón que `IntegrationPromptTemplate` en la Fase 3: contexto suficiente sin exceder el contexto del modelo.
- **D-09:** `CorrectionPromptTemplate` se agrega a `prompts/prompt_builder.py` como nueva subclase registrada en `_REGISTRY`. Consistente con `PythonPromptTemplate` e `IntegrationPromptTemplate`.
- **D-10:** Las firmas del módulo bajo test se re-derivan en el momento de la corrección llamando a `ast_extractor.extract()` sobre el archivo fuente relevante. `autocorrect()` no recibe `ast_result` como parámetro; lo obtiene internamente a partir de `repo_path` y del test_id (que contiene el nombre del módulo).

### Coordinación runner / autocorrector
- **D-11:** `autocorrector.py` es autónomo. Función pública: `autocorrect(results: dict, repo_path: str) -> dict`. El ciclo de corrección (hasta 3 intentos por test_id fallido) vive dentro de `autocorrect()`. `agent.py` solo hace dos llamadas: `results = test_runner.run(tests_dir)` y `final = autocorrector.autocorrect(results, repo_path)`.
- **D-12:** Para verificar que una corrección fue exitosa, el autocorrector re-corre solo el test_id específico con `subprocess.run([sys.executable, '-m', 'pytest', '-v', 'path/test_file.py::test_nombre'])`. No re-corre la suite completa.
- **D-13:** `autocorrect()` devuelve el mismo formato que `run()`: `{test_id: {'status': ..., 'traceback': ...}}`. Tests corregidos exitosamente → status `'passed'`. Tests que agotaron los 3 intentos → status `'sin_resolver'`. El status `'sin_resolver'` no bloquea el flujo del agente.

### Claude's Discretion
- Parseo del stdout de pytest -v: usar regex sobre líneas con ` PASSED` / ` FAILED` / ` ERROR` para extraer test IDs y resultados; el traceback queda entre la línea `FAILED` y la siguiente línea de separación.
- Nombre del campo en el dict resultado para traceback ausente: `None` (no string vacío).
- El módulo bajo test se infiere del test_id: `tests_generados/unit/test_calculadora.py::test_X` → buscar `calculadora.py` o similar en `repo_path`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos y roadmap
- `.planning/REQUIREMENTS.md` §EXEC-01..04 — criterios de aceptación de ejecución y autocorrección
- `.planning/ROADMAP.md` §Fase 4 — criterios de éxito (5 criterios concretos), HU-07 y HU-08

### Código existente que los módulos nuevos consumen directamente
- `agent/llm_client.py` — `LLMClient.generate(prompt, system)`: no modificar
- `agent/ast_extractor.py` — `extract(files, repo_path)`: re-derivar firmas del módulo en `autocorrect()`
- `prompts/prompt_builder.py` — agregar `CorrectionPromptTemplate`; `clean_response()` disponible; `_REGISTRY` donde registrar el nuevo template

### Código paralelo de referencia
- `agent/test_generator.py` — patrón de subprocess, `_write_conftest()`, validación con `ast.parse()` + 1 reintento
- `agent/integration_generator.py` — patrón de IntegrationPromptTemplate (firmas en vez de código completo), `_find_pairs()`, `_write_conftest()`
- `.planning/phases/03-generacion-de-tests-de-integracion/03-CONTEXT.md` — D-03/D-04 (IntegrationPromptTemplate) es el patrón exacto para `CorrectionPromptTemplate`
- `.planning/phases/02-generacion-de-tests-unitarios/02-CONTEXT.md` — D-05..D-08 (validación con ast.parse + 1 reintento)

### Punto de entrada
- `agent.py` — donde se conectan las dos llamadas: `test_runner.run()` → `autocorrector.autocorrect()`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LLMClient.generate(prompt, system)` — listo para usar sin modificar
- `clean_response(response)` — limpia markdown y texto explicativo del output del LLM
- `ast_extractor.extract()` — devuelve firmas de funciones/clases + imports; reutilizar en `autocorrect()` para obtener firmas del módulo bajo test
- Patrón `subprocess.run([sys.executable, '-m', 'pytest', ...]` — ya conocido del proyecto (se usa en tests del agente)

### Established Patterns
- Sin dependencias externas: solo stdlib (`pathlib`, `ast`, `subprocess`, `re`) + módulos del propio agente
- Commit por HU: `feat: HU-07 - <desc>` y `feat: HU-08 - <desc>` + actualización de `context/marco_teorico_notas.md`
- Tests del agente en `tests/`, output del agente en `tests_generados/` (nunca mezclar)
- Módulo expone una función pública principal: `run()` para test_runner, `autocorrect()` para autocorrector
- Validación con `ast.parse()` antes de escribir código generado/corregido al disco

### Integration Points
- `test_runner.run(tests_dir)` recibe la ruta a `tests_generados/` y devuelve el dict de resultados
- `autocorrector.autocorrect(results, repo_path)` recibe el dict del runner y la ruta al repo analizado
- `agent.py` conecta los dos módulos en secuencia tras la generación de tests

</code_context>

<specifics>
## Specific Ideas

- El prompt de corrección incluye explícitamente: "Return only the corrected test function, no explanations." — mismo estilo directivo que los prompts existentes.
- El test_id completo (`path/file.py::test_nombre`) es suficiente para que pytest re-corra un test individual en el paso de verificación.
- La inferencia del módulo bajo test desde el test_id: `test_calculadora.py` → buscar `calculadora.py` en `repo_path`. Convención `test_<stem>.py` → `<stem>.py` ya establecida por `test_generator.py`.

</specifics>

<deferred>
## Deferred Ideas

- Re-correr la suite completa al final para detectar si una corrección rompió tests que antes pasaban → Fase 5 (o puede hacerse en el reporte).
- Caché de correcciones para no re-corregir tests idénticos en ejecuciones sucesivas → QUAL-01 (v2).
- Timeout configurable por test en el runner → v2.

</deferred>

---

*Phase: 4-Ejecución y Autocorrección*
*Context gathered: 2026-05-04*
