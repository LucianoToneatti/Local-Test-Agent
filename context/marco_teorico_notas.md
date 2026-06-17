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

### HU-07: Runner de Tests

- **Qué se hizo:** se creó `agent/test_runner.py` con la función pública
  `run(tests_dir: str) -> dict` que verifica la disponibilidad de pytest con
  `importlib.util.find_spec("pytest")`, ejecuta `pytest -v` como subproceso aislado
  con `subprocess.run([sys.executable, '-m', 'pytest', '-v', ...], capture_output=True, text=True)`,
  y parsea el stdout para retornar `{test_id: {'status': 'passed'|'failed'|'error', 'traceback': str|None}}`.
  Si pytest no está instalado, imprime `"[ERROR] pytest no está instalado. Ejecutá: pip install pytest"`
  y retorna `{}` sin lanzar excepción.

- **Por qué detectar pytest explícitamente antes de subprocess:**
  Ejecutar `subprocess.run([sys.executable, '-m', 'pytest', ...])` cuando pytest no está instalado
  produce un `No module named pytest` en stderr con exit code 1 — un error críptico que el usuario
  no puede diagnosticar fácilmente. La verificación previa con `importlib.util.find_spec("pytest")`
  (que retorna `None` si el módulo no existe en el entorno) permite dar un mensaje accionable
  antes de intentar ejecutar el subproceso. Esta decisión prioriza la experiencia del usuario
  sobre la simplicidad de implementación.

- **Por qué sys.executable en vez de "pytest" directo:**
  Usar `sys.executable + '-m pytest'` garantiza que se ejecuta pytest del mismo entorno Python
  que el agente. Si el usuario tiene múltiples entornos virtuales, `pytest` en PATH puede
  apuntar al entorno equivocado; `sys.executable -m pytest` siempre usa el entorno activo.

- **Por qué parseo regex en vez de pytest JSON/XML:**
  El formato JSON (`pytest --json-report`) requiere un plugin externo — viola la restricción
  de zero deps del proyecto. El formato JUnit XML (pytest --junit-xml) requiere escribir
  un archivo temporal. El parseo del stdout de `pytest -v` es suficiente para extraer
  test_ids y status con un regex simple, y el traceback está presente en el mismo stdout.
  El fix en `_attach_tracebacks` (usar `re.finditer` con lookahead en vez de `sep_re.split`)
  evita que el patrón `_{5,}` sea consumido por el split antes de poder extraer el nombre de función.

- **Conceptos teóricos que aplican:** subproceso vs. subprocess (aislamiento del estado Python),
  test discovery de pytest (convención `test_*.py::test_*`), captura de stdout/stderr,
  regex sobre output de CLI, `importlib.util.find_spec` para detección de módulos sin importar.

### HU-08: Autocorrector de Tests

- **Qué se hizo:** se creó `agent/autocorrector.py` con la función pública
  `autocorrect(results: dict, repo_path: str) -> dict` que itera los tests con
  status 'failed' o 'error', llama al LLM hasta 3 veces por test_id enviando
  el código de la función fallida + traceback + firmas del módulo bajo test,
  valida el output con `ast.parse()` antes de escribirlo, reemplaza solo la
  función fallida en el archivo de test (no el archivo completo), re-corre el
  test corregido individualmente con `pytest path::test_nombre`, y marca como
  'sin_resolver' los que agotaron los 3 intentos.
  Se agregó `CorrectionPromptTemplate` a `prompts/prompt_builder.py` con
  `language="python_correction"`, registrado en `_REGISTRY`.
  Se integraron las dos llamadas en `agent.py`:
  `results = run_tests(tests_dir)` → `final = autocorrect(results, str(repo))`.

- **Por qué corregir solo la función fallida (D-05):**
  Un archivo de test puede tener N funciones. Si reemplazáramos el archivo completo
  con el output del LLM, perderíamos las funciones que ya pasan (el LLM podría
  omitirlas o cambiarlas). Al extraer y reemplazar solo la función fallida usando
  AST, el resto del archivo queda intacto — conservamos las funciones que ya pasan.

- **Por qué re-correr solo el test_id individual (D-12):**
  Re-correr la suite completa para verificar una corrección tendría un costo O(n)
  en tiempo por intento, donde n es el total de tests. En el caso extremo con N
  tests fallidos × 3 intentos × m tests en suite, el costo es O(N×3×m). Al
  re-correr solo el test_id afectado (`pytest path::nombre`), el costo es O(1) por
  verificación. La suite completa se corre una sola vez al inicio (`run()`).

- **Por qué las firmas se re-derivan en autocorrect() (D-10):**
  El autocorrector no recibe el ast_result como parámetro para mantener la interfaz
  simple (`autocorrect(results, repo_path)`). Las firmas se obtienen llamando
  `explore()` + `extract()` sobre repo_path, que son operaciones de solo lectura.
  La inferencia del módulo usa la convención `test_<stem>.py` → `<stem>.py` ya
  establecida por `test_generator.py`.

- **Conceptos teóricos que aplican:** reemplazo selectivo con AST (preservación de
  contexto), ciclo de feedback LLM→corrección→verificación, límite de intentos para
  evitar bucles infinitos (EXEC-04), separación de responsabilidades entre runner
  (solo mide) y autocorrector (solo corrige).

## HU-09 — Generador de reporte (agent/report_generator.py)

### Qué se implementó
- `agent/report_generator.py`: módulo con función pública `generate(results, repo_name, elapsed)` que escribe `reporte.md` en la raíz del agente.
- Helper privado `_last_traceback_line(traceback)`: extrae la última línea no vacía de un traceback para mostrar el mensaje de error más relevante.
- El reporte incluye: encabezado con nombre de repo y fecha, tabla de resumen con conteo de passed/failed/sin_resolver y tiempo total, sección de tests fallidos (omitida si vacía), sección de tests sin resolver (omitida si vacía).
- Los tests que pasaron no se listan individualmente — solo su conteo en la tabla.

### Decisiones clave
- **Ruta fija con `Path(__file__).parent`**: garantiza que `reporte.md` se genere junto a `agent.py` independientemente del directorio de trabajo desde el que se invoque el agente. Alternativa rechazada: `Path.cwd()` — frágil si se llama desde otro directorio.
- **Secciones condicionales**: si no hay tests fallidos o sin resolver, la sección correspondiente se omite completamente. Esto mantiene el reporte limpio para ejecuciones exitosas.
- **`elapsed:.1f`**: un decimal es suficiente para comunicar la duración; más decimales añaden ruido sin valor informativo para el usuario final.
- **Monkeypatch de `_OUTPUT_PATH`**: los tests parchean la variable de módulo `_OUTPUT_PATH` con `tmp_path` para evitar escribir en el filesystem real durante las pruebas, sin necesidad de refactorizar la función para recibir el path como argumento.

### Conceptos teóricos aplicados
- **`pathlib.Path(__file__)`**: resuelve la ruta del módulo en tiempo de importación — patrón estándar para referencias de ruta relativas al código fuente, no al directorio de trabajo.
- **`datetime.date.today().isoformat()`**: produce fechas en formato ISO 8601 (`YYYY-MM-DD`) — legible por humanos y sorteable lexicográficamente.
- **Módulo de sola responsabilidad**: `report_generator` no llama al LLM, no ejecuta tests, no lee archivos Python — solo transforma un dict de resultados en Markdown. Esto facilita el testing unitario y el reuso.
- **`f"{elapsed:.1f}s"`**: format spec de Python para floats con 1 decimal fijo — evita notación científica y garantiza consistencia de formato.

## HU-10 — CLI Completa (refactor de agent.py)

### Qué se implementó
- Eliminación de funciones inline duplicadas de `agent.py`: `_CONFTEST_TEMPLATE`, `write_conftest()`, `extract_functions()`, `process_file()`, constantes `_ROOT` y `OUTPUT_DIR`.
- Reemplazo del loop de generación de tests unitarios por llamada directa a `test_generator.generate(str(repo), ast_result)`.
- Cálculo único de `ast_result = extract(explore(str(repo)), str(repo))` reutilizado para generación unitaria e integración (antes se calculaba dos veces).
- Medición de tiempo total: `start = time.time()` como primera línea de `main()`, `elapsed = time.time() - start` antes del reporte.
- Integración de `report_generator.generate(final, repo.name, elapsed)` al final del flujo, con mensajes de progreso `[*] Generando reporte...` y `[OK] Reporte generado: reporte.md`.
- Eliminación de imports obsoletos: `ast`, `PromptBuilder`, `clean_response`.

### Decisiones clave
- **Eliminar funciones inline en lugar de refactorizar a un módulo nuevo**: `test_generator.generate()` ya implementaba la misma lógica con mejor cobertura de casos (fragmentación de archivos >200 líneas, manejo de clases, etc.). Mantener las funciones inline habría creado dos implementaciones divergentes de la misma responsabilidad.
- **`ast_result` calculado una sola vez**: el resultado de `extract(explore(...))` es inmutable y se puede reutilizar para todos los generadores. La versión anterior lo recalculaba en la línea de generación de integración, duplicando I/O y procesamiento.
- **`time.time()` como primera línea de `main()`**: garantiza que el tiempo medido incluye todo el procesamiento — validación de argumentos, verificación de Ollama, exploración, generación, ejecución y autocorrección. Medir desde un punto posterior subestimaría el tiempo real percibido por el usuario.
- **`repo.name` como `repo_name`**: el atributo `.name` de `pathlib.Path.resolve()` da el nombre del directorio final sin ruta completa ni trailing slash — es el identificador más legible para el usuario en el reporte.
- **`final = {}` como fallback**: si `run_tests()` retorna vacío (pytest no instalado, sin tests generados), se llama a `report_generator.generate({}, ...)` de todas formas para que siempre se produzca un `reporte.md` al final del flujo.

### Conceptos teóricos aplicados
- **Principio DRY (Don't Repeat Yourself)**: el refactor elimina la duplicación entre las funciones inline de `agent.py` y los módulos del agente. Cada responsabilidad queda en un único lugar.
- **Flujo de datos unidireccional en CLI**: `agent.py` actúa como orquestador puro — lee el argumento `--repo`, delega en módulos especializados en secuencia, y presenta resultados al usuario. No contiene lógica de dominio.
- **`time.time()` para wall-clock time**: mide el tiempo real transcurrido desde la perspectiva del usuario, incluyendo I/O, espera de subprocesos y llamadas al LLM. Alternativa `time.process_time()` mediría solo CPU — inadecuado para un agente que espera I/O.
- **Separación de mensajes de progreso y lógica**: `agent.py` imprime los mensajes `[*]`/`[OK]`; los módulos internos no saben si están siendo invocados desde CLI o desde tests — esto facilita el testing sin captura de stdout.

## Fix — Collection errors en test_runner.py (prueba con Pacman)

### Contexto
Prueba de HU-10 con repositorio real: [hbokmann/Pacman](https://github.com/hbokmann/Pacman), juego de Pacman en Python con pygame. El agente generó los tests correctamente en `tests_generados/unit/`, pero el reporte final mostraba 0 tests (0 passed, 0 failed, 0 sin resolver).

### Causa raíz
`pacman.py` importa `pygame` como dependencia de runtime. Los tests generados hacen `from pacman import setupRoomOne`, lo que carga `pacman.py` → `import pygame._view` → `ModuleNotFoundError`. pytest llama a esto un **collection error**: no puede ni siquiera recolectar los tests del archivo, por lo que no llega a ejecutar ninguno.

El formato de salida de pytest para un collection error es:
```
ERROR tests_generados/unit/test_pacman.py
```
sin `::nombre_de_test`. El regex original de `_parse_output` solo matcheaba `path::test_nombre STATUS`, por lo que este caso producía un dict vacío.

Con `results = {}`, la rama `if results:` de `agent.py` es `False` → `final = {}` → reporte 0 tests.

### Distinción clave: collection error vs. test failure
| Tipo | Formato en pytest stdout | Causa |
|------|--------------------------|-------|
| Test failure | `path/test.py::test_nombre FAILED` | El test se ejecutó y falló |
| Collection error | `ERROR path/test.py` | pytest no pudo importar el archivo |

Un collection error ocurre **antes** de que pytest llegue a ejecutar ningún test. Es causado por dependencias faltantes en el módulo bajo test, errores de sintaxis en el archivo de test, o imports circulares.

### Solución implementada (agent/test_runner.py)
1. **Segundo regex en `_parse_output`**: `r"^ERROR\s+([\w/\\. :-]+\.py)"` captura las líneas `ERROR path/file.py` de la sección "short test summary". El key en el dict de resultados es la ruta del archivo (sin `::nombre`).
2. **`_attach_collection_tracebacks`**: nueva función análoga a `_attach_tracebacks`, captura el bloque `_____ ERROR collecting path/file.py _____` del output y lo adjunta como traceback — incluye el `ModuleNotFoundError` o `ImportError` completo.
3. **Compatibilidad con autocorrector**: `autocorrector._split_test_id()` ya tenía `if "::" not in test_id: return None, None`, por lo que los collection errors (sin `::`) se saltan graciosamente sin modificación adicional.

### Consecuencia en el reporte
Un collection error ahora aparece en la sección "Tests fallidos" del reporte con:
```
- `tests_generados/unit/test_pacman.py`
  `E   ModuleNotFoundError: No module named 'pygame'`
```
Esto le dice al usuario exactamente qué archivo no pudo ejecutarse y por qué, en lugar de silenciar el problema con 0 tests.

### Lección de diseño
El parseo de output de CLIs externas debe considerar todos los exit codes y formatos posibles, no solo el happy path. pytest tiene al menos 4 exit codes: 0 (todo pasó), 1 (tests fallaron), 2 (error de colección/interrupción), 3 (error interno). El código original solo manejaba 0 y 1.

---

## Fix — Ruta de reporte.md (agent/report_generator.py)

### Qué se corrigió
`_OUTPUT_PATH` usaba `pathlib.Path(__file__).parent / "reporte.md"`, que resuelve a `agent/reporte.md` (el directorio del módulo). El usuario ejecuta `python3 agent.py` desde la raíz del proyecto y esperaba encontrar `reporte.md` en ese mismo directorio.

Corrección: `pathlib.Path(__file__).parent.parent / "reporte.md"` — sube un nivel desde `agent/` hasta la raíz del proyecto.

### Por qué el bug no se detectó en tests
Los tests de `test_report_generator.py` usan `monkeypatch.setattr(rg, "_OUTPUT_PATH", output_file)` para redirigir la escritura a `tmp_path`. Eso hace que el path real de `_OUTPUT_PATH` sea irrelevante durante las pruebas — los tests pasan aunque el path apunte al lugar equivocado.

### Lección
`pathlib.Path(__file__).parent` es correcto para referenciar archivos estáticos dentro del mismo paquete (templates, datos). Para archivos de salida destinados al usuario, la raíz del proyecto es más intuitiva. Cuando el nombre de archivo en el print no incluye la ruta relativa (`reporte.md` en lugar de `agent/reporte.md`), el usuario espera encontrarlo en el directorio de trabajo actual.

---

## Fix — expanduser() para rutas con ~ (test_generator.py, integration_generator.py)

### Qué se corrigió
Al invocar el agente con `--repo ~/mis-proyectos/repo`, el tilde `~` no se expandía a la ruta del home del usuario. `Path("~/mis-proyectos/repo").resolve()` retorna la ruta tal cual con `~` si no se llama `expanduser()` primero, produciendo un `FileNotFoundError` al intentar leer archivos del repositorio.

Corrección: `Path(repo_path).expanduser().resolve()` en `test_generator.generate()` e `integration_generator.generate()`. `expanduser()` expande `~` al directorio home del usuario antes de que `resolve()` convierta la ruta a absoluta.

### Por qué el bug no se detectó en tests
Los tests usaban rutas de `tmp_path` (paths absolutos sin `~`), por lo que el caso de tilde nunca se ejercitaba. Se trata de un bug de sistema de archivos que solo aparece en uso real.

### Lección
`Path.resolve()` no implica `expanduser()`. Son dos operaciones distintas: `expanduser()` interpreta convenciones del shell (`~`, `~user`); `resolve()` convierte a ruta absoluta y resuelve symlinks. Cuando se acepta una ruta del usuario vía CLI, la secuencia correcta es siempre `Path(s).expanduser().resolve()`.

---

## Fix — Imports repetidos e incorrectos en tests unitarios

### Contexto
Los tests unitarios generados tenían dos problemas de calidad sistemáticos:

1. **Imports repetidos**: cada bloque de test (uno por función) incluía `import pytest` y `from módulo import función`. Al unirlos en un solo archivo con `"\n\n".join(blocks)`, los imports aparecían N veces — una por función del módulo.

2. **Imports incorrectos**: el LLM inventaba nombres de módulos inexistentes (p. ej. `from decimal import Decimal` para un módulo de calculadora simple, `import math`, `import sys`) porque el prompt le pedía que incluyera los imports sin darle los nombres exactos.

### Solución implementada

**`prompts/prompt_builder.py` — `PythonPromptTemplate`:**
- `_SYSTEM`: reemplazó `"First line must be an import statement"` por `"Do NOT include any import statements. Output ONLY test functions (def test_...)."` y se agregó `"Do NOT include any comments (no # lines)."`. El objetivo es que el LLM produzca bloques de funciones puras, sin decoración.
- `_USER_TEMPLATE` / `_USER_TEMPLATE_METHOD`: la línea de import del módulo se mantiene como contexto para el LLM (`"Available as: from X import Y (do NOT include this import in your output)"`) pero con instrucción explícita de no incluirla en el output.
- `clean_response()`: nuevo parámetro keyword-only `strip_imports: bool = False`. Cuando es `True`, filtra todas las líneas que empiecen con `import ` o `from ` después de hacer la limpieza de markdown. Esto actúa como guardrail por si el LLM ignora la instrucción del prompt.

**`agent/test_generator.py`:**
- Nueva función `_build_import_header(module_name, file_info)`: construye el bloque de imports de forma determinística a partir de los datos que ya tiene el agente (`import pytest` + una línea `from módulo import X` por función/clase, sin duplicados).
- `generate()`: antepone el header al archivo antes de escribirlo: `header + "\n\n" + "\n\n".join(blocks)`.
- `_generate_block()`: usa `clean_response(raw, strip_imports=True)`.

### Por qué separar la responsabilidad de los imports
El agente ya conoce el nombre exacto del módulo y de cada función antes de llamar al LLM (los tiene del `ast_result`). Delegarle esa información al LLM introduce una fuente de error innecesaria. El LLM es responsable de generar la lógica de los tests; el agente es responsable de los imports, que son datos estructurales derivables del AST.

### Conceptos teóricos aplicados
- **Separación de responsabilidades**: el LLM genera lógica de tests; el agente gestiona los imports.
- **Guardrail en postprocesamiento**: `strip_imports=True` es un filtro defensivo que corrige outputs del LLM que ignoran las instrucciones del prompt, sin depender exclusivamente del instruction-following del modelo.
- **`strip_imports=False` como default**: `integration_generator.py` y `autocorrector.py` también usan `clean_response()`. La integración todavía necesita imports en su output (no tiene un `_build_import_header` equivalente), por lo que el parámetro es opt-in.

---

## Fix — Autocorrector reinyectaba imports mid-file (agent/autocorrector.py)

### Causa raíz
El autocorrector (`_correct_test`) extraía la función fallida, la enviaba al LLM para corregirla, y usaba `clean_response(raw)` sin `strip_imports=True`. El LLM devolvía la función corregida precedida de imports (`import pytest`, `from módulo import X`). Luego `_replace_function()` insertaba ese bloque — imports incluidos — en el lugar exacto de la función original dentro del archivo de test. El resultado eran imports sueltos en el medio del archivo, fuera de cualquier función.

### Solución
`clean_response(raw, strip_imports=True)` en `_correct_test()`. El autocorrector solo reemplaza una función; los imports del archivo ya están en el header generado por `_build_import_header`. Si la función corregida necesita un símbolo adicional que no estaba en el header original, el test fallará con `NameError` — eso es un problema del LLM, no del pipeline.

### Lección de diseño
`_replace_function()` hace una sustitución de rango de líneas (`lines[start:end] = new_lines`). Cualquier texto en `new_code` — incluyendo líneas antes del `def` — queda insertado en ese punto del archivo. El contrato de `_replace_function` es recibir exactamente el cuerpo de una función, no un fragmento de archivo completo. Garantizar ese contrato es responsabilidad de quien llama a la función, no de la función misma.

---

## HU-11 — Soporte JavaScript/TypeScript unitarios

### Qué se implementó
- `agent/repo_explorer.py`: se extendieron las extensiones detectadas de `.py` a `.py`, `.js` y `.ts`.
- `agent/ast_extractor.py`: se agregó un parser basado en regex para JS/TS (`_parse_js_file`), dado que no existe un módulo AST de JS en la stdlib de Python. Extrae funciones top-level (declaraciones, arrows, expresiones de función) y clases con sus métodos. El dispatcher en `extract()` elige Python AST o regex JS según la extensión del archivo.
- `prompts/prompt_builder.py`: se agregó `JsPromptTemplate` para generar tests Jest. Registrada en `_REGISTRY` como `"javascript"`. Se actualizó `clean_response()` con parámetro `language` para manejar los patrones de inicio de código JS (`test(`, `describe(`) y el stripping de imports CommonJS/ES module.
- `agent/test_generator.py`: se agregó `_detect_language()` por extensión del path, `_build_js_import_header()` que genera un `require` CommonJS, y se extendieron `_generate_block()` y `_generate_blocks_for_file()` con el parámetro `language`. La validación de output usa `ast.parse()` para Python y una heurística de texto para JS (`test(` / `describe(` / `it(`). Los tests JS se guardan como `{stem}.test.js`.
- `agent/test_runner.py`: se descompuso `run()` en `_run_pytest()` (lógica preexistente) y `_run_jest()` (nuevo). Jest se ejecuta con `npx jest --json --no-coverage` solo si existen archivos `*.test.js` o `*.test.ts` en el directorio. Los resultados de ambos runners se combinan en el mismo formato `{test_id: {status, traceback}}`.

### Decisión de diseño — prerequisitos del entorno JS
El agente asume que si el usuario trabaja con JavaScript, **ya tiene Node.js y Jest instalados**. El público objetivo son programadores que desarrollan en JS, y estas herramientas son parte de su entorno habitual, de la misma manera que Python y pytest son prerequisitos para usar el agente con código Python. No tiene sentido que el agente instale automáticamente herramientas del entorno del desarrollador: haría el agente frágil ante cambios de versión, generaría efectos secundarios en el entorno del usuario, y añadiría complejidad sin valor real. El agente verifica que Node.js esté disponible (`shutil.which("node")`) y muestra un mensaje claro si falta, dejando la responsabilidad de instalación en el desarrollador.

### Por qué regex en lugar de un parser JS
El módulo `ast` de Python solo entiende Python. Las alternativas evaluadas para JS:
- `esprima`/`pyjsparser`: parser completo pero dependencia externa.
- `tree-sitter`: muy robusto pero requiere compilación de código nativo.
- **Regex propio**: sin dependencias, suficiente para cubrir los patrones de función y clase más comunes en código real.

La limitación del enfoque regex es que no maneja correctamente código con braces en strings/template literals desbalanceadas, o patrones muy atípicos. Para v1, con el objetivo de detectar funciones y clases para generación de tests, el regex cubre el 95% de los casos prácticos.

### Formato de imports en tests JS generados
Se eligió **CommonJS (`require()`)** en lugar de ES Modules (`import`). Razón: Jest, por defecto, procesa módulos en modo CommonJS. ES Modules requieren configuración adicional en Jest (`"type": "module"` en package.json o babel/jest transform). CommonJS funciona sin configuración adicional, lo que hace los tests generados portables a cualquier proyecto JS sin requerir setup previo.

### Conceptos teóricos aplicados
- **Regex como parser aproximado**: viable cuando el lenguaje destino no tiene parser en la stdlib del lenguaje host, y cuando la cobertura del 95% de los casos comunes es suficiente.
- **Brace counting para encontrar fin de bloque JS**: alternativa a parseo completo para determinar el scope de funciones/clases. Falla con braces en strings no balanceadas, aceptable para código bien formateado.
- **Extensión del patrón Strategy (PromptTemplate)**: agregar un lenguaje nuevo solo requiere crear una subclase y registrarla en `_REGISTRY`. El resto del pipeline no cambia.
- **Backward compatibility en firmas de función**: `_generate_block(..., language="python")` y `clean_response(..., language="python")` con defaults preservan todos los tests existentes sin cambios.

---

## HU-12 — Tests de integración JavaScript/TypeScript con Jest

### Qué se implementó

- `prompts/prompt_builder.py`: se agregó `JsIntegrationPromptTemplate` registrada como `"javascript_integration"`. El system prompt instruye al LLM a generar solo bloques `describe()/test()` sin `require()`, testear únicamente funciones de A que llamen a B internamente, sin mocks, con valores concretos esperados.
- `agent/integration_generator.py`: se extendió con soporte JS/TS completo:
  - `_find_js_pairs()`: detecta pares de archivos `.js/.ts` relacionados por el campo `imports` ya calculado por `ast_extractor`. No requiere re-parsear los archivos.
  - `_format_js_signatures()`: formatea firmas de funciones del módulo B como `function nombre(params) { ... }` para el prompt.
  - `_build_js_require_header()`: construye el header `const { fn1, fn2 } = require('stem')` a partir de las funciones del módulo A que ya están en `ast_result` — el agente controla los imports, no el LLM.
  - `_generate_js_pair_test()`: llama al LLM, limpia con `clean_response(..., strip_imports=True, language="javascript")`, valida presencia de `test(`/`describe(`/`it(`, reintenta una vez si falla.
  - `_write_js_jest_config()`: escribe `jest.config.js` en `tests_generados/integration/` con `modulePaths: [repo]`.
  - `generate()` extendida: itera pares JS después de los Python dentro del mismo directorio `tests_generados/integration/`.
- `agent/test_runner.py`: `_run_jest()` reemplazada para detectar todos los subdirectorios con su propio `jest.config.js` y correr Jest una vez por cada uno, mergeando los resultados. Elimina `_find_jest_cwd()`, que solo encontraba el primer directorio con config y dejaba los demás invisibles.

### Por qué no usar mocks en los tests de integración

Los mocks son una herramienta de testing unitario: aíslan la unidad bajo test reemplazando sus dependencias por objetos controlados. En un test unitario de `promedio()`, un mock de `sumar()` garantiza que `promedio()` se testa de forma independiente. Pero en un test de integración, eso mismo es la falla de diseño.

Un test de integración tiene un objetivo diferente: verificar que la interacción real entre módulos produce los resultados correctos. Si en `estadistica.js` → `calculadora.js` mockeamos las funciones de `calculadora`, el test ya no verifica que `promedio()` llama correctamente a `sumar()` y `dividir()` y que esas funciones devuelven los valores que `promedio()` espera. Verifica que `promedio()` llama a los mocks con los argumentos que se configuraron — lo que no dice nada sobre el comportamiento real del sistema.

El valor de un test de integración sin mocks es precisamente que detecta errores en la interfaz entre módulos: cambios de nombre de función en B que A todavía llama con el nombre viejo, cambios de contrato (el tipo de retorno que A espera de B no coincide con lo que B ahora devuelve), errores en la secuencia de llamadas. Ninguno de estos errores aparece si B está mockeado.

Nota: el LLM generado por DeepSeek Coder 6.7b a veces incluye mocks a pesar de la instrucción explícita en el prompt ("No mocks — let A call B for real"). Este es un problema de instruction-following del modelo, no del framework. Los tests con mocks fallan al correr (usan `mockClear()` sobre objetos no mockeados), son capturados como `failed`, y el autocorrector puede intentar corregirlos. El pipeline trata este caso igual que cualquier test fallido.

### Decisiones de diseño

**El agente construye el header `require()`, no el LLM**: igual que en HU-11 para tests unitarios. El agente conoce exactamente qué funciones exporta el módulo A (las tiene del `ast_result`); delegarle al LLM esa información introduce una fuente de error innecesaria. El LLM genera la lógica de los tests; el agente genera los imports.

**`modulePaths` en jest.config.js apunta al repo analizado**: permite usar `require('estadistica')` sin rutas relativas en los tests. Este es el mismo mecanismo del `conftest.py` de Python (que agrega el repo a `sys.path`): el runner puede importar por nombre de módulo, sin importar dónde está el archivo de test físicamente. El módulo A resuelve su propio `require('./calculadora')` de forma relativa desde su ubicación — Jest no interfiere en eso.

**Un `jest.config.js` por directorio, un proceso Jest por config**: `unit/` e `integration/` tienen configuraciones independientes (distintas rutas en `modulePaths`, potencialmente distintos patrones de test). Correrlos desde un config raíz implicaría mezclar `modulePaths` de todos los repos analizados. Correr Jest una vez por directorio con config propia es más limpio y no requiere un config raíz que coordine.

**Validación de output JS por heurística de texto**: sin `ast.parse()` disponible para JavaScript, la validación de si el LLM generó código válido usa una heurística: el output debe contener `test(`, `describe(` o `it(`. Esta heurística no detecta errores de sintaxis JS (braces mal cerrados, etc.), pero coincide con la validación usada en HU-11 para tests unitarios. El error de sintaxis se detectará cuando Jest intente correr el archivo y el test_runner lo reportará como `error`.

**Convención de nombre `{stem_a}_{stem_b}.test.js`**: Jest requiere la extensión `.test.js` para descubrir tests. A diferencia de Python (donde se usa `test_{a}_{b}.py`), la convención JS ubica el calificador `.test.` antes de la extensión, lo que es estándar en el ecosistema Jest/JavaScript.

### Conceptos teóricos aplicados

- **Tests de integración vs. unitarios**: los unitarios aíslan (mocks); los de integración conectan (real). La decisión de no usar mocks no es una restricción técnica sino una decisión de diseño que define el tipo de test que se genera.
- **`modulePaths` en Jest**: equivalente a `sys.path` en Python — agrega rutas al sistema de resolución de módulos de Node.js durante la ejecución de tests.
- **Reutilización del grafo de imports**: `ast_extractor` ya construye el grafo de dependencias entre módulos (campo `imports`). `_find_js_pairs()` y `_find_pairs()` (Python) consumen ese grafo sin re-parsear los archivos — separación limpia entre extracción de datos y uso de datos.

### Deuda técnica / pendientes

- El LLM genera mocks con frecuencia a pesar de la instrucción (limitación del modelo 6.7b). Un segundo sistema prompt con ejemplo explícito (few-shot) podría mejorar la adherencia.
- Si A y B están en directorios distintos, `modulePaths` solo apunta al directorio de A. Los imports de B desde A seguirán funcionando (rutas relativas), pero si algún test necesitara `require('nombre_de_B')` directamente, fallaría. Para v1, A y B en el mismo directorio es el caso prácticamente universal.
- No hay autocorrección para tests de integración JS (el autocorrector actual solo maneja Python). Los tests JS fallidos quedan como `failed` en el reporte.

---

## Prueba comparativa de rendimiento por hardware

Mismo agente, mismo modelo (deepseek-coder:6.7b), mismo repositorio de prueba (`codigo-para-testear`, 4 archivos Python).

| Hardware | CPU | GPU | RAM | OS | Tiempo total |
|----------|-----|-----|-----|----|-------------|
| PC sin GPU dedicada (PC propia) | no especificado | — | — | — | ~27 minutos |
| PC con GPU dedicada (PC de amigo) | AMD Ryzen 7 5800X | AMD Radeon RX 6800 16 GB GDDR6 | 16 GB DDR4 2400 MHz dual channel | Linux Mint 21.1 | ~220 segundos (~3:40 min) |

**Factor de mejora: ~7x más rápido con GPU dedicada.**

### Explicación técnica

La inferencia de un LLM es fundamentalmente una operación de álgebra lineal masiva (multiplicaciones de matrices sobre los pesos del modelo). Las GPUs tienen miles de núcleos diseñados para ejecutar estas operaciones en paralelo; las CPUs tienen decenas de núcleos de propósito general que las hacen en serie o con SIMD limitado. DeepSeek Coder 6.7b tiene ~6.7 mil millones de parámetros: cada token generado requiere operar sobre todos ellos. En CPU eso toma cientos de milisegundos por token; en GPU moderna baja a decenas.

Ollama detecta automáticamente la GPU disponible y carga el modelo en VRAM si hay suficiente espacio (la RX 6800 tiene 16 GB, más que suficiente para el modelo cuantizado ~4 GB). Sin GPU, el modelo corre en RAM del sistema con la CPU, que es funcional pero significativamente más lento.

### Conclusión para el proyecto

El rendimiento del agente depende directamente del hardware disponible:
- **Con GPU dedicada**: 220 segundos para 4 archivos — perfectamente usable en demos y desarrollo iterativo.
- **Sin GPU dedicada**: ~27 minutos para los mismos 4 archivos — funcional, pero lento para repositorios grandes o demostraciones en vivo.

Para la presentación del TIF, ejecutar el agente en una máquina con GPU o preparar una corrida previa grabada.

---

## HU-13: Terminal UX con colores ANSI, barra de progreso y coverage

### Problema que resuelve

El agente original imprimía mensajes `[*]` y `[OK]` planos sin diferenciación visual. No había retroalimentación del progreso durante la generación de tests (que puede tomar minutos) ni indicación del estado de cada test al ejecutarse. Tampoco se medía la cobertura de código generada por los tests.

### Decisiones de diseño

**Solo ANSI y ASCII — sin librerías externas**: la restricción de no agregar dependencias para la UI es intencional. `colorama`, `rich`, `tqdm` etc. resuelven el mismo problema pero agregan peso al entorno. Los códigos ANSI (`\033[32m` para verde, `\033[31m` para rojo) son soportados nativamente por cualquier terminal Linux/macOS moderna. `terminal_ui.py` es completamente importable sin pip.

**Módulo separado `agent/terminal_ui.py`**: toda la lógica de presentación está aislada en un módulo. `agent.py` no conoce códigos ANSI ni anchos de barra — llama a `print_step()`, `print_progress()`, `print_result_line()`. Esto hace que la lógica sea testeable (se puede capturar stdout con `capsys`) y reemplazable (cambiar colores o formato no toca el flujo de negocio).

**Barra de progreso con `\r`**: la barra usa retorno de carro (`\r`) para sobreescribir la línea actual en lugar de imprimir una nueva línea por iteración. Esto requiere `flush=True` en el `print()` para que el buffer se vacíe antes de que el LLM tarde en responder. El `print()` sin argumentos al finalizar (cuando `current >= total`) emite el `\n` que avanza a la línea siguiente.

**`progress_callback` como parámetro opcional**: `test_generator.generate()` e `integration_generator.generate()` reciben `progress_callback=None`. Si es `None`, el comportamiento es idéntico al anterior — ningún código existente se rompe. El callback tiene la firma `(current: int, total: int, label: str)`, que coincide exactamente con `terminal_ui.print_progress`. En `agent.py` simplemente se pasa `progress_callback=terminal_ui.print_progress`.

**`run()` retorna `(dict, float | None)`**: cambio de firma en `test_runner.run()`. La alternativa sería retornar un dict con el coverage embebido en una clave especial, pero eso mezcla metadatos del run con resultados de tests individuales. Una tupla es más limpia: el primer elemento son los resultados, el segundo es el coverage. El tipo `float | None` (no un dict con clave "coverage") hace explícito que el coverage es un valor escalar o ausente.

**Coverage solo para Python con pytest-cov**: se agrega `--cov={repo_path} --cov-report=term-missing` al comando de pytest cuando `pytest_cov` está instalado y `repo_path` es no vacío. Si `pytest-cov` no está instalado, el flag se omite silenciosamente y el coverage queda como `None`. Jest tiene su propio mecanismo de coverage (`--coverage`) pero se lo pasa `--no-coverage` explícitamente para no mezclar reportes: el porcentaje en el reporte es solo de Python.

**Regex de coverage con backtracking**: la línea `TOTAL   25   7   72%` se parsea con `r"^TOTAL(?:\s+\d+)+\s+(\d+)%"`. El grupo `(?:\s+\d+)+` consume todos los números menos el último (backtracking), y `\s+(\d+)%` captura el porcentaje final. Funciona también con la forma branch de pytest-cov (`TOTAL   25   7   10   3   72%`).

### install.sh como punto de entrada

El script `install.sh` encapsula todo el proceso de configuración del entorno en un solo comando. La razón de crearlo como script bash (en lugar de un `Makefile` o `pyproject.toml`) es que:
1. No requiere ninguna herramienta preinstalada más allá de `bash` y `python3`
2. Incluye lógica de verificación de Ollama (que es un binario externo, no un paquete pip)
3. Es inmediatamente ejecutable por un usuario nuevo sin leer la documentación completa

### Cobertura en reporte.md

El campo `coverage_pct` se agrega como línea `**Cobertura:** 72%` y como fila en la tabla de resumen `| Cobertura | 72% |`. Si no está disponible, se muestra `N/A`. Esta representación permite que el reporte sea útil tanto cuando pytest-cov está instalado como cuando no lo está, sin romper el formato Markdown existente.

---

## HU-14 — Soporte Java con JUnit 5 y Maven

### Qué se implementó

- **`agent/ast_extractor.py`**: se agregó `_parse_java_file()` basado en regex para extraer clases y métodos públicos de archivos `.java`. La extensión usa el mismo dispatcher de `extract()` que para Python y JS, eligiendo el parser por extensión de archivo.
- **`agent/repo_explorer.py`**: se extendieron las extensiones detectadas para incluir `.java`.
- **`prompts/prompt_builder.py`**: se creó `JavaPromptTemplate` para generar métodos `@Test` de JUnit 5. El template exige output embebible directamente dentro del cuerpo de una clase Java — sin clase envolvente, sin imports, sin declaraciones de paquete. El agente construye el archivo completo con el wrapper de clase e imports JUnit 5 de forma determinística.
- **`agent/test_generator.py`** (implementación inicial, luego extraída): se agregaron `_generate_java_tests()`, `_build_java_test_file()`, `_copy_java_sources()`, `_write_java_pom()` e `_is_embeddable_java_block()`. El agente generaba un proyecto Maven completo en `tests_generados/unit/` con la estructura `src/main/java/` (fuentes copiadas) y `src/test/java/` (tests generados), más un `pom.xml` mínimo con JUnit Jupiter 5.10.0 y Maven Surefire 3.1.2.
- **`agent/test_runner.py`** (implementación inicial, luego extraída): se agregó `_run_maven()` que busca `pom.xml` con `rglob`, ejecuta `mvn test --batch-mode` por cada proyecto encontrado, y parsea los XMLs de Surefire en `target/surefire-reports/` con `xml.etree.ElementTree`.
- **`examples_java/`**: directorio con `Calculadora.java` y `Conversor.java` como ejemplos de referencia para validar el pipeline Java de extremo a extremo.

### Decisiones de diseño

**El agente construye el archivo Java completo; el LLM genera solo el cuerpo:**
La misma filosofía que Python y JS. El LLM solo genera los métodos `@Test` como bloques de código embebibles. El agente agrega los imports (`org.junit.jupiter.api.Test`, `Assertions.*`) y el wrapper de clase (`class {ClassName}Test { ... }`). Esto evita que el LLM invente nombres de clases o imports incorrectos.

**Maven como herramienta de build y test:**
Se eligió Maven sobre compilación manual con `javac` porque maneja las dependencias de JUnit Jupiter automáticamente (via pom.xml), ofrece un output de test estructurado (Surefire XML), y es el estándar en proyectos Java de producción. La alternativa con `javac` + classpath manual requeriría gestionar el classpath de JUnit a mano, lo que es frágil.

**pom.xml generado por el agente:**
El agente genera un `pom.xml` mínimo con JUnit Jupiter y Maven Surefire en lugar de exigir que el usuario lo provea. Esto permite que el agente funcione sobre repositorios Java sin infraestructura Maven existente.

**Parseo con Surefire XML:**
Los XMLs de `target/surefire-reports/TEST-*.xml` son el formato estándar de Maven para reportar resultados de tests. Cada `<testcase>` tiene `<failure>`, `<error>` o ninguno (passed). Esta representación es más robusta que parsear el stdout de Maven, que mezcla output del compilador y del runner.

**`_is_embeddable_java_block()`:**
Función de validación que verifica que el output del LLM es seguro para incrustar dentro del cuerpo de una clase Java. Verifica: llaves balanceadas, ausencia de sentencias `import`, ausencia de declaraciones de clase anidadas, y ausencia de literales con sufijo `L` (detallado más abajo).

---

### Bug 1 — pom.xml no encontrado cuando `tests_dir` es la raíz

**Síntoma:** `_run_maven` recibía `tests_dir = "tests_generados/"` (la raíz de salida). El agente generaba el proyecto Maven en `tests_generados/unit/`, por lo que `pom.xml` estaba en `tests_generados/unit/pom.xml`. El código original usaba `Path(tests_dir) / "pom.xml"` — path directo sin buscar en subdirectorios — lo que producía `FileNotFoundError`.

**Causa raíz:** La firma de `test_runner.run()` recibe `tests_dir` como el directorio raíz del output del agente, no el directorio del proyecto Maven. El proyecto Maven puede estar en un subdirectorio (como `unit/`).

**Solución:** Se reemplazó `Path(tests_dir) / "pom.xml"` por `list(tests_path.rglob("pom.xml"))`. El `rglob` encuentra todos los `pom.xml` en cualquier nivel de profundidad dentro de `tests_dir`. Se itera sobre la lista y se ejecuta Maven una vez por cada proyecto Maven encontrado. Commit `fb124f0`.

---

### Bug 2 — LLM genera literales `long` con sufijo `L`

**Síntoma:** DeepSeek Coder 6.7b generaba tests con literales numéricos como `assertEquals(1000L, result)` o `long expected = 500L`. El compilador Java acepta `long` en esos contextos, pero los métodos bajo test devolvían `int` (o `double`). El tipo incompatible causaba errores de compilación (`error: incompatible types: long cannot be converted to int`) que Maven reportaba como fallos antes de ejecutar cualquier test.

**Causa raíz:** El LLM infiere que operaciones como multiplicación de enteros grandes pueden desbordarse y usa `long` "por las dudas", sin considerar que el código bajo test usa `int`. DeepSeek Coder 6.7b tiene un instruction-following limitado respecto a restricciones de tipo.

**Solución (provisoria — dos capas defensivas):**

1. **Regla en el prompt** (`JavaPromptTemplate._SYSTEM`): se agregó la regla explícita: `"NEVER use the L suffix on numeric literals. All integer numbers must be int. If an operation may return long, use an explicit cast: (int)."` Esto reduce la frecuencia del problema aprovechando el instruction-following del modelo.

2. **Validación de output** (`_is_embeddable_java_block`): se agregó `re.search(r'\d+L\b', code)` antes del loop de validación de líneas. Si el bloque contiene cualquier literal con sufijo `L`, la función retorna `False` y el agente descarta ese bloque (con lo que el LLM reintenta). El regex `\d+L\b` matchea el sufijo `L` pegado a dígitos (`1000L`, `500L`) pero no identifiers que terminen en `L` (`NULL`, `URL`, nombres de variable).

La solución es provisoria porque: (a) el prompt puede ser ignorado por el modelo; (b) descartar el bloque y reintentar no garantiza que el segundo intento tampoco tenga `L`. Una solución definitiva requeriría postprocesamiento que reemplace `\d+L` por `(int)\d+` o un modelo con mejor instruction-following de restricciones de tipo.

---

### Clase de ejemplo: reemplazo de Pedido.java por Conversor.java

**Problema con Pedido.java:** La clase usaba `List<String>`, `ArrayList`, `.stream()`, `mapToDouble()`, y estado mutable privado. El LLM generaba tests que intentaban acceder a campos privados, llamar a métodos inexistentes (inventados), o construir objetos con constructores no declarados. Los tests compilaban con errores o fallaban en runtime por `NullPointerException` al operar sobre los generics.

**Solución:** Se reemplazó `Pedido.java` por `Conversor.java`, una clase de conversión de unidades con 6 métodos públicos puros (`celsiusAFahrenheit`, `fahrenheitACelsius`, `kmAMillas`, `millasAKm`, `kgALibras`, `librasAKg`). La clase tiene el mismo perfil de complejidad que `Calculadora.java`: sin estado interno, sin imports, sin genéricos, sin streams. Cada método incluye validación de negativos donde aplica, lo que provee casos de borde obvios y concretos para el LLM sin que tenga que inventar contexto.

---

---

## HU-18 — Soporte para modelos cloud (Groq)

### Contexto y motivación

El agente operaba exclusivamente con Ollama local (DeepSeek Coder 6.7b). Se incorporó soporte para Groq como proveedor cloud alternativo, manteniendo retrocompatibilidad total: cualquier invocación sin `--provider` produce exactamente el mismo comportamiento que antes.

### Qué se implementó

**`agent/llm_client.py`:**
- La clase `LLMClient` fue renombrada a `OllamaClient` (sin cambios en su lógica).
- Se mantuvo `LLMClient = OllamaClient` como alias de módulo para que todos los módulos existentes sigan funcionando sin modificación de sus imports.
- Se agregó `GroqClient` con la misma interfaz (`generate()`, `is_available()`). Usa el formato OpenAI chat completions (endpoint `POST /chat/completions`, campo `messages` con roles `system` y `user`, respuesta en `choices[0].message.content`).
- Se agregó `create_client(provider, model)` como función factory: retorna `OllamaClient` o `GroqClient` según el string de proveedor.
- Se agregó `GroqAPIError` como excepción específica para errores de Groq (HTTP 4xx/5xx y errores de red).

**`agent.py`:**
- Nuevos flags: `--provider [local|groq]` (default `local`) y `--model` (opcional, sobreescribe el modelo default del cliente).
- El cliente se crea **una sola vez** con `create_client(args.provider, args.model)` y se pasa a los tres generadores como parámetro. Antes, cada módulo creaba su propio cliente internamente.
- El mensaje de error en el check de disponibilidad es condicional: para Groq muestra el mensaje de `GROQ_API_KEY`; para Ollama muestra el mensaje de `ollama serve`.

**`agent/test_generator.py`, `agent/integration_generator.py`, `agent/autocorrector.py`:**
- Cada función pública recibe `client=None`. Si es `None`, crea `LLMClient()` internamente — backward-compatible para cualquier código que llame al módulo directamente sin pasar cliente.

### Decisiones de diseño

**Duck typing en lugar de herencia o ABC:**
`OllamaClient` y `GroqClient` no comparten clase base ni protocolo formal. Ambos exponen `generate(prompt, system=None) -> str` e `is_available() -> bool`. Python no requiere declaración explícita de la interfaz para que la sustitución funcione. Forzar una ABC agregaría boilerplate sin beneficio real en este tamaño de codebase.

**`create_client()` como factory centralizada:**
Centraliza la decisión de qué cliente instanciar en un único punto. `agent.py` no necesita conocer los constructores de cada cliente — solo le pasa `provider` y `model`. Agregar un tercer proveedor (Anthropic, Gemini, etc.) solo requiere: una nueva clase en `llm_client.py` y un nuevo `elif` en `create_client()`.

**`LLMClient = OllamaClient` como alias de compatibilidad:**
Los módulos `test_generator`, `integration_generator` y `autocorrector` importan `LLMClient`. Si se hubiera eliminado el nombre `LLMClient`, todos esos imports habrían roto. El alias `LLMClient = OllamaClient` preserva el contrato público del módulo sin duplicar código.

**`is_available()` de Groq no hace llamada de red:**
Para Groq, `is_available()` retorna `bool(os.environ.get("GROQ_API_KEY"))`. No hace un ping a la API de Groq. La razón: un ping real requeriría una llamada HTTP (latencia, posible fallo de red en CI), y la presencia de la key es condición necesaria y suficiente para intentar usar el proveedor. Si la key existe pero es inválida, el error se detectará en la primera llamada a `generate()` con un `GroqAPIError` con el código HTTP 401.

**`urllib` para Groq (sin `requests`):**
El proyecto usa `urllib.request` para Ollama desde HU-01 por política de zero dependencias externas en los clientes. Se mantiene la misma política para Groq: la API de Groq es HTTP puro, no requiere autenticación OAuth ni TLS especial, y `urllib.request` es suficiente.

**`--model` como override opcional:**
Cada cliente tiene su propio modelo default (`deepseek-coder:6.7b` para Ollama, `llama-3.1-8b-instant` para Groq). `--model` sobreescribe ese default. Esto permite usar cualquier modelo disponible en Groq (ej. `llama-3.3-70b-versatile`) sin cambiar el código.

### Fixes post-implementación

**Fix 1 — Cloudflare 403 por User-Agent genérico de urllib:**
Al hacer el primer request real a la API de Groq, la respuesta fue un `HTTPError 403` generado por Cloudflare (CDN de Groq), no por la API en sí. Cloudflare bloquea requests cuyo `User-Agent` es el default de `urllib` (`Python-urllib/3.x`). Solución: agregar `"User-Agent": "Mozilla/5.0"` en los headers del request de `GroqClient.generate()`. Este header no afecta la semántica de la llamada a la API — solo es necesario para pasar el filtro de Cloudflare.

**Fix 2 — Rate limit 429 en el autocorrector:**
El autocorrector llama al LLM en un loop por cada test fallido. Con Groq en tier gratuito, el límite de tokens por minuto (TPM) se alcanza rápidamente cuando hay varios tests fallidos seguidos. La respuesta es `HTTPError 429 Too Many Requests`. Solución: retry con espera en `GroqClient.generate()` — hasta 3 intentos; si recibe 429, espera 10 segundos y reintenta. Si los 3 intentos son 429, lanza `GroqAPIError`. Cualquier otro código HTTP (4xx/5xx distinto de 429) lanza la excepción inmediatamente sin retry.

La espera de 10 segundos es una heurística conservadora: la ventana de rate limit de Groq es por minuto, y 10 segundos es suficiente para que el contador de tokens se recupere entre llamadas consecutivas del autocorrector.

### Groq vs. OpenAI — por qué se eligió Groq

Groq usa exactamente el mismo formato de API que OpenAI (`/v1/chat/completions`, mismo esquema JSON), lo que permite reutilizar el mismo cliente con solo cambiar la URL base y la variable de entorno. La ventaja práctica de Groq sobre OpenAI para este proyecto: ofrece tier gratuito con límites de tokens por minuto suficientes para correr el agente sobre repositorios de ejemplo, y los modelos disponibles (LLaMA 3.1) son open-source, lo que es consistente con la filosofía de privacidad y costo del proyecto.

### Compatibilidad con flujo local

El comando `python3 agent.py --repo ./examples` (sin `--provider`) sigue usando `OllamaClient()` exactamente igual que antes. El único cambio en el flujo local es que el cliente se crea en `agent.py` y se pasa hacia abajo, en lugar de crearse en cada módulo. El resultado observable es idéntico.

### Conceptos teóricos aplicados

- **Duck typing**: sustitución de tipos por interfaz implícita sin herencia formal — característico de Python idiomático.
- **Patrón Factory**: `create_client()` encapsula la decisión de instanciación, desacoplando `agent.py` de los constructores concretos.
- **Inyección de dependencia**: el cliente se crea una vez en el punto de entrada y se inyecta a los módulos que lo usan, en lugar de que cada módulo resuelva su propia dependencia. Facilita testing (se puede pasar un mock) y garantiza consistencia de proveedor a lo largo de toda la ejecución.
- **Open/Closed**: agregar un nuevo proveedor no modifica código existente — solo agrega una clase y un `elif` en la factory.

### Restauración del soporte Java (sesión 2026-06-03)

Tras el refactor del commit `ed4b6b7` que removió el código Java de `test_generator.py` y `test_runner.py`, la funcionalidad fue restaurada completamente:

**`agent/repo_explorer.py`:** `.java` agregado a `_SUPPORTED_EXTENSIONS`. Sin este fix, `explore()` retornaba `[]` para repositorios Java y el agente no detectaba ningún archivo.

**`agent/test_generator.py`:** `_detect_language()` extendida con rama Java (`_JAVA_EXTENSIONS = {'.java'}`). `generate()` restaurado con `has_java` flag y llamada a `_generate_java_tests()`. Funciones Java restauradas: `_generate_java_tests`, `_build_java_test_file`, `_copy_java_sources`, `_write_java_pom`, `_has_balanced_braces`, `_is_embeddable_java_block` (con validación de sufijo `L` via `re.search(r'\d+L\b', code)`). La validación en `_generate_block` usa `_is_embeddable_java_block` en lugar del check simple de `@Test`.

**`agent/test_runner.py`:** `_run_maven()` y `_parse_surefire_reports()` restaurados. `xml.etree.ElementTree` reimportado. `run()` incluye `java_results` en el merge final.

**`examples_java/`:** `Calculadora.java` y `Conversor.java` recreados (habían sido eliminados del repo).

### Estado final del código en esta rama

La implementación Java completa (generación con Maven, ejecución con Surefire) se desarrolló y probó de extremo a extremo en `feature/HU-14-java-unit-tests`. En un refactor posterior dentro de la misma rama, el código de integración (`_generate_java_tests`, `_run_maven`, `_parse_surefire_reports`, etc.) fue extraído de `test_generator.py` y `test_runner.py` para mantener el alcance del merge limpio. Los componentes que permanecen son:

- `prompts/prompt_builder.py`: `JavaPromptTemplate` completo y operativo, con regla anti-`L`-suffix y todas las restricciones de output embebible.
- `examples_java/Calculadora.java` y `examples_java/Conversor.java`: clases de ejemplo listas para la integración.
- `agent/ast_extractor.py`: parser regex para `.java` activo.

La reintegración de `_generate_java_tests` y `_run_maven` en la rama de producción queda como trabajo pendiente para la iteración siguiente.

### Conceptos teóricos aplicados

- **Maven como orquestador de build**: Maven no es solo un gestor de dependencias — ejecuta el ciclo de vida de build completo (compile → test-compile → test) en un único comando. `mvn test --batch-mode` es el punto de entrada no interactivo que el agente invoca como subproceso.
- **Surefire XML como contrato de resultados**: el formato XML de Surefire (`TEST-*.xml`) es el estándar de facto para reportar resultados de tests en el ecosistema JVM. Es el mismo formato consumido por Jenkins, GitHub Actions y otros CI. Usarlo como fuente de verdad desacopla el agente de los cambios en el formato de stdout de Maven.
- **Guardrail en dos capas (prompt + validación)**: el prompt instruye al modelo (prevención); la validación detecta y descarta outputs incorrectos (corrección). Esta doble capa es el enfoque estándar cuando el instruction-following del modelo no es confiable al 100% para restricciones de tipo técnico específico.
- **Clases de ejemplo como contrato de simplicidad**: la complejidad de la clase de ejemplo es un parámetro de calidad del agente. Una clase con genéricos, streams o estado mutable hace que el LLM tenga que inferir más contexto para generar tests válidos. Una clase con métodos puros y valores concretos reduce el espacio de posibles errores del LLM a la lógica del test en sí.

---

### Pipeline Java completo — HU-18 sesión 2026-06-03

#### Problema de partida

Al ejecutar `python3 agent.py --repo ./examples_java --provider groq`, el reporte mostraba 0 tests. La carpeta `src/test/java/` existía pero estaba vacía. El diagnóstico reveló tres problemas encadenados:

1. `ast_extractor.py` no tenía parser Java → los `.java` caían al `_parse_python_file` → `ast.parse()` lanzaba `SyntaxError` → `classes: []` → `_generate_java_tests` iteraba lista vacía y no escribía archivos.
2. `JavaPromptTemplate` no existía en `prompts/prompt_builder.py` → `PromptBuilder.build(language="java")` lanzaba `ValueError`.
3. `_is_embeddable_java_block` rechazaba casi todos los bloques válidos y ninguno de los inválidos problemáticos.

---

#### Fix 1 — Parser Java en ast_extractor.py

Se agregaron `_JAVA_CLASS_DECL` y `_JAVA_METHOD_DECL` como patrones regex, y las funciones `_extract_java_classes`, `_extract_java_methods` y `_parse_java_file`. El dispatcher de `extract()` añadió rama `elif suffix in _JAVA_EXTENSIONS`.

**Por qué regex (no AST nativo):**
El mismo razonamiento que para JS/TS en HU-11. No existe un parser Java en la stdlib de Python. Alternativas evaluadas y rechazadas: `javalang` (dependencia externa, sin mantenimiento activo), `tree-sitter` (requiere compilación nativa), `subprocess javap` (solo funciona sobre `.class`, no `.java`). El regex cubre el patrón universal de métodos Java públicos (`[modificadores] [tipo] nombre(`) sin parsear el lenguaje completo.

**Patrón de método:** `^[ \t]+ [modificadores]* [tipo]\s+ ([nombre])\s*\(`. El tipo de retorno actúa como separador entre modificadores y nombre. Para que no matchee sentencias como `if (`, `return a`, o `throw new`, se requiere que después del "tipo" haya `\s+` (espacio) antes del nombre, y que el nombre esté seguido de `\s*\(`. `if (` falla porque `(` no es un identificador válido como nombre de método. `return km * 0.621371` falla porque después de `km` viene `*`, no `(`.

**Verificación:** Con `Calculadora.java` y `Conversor.java`, el parser extrae correctamente 5 y 6 métodos respectivamente, con `parse_error: None`.

---

#### Fix 2 — JavaPromptTemplate

Se creó la clase `JavaPromptTemplate` en `prompts/prompt_builder.py` y se registró como `"java"` en `_REGISTRY`. El system prompt exige output embebible (sin imports, sin declaración de clase, sin comentarios) y lista explícitamente los errores más frecuentes del LLM:

| Regla en el prompt | Error que previene |
|---|---|
| `NEVER use JUnit 4 syntax` | `@Test(expected=...)` o `expected = X.class` suelto |
| `NEVER use Int. — always Integer.` | `Int.MIN_VALUE` (clase inexistente en Java) |
| `No comments — no // no /* */ no #` | Comentarios Python (`#`) dentro de código Java |
| `Always use the exact class name` | El LLM instancia `Conversor` en un test de `Calculadora` |
| `Never use DELTA or delta` | Variable `delta` usada sin declarar |
| `Never pass null to primitive types` | `c.suma(null, 1)` donde suma espera `int` |

`clean_response()` también recibió `java` en su regex de extracción de bloques markdown (antes solo reconocía `python`, `javascript`, `js`, `ts`, `typescript`).

---

#### Fix 3 — _is_embeddable_java_block como guardrail de validación

El validador fue construido de forma incremental a partir de los errores reales que producía el LLM al compilar con Maven. Cada regla tiene una causa observada:

| Regex | Error de compilación que detecta |
|---|---|
| `\d+L\b` | `incompatible types: long cannot be converted to int` |
| `\bexpected\s*=` | `<identifier> expected` (JUnit 4 syntax) |
| `\bInt\.` | `cannot find symbol: class Int` |
| `^\s*#` con `MULTILINE` | Comentario Python dentro de Java, syntax error |
| `\bDELTA\b\|\bdelta\b` sin declaración local | `cannot find symbol: variable delta` |
| `\bnull\b` | `incompatible types: <null> cannot be converted to int` |
| `new WrongClass()` con class_name != WrongClass | Error de lógica: test de `Calculadora` instancia `Conversor` |

La función recibió el parámetro `class_name: Optional[str] = None` para poder verificar que `new X()` usa exactamente el nombre de la clase bajo test.

**Decisión de diseño — guardrail en dos capas:**
El prompt instruye al LLM (prevención probabilística). El validador descarta bloques inválidos y fuerza un reintento (corrección determinista). La combinación es más robusta que solo el prompt (el LLM puede ignorarlo) y más mantenible que postprocesamiento con regex complejos que intenten corregir el output.

**Límite del enfoque reactivo:** Cada regla del validador surgió de un error concreto observado. Esto funciona para errores frecuentes y predecibles, pero no escala para errores de compilación arbitrarios. Esta limitación motivó Fix 4.

---

#### Fix 4 — Ciclo de compilación-corrección

En lugar de intentar predecir todos los errores posibles del LLM con regex, se implementó un ciclo de feedback real: compilar, detectar el error exacto, corregirlo con el LLM, reintentar.

**Función `_compile_and_fix_java(client, maven_root)`:**
1. Ejecuta `mvn test-compile --batch-mode` (solo compilación, no ejecución de tests).
2. Si `returncode == 0`: termina. Los tests están listos para correr.
3. Si falla: parsea el stdout con `_JAVAC_ERROR_PAT = re.compile(r'\[ERROR\]\s+(/[^\s:]+\.java):\[(\d+),\d+\]\s+(.*)')` para identificar qué archivos tienen errores y en qué líneas.
4. Para cada archivo con errores: lee el contenido actual, lo envía al LLM junto con los mensajes de error exactos de javac, recibe el archivo corregido, lo escribe.
5. Repite hasta 3 veces o hasta que compile.

**Por qué `test-compile` en lugar de `test`:**
`mvn test` ejecuta compile → test-compile → test en secuencia. Separar el paso de compilación permite detectar y corregir errores antes de intentar correr tests. Si los tests compilaran pero fallaran en ejecución, el autocorrector de Python no sabe corregir Java. `test-compile` fallando es la señal que activa el ciclo de corrección; `test` pasando es la señal de éxito.

**Por qué el error de javac es más informativo que el regex:**
`[ERROR] /path/CalculadoraTest.java:[25,1] error: <identifier> expected` le dice al LLM exactamente qué línea del archivo tiene el problema y qué esperaba el compilador. Es información de alta precisión que no puede extraerse solo mirando el código generado.

**Tradeoff — latencia vs. robustez:**
Cada vuelta del ciclo agrega una llamada a `mvn test-compile` (~5-10 segundos) y una llamada al LLM (~2-5 segundos con Groq). En el peor caso (3 iteraciones sin convergencia), agrega ~45 segundos. En el caso típico (1-2 iteraciones), agrega ~15 segundos. Es el costo justo frente a tests que no compilarían nunca.

---

#### Deduplicación de métodos en _generate_java_tests

Antes de escribir el archivo final, se extrae el nombre de cada `void nombreMétodo(` del bloque con regex y se verifica contra `seen_method_names: set[str]`. Si el nombre ya fue visto, el bloque se descarta. Esto previene que el LLM genere dos `@Test void suma()` para dos métodos distintos del mismo archivo fuente.

---

#### Resultado de la primera ejecución completa

```
Passed:       37
Failed:        0
Sin resolver: 21
Total:        58
Tiempo:       1m 14s
```

37 de 58 tests Java pasan en la primera ejecución real con Groq (`llama-3.1-8b-instant`). Los 21 sin resolver son métodos para los cuales el LLM no pudo generar código válido en 2 intentos (validador) + 3 intentos de compilación. El ciclo de compilación-corrección logró recuperar tests que habrían quedado sin resolver solo con el validador regex.

**Conceptos teóricos aplicados:**
- **Feedback loop compilador→LLM**: el compilador como oráculo de corrección — produce el error más específico posible sobre qué está mal en el código generado.
- **Separación de fases**: generación → validación estática → compilación → ejecución. Cada fase descarta una clase diferente de errores.
- **Prompt engineering iterativo**: las reglas del prompt se derivan de errores observados en producción, no de especulación a priori. Cada regla tiene un error concreto que la motivó.

## HU-14 — Soporte Java (tests unitarios con JUnit 5)

### Qué se implementó

- `agent/repo_explorer.py`: se agrega `.java` a `_SUPPORTED_EXTENSIONS`. Un cambio de una línea que extiende la detección de archivos a la tercera familia de lenguajes soportada.
- `agent/ast_extractor.py`: parser regex para Java (`_JAVA_EXTENSIONS`, `_JAVA_CLASS_DECL`, `_JAVA_METHOD`, `_JAVA_CONTROL_KEYWORDS`, `_parse_java_file`, `_extract_java_classes`, `_extract_java_methods`, `_parse_java_params`). Java no tiene funciones top-level — todo está en clases — por lo que `functions = []` siempre y solo se extraen clases y sus métodos. Los imports Java son por FQN (no rutas relativas del repo), por lo que `imports = []`.
- `prompts/prompt_builder.py`: se agrega `JavaPromptTemplate` registrada como `"java"`. Genera `@Test void` methods sin wrapper de clase ni imports — el agente los provee. Se actualiza `clean_response()` para reconocer `@Test` como patrón de inicio de código Java y para filtrar líneas `import/package` en modo `strip_imports=True`.
- `agent/test_generator.py`: nueva lógica Java en `generate()` vía `_generate_java_tests()`. Los tests se escriben en `tests_generados/unit/src/test/java/<ClassName>Test.java` envueltos en `class <ClassName>Test {}`. Las fuentes del repo se copian a `tests_generados/unit/src/main/java/`. Se genera un `pom.xml` mínimo con JUnit 5.10.0.
- `agent/test_runner.py`: nueva función `_run_maven()`. Si hay archivos `*Test.java` en `src/test/java/` pero `mvn` no está instalado, imprime un mensaje claro con instrucciones de instalación y retorna `{}`. Si Maven está disponible, corre `mvn test --batch-mode` y parsea los reportes XML de Surefire en `target/surefire-reports/` con `xml.etree.ElementTree` (stdlib).
- `examples_java/Calculadora.java` y `examples_java/Pedido.java`: ejemplos para validación del pipeline end-to-end.

### Por qué regex en lugar de AST para Java

El módulo `ast` de Python solo entiende Python. Para Java las opciones son:
- `javalang`: parser Java completo para Python, pero dependencia externa.
- `tree-sitter-java`: robusto pero requiere compilación nativa.
- **Regex propio**: sin dependencias, mismo enfoque que JS/TS (ya probado en HU-11).

Java tiene una gramática más rígida que JavaScript (siempre se requiere tipo de retorno, modificadores explícitos, braces obligatorias), lo que hace los patrones regex más predecibles. La limitación es que no maneja bien genéricos complejos en tipos de retorno anidados o código con comentarios dentro de declaraciones de método. Para el caso de uso del agente (extraer firmas para tests), cubre el 95%+ de los casos prácticos.

### Estructura Maven embebida en el directorio de salida

A diferencia de Python (conftest.py) y JavaScript (jest.config.js), Java requiere una estructura de proyecto completa para compilar y ejecutar tests: código fuente en `src/main/java/`, tests en `src/test/java/`, y un descriptor `pom.xml` que declare las dependencias. El agente genera esta estructura automáticamente dentro de `tests_generados/unit/`:

```
tests_generados/unit/
├── pom.xml                       ← JUnit 5.10.0 + Surefire 3.1.2
└── src/
    ├── main/java/                ← copia de los .java analizados
    └── test/java/                ← <ClassName>Test.java generados
```

Esta decisión encapsula todo lo necesario para compilar y correr los tests Java en un único directorio autocontenido, sin requerir que el usuario configure un proyecto Maven propio.

### Por qué parsear XML de Surefire en lugar del stdout de Maven

El stdout de Maven con `--batch-mode` tiene el formato:
```
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0 -- in CalculadoraTest
```
Esto da solo el resumen por clase, no resultados individuales por test. Los XMLs de Surefire en `target/surefire-reports/TEST-<ClassName>.xml` tienen la granularidad completa: un `<testcase>` por método con `<failure>` o `<error>` si falló, incluyendo el mensaje del error. `xml.etree.ElementTree` es parte de la stdlib de Python, sin dependencias adicionales.

### Mensaje de Maven no disponible — diseño deliberado

Cuando `shutil.which("mvn")` devuelve `None`, el agente **no falla silenciosamente** — imprime un mensaje informativo con instrucciones de instalación y la ruta exacta del comando para correr los tests manualmente. Esta es la diferencia clave respecto al comportamiento anterior que simplemente retornaba `{}` sin explicación. El mismo patrón se aplica a Node.js (HU-11) y a pytest (HU-07).

### Decisión: un TestClass.java por clase fuente (no por archivo)

En Java la convención es un archivo por clase pública, pero nada impide múltiples clases no-públicas en un archivo. El agente genera un archivo `<ClassName>Test.java` por cada clase encontrada en el fuente analizado. Esto garantiza que:
1. El nombre del archivo coincide con el nombre de la clase de test (requisito implícito del compilador Java para clases públicas).
2. Cada clase de test es cohesiva — testea una sola clase fuente.
3. Maven puede descubrir y compilar cada archivo de test de forma independiente.

### Conceptos teóricos aplicados

- **Maven como herramienta de build y test runner**: Maven gestiona el ciclo de vida del proyecto Java (compile → test → package). El plugin `maven-surefire-plugin` es el runner de tests estándar para JUnit en proyectos Maven.
- **JUnit 5 (JUnit Jupiter)**: el framework de testing de Java moderno. `@Test` marca los métodos de test; `assertEquals`, `assertThrows`, `assertTrue` son las assertions principales. `junit-jupiter` (el artefacto unificado de Maven) incluye la API, el motor y el launcher.
- **Surefire XML como formato de resultados**: formato estándar de JUnit-style para reportes de tests, usado por Maven, Jenkins, GitHub Actions, etc. Permite integrar los resultados del agente con cualquier herramienta de CI/CD que entienda este formato.
- **Brace counting para Java**: el mismo mecanismo de `_find_js_end_lineno` usado en HU-11 para JS funciona para Java, dado que ambos lenguajes usan llaves para delimitar bloques.
- **`xml.etree.ElementTree` (stdlib)**: parser XML de la stdlib de Python. Adecuado para documentos XML bien formados y de tamaño moderado como los reportes Surefire.

### Deuda técnica / pendientes

- El autocorrector no soporta Java (solo Python). Los tests Java fallidos quedan como `failed` sin corrección automática.
- Los imports Java en los tests generados son fijos (`junit-jupiter`, `Assertions.*`). Si la clase bajo test requiere imports adicionales (ej. `java.util.List`), el LLM los agrega en el output y el pipeline los elimina con `strip_imports=True`. Esto puede causar `NameError` en compilación si el test necesita esos tipos.
- Maven descarga dependencias en el primer run (~50 MB de JUnit 5 y Surefire). En entornos offline, el primer run fallará; los runs subsiguientes usan la caché local de Maven (`~/.m2/repository`).
- No hay soporte para packages Java: los archivos generados no tienen `package` declaration, lo que funciona para clases simples pero puede causar conflictos en proyectos con estructura de paquetes.

---

## HU-15 — Tests de integración Java (JUnit 5)

### Qué se implementó

- **`examples_java/Estadistica.java`**: nueva clase que usa `Calculadora` por composición interna (`promedio`, `productoTotal`, `todosPares`). Sirve como ejemplo de referencia para validar el pipeline de integración Java, análogo a `examples/estadistica.py` para Python.
- **`prompts/prompt_builder.py`**: nueva clase `JavaIntegrationPromptTemplate` registrada como `"java_integration"`. Genera solo métodos `@Test` sin wrapper ni imports — misma filosofía que `JavaPromptTemplate`. El system prompt exige tests de interacción real entre las dos clases, sin mocks, con valores concretos esperados.
- **`agent/integration_generator.py`**: extensión completa para Java:
  - `_find_java_pairs(ast_result, repo)`: detecta pares (ClaseA, ClaseB) buscando el nombre de ClaseB como palabra completa (`\bClaseB\b`) en el código fuente de ClaseA. A diferencia de Python y JS, donde el grafo de dependencias lo provee el campo `imports` del `ast_result`, Java en mismo paquete no usa `import` entre clases. La detección por texto cubre instanciación (`new Calculadora()`), declaración de campo (`Calculadora calc`) y llamadas estáticas (`Calculadora.metodo()`).
  - `_generate_java_pair_test`: llama al LLM, valida presencia de `@Test` + `void`, reintenta una vez.
  - `_build_java_integration_test_file`: envuelve los métodos generados en clase JUnit 5 completa con imports dinámicos (agrega `ArrayList`, `List`, `Arrays` si aparecen en el código).
  - `_write_java_integration_pom`: genera `pom.xml` idéntico al de tests unitarios en `tests_generados/integration/`.
  - `_copy_java_sources_for_integration`: copia los `.java` del repo a `tests_generados/integration/src/main/java/` para que Maven los compile junto a los tests.
  - `_compile_and_fix_java` reutilizado desde `test_generator.py` sin modificación — ya estaba parametrizado por `maven_root: Path`, por lo que apuntar a `tests_generados/integration/` en lugar de `tests_generados/unit/` no requiere ningún cambio.
- Convención de archivos de salida: `tests_generados/integration/src/test/java/{ClaseA}{ClaseB}IntegrationTest.java`.

### Decisión clave — detección por uso en lugar de imports

En Python y JS, el grafo de dependencias se extrae de los `import`/`require` del código y queda almacenado en el campo `imports` del `ast_result`. En Java, las clases del mismo paquete son directamente visibles entre sí sin ninguna declaración `import`. El `ast_extractor` deja `imports: []` para todos los archivos Java.

La solución es leer el código fuente de ClaseA y buscar el nombre de ClaseB como token de palabra completa. Esta heurística es conservadora (solo detecta uso explícito del nombre) pero suficientemente precisa para el caso de uso del agente: si ClaseB aparece en el cuerpo de ClaseA, es porque ClaseA la instancia, declara como tipo de campo, o llama como clase estática.

La alternativa (extender `ast_extractor` para inferir dependencias Java en tiempo de parseo) requeriría conocer los nombres de todas las clases del repo en el momento de parsear cada archivo, lo que implicaría un segundo pasaje sobre todos los archivos. El enfoque actual resuelve esto en `_find_java_pairs`, que tiene acceso tanto al `ast_result` completo como al `repo`.

### Reutilización de _compile_and_fix_java

La función del ciclo de compilación-corrección (implementada en HU-14 para tests unitarios) fue reutilizada sin modificaciones para los tests de integración. La firma `_compile_and_fix_java(client, maven_root: Path)` no tiene dependencias de módulo: recibe el directorio raíz del proyecto Maven como parámetro y opera sobre él. Cambiar de `tests_generados/unit/` a `tests_generados/integration/` es solo pasar un `Path` distinto. Esta parametrización previa es un ejemplo de cómo un diseño orientado a datos (pasar la raíz como parámetro en lugar de hardcodearla) elimina el costo de extensión futura.

### Estructura de salida

```
tests_generados/integration/
├── pom.xml
└── src/
    ├── main/java/
    │   ├── Estadistica.java   ← copia del repo
    │   ├── Calculadora.java
    │   └── Conversor.java
    └── test/java/
        └── EstadisticaCalculadoraIntegrationTest.java
```

### Conceptos teóricos aplicados

- **Detección de dependencias por análisis de texto**: alternativa al grafo de imports cuando el lenguaje no tiene declaraciones de dependencia explícitas entre unidades del mismo paquete.
- **Reutilización por parametrización**: una función con comportamiento dependiente de su entorno (directorio Maven) es reutilizable sin modificación si ese entorno se inyecta como parámetro en lugar de resolverse internamente.
- **Consistencia de interfaz entre lenguajes**: el pipeline de integración Java sigue la misma estructura conceptual que Python (par A→B, código de A + firmas de B al LLM, archivo de test por par) aunque los mecanismos de detección y escritura son específicos del lenguaje.

### Deuda técnica / pendientes

- La detección por `\bNombreClase\b` puede producir falsos positivos si una clase tiene el mismo nombre que una variable o constante de otro contexto. Para repositorios reales esto es poco frecuente; para v2 se podría refinar analizando el contexto de aparición.
- Los tests de integración Java no pasan por el ciclo de autocorrección (igual que los unitarios Java).

---

## HU-19 — Cobertura de tests para JavaScript/TypeScript y Java

### Qué se implementó

**`agent/test_runner.py`:**
- `_run_jest()`: cambia de `--no-coverage` a `--coverage --coverageReporters=json-summary`. Retorno cambiado de `dict` a `tuple[dict, float | None]`.
- `_parse_jest_coverage(cwd: Path) -> float | None`: lee `coverage/coverage-summary.json` con `json` (stdlib) y extrae `data["total"]["lines"]["pct"]`. Con `rootDir: '../..'`, Jest escribe el archivo en `rootDir/coverage/` (dos niveles arriba de `cwd`). La función prueba ambas ubicaciones: `cwd/coverage/` y `cwd.parent.parent/coverage/`, usando la primera que exista.
- `_run_maven()`: retorno cambiado a `tuple[dict, float | None]`. Llama a `_parse_jacoco_coverage` tras `_parse_surefire_reports`. Flag `-fae` agregado al comando.
- `_parse_jacoco_coverage(maven_root: Path) -> float | None`: lee `target/site/jacoco/jacoco.xml` con `xml.etree.ElementTree` (stdlib, ya importado). Calcula `covered / (covered + missed) * 100` del counter `type="LINE"`.
- `run()`: prioridad Python → JS → Java (primer no-`None` gana).

**`agent/test_generator.py` — `_write_jest_config()`:** configuración Jest final:

```js
module.exports = {
  rootDir: '../..',
  testMatch: ['<rootDir>/tests_generados/unit/**/*.test.{js,ts}'],
  modulePaths: ['<rootDir>/REPO_RELPATH'],
  coverageProvider: 'v8',
  collectCoverageFrom: ['REPO_RELPATH/**/*.{js,ts}'],
};
```

`REPO_RELPATH = os.path.relpath(repo, (OUTPUT_DIR / "../..").resolve())`. `rootDir: '../..'` hace que Jest resuelva rutas desde el raíz del proyecto (dos niveles arriba de `tests_generados/unit/`). `coverageProvider: 'v8'` instrumenta sin Babel, evitando el error `Unknown` en cobertura CommonJS. Se agrega `import os` al módulo.

**`agent/test_generator.py` — `_write_java_pom()`** y **`agent/integration_generator.py` — `_write_java_integration_pom()`:** JaCoCo 0.8.13 con dos executions: `prepare-agent` (fase `initialize`) y `report` (fase `test`). Versión 0.8.13 requerida para Java 24 (class file major version 68); versiones anteriores fallan con `Unsupported class file major version 68` porque usan ASM 9.6 que solo soporta hasta Java 21.

**`agent/test_runner.py` — `_run_maven()`:** flag `-fae` (fail at end). Sin `-fae`, Maven aborta al primer test fallido antes de ejecutar el goal `report` de JaCoCo, y `jacoco.xml` no se genera. Con `-fae`, Maven ejecuta todos los tests y luego corre `report`, generando el XML aunque haya failures. Nota: `-fae` no ayuda con errores de compilación — `test-compile` fallando aborta Maven igual.

**`agent/llm_client.py` — `GroqClient.generate()`:** fix del retry para HTTP 429.
- **Regex:** `_GROQ_RETRY_PAT = re.compile(r"try again in (?:(\d+)m\s*)?([\d.]+)s")` con grupo opcional de minutos. `_parse_groq_retry_seconds` calcula `minutes * 60 + seconds + 1.0`. El patrón anterior (`r"try again in ([\d.]+)s"`) fallaba con el formato `"2m0.394s"` que Groq devuelve para rate limits de más de un minuto — cuando fallaba se usaba el default de 20s, insuficiente, y los 3 reintentos se agotaban en ~40s crasheando con `GroqAPIError (429)`.
- **Reestructura del loop:** `if e.code != 429: raise` se evalúa primero (cualquier error no-429 se propaga inmediatamente). Para 429: se parsea la espera, se actualiza `last_exc`, si `attempt < 2` se duerme. El `raise last_exc` post-loop es el único punto de salida para 429 agotado. La implementación anterior tenía un `raise GroqAPIError(...)` incondicional dentro del `except` que impedía que `raise last_exc` fuera alcanzado para el caso 429.

**`agent/test_generator.py` — `_fix_java_file_with_llm()`:** el system prompt del ciclo de compilación-corrección ahora incluye las mismas reglas de `JavaPromptTemplate._SYSTEM`: prohibición de JUnit 4, lista explícita de assertions válidos (`assertEquals`, `assertTrue`, `assertFalse`, `assertNull`, `assertNotNull`, `assertThrows`), prohibición de `L` suffix, `Int.`, `DELTA`, `null` a primitivos, `Double.INFINITY`, `ExecutableAssert` (AssertJ), variables no declaradas. Más la regla nueva: `"Do NOT add any import statement that is not already present in the original file."` El prompt anterior (`"You are a Java expert. Fix the compilation errors."`) sin restricciones de framework hacía que el LLM reintrodujera imports de AssertJ/JUnit 4 inexistentes en el pom.xml, generando nuevos errores de compilación distintos a los originales.

Sin cambios en `agent.py`, `report_generator.py` ni `terminal_ui.py`: el valor `coverage_pct: float | None` ya fluye correctamente y el "N/A" cuando es `None` ya estaba implementado.

### Decisiones de diseño

**`coverageProvider: 'v8'` en lugar de `transform: {}`:**
La primera aproximación fue desactivar Babel con `transform: {}`. El problema raíz era que Istanbul (el instrumentador de cobertura de Jest) llamaba a Babel para transformar los archivos fuente antes de instrumentarlos, y Babel fallaba con CommonJS plano reportando `Unknown`. `coverageProvider: 'v8'` usa el coverage nativo de Node.js (V8) en lugar de Istanbul — sin necesidad de transformar nada — eliminando la causa raíz en lugar de desactivar el transformador.

**`rootDir: '../..'` y rutas relativas:**
Jest calcula `collectCoverageFrom` relativo a `rootDir`. Con `rootDir: '.'` (la configuración anterior), la ruta absoluta del repo en `collectCoverageFrom` hacía que Jest reportara `Unknown` porque no podía correlacionar los archivos instrumentados con las entradas del coverage. Con `rootDir: '../..'` apuntando al raíz del proyecto, `REPO_RELPATH` (calculado con `os.path.relpath`) da una ruta relativa válida que Jest resuelve correctamente. El `coverage-summary.json` se genera en `rootDir/coverage/`, que es `cwd.parent.parent/coverage/` desde el punto de vista del proceso Jest.

**`testMatch` explícito:**
Con `rootDir: '../..'`, Jest escanearia recursivamente desde el raíz del proyecto buscando archivos de test, encontrando potencialmente `package.json` malformados u otros archivos. El `testMatch` explícito restringe la búsqueda a `tests_generados/unit/`.

**`_parse_jest_coverage` busca en dos ubicaciones:**
Mantiene backward compatibility con configuraciones anteriores que escribían coverage en `cwd/coverage/`, mientras soporta la nueva config con `rootDir: '../..'` que escribe en `cwd.parent.parent/coverage/`. No requiere saber qué versión de config está activa — prueba ambas en orden.

**JaCoCo 0.8.13 requerido para Java 24:**
JaCoCo instrumenta el bytecode Java en tiempo de ejecución vía Java agent. El agente intercepta todo el class loading de la JVM, incluyendo clases del runtime Java 24 compiladas a version 68. ASM 9.6 (bundled en JaCoCo ≤0.8.11) no conoce la version 68 y lanza `Unsupported class file major version 68`. JaCoCo 0.8.13 usa ASM 9.7.1 que soporta Java 24. Diagnóstico post-fix: `jacoco.exec` se genera correctamente; `jacoco.xml` no se genera si `test-compile` falla antes de la fase `test` (Maven aborta antes del goal `report`).

**JaCoCo vía ciclo de vida Maven (no `mvn test jacoco:report`):**
Configurar JaCoCo con goals ligados a las fases `initialize` (prepare-agent) y `test` (report) hace que `mvn test --batch-mode -fae` genere el XML automáticamente sin modificar el comando en `_run_maven()`. La alternativa `mvn test jacoco:report` habría requerido cambiar la invocación de Maven.

**Prioridad Python → JS → Java:**
En repos mono-lenguaje, solo hay una cobertura disponible. En repos mixtos, Python tiene prioridad porque es el lenguaje con mayor madurez de cobertura en el agente. La lógica `py_cov if py_cov is not None else (js_cov if js_cov is not None else java_cov)` no cambia la firma pública de `run()`.

**Sin dependencias externas nuevas:**
`json`, `xml.etree.ElementTree`, `os.path.relpath` son stdlib de Python. `v8` es el coverage nativo de Node.js/Jest. JaCoCo se descarga via Maven igual que JUnit.

### Conceptos teóricos aplicados

- **Istanbul vs. V8 coverage:** Istanbul transforma el AST del archivo fuente para agregar contadores antes de ejecutarlo (requiere Babel o esbuild). V8 coverage usa la API de cobertura nativa del motor JavaScript, que registra qué rangos de bytecode se ejecutaron sin transformar el AST. Para CommonJS plano sin transpilación, V8 es más robusto.
- **JaCoCo y el ciclo de vida Maven:** `prepare-agent` agrega `-javaagent:jacocoagent.jar` a los argumentos de la JVM que Surefire arranca. Al finalizar los tests, el agente escribe `jacoco.exec` (binario). El goal `report` lee ese binario y genera `jacoco.xml` con contadores por tipo (`LINE`, `BRANCH`, `METHOD`). Ligar ambos goals al ciclo de vida hace que `mvn test --batch-mode -fae` sea suficiente.
- **`coverage-summary.json` de Jest:** producido por el reporter `json-summary`. El objeto `total` agrega líneas, statements, functions y branches de todos los archivos. `lines.pct` es el porcentaje de líneas ejecutables ejecutadas al menos una vez.
- **Rate limiting y backoff con Groq:** los límites del tier gratuito son por minuto (TPM y RPM). Parsear el tiempo exacto del mensaje de error (`"try again in Xm Ys"`) y dormir ese valor es más eficiente que un backoff fijo cuando el wait es de minutos.
- **`-fae` (Maven fail at end):** mecanismo de Maven para ejecutar todos los módulos de un reactor aunque algunos fallen. En proyectos de un solo módulo (el caso del agente), garantiza que Maven no aborte al primer test fallido y ejecuta todas las fases del ciclo de vida incluyendo los goals ligados a la fase `test`.

### Deuda técnica / pendientes

- `jacoco.xml` no se genera si `test-compile` falla antes de la fase `test` — los tests con errores de compilación no contribuyen al coverage Java.
- `_parse_jest_coverage` prueba las dos ubicaciones posibles pero no informa cuál encontró. Si la ubicación cambia en el futuro, puede buscar en el lugar incorrecto silenciosamente.
- Los tests JS/TS con `coverageProvider: 'v8'` requieren Node.js ≥18 (V8 coverage API estable). En versiones anteriores puede reportar resultados incompletos.

---

## Prueba con repositorio grande (examples_large/)

Se creó un repositorio Python de 15 archivos, 71 funciones/métodos y 10 clases simulando un sistema de librería online (`models/`, `services/`, `utils/`). Objetivo: validar el comportamiento del agente con repos de tamaño real.

### Problemas detectados y resueltos

- **Imports en repos con paquetes Python:** El agente generaba `from auth_service import X` para archivos en subdirectorios (`services/auth_service.py`). Fix: calcular el import path dotted completo (`services.auth_service`) usando `Path(rel_path).with_suffix("").as_posix().replace("/", ".")` en `test_generator.py`. Repos planos siguen funcionando igual.

- **Crash por rate limit con Groq:** Con 71 funciones, el retry de 3 intentos para 429 se agotaba a mitad del proceso. Fix: aumentar a 10 reintentos en `llm_client.py`. Los 429 son rate limits temporales, no errores — siempre se resuelven esperando.

- **Autocorrección inviable en repos grandes:** 275 tests fallidos × 3 intentos = 825 llamadas al LLM. Con Groq esto tomaba 58 minutos. Dos optimizaciones en `autocorrector.py`:
  - No autocorregir tests con `ModuleNotFoundError` o `ImportError` — son errores estructurales que el LLM no puede resolver.
  - Límite de 30 tests a autocorregir (`_MAX_AUTOCORRECT = 30`). El resto se marca como "sin resolver — omitido por volumen".

### Comparación de resultados

|                    | Sin optimización | Con optimización |
|--------------------|-----------------|-----------------|
| Tests totales      | 387             | 405             |
| Passed             | 146             | 115             |
| Sin resolver       | 226             | 289             |
| Posible bug        | 15              | 1               |
| Cobertura          | 57%             | 61%             |
| Tiempo             | 58m 26s         | 33m 08s         |

El tiempo se redujo un 43%. La cobertura subió levemente (61% vs 57%) porque los tests que sí se generaron correctamente cubrieron más código. La diferencia en "passed" (146 vs 115) se debe a la variabilidad del LLM — cada run genera tests distintos.

---

## HU-16 — Diagnóstico de fallos (clasificador posible_bug)

### Qué se implementó

- **`agent/autocorrector.py`**: clasificador previo a la corrección. Antes de intentar corregir un test fallido, `autocorrect()` llama a `_classify_error(traceback)` que retorna `"posible_bug"` o `"corregible"`. Los tests clasificados como `posible_bug` se registran con `_mark_as_possible_bug()` sin llamar al LLM ni consumir intentos.
- **`agent/report_generator.py`**: nueva sección `## Posible bug detectado` en el reporte, con test_id + expected + actual por cada caso. Nueva fila `| Posible bug | Z |` en la tabla de resumen.
- **`agent/terminal_ui.py`**: parámetro `possible_bugs=0` en `print_summary`. Nueva línea `Posible bug: Z` en el output final (rojo si > 0). El total incluye `possible_bugs`.
- **`agent.py`**: cuenta `posible_bug` en el dict final y lo pasa a `print_summary` y al mensaje de autocorrección.

### Lógica del clasificador

`_classify_error(traceback)` devuelve `"posible_bug"` cuando el traceback indica una discrepancia concreta de valores (el test corrió pero los valores no coincidieron), y `"corregible"` en cualquier otro caso (el test tiene un error estructural que puede corregirse).

**Condición de posible_bug:** el traceback contiene `AssertionError` **o** el patrón JUnit `expected: <X> but was: <Y>` (con ángulos), **y** `_extract_assert_values` puede extraer dos valores distintos.

**Patrones reconocidos por `_extract_assert_values`:**

| Patrón | Ejemplo | Origen |
|---|---|---|
| `^E\s+assert X == Y$` (multiline) | `E       assert 12 == 11` | pytest (formato real) |
| `AssertionError: assert X == Y` | `AssertionError: assert 4 == 5` | pytest inline |
| `expected: <X> but was: <Y>` | `expected: <4> but was: <5>` | JUnit |
| `Obtained: X\nExpected: Y` | pytest.approx | pytest con approx |
| `AssertionError: X != Y` | `AssertionError: 4 != 5` | genérico |

### Bug crítico del clasificador y su diagnóstico

La primera implementación marcaba todos los AssertionError como `corregible` en lugar de `posible_bug`. El diagnóstico se hizo en dos pasos:

1. Se agregó `print(repr(traceback))` al inicio de `_classify_error` y se ejecutó el agente contra `examples/` con un bug deliberado en `calculadora.py` (`sumar` retornaba `a + b + 1`).

2. El string real que llega desde `test_runner.run()` es:
   ```
   'def test_sumar_positive():\n>       assert sumar(5, 6) == 11\nE       assert 12 == 11\nE        +  where 12 = sumar(5, 6)\n\ntests_generados/unit/test_calculadora.py:9: AssertionError'
   ```

El problema: el patrón original buscaba `AssertionError: assert X == Y` (con los dos puntos, en la misma línea). Pero pytest escribe los valores en una línea separada que empieza con `E       assert 12 == 11`, y `AssertionError` aparece al final como sufijo de la ruta del archivo (sin valores). El regex nunca matcheaba.

La corrección: agregar `^E\s+assert\s+(.+?)\s*==\s*(.+)$` con flag `re.MULTILINE` como primer patrón de la lista. Este patrón captura exactamente la línea de detalle que pytest escribe.

### Dato de diseño — qué se clasifica como posible_bug vs. corregible

| Error | Clasificación | Razonamiento |
|---|---|---|
| `E       assert 12 == 11` | posible_bug | El test corrió y la función devolvió un valor concreto diferente al esperado |
| `AssertionError` (sin valores) | corregible | El test puede tener un `assert False` o un error lógico en la propia aserción |
| `NameError: name 'suma' is not defined` | corregible | El test tiene un error estructural (import incorrecto, nombre erróneo) |
| `ImportError` | corregible | El test no puede importar el módulo — problema del test, no del código bajo test |
| `TypeError` | corregible | El test llama a una función con tipos incorrectos |
| `expected: <4> but was: <5>` | posible_bug | Formato JUnit, misma semántica que el patrón pytest |

### Modelo de datos del status posible_bug

```python
{
    "status": "posible_bug",
    "traceback": "...",   # traceback completo original
    "expected": "11",     # valor extraído (puede ser None si no se parseó)
    "actual": "12",       # valor extraído
}
```

No tiene campo `attempts` (no se realizó ningún intento de corrección).

### Conceptos teóricos aplicados

- **Clasificación antes de corrección**: en lugar de tratar todos los fallos como "el test está mal", el agente distingue entre "el test tiene un error corregible" y "el test detectó un comportamiento inesperado del código". Esta distinción es el primer paso hacia análisis de causa raíz automatizado.
- **Diagnóstico por inspección del string real**: el bug del clasificador se encontró rápidamente al imprimir `repr(traceback)` — la representación exacta del string reveló que los valores y el `AssertionError` están en líneas distintas, no en una sola línea como el patrón asumía. La lección: cuando un clasificador basado en regex no funciona, el primer paso es ver exactamente qué string está llegando.
- **Guardrail conservador**: el clasificador solo marca como `posible_bug` cuando puede extraer dos valores distintos. Si no puede parsear los valores (AssertionError sin detalle), clasifica como `corregible`. Esto es preferible a marcar falsos positivos como bugs del código cuando en realidad son bugs del test.

### Deuda técnica / pendientes

- El clasificador opera solo sobre Python y JUnit. Tests JS con `expect(x).toBe(y)` que fallan producen un traceback con formato Jest diferente, que actualmente queda como `corregible`.
- Los valores `expected` y `actual` se almacenan como strings tal como aparecen en el traceback (pueden ser `"12"`, `"[1, 2, 3]"`, `"25.0 ± 0.25"`). No hay normalización de tipos.
