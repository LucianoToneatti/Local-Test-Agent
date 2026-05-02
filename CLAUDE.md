# Local-Test-Agent — Guía de trabajo para Claude

## Proyecto

Agente CLI local que analiza repositorios Python y genera tests con un LLM local (Ollama + DeepSeek Coder 6.7b). Sin internet. Sin servicios en la nube.

Ver contexto completo en `.planning/PROJECT.md`.

## Flujo de trabajo GSD

Este proyecto usa el framework GSD (Get Shit Done). Los artefactos de planificación viven en `.planning/`.

```
.planning/
├── PROJECT.md        # Contexto del proyecto (qué, por qué, quién)
├── config.json       # Preferencias de flujo de trabajo
├── REQUIREMENTS.md   # Requisitos v1 con REQ-IDs
├── ROADMAP.md        # 5 fases con criterios de éxito
└── STATE.md          # Estado actual del proyecto
```

**Fase actual:** Fase 1 — Exploración y Análisis (HU-03, HU-04)

**Comandos GSD disponibles:**
- `/gsd-plan-phase 1` — Crear plan detallado para la Fase 1
- `/gsd-discuss-phase 1` — Discutir el enfoque antes de planificar

## Convenciones del proyecto

### Después de cada HU completada
1. Commitear con el mensaje correspondiente: `feat: HU-0X - <descripción breve>`
2. Actualizar `context/marco_teorico_notas.md` con:
   - Qué se implementó
   - Por qué se tomaron las decisiones clave
   - Qué conceptos teóricos aplican (AST, pytest, Ollama API, etc.)

### Stack técnico
- **Python 3.10+** — sin dependencias externas salvo `pytest`
- **`ast` stdlib** — para extracción de funciones/clases
- **Ollama HTTP API** — `localhost:11434/api/generate`
- **DeepSeek Coder 6.7b** — modelo LLM local
- **pytest** — framework de tests generados y del agente

### Estructura de archivos del agente
```
agent/
├── llm_client.py          # ✓ Cliente HTTP para Ollama (HU-01)
├── repo_explorer.py        # ← HU-03 (próximo)
├── ast_extractor.py        # ← HU-04
├── test_generator.py       # ← HU-05
├── integration_generator.py # ← HU-06
├── test_runner.py          # ← HU-07
├── autocorrector.py        # ← HU-08
└── report_generator.py     # ← HU-09

prompts/
└── prompt_builder.py       # ✓ Templates de prompts (HU-02)

agent.py                    # Punto de entrada (refactor completo en HU-10)
```

### Fragmentación de archivos grandes
Archivos Python de más de 200 líneas deben procesarse en fragmentos para no exceder el contexto del modelo. Esta es una restricción de diseño explícita.

### Tests generados vs tests del agente
- `tests/` — tests del propio agente (pytest sobre el código del agente)
- `tests_generados/` — output del agente (tests generados sobre repositorios analizados)

Nunca mezclar estos dos directorios.
