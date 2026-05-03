# Requirements: Local-Test-Agent

**Definido:** 2026-05-02
**Core Value:** Un solo comando analiza cualquier repositorio Python y produce tests listos para pytest, completamente offline.

## Requisitos Validados (HU completadas)

Ya implementadas y comprometidas en el repositorio.

### Fundación

- ✓ **FOUND-01**: Estructura de proyecto con directorios `agent/`, `prompts/`, `tests/`, `tests_generados/unit/`, `tests_generados/integration/`, `context/`, `docs/` — HU-00
- ✓ **FOUND-02**: El agente se conecta a Ollama vía HTTP (`localhost:11434`) y obtiene respuestas del modelo DeepSeek Coder 6.7b — HU-01 (`agent/llm_client.py`)
- ✓ **FOUND-03**: El sistema construye prompts con templates estrictos para pytest y limpia la respuesta del LLM para extraer código Python válido — HU-02 (`prompts/prompt_builder.py`)

## v1 Requirements

Scope comprometido para esta iteración. Mapean a las fases del roadmap.

### Exploración de Repositorio

- [ ] **EXPL-01**: El agente lista recursivamente todos los archivos `.py` de un repositorio dado, ignorando `__pycache__`, `.git`, `venv` y `dist` — HU-03
- [ ] **EXPL-02**: El resultado de la exploración es una lista estructurada con rutas relativas al repositorio analizado — HU-03
- [ ] **EXPL-03**: La exploración identifica imports entre módulos del repositorio para detectar relaciones entre archivos — HU-06 (prerequisito)

### Análisis de Código (AST)

- [ ] **ANLS-01**: El agente extrae nombres, parámetros y docstrings de todas las funciones y clases de cada archivo `.py` usando el módulo `ast` de Python stdlib — HU-04
- [ ] **ANLS-02**: El resultado del análisis es un diccionario estructurado como `{ archivo: [lista de funciones/clases] }` — HU-04
- [ ] **ANLS-03**: Archivos de más de 200 líneas se procesan en fragmentos para no exceder el contexto del modelo — HU-04

### Generación de Tests Unitarios

- [ ] **TGEN-01**: Para cada función extraída, el agente genera al menos 2 casos de test (happy path + edge case) usando el LLM — HU-05
- [ ] **TGEN-02**: Los tests unitarios generados son archivos `.py` válidos con formato pytest, guardados en `tests_generados/unit/test_<nombre_archivo>.py` — HU-05
- [ ] **TGEN-03**: Cada test generado incluye un `conftest.py` que agrega el directorio del repositorio al `sys.path` — HU-05

### Generación de Tests de Integración

- [ ] **INTG-01**: El agente identifica pares de módulos relacionados a partir de los imports entre archivos del repositorio — HU-06
- [ ] **INTG-02**: Para cada par de módulos relacionados, el agente genera al menos 1 test de integración que valida la interacción entre ellos — HU-06
- [ ] **INTG-03**: Los tests de integración se guardan en `tests_generados/integration/test_<modulo_a>_<modulo_b>.py` — HU-06

### Ejecución de Tests

- [ ] **EXEC-01**: El agente corre pytest automáticamente sobre los tests generados y captura stdout y stderr — HU-07
- [ ] **EXEC-02**: El agente registra el resultado de cada test (passed / failed / error) — HU-07
- [ ] **EXEC-03**: Si un test falla, el agente envía el test + el mensaje de error al LLM y solicita una versión corregida — HU-08
- [ ] **EXEC-04**: El proceso de autocorrección tiene un máximo de 3 intentos por test; si tras 3 intentos sigue fallando, se marca como "sin resolver" — HU-08

### Reporte de Resultados

- [ ] **REPO-01**: El agente genera `reporte.md` con el resumen de passed, failed y tests sin resolver — HU-09
- [ ] **REPO-02**: El reporte incluye el tiempo total de ejecución — HU-09

### CLI

- [ ] **CLI-01**: El comando `python3 agent.py --repo ./path` ejecuta el flujo completo de extremo a extremo: exploración → análisis → generación → ejecución → autocorrección → reporte — HU-10
- [ ] **CLI-02**: La CLI informa el progreso al usuario en la terminal durante la ejecución — HU-10

## v2 Requirements

Reconocidos pero diferidos. No están en el roadmap actual.

### Calidad y Robustez

- **QUAL-01**: Caché de resultados del LLM para evitar reprocesar funciones no modificadas
- **QUAL-02**: Soporte para repositorios con múltiples sub-paquetes o estructura `src/`
- **QUAL-03**: Configuración por archivo (`.local-test-agent.toml`) para excluir funciones o módulos

### Extensibilidad

- **EXT-01**: Soporte para modelos LLM alternativos (llama3, codellama, etc.) vía parámetro de CLI
- **EXT-02**: Soporte para frameworks de test alternativos (unittest)

## Out of Scope

| Feature | Motivo |
|---------|--------|
| Windows / macOS | El proyecto apunta a Linux; otras plataformas agregan complejidad sin beneficio para el público objetivo |
| APIs de LLM en la nube | El requisito central es funcionamiento 100% offline |
| Lenguajes distintos de Python | El análisis AST y los prompts están optimizados para Python |
| UI gráfica o web | La interfaz es CLI; GUI excede el alcance |
| Integración con CI/CD | Los tests generados se revisan manualmente antes de incorporarlos a pipelines |

## Trazabilidad

Actualizada durante la creación del roadmap.

| Requisito | Fase | Estado |
|-----------|------|--------|
| FOUND-01 | Validado | Completo |
| FOUND-02 | Validado | Completo |
| FOUND-03 | Validado | Completo |
| EXPL-01 | Fase 1 | Pending |
| EXPL-02 | Fase 1 | Pending |
| EXPL-03 | Fase 1 | Pending |
| ANLS-01 | Fase 1 | Pending |
| ANLS-02 | Fase 1 | Pending |
| ANLS-03 | Fase 1 | Pending |
| TGEN-01 | Fase 2 | Pending |
| TGEN-02 | Fase 2 | Pending |
| TGEN-03 | Fase 2 | Pending |
| INTG-01 | Fase 2 | Pending |
| INTG-02 | Fase 2 | Pending |
| INTG-03 | Fase 2 | Pending |
| EXEC-01 | Fase 3 | Pending |
| EXEC-02 | Fase 3 | Pending |
| EXEC-03 | Fase 3 | Pending |
| EXEC-04 | Fase 3 | Pending |
| REPO-01 | Fase 4 | Pending |
| REPO-02 | Fase 4 | Pending |
| CLI-01 | Fase 4 | Pending |
| CLI-02 | Fase 4 | Pending |

**Cobertura:**
- Requisitos v1: 20 total
- Mapeados a fases: 20
- Sin mapear: 0 ✓

---
*Requirements definidos: 2026-05-02*
*Last updated: 2026-05-02 after initial definition*
