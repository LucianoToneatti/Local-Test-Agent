# Local-Test-Agent

```
+--------------------------------------------------+
|  Local-Test-Agent v1.0                           |
|  Generación automática de tests con LLM          |
|  Python · JavaScript/TypeScript · Java           |
+--------------------------------------------------+
```

Agente de generación automática de tests unitarios y de integración para repositorios **Python, JavaScript/TypeScript y Java**, impulsado por un LLM local (Ollama) o cloud (Groq). Analiza el código fuente, genera los tests, los ejecuta, autocorrige los fallidos y produce un reporte con cobertura de código.

---

## Cómo funciona

```
1. ANALIZAR    Explora el repo y extrae funciones, clases y métodos con AST/regex
       ↓
2. GENERAR     Llama al LLM una vez por función para generar tests unitarios y de integración
       ↓
3. EJECUTAR    Corre pytest / Jest / Maven y muestra los resultados en tiempo real
       ↓
4. CORREGIR    Reenvía los tests fallidos al LLM con el traceback (hasta 3 intentos)
       ↓
5. REPORTAR    Escribe reporte.md con passed, sin resolver, posibles bugs y cobertura
```

---

## Características

- **Multi-lenguaje:** Python (pytest), JavaScript/TypeScript (Jest), Java (JUnit 5 + Maven)
- **Local-first:** corre con Ollama en tu máquina, sin exponer código a servicios externos
- **Cloud opcional:** soporte para Groq con los mismos comandos, mucho más rápido
- **Autocorrección:** los tests fallidos se reenvían al LLM con el traceback; hasta 3 intentos por test
- **Diagnóstico de bugs:** distingue entre un test con error corregible y un posible bug real en el código
- **Cobertura:** Python (pytest-cov), JavaScript/TypeScript (Jest V8), Java (JaCoCo 0.8.13)

---

## Requisitos previos

### Python 3.11+

```bash
python3 --version   # debe mostrar 3.11 o superior
```

Si no tenés Python 3.11, descargalo desde [python.org/downloads](https://www.python.org/downloads/) o con tu gestor de paquetes:

```bash
# Ubuntu/Debian
sudo apt install python3.11 python3.11-venv
```

### Ollama (para modo local)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull deepseek-coder:6.7b   # ~3.8 GB
```

Verificación:

```bash
ollama list   # debe mostrar deepseek-coder:6.7b
```

### Node.js 18+ (solo para repos JS/TS)

Con `nvm` (recomendado):

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install 18
nvm use 18
node --version   # debe mostrar v18 o superior
```

O con apt:

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

**Jest** debe instalarse dentro del proyecto JS que querés analizar:

```bash
cd /ruta/al/repo-js
npm install --save-dev jest
```

### Java 24 + Maven (solo para repos Java)

Con SDKMAN (recomendado):

```bash
curl -s "https://get.sdkman.io" | bash
source "$HOME/.sdkman/bin/sdkman-init.sh"

sdk install java 24-open
sdk install maven 3.9.9

java --version    # debe mostrar Java 24
mvn --version     # debe mostrar Maven 3.9.x
```

---

## Instalación

```bash
git clone <url-del-repo>
cd Local-Test-Agent
bash install.sh
```

El script crea el entorno virtual, instala `pytest` y `pytest-cov`, verifica Ollama y descarga el modelo si no está disponible.

### Verificación rápida antes de correr

```bash
source venv/bin/activate
python3 --version       # 3.11+
ollama list             # deepseek-coder:6.7b presente
node --version          # v18+ (si vas a analizar JS/TS)
java --version          # 24 (si vas a analizar Java)
mvn --version           # 3.9+ (si vas a analizar Java)
```

---

## Uso

```bash
source venv/bin/activate
python3 agent.py --repo ./ruta/al/repositorio
```

> **Nota:** el repositorio a analizar debe usar solo la biblioteca estándar del lenguaje (sin dependencias externas como pip packages, npm modules o Maven dependencies de terceros).

### Python

```bash
python3 agent.py --repo ./examples
```

### JavaScript / TypeScript

```bash
python3 agent.py --repo ./examples_js
```

El agente detecta archivos `.js` y `.ts` automáticamente. Asegurate de que Jest esté instalado en el repo (ver Requisitos).

### Java

```bash
python3 agent.py --repo ./examples_java
```

El agente genera un proyecto Maven completo en `tests_generados/unit/` con `pom.xml`, las fuentes copiadas y los tests JUnit 5.

---

## Proveedor cloud: Groq

Groq es una alternativa cloud que usa la misma interfaz que el modo local, pero puede ser **5-10x más rápida** para repos grandes.

### Paso a paso para obtener la API key

1. Ir a [console.groq.com](https://console.groq.com) y crear una cuenta gratuita
2. En el menú izquierdo, ir a **API Keys**
3. Hacer clic en **Create API Key**, asignarle un nombre y copiar el valor (`gsk_...`)

### Configurar y usar

```bash
export GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
python3 agent.py --repo ./examples_java --provider groq
```

Para usar un modelo más potente:

```bash
python3 agent.py --repo ./examples --provider groq --model llama-3.3-70b-versatile
```

### Rate limits del tier gratuito

El tier gratuito de Groq tiene un límite de **6000 tokens por minuto (TPM)**. El agente maneja automáticamente los errores 429 — si se alcanza el límite, espera el tiempo indicado por Groq y reintenta. Para repos con muchas funciones, esto puede agregar tiempo de espera entre llamadas.

---

## Modelos soportados

| Proveedor | Modelo default | Alternativas |
|-----------|---------------|--------------|
| Local (Ollama) | `deepseek-coder:6.7b` | cualquier modelo disponible en `ollama list` |
| Cloud (Groq) | `llama-3.1-8b-instant` | `llama-3.3-70b-versatile`, `mixtral-8x7b-32768` |

Cambiá el modelo con `--model nombre-del-modelo` en cualquier modo.

---

## Ejemplo de salida

Run completo contra `examples/` con `--provider groq`:

```
(venv) lucianotoneatti@debianHP:~/Proyectos-CC/TIF/Local-Test-Agent$ python3 agent.py --repo ./examples --provider groq


  __  __       _ _   _       _
 |  \/  |_   _| | |_(_)     | |    __ _ _ __   __ _ _   _  __ _  __ _  ___
 | |\/| | | | | | __| |_____| |   / _` | '_ \ / _` | | | |/ _` |/ _` |/ _ \
 | |  | | |_| | | |_| |_____| |__| (_| | | | | (_| | |_| | (_| | (_| |  __/
 |_|  |_|\__,_|_|\__|_|     |_____\__,_|_| |_|\__, |\__,_|\__,_|\__, |\___|
                                               |___/             |___/
  _____         _        _                    _
 |_   _|__  ___| |_     / \   __ _  ___ _ __ | |_
   | |/ _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
   | |  __/\__ \ |_   / ___ \ (_| |  __/ | | | |_
   |_|\___||___/\__| /_/   \_\__, |\___|_| |_|\__|
                             |___/
v1.0

[*] Analizando repositorio 'examples'...
[*] Generando tests unitarios (2 archivo(s))...
  [==============================] 100% estadistica.py   
[OK] tests_generados/unit/

[*] Generando tests de integracion...
  [==============================] 100% estadistica+calculadora   
[OK] tests_generados/integration/

[*] Ejecutando tests generados...
  [PASS] tests_generados/unit/test_calculadora.py::test_sumar_happy
  [PASS] tests_generados/unit/test_calculadora.py::test_sumar_edge
  [PASS] tests_generados/unit/test_calculadora.py::test_sumar_exception_type
  [PASS] tests_generados/unit/test_calculadora.py::test_sumar_exception_type2
  [FAIL] tests_generados/unit/test_calculadora.py::test_restar_happy_path
  [PASS] tests_generados/unit/test_calculadora.py::test_restar_edge_cases
  [PASS] tests_generados/unit/test_calculadora.py::test_restar_negative_result
  [FAIL] tests_generados/unit/test_calculadora.py::test_restar_zero_division
  [PASS] tests_generados/unit/test_calculadora.py::test_restar_type_error
  [PASS] tests_generados/unit/test_calculadora.py::test_multiplicar_happy_path
  [PASS] tests_generados/unit/test_calculadora.py::test_multiplicar_edge_case
  [PASS] tests_generados/unit/test_calculadora.py::test_multiplicar_negative_numbers
  [PASS] tests_generados/unit/test_calculadora.py::test_multiplicar_non_integer
  [FAIL] tests_generados/unit/test_calculadora.py::test_multiplicar_invalid_input_type
  [FAIL] tests_generados/unit/test_calculadora.py::test_multiplicar_invalid_input_type_2
  [PASS] tests_generados/unit/test_calculadora.py::test_dividir_happy_path
  [PASS] tests_generados/unit/test_calculadora.py::test_dividir_cero_divisor
  [PASS] tests_generados/unit/test_calculadora.py::test_dividir_cero_dividendo
  [PASS] tests_generados/unit/test_calculadora.py::test_dividir_negativos
  [PASS] tests_generados/unit/test_calculadora.py::test_dividir_floater
  [PASS] tests_generados/unit/test_calculadora.py::test_potencia_happy_path
  [PASS] tests_generados/unit/test_calculadora.py::test_potencia_positivo_base_negativo_exponente
  [PASS] tests_generados/unit/test_calculadora.py::test_potencia_positivo_base_cero_exponente
  [PASS] tests_generados/unit/test_calculadora.py::test_potencia_cubo_base_cero_exponente
  [FAIL] tests_generados/unit/test_calculadora.py::test_potencia_base_negativo_exponente_negativo
  [PASS] tests_generados/unit/test_calculadora.py::test_potencia_raiz_base_negativo_exponente_parity
  [PASS] tests_generados/unit/test_calculadora.py::test_potencia_exponente_zero_base_cero
  [PASS] tests_generados/unit/test_calculadora.py::test_potencia_exponente_zero_base_deseado
  [FAIL] tests_generados/unit/test_calculadora.py::test_potencia_zero_division_error
  [PASS] tests_generados/unit/test_estadistica.py::test_promedio_happy_path
  [PASS] tests_generados/unit/test_estadistica.py::test_promedio_un_elemento
  [PASS] tests_generados/unit/test_estadistica.py::test_promedio_lista_vacia
  [PASS] tests_generados/unit/test_estadistica.py::test_promedio_con_zeros
  [PASS] tests_generados/unit/test_estadistica.py::test_promedio_con_cifras_decimales
  [FAIL] tests_generados/unit/test_estadistica.py::test_varianza_happy_path
  [PASS] tests_generados/unit/test_estadistica.py::test_varianza_empty_list
  [FAIL] tests_generados/unit/test_estadistica.py::test_varianza_calculator_malfunction
  [FAIL] tests_generados/unit/test_estadistica.py::test_varianza_calculator_malfunction2
  [PASS] tests_generados/unit/test_estadistica.py::test_varianza_function_promedio_not_defined
  [PASS] tests_generados/unit/test_estadistica.py::test_varianza_function_sumar_not_defined

[*] Autocorrigiendo 9 test(s) fallido(s) (hasta 3 intentos)...
[OK] Autocorreccion: 32 resuelto(s), 6 sin resolver, 2 posible(s) bug

[*] Generando reporte...
[OK] Reporte generado: reporte.md

+--- Preview del reporte ---+
  Posibles bugs (2):
    [BUG] tests_generados/unit/test_calculadora.py::test_restar_happy_path
          Esperado: -5 — Obtenido: 5
    [BUG] tests_generados/unit/test_calculadora.py::test_potencia_base_negativo_exponente_negativo
          Esperado: -0.125 — Obtenido: (1 / 8)

  Sin resolver (6):
    [WARN] tests_generados/unit/test_calculadora.py::test_multiplicar_invalid_input_type
           tests_generados/unit/test_calculadora.py:59: Failed
    [WARN] tests_generados/unit/test_calculadora.py::test_multiplicar_invalid_input_type_2
           tests_generados/unit/test_calculadora.py:63: Failed
    [WARN] tests_generados/unit/test_calculadora.py::test_potencia_zero_division_error
           tests_generados/unit/test_calculadora.py:113: Failed
    [WARN] tests_generados/unit/test_estadistica.py::test_varianza_happy_path
           tests_generados/unit/test_estadistica.py:30: NameError
    [WARN] tests_generados/unit/test_estadistica.py::test_varianza_calculator_malfunction
           tests_generados/unit/test_estadistica.py:42: NameError
    [WARN] tests_generados/unit/test_estadistica.py::test_varianza_calculator_malfunction2
           tests_generados/unit/test_estadistica.py:51: NameError
+---------------------------+


+--- Resumen final ---+
  Passed:       32
  Failed:       0
  Sin resolver: 6
  Posible bug:  2
  Total:        40
  Cobertura:    100%
  Tiempo:       1m 08s
```

---

## Archivos generados

El agente escribe los tests en `tests_generados/` y el reporte en `reporte.md`:

**Tests unitarios:**
- Python: `tests_generados/unit/test_<modulo>.py`
- JavaScript/TypeScript: `tests_generados/unit/<modulo>.test.js`
- Java: `tests_generados/unit/src/test/java/<Clase>Test.java`

**Tests de integración:**
- Python: `tests_generados/integration/test_<a>_<b>.py`
- JavaScript/TypeScript: `tests_generados/integration/<a>_<b>.test.js`
- Java: `tests_generados/integration/src/test/java/<A><B>IntegrationTest.java`

**Reporte:** `reporte.md` con fecha, tiempo, cobertura, tabla de resumen, tests fallidos, sin resolver y posibles bugs detectados.

---

## Estructura del proyecto

```
Local-Test-Agent/
├── agent/
│   ├── ast_extractor.py         # Extracción de funciones y clases (AST Python, regex JS/Java)
│   ├── autocorrector.py         # Autocorrección y diagnóstico de posibles bugs
│   ├── integration_generator.py # Tests de integración (Python, JS/TS, Java)
│   ├── llm_client.py            # Clientes HTTP para Ollama y Groq
│   ├── report_generator.py      # Escritura de reporte.md
│   ├── repo_explorer.py         # Exploración de archivos .py/.js/.ts/.java
│   ├── terminal_ui.py           # Colores ANSI, barra de progreso, resumen final
│   ├── test_generator.py        # Tests unitarios (Python, JS/TS, Java)
│   └── test_runner.py           # pytest / Jest / Maven + parseo de cobertura
├── prompts/
│   └── prompt_builder.py        # Templates de prompt por lenguaje y tipo de test
├── examples/                    # Ejemplo Python: calculadora.py, estadistica.py
├── examples_js/                 # Ejemplo JS: calculadora.js, estadistica.js
├── examples_java/               # Ejemplo Java: Calculadora.java, Conversor.java, Estadistica.java
├── tests/                       # Tests del propio agente
├── tests_generados/             # Output generado (en .gitignore)
├── context/                     # Notas de diseño y decisiones técnicas
├── agent.py                     # Punto de entrada CLI
├── install.sh                   # Script de instalación
└── reporte.md                   # Reporte del último run
```

---

## Limitaciones conocidas

- **Tiempo con modelo local:** el agente llama al LLM una vez por función/método. Un repo con 50 funciones puede tardar 20-40 minutos sin GPU dedicada. Con Groq el mismo repo tarda ~5 minutos (sujeto a rate limits).
- **Calidad de tests:** los tests son generados por un LLM y pueden tener errores lógicos. Revisarlos antes de incorporarlos a un pipeline de CI.
- **Cobertura Java con errores de compilación:** si los tests Java no compilan, JaCoCo no genera el reporte y la cobertura queda como N/A.
- **Tests generados no se versionan:** `tests_generados/` está en `.gitignore`. Cada ejecución sobreescribe los tests anteriores.
- **Repos sin dependencias externas:** el agente está diseñado para repositorios que usan solo la biblioteca estándar del lenguaje. Si el código fuente importa librerías externas (como `requests`, `pandas`, `express`, `Spring`, etc.), los tests generados fallarán porque esas dependencias no estarán disponibles en el entorno de ejecución de los tests.

---

## Licencia

MIT
