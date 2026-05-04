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

## Flujo del agente — diagrama narrativo

> Describe en orden exacto qué ocurre cuando se ejecuta `python3 agent.py --repo ./examples`.

### 1. Arranque del intérprete y resolución de imports

Python carga `agent.py`. Las primeras instrucciones que se ejecutan son los imports de módulos estándar (`argparse`, `ast`, `pathlib`, `sys`) y los imports internos del proyecto (`LLMClient`, `OllamaConnectionError`, `PromptBuilder`, `clean_response`). En este momento también se evalúan las dos constantes de módulo: `_ROOT` queda apuntando al directorio donde vive `agent.py`, y `OUTPUT_DIR` queda construido como `_ROOT/tests_generados/unit`.

### 2. Parsing de argumentos CLI

`main()` construye un `ArgumentParser` y llama a `parse_args()`. El sistema operativo ya pasó la lista `['--repo', './examples']` como `sys.argv`. argparse valida que el flag obligatorio `--repo` esté presente y guarda el valor `'./examples'` en `args.repo`. Si faltara el flag, argparse imprimiría el uso y saldría con error en este punto.

### 3. Validación del directorio destino

`pathlib.Path('./examples').resolve()` convierte la ruta relativa en absoluta (por ejemplo `/home/user/proyecto/examples`). Se verifica que esa ruta sea un directorio existente; si no lo fuera, el agente imprime un mensaje de error y termina con `sys.exit(1)`.

### 4. Creación del directorio de salida

`OUTPUT_DIR.mkdir(parents=True, exist_ok=True)` garantiza que `tests_generados/unit/` exista antes de intentar escribir archivos. Si ya existe, no hace nada.

### 5. Verificación de disponibilidad del modelo

Se instancia `LLMClient()` con los valores por defecto (`deepseek-coder:6.7b`, `http://localhost:11434`). Luego se llama a `is_available()`, que hace un `GET /api/tags` a la API REST de Ollama y verifica que el nombre del modelo aparezca en la lista de modelos descargados. Si Ollama no está corriendo o el modelo no fue descargado, el agente imprime instrucciones de remediación y termina. Este chequeo temprano evita esperar varios segundos de procesamiento antes de recibir un error de conexión.

### 6. Descubrimiento de archivos

`repo.glob("*.py")` lista todos los `.py` de `examples/`. El resultado se filtra para excluir archivos que empiecen con `_` (convención Python para archivos internos como `__init__.py`) y se ordena alfabéticamente. En el caso del demo, el resultado es `[calculadora.py]`.

### 7. Procesamiento de cada archivo — lectura y extracción de funciones

Para cada archivo (en este caso `calculadora.py`) se llama a `process_file()`. Dentro:

1. Se lee el contenido completo del archivo como string con `read_text(encoding='utf-8')`.
2. Se llama a `extract_functions(source)`, que usa el módulo estándar `ast` para parsear el código Python en un árbol sintáctico abstracto (AST). Se itera sobre `tree.body` — solo los nodos de nivel top del módulo — y se seleccionan los nodos de tipo `FunctionDef`. Para cada uno se reconstituye el código fuente original usando los números de línea que el AST registra (`lineno` y `end_lineno`). El resultado es una lista de tuplas `(nombre, código_fuente)`: `[('sumar', 'def sumar...'), ('restar', 'def restar...'), ...]`.

### 8. Generación de tests — bucle por función

Por cada función extraída se ejecutan tres pasos en secuencia:

**a) Construcción del prompt:**  
`PromptBuilder.build(func_code, language='python', function_name=func_name)` resuelve el template `PythonPromptTemplate` desde el registro `_REGISTRY`. El template produce un `BuiltPrompt` con dos campos: `system` (las reglas estrictas de formato que definen el rol del modelo) y `user` (el código de la función embebido junto con la instrucción concreta de generar tests). El system prompt y el user prompt se mantienen separados para aprovechar el campo `system` dedicado de la API de Ollama.

**b) Llamada al modelo:**  
`client.generate(prompt.user, system=prompt.system)` serializa ambos campos en un JSON `{"model": "deepseek-coder:6.7b", "prompt": "<user>", "system": "<system>", "stream": false}` y hace un `POST /api/generate` a Ollama. Con `stream=false`, Ollama procesa el prompt completo, genera la respuesta token a token internamente y devuelve un único JSON con el campo `"response"` ya completo. El método devuelve ese string.

**c) Limpieza del output:**  
`clean_response(raw)` sanea el string devuelto por el modelo aplicando tres estrategias en orden: primero busca bloques markdown con triple backtick y extrae solo su contenido; si no los hay, descarta todo el texto previo a la primera línea que empiece con `import`, `from` o `def test_`; finalmente elimina backticks sueltos residuales. El resultado es código Python puro listo para escribirse a disco.

### 9. Escritura del archivo de tests

Después de procesar todas las funciones del archivo, todos los bloques de tests limpiados se concatenan con `"\n\n"` como separador. El archivo de salida se escribe en `tests_generados/unit/test_calculadora.py` con `write_text(encoding='utf-8')`. El nombre sigue el patrón `test_<stem>.py` donde `stem` es el nombre del archivo fuente sin extensión.

### 10. Fin del agente

Una vez procesados todos los archivos, `main()` retorna normalmente. Python imprime la confirmación de cada archivo procesado y el proceso termina con código 0.

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

---

### HU-03: Explorador de repositorio

- **Qué se hizo:** se creó `agent/repo_explorer.py` con la función `explore(repo_path)` que
  recorre recursivamente un directorio Python usando `os.walk`, ignora directorios del sistema
  (`__pycache__`, `.git`, `venv`, `dist`, etc.) modificando `dirnames` in-place, y devuelve
  una lista ordenada de rutas relativas a archivos `.py`.

- **Por qué esta solución:** separación clara de responsabilidades — `repo_explorer.py` es
  puramente filesystem, sin leer contenido de archivos. La modificación in-place de `dirnames`
  en `os.walk` es el mecanismo estándar de Python para podar el árbol de recursión sin necesidad
  de filtrado posterior. Las rutas relativas (no absolutas) son el contrato esperado por
  `ast_extractor.py` y evitan acoplamiento a rutas absolutas del sistema.

- **Conceptos teóricos que aplican:** `os.walk` con pruning de directorios (modificación
  in-place de `dirnames`), `pathlib.Path.relative_to()` para normalización de rutas,
  principio de responsabilidad única (SRP).

- **Deuda técnica / pendientes:** soporte para estructura `src/` (v2 QUAL-02), opción para
  incluir/excluir dirs adicionales por parámetro.

---

### HU-04: Extractor AST

- **Qué se hizo:** se creó `agent/ast_extractor.py` con la función pública `extract(files, repo_path)`
  que analiza cada archivo `.py` usando el módulo `ast` de stdlib y devuelve un dict unificado
  `{ruta: {functions, classes, imports}}`. Incluye detección de imports cruzados entre módulos del
  mismo repositorio y la función `fragment()` para dividir archivos grandes en porciones ≤200 líneas
  sin cortar unidades sintácticas a la mitad.

- **Por qué `ast` en lugar de regex o lectura de texto:**
  El módulo `ast` de Python stdlib convierte el código fuente en un Árbol de Sintaxis Abstracta (AST),
  una representación estructurada exacta de la gramática del lenguaje. A diferencia de regex, el AST
  entiende la jerarquía del código (qué es un cuerpo de clase, qué es un parámetro de función, qué
  es un decorador). `ast.parse()` lanza `SyntaxError` si el archivo tiene código inválido, lo que
  permite detectar y registrar errores de parsing sin abortar el flujo. `ast.get_docstring()` extrae
  la docstring limpia (sin comillas) de cualquier nodo con cuerpo.

- **Cómo funciona la fragmentación inteligente:**
  Cada función y clase tiene `node.lineno` y `node.end_lineno` en el AST. La función `fragment()`
  agrupa las unidades en lotes usando un algoritmo greedy: agrega unidades al fragmento actual mientras
  la suma de líneas sea ≤ FRAGMENT_THRESHOLD (200). Si una unidad individual supera el umbral, forma
  su propio fragmento (garantía de nunca partir una unidad). Este mecanismo asegura que cada fragmento
  enviado al LLM sea autocontenido y parseable de forma independiente.

- **Cómo se detectan los imports del mismo repositorio:**
  `_extract_repo_imports()` convierte los nombres de módulos importados (ej. `pkg.mod`) a rutas
  relativas (ej. `pkg/mod.py`) y verifica si esa ruta está en el conjunto de archivos conocidos del
  repositorio. Solo imports que existen en el repo quedan registrados; stdlib y third-party se filtran.

- **Conceptos teóricos que aplican:** Árbol de Sintaxis Abstracta (AST), algoritmo greedy de
  particionado, patrón de diccionario unificado como contrato de datos entre módulos, manejo
  defensivo de errores de parsing.

- **Deuda técnica / pendientes:** soporte para `async def` en métodos de clase (parcialmente cubierto),
  extracción de type hints de parámetros para prompts más ricos (v2), caché de resultados para repos
  grandes (v2 QUAL-01).

---

### HU-05: Generador de Tests Unitarios

- **Qué se hizo:** se creó `agent/test_generator.py` con la función pública
  `generate(repo_path, ast_result)` que itera el dict de `extract()`, llama al LLM una vez
  por función/método, valida el output con `ast.parse()` (1 reintento si falla), y escribe
  los tests en `tests_generados/unit/test_<stem>.py` más un `conftest.py` con el `sys.path`
  del repositorio analizado. Se agregó el parámetro opcional `class_name` a
  `PythonPromptTemplate` y `PromptBuilder.build()` para adaptar el prompt a métodos de clase.

- **Por qué LLM una vez por función (no por archivo):**
  Enviar una función a la vez reduce el riesgo de que el modelo "olvide" funciones en un
  archivo largo (problema de atención en modelos pequeños como 6.7b). El trade-off es
  más llamadas al LLM, pero es aceptable para v1 donde el objetivo es cobertura, no velocidad.

- **Por qué `ast.parse()` para validar el output:**
  `ast.parse()` es la verificación mínima que garantiza que el código generado por el LLM
  es Python sintácticamente correcto antes de escribirlo al disco. No verifica semántica
  (el test puede fallar en runtime), pero asegura que pytest pueda al menos importar el archivo.
  La validación semántica es responsabilidad del módulo de ejecución (HU-07/HU-08).

- **Por qué slicing por `_lineno`/`_end_lineno` en lugar de re-parsear:**
  Los atributos `_lineno` y `_end_lineno` ya están en el dict de `extract()`. Releer el
  archivo fuente y slicear es O(n) en líneas y no requiere una segunda pasada de AST.
  Mantiene `test_generator.py` desacoplado de `ast_extractor.py` (lo consume como dato,
  no lo reimplementa).

- **Cómo funciona el mecanismo de reintento:**
  `_generate_block()` itera `range(2)`. En el attempt 0: genera, limpia, valida. Si
  `ast.parse()` lanza `SyntaxError`, hace `continue` al attempt 1 (reintento). Si el
  segundo attempt también falla, sale del loop y devuelve el comentario de error.
  Máximo 1 reintento por función (D-06).

- **Conceptos teóricos que aplican:** validación de AST como guardrail de calidad,
  granularidad de contexto LLM (función vs. archivo), patrón de reintento acotado,
  sys.path como mecanismo de resolución de imports en pytest.

- **Deuda técnica / pendientes:** soporte para `async def` en prompts (template actual
  no menciona async), caché de resultados para no re-llamar al LLM para funciones sin
  cambios (v2 QUAL-01), template separado para métodos vs. funciones (v2 si se necesita).

---

### HU-06: Generador de Tests de Integración

- **Qué se hizo:** se creó `agent/integration_generator.py` con la función pública
  `generate(repo_path, ast_result)` que detecta pares de módulos relacionados por imports
  (campo `imports` del dict de `extract()`), llama al LLM una vez por par, valida el output
  con `ast.parse()` (1 reintento si falla), y escribe los tests en
  `tests_generados/integration/test_<stemA>_<stemB>.py` más un `conftest.py` con `sys.path`.
  Se agregó `IntegrationPromptTemplate` a `prompts/prompt_builder.py` con
  `language="python_integration"`, registrado en `_REGISTRY`.
  Se creó `examples/estadistica.py` como módulo de referencia que importa funciones de
  `calculadora.py` para validar los criterios de éxito de la Fase 3.

- **Por qué LLM una vez por par (no por función de integración):**
  A diferencia de los tests unitarios (una llamada por función), los tests de integración
  deben validar la INTERACCIÓN entre módulos. Enviar el módulo A completo + las firmas de B
  le permite al LLM entender el flujo de datos entre los dos módulos y generar asserts
  significativos. Si llamáramos por función de A, perderíamos el contexto del módulo importado.

- **Por qué solo firmas de B (no el código fuente completo):**
  Enviar el cuerpo completo de B junto con el de A puede exceder el contexto del modelo
  (DeepSeek Coder 6.7b tiene límite de ~4096 tokens). Las firmas (nombre + parámetros)
  son suficientes para que el LLM sepa cómo llamar las funciones de B y qué valores esperar.
  Esta decisión (D-03) balancea calidad de prompt vs. tamaño de contexto.

- **Cómo funciona la detección de pares (INTG-01):**
  `_find_pairs()` itera el dict de `extract()` y para cada archivo busca en su campo `imports`
  (ya calculado por `ast_extractor._extract_repo_imports()`) las rutas de otros módulos del repo.
  Un par (A, B) se incluye solo si B también está como key en el dict — esto excluye imports
  externos (stdlib, pip). La detección es transitiva: si A→B y B→C, se generan pares (A,B)
  y (B,C) pero no (A,C) directamente (v1 solo pares directos, v2 puede agregar triplas).

- **Por qué IntegrationPromptTemplate no usa PromptBuilder.build():**
  La firma de `PromptBuilder.build()` está diseñada para el caso unitario (función individual).
  El caso de integración requiere pasar 4 datos distintos (fuente de A, firmas de B, nombre A,
  nombre B). En lugar de sobrecargar la firma existente con kwargs opcionales, `integration_generator.py`
  instancia `IntegrationPromptTemplate` directamente. La clase sigue registrada en `_REGISTRY`
  para futura integración con `PromptBuilder.build()` vía kwargs o si se refactoriza la interfaz.

- **Conceptos teóricos que aplican:** grafos de dependencias entre módulos (pares de imports),
  cobertura de integración vs. unitaria, context window budget en modelos pequeños,
  patrón de reintento acotado (mismo que HU-05), conftest.py por directorio en pytest.

- **Deuda técnica / pendientes:** deduplicación de pares bidireccionales (A→B y B→A generan
  tests solapados — v2 QUAL-02), triplas de dependencia A→B→C (v2), template separado por tipo
  de interacción clase vs. función libre (v2 si se necesita).
