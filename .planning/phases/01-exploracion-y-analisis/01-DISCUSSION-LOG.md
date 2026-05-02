# Phase 1: Exploración y Análisis - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 1-Exploración y Análisis
**Areas discussed:** Responsabilidad de imports, Clases y métodos, Estrategia de fragmentación, Estructura de datos unificada

---

## Responsabilidad de imports

| Option | Description | Selected |
|--------|-------------|----------|
| ast_extractor | repo_explorer solo lista paths; ast_extractor detecta imports junto con el análisis AST completo | ✓ |
| repo_explorer (pre-parse rápido) | El explorador hace un scan rápido de imports; el extractor hace el parse profundo. Dos pasadas separadas. | |
| Vos decidís | Delegar la separación al planner | |

**User's choice:** ast_extractor  
**Notes:** Todo el trabajo de parse vive en un solo lugar. repo_explorer es puramente filesystem.

---

## Clases y métodos

| Option | Description | Selected |
|--------|-------------|----------|
| Clase + métodos como sub-items | La clase tiene su propio item con nombre y docstring, y sus métodos aparecen como sub-lista | ✓ |
| Solo funciones top-level | El extractor ignora clases o las registra solo con nombre. Más simple. | |
| Métodos aplanados como funciones | Los métodos se exponen al mismo nivel con prefijo 'ClassName.method_name' | |

**User's choice:** Clase + métodos como sub-items  
**Notes:** PromptBuilder puede recibir el método individualmente para generar tests de cada uno.

---

## Estrategia de fragmentación

| Option | Description | Selected |
|--------|-------------|----------|
| Por función/clase completa | Agrupa funciones/clases en fragmentos ≤200 líneas usando AST. Nunca corta una unidad al medio. | ✓ |
| Por bloque de líneas fijo | Exactamente 200 líneas por fragmento. Puede cortar una función al medio. | |

**User's choice:** Por función/clase completa  
**Notes:** Fragmentación inteligente; cada fragmento es siempre parseable independientemente.

---

## Estructura de datos unificada

| Option | Description | Selected |
|--------|-------------|----------|
| Dict unificado por archivo | `{ 'path.py': { 'functions': [...], 'classes': [...], 'imports': [...] } }` | ✓ |
| Estructuras separadas | repo_explorer devuelve lista de paths; ast_extractor devuelve el dict; agent.py los combina | |

**User's choice:** Dict unificado por archivo  
**Notes:** Un solo objeto por archivo. Consumo directo para el generador de tests en Fases 2 y 3.

---

## Claude's Discretion

- Manejo de archivos con errores de sintaxis: devolver estructura con `parse_error` en lugar de abortar el flujo.
- Filtrado de imports: solo imports que referencian módulos del mismo repo (excluir stdlib y third-party).

## Deferred Ideas

- Caché de resultados del extractor (evitar reprocesar archivos no modificados) → v2 QUAL-01
- Soporte para estructura `src/` → v2 QUAL-02
