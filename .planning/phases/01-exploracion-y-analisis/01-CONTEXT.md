# Phase 1: Exploración y Análisis - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

El agente recorre un repositorio Python, lista todos sus archivos `.py` ignorando directorios del sistema (`__pycache__`, `.git`, `venv`, `dist`), y produce un diccionario unificado con la estructura completa de funciones, clases e imports de cada archivo. Esta estructura es el contrato de datos que las Fases 2 y 3 consumen directamente.

**Dos módulos nuevos:**
- `agent/repo_explorer.py` — HU-03: recorrido de filesystem, lista de paths relativos
- `agent/ast_extractor.py` — HU-04: análisis AST, detección de imports, fragmentación

</domain>

<decisions>
## Implementation Decisions

### Responsabilidad de imports (EXPL-03)
- **D-01:** `repo_explorer.py` es puramente filesystem — recibe un path de repositorio y devuelve una lista de rutas relativas a archivos `.py`. No lee el contenido de los archivos.
- **D-02:** `ast_extractor.py` detecta los imports entre módulos del mismo repositorio junto con el análisis AST completo. Todo el trabajo de parse vive en un solo lugar.

### Clases y métodos (ANLS-01, ANLS-02)
- **D-03:** Las clases se extraen con `type: 'class'` y tienen una sub-lista `methods` con sus métodos individuales (nombre, params, docstring). Los métodos son ciudadanos de primera clase para que el generador de tests (HU-05) los reciba como unidades testeables.
- **D-04:** Las funciones top-level se extraen con `type: 'function'`. Ambos tipos conviven en la lista `functions` del archivo (o separados como `functions` y `classes` — ver D-07).

### Estrategia de fragmentación (ANLS-03)
- **D-05:** Fragmentación inteligente por función/clase completa usando AST para agrupar. El extractor agrupa funciones/clases en fragmentos que no superen ~200 líneas. Nunca corta una unidad sintáctica al medio.
- **D-06:** Cada fragmento siempre contiene unidades completas y es parseable independientemente. Una función que por sí sola supera 200 líneas forma su propio fragmento.

### Estructura de datos unificada (ANLS-02 + EXPL-03)
- **D-07:** `ast_extractor.extract()` devuelve un dict unificado por archivo como clave (ruta relativa al repo):
  ```python
  {
    'pkg/mod_a.py': {
      'functions': [
        {'name': 'sumar', 'type': 'function', 'params': ['a', 'b'], 'docstring': ''}
      ],
      'classes': [
        {
          'name': 'Calculadora',
          'type': 'class',
          'docstring': '',
          'methods': [
            {'name': 'sumar', 'params': ['self', 'a', 'b'], 'docstring': ''}
          ]
        }
      ],
      'imports': ['pkg/mod_b']  # solo imports que referencian otros módulos del repo
    }
  }
  ```
- **D-08:** El campo `imports` contiene únicamente imports de módulos del mismo repositorio (no stdlib, no third-party). Se filtra comparando contra la lista de paths conocidos del repo.

### Claude's Discretion
- Convención de nombres de archivos de test generados (`test_<nombre_archivo>.py`) — consistente con lo ya definido en REQUIREMENTS.md TGEN-02.
- Manejo de archivos con errores de sintaxis: el extractor puede silenciar el error y devolver `{'functions': [], 'classes': [], 'imports': [], 'parse_error': '...'}` para no bloquear el flujo.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos y roadmap
- `.planning/REQUIREMENTS.md` §EXPL-01..03, ANLS-01..03 — requisitos concretos de esta fase con criterios de aceptación
- `.planning/ROADMAP.md` §Fase 1 — criterios de éxito y planes (HU-03, HU-04)

### Código existente que los módulos nuevos deben ser compatibles con
- `agent/llm_client.py` — cliente HTTP ya implementado; los nuevos módulos pueden importarlo
- `prompts/prompt_builder.py` — espera `code` (str), `function_name` (str), `module_name` (str); la estructura de extracción debe producir estos campos para cada función/método
- `examples/calculadora.py` — archivo de referencia: 5 funciones top-level, sin clases, <200 líneas; criterio de éxito #2 del roadmap usa este archivo

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/llm_client.py` (`LLMClient.generate`, `LLMClient.is_available`): ya implementado y testeado; los módulos nuevos lo importan directamente
- `prompts/prompt_builder.py` (`PromptBuilder.build`, `clean_response`): compatible con cualquier función extraída si se pasan `code`, `function_name`, `module_name`

### Established Patterns
- Sin dependencias externas: solo stdlib de Python. El extractor debe usar `ast`, `os`, `pathlib` — nada de pip.
- Estructura de módulo: cada archivo en `agent/` expone una función o clase principal. `llm_client.py` expone `LLMClient`; siguiendo el patrón, `repo_explorer.py` expondrá `explore(repo_path)` y `ast_extractor.py` expondrá `extract(files, repo_path)`.

### Integration Points
- `agent.py` llamará `explore()` → `extract()` en secuencia. La salida de `explore()` (lista de paths) es la entrada de `extract()`.
- El dict unificado que devuelve `extract()` es lo que `test_generator.py` (HU-05) consumirá para iterar funciones/métodos.

</code_context>

<specifics>
## Specific Ideas

- El criterio de éxito #2 del roadmap es concreto: `{ "examples/calculadora.py": [{"name": "sumar", "params": [...], "docstring": "..."}, ...] }`. El formato exacto debe matchear esto (o ser equivalente con la separación `functions`/`classes`).
- El criterio de éxito #1: `agent.py --repo ./examples` lista `examples/calculadora.py` sin incluir `__pycache__`, `.git` ni `venv`.
- El criterio de éxito #3: un archivo >200 líneas se procesa en fragmentos sin error — se necesita al menos un archivo de prueba de >200 líneas para validar esto.

</specifics>

<deferred>
## Deferred Ideas

- Caché de resultados del extractor para evitar reprocesar archivos no modificados → v2 (QUAL-01 en REQUIREMENTS.md)
- Soporte para repositorios con estructura `src/` → v2 (QUAL-02)

</deferred>

---

*Phase: 1-Exploración y Análisis*
*Context gathered: 2026-05-02*
