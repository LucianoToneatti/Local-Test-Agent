# Phase 2: Generación de Tests Unitarios - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

El agente genera archivos pytest válidos a partir del diccionario estructurado producido por la Fase 1. Para cada función top-level y cada método de clase en el repositorio analizado, llama al LLM (función por función), limpia y valida el output, y escribe un archivo `tests_generados/unit/test_<nombre_archivo>.py` más un `conftest.py` con el `sys.path` configurado.

**Un módulo nuevo:** `agent/test_generator.py`

</domain>

<decisions>
## Implementation Decisions

### Granularidad del LLM (TGEN-01)
- **D-01:** El generador llama al LLM **una vez por función** (y una vez por método de clase). No envía el archivo completo. Reutiliza el `PromptBuilder` y `LLMClient` ya existentes sin refactorización de su interfaz.
- **D-02:** Para obtener el código fuente de cada función/método, `test_generator.py` **relee el archivo `.py` y slicéa por `_lineno`.._end_lineno`** (atributos ya presentes en el dict del extractor). No se modifica `ast_extractor.py`.

```python
source = Path(repo_path, rel_path).read_text()
lines = source.splitlines()
func_source = '\n'.join(lines[func['_lineno']-1:func['_end_lineno']])
```

### Clases y métodos (TGEN-01)
- **D-03:** HU-05 genera tests tanto para **funciones top-level** (`entry['functions']`) como para **métodos de clases** (`entry['classes'][*]['methods']`). Ambos son unidades testeables.
- **D-04:** Para adaptar el prompt a métodos de clases, se agrega un parámetro opcional `class_name` al template `PythonPromptTemplate` en `prompts/prompt_builder.py`. Si `class_name` está presente, el import del prompt cambia a `from {module_name} import {class_name}` y el contexto indica que se testa un método de instancia.

### Validación del output (TGEN-02)
- **D-05:** Después de `clean_response()`, se intenta `ast.parse(code)` sobre el output.
  - Si parsea OK → escribe el bloque de tests.
  - Si falla → **reintenta la llamada al LLM una vez**.
  - Si el segundo intento también falla → escribe un comentario de error en el archivo final: `# ERROR: no se pudo generar tests para <func_name>` y continúa con la siguiente función.
- **D-06:** Máximo **1 reintento** por función (no configurable en v1).

### conftest.py (TGEN-03)
- **D-07:** `test_generator.py` escribe un único `conftest.py` en `tests_generados/unit/` con la **ruta absoluta** del repositorio analizado en `sys.path`. Se regenera en cada ejecución (sobrescribe).

```python
# conftest.py generado
import sys
sys.path.insert(0, '/ruta/absoluta/al/repo/analizado')
```

- **D-08:** Un solo `conftest.py` global para toda la carpeta `unit/`. Si se analizan múltiples repos en secuencia, el último sobreescribe (comportamiento aceptable para v1).

### Claude's Discretion
- Nombre de la función pública en `test_generator.py`: libre, pero sugerido `generate(repo_path, ast_result)` donde `ast_result` es el dict de `extract()`.
- Orden de las funciones/métodos en el archivo de tests: el mismo orden que devuelve `extract()` (ya ordenado por nombre de archivo).
- Separadores entre bloques de tests por función: opcional, una línea en blanco entre bloques es suficiente.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos y roadmap
- `.planning/REQUIREMENTS.md` §TGEN-01..03 — criterios de aceptación de generación de tests unitarios
- `.planning/ROADMAP.md` §Fase 2 — criterios de éxito (4 criterios concretos con asserts)

### Código existente que test_generator.py consume directamente
- `agent/llm_client.py` — `LLMClient.generate(prompt, system)`: interfaz ya testeada; no modificar
- `prompts/prompt_builder.py` — `PromptBuilder.build(code, function_name, module_name)`: agregar parámetro `class_name` opcional; `clean_response()` ya disponible
- `agent/ast_extractor.py` — `extract(files, repo_path)` devuelve el dict; cada entrada tiene `_lineno` y `_end_lineno` para slicear fuente
- `agent/repo_explorer.py` — `explore(repo_path)`: usado upstream, no se llama desde test_generator.py

### Archivo de referencia para validar
- `examples/calculadora.py` — 5 funciones top-level, 0 clases, <200 líneas; criterio de éxito #1 del roadmap

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LLMClient.generate(prompt, system)` — listo para usar; acepta system prompt separado
- `PromptBuilder.build(code, function_name, module_name)` → `BuiltPrompt(system, user)` — reutilizar directamente; agregar `class_name` opcional
- `clean_response(response)` — ya limpia markdown y texto explicativo del output del LLM
- `ast_extractor.extract()` dict — tiene `_lineno`/`_end_lineno` para extraer fuente sin re-parsear el AST

### Established Patterns
- Sin dependencias externas: solo stdlib (`pathlib`, `ast`) + los módulos del propio agente
- Commit por HU con mensaje `feat: HU-0X - <desc>` + actualización de `context/marco_teorico_notas.md`
- Tests del agente en `tests/`, output del agente en `tests_generados/` (nunca mezclar)
- Módulo expone una función pública principal; bloque `if __name__ == "__main__"` para prueba manual

### Integration Points
- `test_generator.py` recibe el output de `extract()` (dict) y la ruta del repo
- Escribe en `tests_generados/unit/test_<stem>.py` donde `stem` es el nombre del archivo fuente sin extensión ni ruta
- Escribe `tests_generados/unit/conftest.py` con sys.path del repo analizado

</code_context>

<specifics>
## Specific Ideas

- El snippet de slicing de fuente confirmado por el usuario:
  ```python
  source = Path(repo_path, rel_path).read_text()
  lines = source.splitlines()
  func_source = '\n'.join(lines[func['_lineno']-1:func['_end_lineno']])
  ```
- El conftest.py confirmado por el usuario:
  ```python
  import sys
  sys.path.insert(0, '/ruta/al/repo/analizado')
  ```
- Para métodos de clases: el import en el prompt debe decir `from {module_name} import {class_name}`, no `import {method_name}`.

</specifics>

<deferred>
## Deferred Ideas

- Multi-repo con conftest.py por subdirectorio → v2 (más complejo, no necesario para v1)
- Template separado `PythonClassMethodPrompt` en lugar de parámetro opcional → v2 si se necesitan prompts muy distintos por tipo
- Más de 1 reintento al LLM para syntax errors → configurable en v2 (QUAL-03)

</deferred>

---

*Phase: 2-Generación de Tests Unitarios*
*Context gathered: 2026-05-02*
