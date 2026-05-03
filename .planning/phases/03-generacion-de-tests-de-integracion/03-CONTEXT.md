# Phase 3: Generación de Tests de Integración - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

El agente consume el campo `imports` del dict producido por `ast_extractor.extract()`, identifica los pares de módulos relacionados por imports, llama al LLM una vez por par para generar un test de integración, valida el output con `ast.parse()` y escribe `tests_generados/integration/test_<modA>_<modB>.py` más un `conftest.py` con el `sys.path` configurado.

**Un módulo nuevo:** `agent/integration_generator.py`
**Un template nuevo:** `IntegrationPromptTemplate` en `prompts/prompt_builder.py`
**Un archivo de ejemplo nuevo:** `examples/estadistica.py`

</domain>

<decisions>
## Implementation Decisions

### Repositorio de ejemplo (INTG-01)
- **D-01:** Se crea `examples/estadistica.py` con funciones como `promedio()` y `varianza()` que **usan internamente** funciones de `calculadora.py` (`sumar`, `multiplicar`). El import en estadistica.py referencia al módulo del mismo directorio: `from calculadora import sumar, multiplicar`.
- **D-02:** Este par `(calculadora, estadistica)` es el caso de uso de referencia para validar todos los criterios de éxito de la Fase 3.

### Contenido del prompt de integración (INTG-02)
- **D-03:** El prompt le pasa al LLM el **código fuente completo del módulo A** (el que importa) más las **firmas** (nombre + parámetros) de las funciones del módulo B (el importado). No se envía el cuerpo de B para acotar el tamaño del prompt.
- **D-04:** El template `IntegrationPromptTemplate` se agrega a `prompts/prompt_builder.py` como nueva subclase de `PromptTemplate`, registrada en `_REGISTRY` con `language="python_integration"`. Sigue el mismo patrón que `PythonPromptTemplate`.

### Qué valida el test generado (INTG-02)
- **D-05:** El system prompt le instruye al LLM que genere tests que **verifiquen que el módulo A puede llamar funciones del módulo B y obtener el resultado esperado** — asserts con valores concretos (ej: `assert estadistica.promedio([1, 2, 3]) == 2.0`). No alcanza con verificar que el import no falla.
- **D-06:** El LLM infiere valores de prueba razonables a partir del código de ambos módulos. Si el LLM genera valores incorrectos, la Fase 4 (autocorrección) los corregirá.

### conftest.py para integration/ (INTG-03)
- **D-07:** `integration_generator.py` genera un `conftest.py` propio en `tests_generados/integration/` con la ruta absoluta del repositorio analizado en `sys.path`. Mismo patrón que `test_generator.py` para `tests_generados/unit/`. Cada subdirectorio de `tests_generados/` es autosuficiente.

### Validación y reintentos
- **D-08:** Después de `clean_response()`, se valida con `ast.parse()`. Si falla → 1 reintento. Si el segundo intento también falla → escribe comentario de error `# ERROR: no se pudo generar test de integración para <modA>_<modB>` y continúa. Mismo comportamiento que HU-05 (D-05/D-06 de Fase 2).

### Claude's Discretion
- Nombre del par en el archivo de tests: `test_<stem_A>_<stem_B>.py` donde A es el módulo que importa y B el importado. Si hay múltiples dependencias (A importa B y C), se genera un archivo por par: `test_A_B.py` y `test_A_C.py`.
- Función pública principal: `generate(repo_path, ast_result)` — misma firma que `test_generator.generate()`.
- Orden de las funciones de test dentro del archivo: libre.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos y roadmap
- `.planning/REQUIREMENTS.md` §INTG-01..03 — criterios de aceptación de tests de integración
- `.planning/ROADMAP.md` §Fase 3 — criterios de éxito (3 criterios concretos)

### Código existente que integration_generator.py consume directamente
- `agent/ast_extractor.py` — `extract()` devuelve `{rel_path: {functions, classes, imports}}`; el campo `imports` es una lista de rutas relativas a otros módulos del repo que este archivo importa
- `agent/llm_client.py` — `LLMClient.generate(prompt, system)`: no modificar
- `prompts/prompt_builder.py` — agregar `IntegrationPromptTemplate`; `clean_response()` ya disponible; `_REGISTRY` donde registrar el nuevo template

### Código paralelo de referencia
- `agent/test_generator.py` — patrón exacto a replicar: `generate(repo_path, ast_result)`, `_write_conftest()`, validación con `ast.parse()` + 1 reintento
- `.planning/phases/02-generacion-de-tests-unitarios/02-CONTEXT.md` — decisiones D-05..D-08 que esta fase replica para integración

### Archivo de ejemplo de referencia
- `examples/calculadora.py` — módulo B (importado); 5 funciones top-level
- `examples/estadistica.py` — módulo A (importador, a crear en HU-06); usa sumar/multiplicar de calculadora

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LLMClient.generate(prompt, system)` — listo para usar sin modificar
- `clean_response(response)` — limpia markdown y texto explicativo del output del LLM
- `_write_conftest(repo)` de `test_generator.py` — copiar/adaptar para `integration_generator.py`
- `ast_extractor.extract()['imports']` — ya contiene la lista de módulos del repo que cada archivo importa; no requiere trabajo adicional de extracción

### Established Patterns
- Sin dependencias externas: solo stdlib (`pathlib`, `ast`) + módulos del propio agente
- Commit por HU: `feat: HU-06 - <desc>` + actualización de `context/marco_teorico_notas.md`
- Tests del agente en `tests/`, output del agente en `tests_generados/` (nunca mezclar)
- Módulo expone `generate(repo_path, ast_result)` como función pública principal

### Integration Points
- `integration_generator.py` recibe el mismo dict que `test_generator.py` — no hay dependencia entre HU-05 y HU-06 en runtime, solo comparten el formato de entrada
- Escribe en `tests_generados/integration/test_<stemA>_<stemB>.py`
- Escribe `tests_generados/integration/conftest.py` con sys.path del repo analizado
- `prompts/prompt_builder.py` necesita un nuevo template `IntegrationPromptTemplate` — modificación acotada al registro en `_REGISTRY`

</code_context>

<specifics>
## Specific Ideas

- El par se forma con `(módulo_importador, módulo_importado)`. Si A importa B, el test se llama `test_A_B.py` (A es el punto de entrada del test — llama funciones de A que internamente usan B).
- El prompt de integración recibe: (1) código completo de A, (2) solo firmas de B (nombre + params), (3) lista de imports que A hace de B.
- El system prompt para integración debe decir explícitamente: "Generate pytest integration tests that call functions from module A (which uses module B internally). Use concrete assert values."
- `examples/estadistica.py` debe tener al menos 2 funciones que usen calculadora: `promedio(lista)` y `varianza(lista)` o similar. Esto garantiza que el test generado tenga al menos 2 casos de prueba.

</specifics>

<deferred>
## Deferred Ideas

- Pares bidireccionales (A importa B y B importa A) → comportamiento en v1: se genera un test por dirección si hay imports en ambas direcciones. Si resulta redundante, v2 puede deduplicar.
- Repos con más de 2 módulos relacionados en cadena (A → B → C): en v1 se generan solo pares directos (A-B y B-C), no triplas.
- Template separado por tipo de interacción (clase vs. función libre) → v2 si se necesita.

</deferred>

---

*Phase: 3-Generación de Tests de Integración*
*Context gathered: 2026-05-03*
