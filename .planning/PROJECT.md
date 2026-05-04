# Local-Test-Agent

## What This Is

Agente CLI local que analiza repositorios Python y genera automáticamente tests unitarios e
de integración usando un LLM local (Ollama + DeepSeek Coder 6.7b). No requiere conexión a
internet ni servicios en la nube. Orientado a desarrolladores Linux que trabajan con Python.

## Core Value

Un solo comando (`python3 agent.py --repo ./path`) analiza cualquier repositorio Python y
produce tests listos para correr con pytest, completamente offline.

## Requirements

### Validated

- ✓ Estructura de proyecto y repositorio GitHub — HU-00
- ✓ Cliente LLM local: `agent/llm_client.py` conecta con la API HTTP de Ollama — HU-01
- ✓ Constructor de prompts: `prompts/prompt_builder.py` con templates estrictos para pytest — HU-02
- ✓ Exploración automática de repositorio — `agent/repo_explorer.py` — HU-03 (Fase 1)
- ✓ Extracción AST — `agent/ast_extractor.py` — HU-04 (Fase 1)
- ✓ Generación de tests unitarios — `agent/test_generator.py`, TGEN-01/02/03 — HU-05 (Fase 2)
- ✓ Generación de tests de integración — `agent/integration_generator.py`, `IntegrationPromptTemplate`, INTG-01/02/03 — HU-06 (Fase 3)

### Active

- [ ] **HU-07**: Ejecución automática de tests — correr pytest, capturar stdout/stderr, registrar passed/failed/error (Fase 4)
- [ ] **HU-08**: Autocorrección de tests fallidos — enviar test + error al LLM y pedir versión corregida, máximo 3 intentos por test (Fase 4)
- [ ] **HU-09**: Reporte de resultados — generar `reporte.md` con resumen de passed/failed/sin resolver y tiempo total de ejecución (Fase 5)
- [ ] **HU-10**: CLI completa — `python3 agent.py --repo ./path` ejecuta el flujo completo de extremo a extremo (Fase 5)

### Out of Scope

- Soporte para Windows/macOS — el proyecto apunta a Linux (Debian/Ubuntu); otras plataformas agregan complejidad sin beneficio para el público objetivo
- APIs de LLM en la nube (OpenAI, Anthropic, etc.) — el requisito central es funcionamiento 100% offline
- Soporte para lenguajes distintos de Python — el análisis AST y los prompts están optimizados para Python
- UI gráfica o web — la interfaz es CLI; añadir GUI excede el alcance del proyecto
- CI/CD integrado — los tests generados se revisan manualmente antes de incorporarlos a pipelines

## Context

- **Current State:** Fase 3 completa — `integration_generator.generate()` en producción, 52/52 tests del agente pasan; tests unitarios e integración generados para `examples/`
- **Repositorio activo**: rama `feature/HU-06-integration-test-generator`
- **Modelo LLM**: DeepSeek Coder 6.7b vía Ollama (API local HTTP en `localhost:11434`); ocupa ~4 GB de RAM con cuantización Q4
- **Ejemplo de referencia**: `examples/calculadora.py` — calculadora simple usada para validar cada HU
- **Notas de diseño**: `context/marco_teorico_notas.md` — se actualiza después de cada HU con qué se hizo, por qué y qué conceptos teóricos aplican
- **Tests del propio agente**: `tests/` — separados de los tests generados (`tests_generados/`)
- **Sin dependencias externas actuales** — usa solo stdlib de Python más pytest para correr los tests generados

## Constraints

- **Runtime**: Python 3.10+ en Linux (Debian/Ubuntu)
- **LLM**: Ollama debe estar corriendo localmente; el agente falla si Ollama no responde
- **Hardware mínimo**: 8 GB de RAM (4 GB libres para el modelo)
- **Offline**: cero llamadas a servicios externos en la ruta crítica
- **Fragmentación**: archivos Python de más de 200 líneas deben procesarse en fragmentos para no exceder el contexto del modelo
- **Reintentos**: máximo 3 intentos de autocorrección por test fallido (HU-08)
- **Workflow de desarrollo**: después de cada HU, commit con mensaje correspondiente y actualización de `context/marco_teorico_notas.md`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Ollama + DeepSeek Coder 6.7b como LLM | Equilibrio entre calidad de código generado, tamaño del modelo (~4 GB) y compatibilidad offline | — Pending |
| AST de Python stdlib para extracción | Sin dependencias externas; acceso directo a la estructura sintáctica del código | — Pending |
| pytest como framework de tests | Estándar de facto en el ecosistema Python; amplia documentación y plugins | — Pending |
| Fragmentación a 200 líneas | Evita exceder el contexto del modelo sin perder demasiado contexto por fragmento | — Pending |
| Separar `tests/` de `tests_generados/` | Los tests del agente no se mezclan con la salida del agente | — Pending |

## Evolution

Este documento evoluciona en cada transición de fase y milestone.

**Después de cada HU completada** (via `/gsd-transition`):
1. ¿Requisitos invalidados? → Mover a Out of Scope con motivo
2. ¿Requisitos validados? → Mover a Validated con referencia de HU
3. ¿Nuevos requisitos emergieron? → Agregar a Active
4. ¿Decisiones a registrar? → Agregar a Key Decisions
5. ¿"What This Is" sigue siendo preciso? → Actualizar si deriva

**Después de cada milestone** (via `/gsd-complete-milestone`):
1. Revisión completa de todas las secciones
2. Check de Core Value — ¿sigue siendo la prioridad correcta?
3. Auditoría de Out of Scope — ¿los motivos siguen siendo válidos?
4. Actualizar Context con estado actual

---
*Last updated: 2026-05-03 after Phase 3 completion*
