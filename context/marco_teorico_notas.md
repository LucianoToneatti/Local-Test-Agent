# Marco Teórico y Notas de Diseño

Archivo vivo: se actualiza al completar cada historia de usuario.

---

## Decisiones de diseño

> _Completar a medida que se tomen decisiones arquitectónicas._

| Decisión | Alternativas consideradas | Razón de la elección |
|----------|--------------------------|----------------------|
|          |                          |                      |

---

## Justificaciones técnicas

> _Documentar por qué se eligió cada tecnología o enfoque._

### LLM local: Ollama + DeepSeek Coder 6.7b

- **Por qué local:** privacidad del código fuente, funcionamiento offline, sin costo por token.
- **Por qué DeepSeek Coder:** buena relación tamaño/rendimiento para generación de código Python; corre en hardware de consumo.
- **Por qué 6.7b:** equilibrio entre calidad de salida y requerimientos de VRAM (~8 GB).

---

## Notas por historia de usuario

> _Una sección por historia de usuario completada. Formato sugerido:_
>
> ### HU-XX: Nombre
> - **Qué se hizo:**
> - **Por qué esta solución:**
> - **Conceptos teóricos que aplican:**
> - **Deuda técnica / pendientes:**

### HU-01: Estructura inicial del proyecto

- **Qué se hizo:** se crearon las carpetas base (`agent/`, `prompts/`, `tests_generados/`, `tests/`, `docs/`, `context/`), el punto de entrada `agent.py`, `.gitignore` y `README.md`.
- **Por qué esta solución:** separación clara de responsabilidades desde el inicio; `tests_generados/` dividido en `unit/` e `integration/` para facilitar el filtrado posterior.
- **Conceptos teóricos que aplican:** estructura de proyecto Python estándar, principio de separación de incumbencias.
- **Deuda técnica / pendientes:** completar pasos de instalación en README cuando se definan las dependencias.
