# Marco Teórico y Notas de Diseño

Archivo vivo: se actualiza al completar cada historia de usuario.

---

## Decisiones de diseño

> _Completar a medida que se tomen decisiones arquitectónicas._

| Decisión | Alternativas consideradas | Razón de la elección |
|----------|--------------------------|----------------------|
| LLM local (Ollama) en lugar de API cloud | OpenAI API, Anthropic API | Privacidad del código, costo cero por token, funcionamiento offline |
| DeepSeek Coder 6.7b como modelo base | CodeLlama 7b, Mistral 7b | Mejor rendimiento en generación de código Python con hardware de consumo |
| `urllib` en lugar de `requests` en llm_client.py | `requests`, `httpx` | Sin dependencias externas para el cliente base; se puede reemplazar luego |
| `stream=False` en la llamada a Ollama | streaming línea por línea | Simplifica el manejo de respuesta; adecuado para prompts de test que no son interactivos |
| System prompt separado del user prompt | prompt único concatenado | La API de Ollama tiene un campo `system` dedicado; separarlos mejora la adherencia al rol y facilita reusar el system prompt entre distintas funciones |
| `_extract_function_name()` con regex sobre el código | AST de Python (`ast.parse`) | Más simple para el alcance actual; no requiere que el código sea sintácticamente perfecto para extraer el nombre |

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

### HU-00: Estructura inicial del proyecto

- **Qué se hizo:** se crearon las carpetas base (`agent/`, `prompts/`, `tests_generados/`, `tests/`, `docs/`, `context/`), el punto de entrada `agent.py`, `.gitignore` y `README.md`.
- **Por qué esta solución:** separación clara de responsabilidades desde el inicio; `tests_generados/` dividido en `unit/` e `integration/` para facilitar el filtrado posterior.
- **Conceptos teóricos que aplican:** estructura de proyecto Python estándar, principio de separación de incumbencias.
- **Deuda técnica / pendientes:** completar pasos de instalación en README cuando se definan las dependencias.

---

### HU-01: Configuración del modelo local

- **Qué se hizo:** se creó `agent/llm_client.py` con la clase `LLMClient` que se conecta a Ollama vía su API REST local (`http://localhost:11434`). Expone dos métodos: `generate(prompt, system)` que devuelve la respuesta del modelo como string, e `is_available()` que verifica que Ollama esté corriendo y el modelo esté descargado. Incluye un bloque `__main__` de prueba manual.

- **Por qué Ollama con modelo preentrenado en lugar de entrenar uno propio:**
  Entrenar un LLM desde cero requiere datasets masivos (cientos de GB de código), semanas de cómputo en GPUs de alta gama y expertise en ML. Los modelos preentrenados como DeepSeek Coder ya internalizaron patrones de código Python a partir de millones de repositorios. Ollama permite ejecutar esos modelos localmente con un simple `ollama pull`, sin costo, sin internet en tiempo de inferencia y sin exponer el código fuente a terceros. El rol del agente es construir prompts de calidad, no reentrenar el modelo.

- **Qué es la API local de Ollama y cómo funciona:**
  Ollama levanta un servidor HTTP en `localhost:11434` que actúa como proxy entre el cliente y el modelo GGUF cargado en memoria. El endpoint principal es `POST /api/generate`, que recibe un JSON con `model`, `prompt` y parámetros opcionales (`stream`, `system`, `temperature`, etc.). Con `stream: false` devuelve la respuesta completa en un único JSON con el campo `response`. También expone `GET /api/tags` para listar los modelos descargados, lo que usamos en `is_available()`.

- **Conceptos teóricos que aplican:** arquitectura cliente-servidor REST, modelos de lenguaje preentrenados (LLM), cuantización GGUF, inferencia local vs. cloud, separación entre cliente HTTP y lógica de negocio.

- **Deuda técnica / pendientes:** agregar timeout configurable en `generate()`, manejo de `temperature` y otros hiperparámetros, test unitario con mock de la API de Ollama.

---

### HU-02: Diseño del prompt base

- **Qué se hizo:** se creó `prompts/prompt_builder.py` con tres componentes:
  - `BuiltPrompt`: dataclass que empaqueta `system` (rol del modelo) y `user` (tarea concreta).
  - `PythonPromptTemplate`: template con system prompt de reglas estrictas y user prompt con el código embebido.
  - `PromptBuilder`: factory estática que resuelve el template por lenguaje usando un registro (`_REGISTRY`). Para agregar un nuevo lenguaje basta con registrar una nueva subclase, sin tocar el resto del código.
  - Función auxiliar `_extract_function_name()` que infiere el nombre de la función por regex cuando no se pasa explícitamente.
  - Bloque `__main__` con prueba de integración end-to-end: construye el prompt, lo envía al LLM y valida que la respuesta tenga `import pytest`, `def test_` y no tenga bloques markdown.

- **Qué es prompt engineering y por qué importa:**
  Prompt engineering es el proceso de diseñar la entrada textual al modelo para maximizar la calidad y consistencia de la salida. Los LLMs no "entienden" instrucciones con certeza; responden a patrones estadísticos aprendidos durante el entrenamiento. Un prompt mal formulado produce respuestas con texto explicativo, bloques markdown, imports faltantes o tests incompletos, lo que rompe el pipeline automático. Un prompt bien formulado actúa como una especificación de contrato: le dice al modelo exactamente qué formato de salida se espera, con cuánta cobertura y bajo qué restricciones. La diferencia entre un prompt vago ("generá un test") y uno estructurado puede ser la diferencia entre código directamente ejecutable y código que requiere edición manual.

- **Por qué estructurar el prompt para recibir solo código:**
  El agente necesita guardar el output directamente como archivo `.py` y ejecutarlo con pytest sin intervención humana. Si el modelo devuelve explicaciones, texto introductorio o bloques de código envueltos en markdown (` ``` `), el pipeline falla o requiere un paso extra de parsing frágil. Pedir "solo código" en el system prompt —con reglas numeradas explícitas— aprovecha el entrenamiento de instruction-following del modelo para producir outputs directamente procesables. Es más robusto que parsear la respuesta a posteriori.

- **Decisiones tomadas en el diseño del template:**
  1. **System prompt con reglas numeradas:** los modelos fine-tuneados para instrucciones responden mejor a listas explícitas que a prosa. Numerar las reglas reduce ambigüedad.
  2. **Cobertura mínima exigida en el prompt:** caso feliz + caso borde + error esperado. Esto guía al modelo a generar tests con valor real, no solo el happy path.
  3. **Patrón de nombre `test_<funcion>_<escenario>`:** hace los tests autodescriptivos y compatibles con la convención estándar de pytest.
  4. **`BuiltPrompt` como dataclass en lugar de dict o string:** tipado explícito, fácil de inspeccionar en debug y desacoplado de la firma de `LLMClient.generate()`.
  5. **Registro `_REGISTRY`:** permite agregar lenguajes sin modificar `PromptBuilder`; principio Open/Closed.

- **Conceptos teóricos que aplican:** prompt engineering, instruction-following en LLMs, principio Open/Closed (SOLID), patrón Factory, separación entre construcción del prompt y ejecución del modelo.

- **Deuda técnica / pendientes:** agregar soporte para funciones con docstring (incluirla en el prompt mejora la generación), manejo de clases y métodos (no solo funciones sueltas), test unitario de `PromptBuilder` sin invocar el LLM.
