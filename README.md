# Local-Test-Agent

```
+--------------------------------------------------+
|  Local-Test-Agent v1.0                           |
|  Automated test generation with LLM              |
|  Python · JavaScript/TypeScript · Java           |
+--------------------------------------------------+
```

**Landing Page:** [https://local-test-agent.netlify.app/](https://local-test-agent.netlify.app/)

Automatic unit and integration test generation agent for **Python, JavaScript/TypeScript, and Java** repositories, powered by a local LLM (Ollama) or cloud LLM (Groq). It analyzes the source code, generates the tests, runs them, auto-fixes the failing ones, and produces a report with code coverage.

---

## How it works

```
1. ANALYZE     Scans the repo and extracts functions, classes, and methods using AST/regex
       ↓
2. GENERATE    Calls the LLM once per function to generate unit and integration tests
       ↓
3. RUN         Runs pytest / Jest / Maven and shows results in real time
       ↓
4. FIX         Resends failing tests to the LLM with the traceback (up to 3 attempts)
       ↓
5. REPORT      Writes reporte.md with passed, unresolved, possible bugs, and coverage
```

---

## Features

- **Multi-language:** Python (pytest), JavaScript/TypeScript (Jest), Java (JUnit 5 + Maven)
- **Local-first:** runs with Ollama on your machine, without exposing code to external services
- **Optional cloud:** Groq support with the same commands, much faster
- **Auto-fix:** failing tests are resent to the LLM with the traceback; up to 3 attempts per test
- **Bug diagnosis:** distinguishes between a fixable test error and a possible real bug in the code
- **Coverage:** Python (pytest-cov), JavaScript/TypeScript (Jest V8), Java (JaCoCo 0.8.13)

---

## Prerequisites

### Python 3.11+

```bash
python3 --version   # should show 3.11 or higher
```

If you don't have Python 3.11, download it from [python.org/downloads](https://www.python.org/downloads/) or with your package manager:

```bash
# Ubuntu/Debian
sudo apt install python3.11 python3.11-venv
```

### Ollama (for local mode)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull deepseek-coder:6.7b   # ~3.8 GB
```

Verification:

```bash
ollama list   # should show deepseek-coder:6.7b
```

### Node.js 18+ (JS/TS repos only)

With `nvm` (recommended):

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install 18
nvm use 18
node --version   # should show v18 or higher
```

Or with apt:

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

**Jest** must be installed inside the JS project you want to analyze:

```bash
cd /path/to/js-repo
npm install --save-dev jest
```

### Java 24 + Maven (Java repos only)

With SDKMAN (recommended):

```bash
curl -s "https://get.sdkman.io" | bash
source "$HOME/.sdkman/bin/sdkman-init.sh"

sdk install java 24-open
sdk install maven 3.9.9

java --version    # should show Java 24
mvn --version     # should show Maven 3.9.x
```

---

## Installation

```bash
git clone <repo-url>
cd Local-Test-Agent
bash install.sh
```

The script creates the virtual environment, installs `pytest` and `pytest-cov`, checks Ollama, and downloads the model if it isn't available.

### Quick check before running

```bash
source venv/bin/activate
python3 --version       # 3.11+
ollama list             # deepseek-coder:6.7b present
node --version          # v18+ (if analyzing JS/TS)
java --version          # 24 (if analyzing Java)
mvn --version           # 3.9+ (if analyzing Java)
```

---

## Usage

```bash
source venv/bin/activate
python3 agent.py --repo ./path/to/repository
```

> **Note:** the repository being analyzed must use only the language's standard library (no external dependencies such as pip packages, npm modules, or third-party Maven dependencies).

### Python

```bash
python3 agent.py --repo ./examples
```

### JavaScript / TypeScript

```bash
python3 agent.py --repo ./examples_js
```

The agent automatically detects `.js` and `.ts` files. Make sure Jest is installed in the repo (see Prerequisites).

### Java

```bash
python3 agent.py --repo ./examples_java
```

The agent generates a complete Maven project in `tests_generados/unit/` with `pom.xml`, the copied sources, and the JUnit 5 tests.

---

## Cloud provider: Groq

Groq is a cloud alternative that uses the same interface as local mode, but can be **5-10x faster** for large repos.

### Step-by-step to get an API key

1. Go to [console.groq.com](https://console.groq.com) and create a free account
2. In the left menu, go to **API Keys**
3. Click **Create API Key**, give it a name, and copy the value (`gsk_...`)

### Configure and use

```bash
export GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
python3 agent.py --repo ./examples_java --provider groq
```

To use a more powerful model:

```bash
python3 agent.py --repo ./examples --provider groq --model llama-3.3-70b-versatile
```

### Free tier rate limits

Groq's free tier has a limit of **6000 tokens per minute (TPM)**. The agent automatically handles 429 errors — if the limit is reached, it waits for the time indicated by Groq and retries. For repos with many functions, this can add wait time between calls.

---

## Supported models

| Provider | Default model | Alternatives |
|-----------|---------------|--------------|
| Local (Ollama) | `deepseek-coder:6.7b` | any model available in `ollama list` |
| Cloud (Groq) | `llama-3.1-8b-instant` | `llama-3.3-70b-versatile`, `mixtral-8x7b-32768` |

Change the model with `--model model-name` in any mode.

---

## Example output

Full run against `examples/` with `--provider groq`:

> **Note:** the console output below is shown exactly as produced by the agent, which generates its console messages in Spanish — they are not translated at runtime. It is kept here as a faithful reference of the actual output.

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

## Generated files

The agent writes the tests to `tests_generados/` and the report to `reporte.md`:

**Unit tests:**
- Python: `tests_generados/unit/test_<module>.py`
- JavaScript/TypeScript: `tests_generados/unit/<module>.test.js`
- Java: `tests_generados/unit/src/test/java/<Class>Test.java`

**Integration tests:**
- Python: `tests_generados/integration/test_<a>_<b>.py`
- JavaScript/TypeScript: `tests_generados/integration/<a>_<b>.test.js`
- Java: `tests_generados/integration/src/test/java/<A><B>IntegrationTest.java`

**Report:** `reporte.md` with date, duration, coverage, summary table, failed tests, unresolved tests, and detected possible bugs.

---

## Project structure

```
Local-Test-Agent/
├── agent/
│   ├── ast_extractor.py         # Function and class extraction (Python AST, JS/Java regex)
│   ├── autocorrector.py         # Auto-fix and possible-bug diagnosis
│   ├── integration_generator.py # Integration tests (Python, JS/TS, Java)
│   ├── llm_client.py            # HTTP clients for Ollama and Groq
│   ├── report_generator.py      # Writes reporte.md
│   ├── repo_explorer.py         # Explores .py/.js/.ts/.java files
│   ├── terminal_ui.py           # ANSI colors, progress bar, final summary
│   ├── test_generator.py        # Unit tests (Python, JS/TS, Java)
│   └── test_runner.py           # pytest / Jest / Maven + coverage parsing
├── prompts/
│   └── prompt_builder.py        # Prompt templates per language and test type
├── examples/                    # Python example: calculadora.py, estadistica.py
├── examples_js/                 # JS example: calculadora.js, estadistica.js
├── examples_java/               # Java example: Calculadora.java, Conversor.java, Estadistica.java
├── tests/                       # The agent's own tests
├── tests_generados/             # Generated output (in .gitignore)
├── context/                     # Design notes and technical decisions
├── agent.py                     # CLI entry point
├── install.sh                   # Installation script
└── reporte.md                   # Report from the last run
```

---

## Known limitations

- **Local model runtime:** the agent calls the LLM once per function/method. A repo with 50 functions can take 20-40 minutes without a dedicated GPU. With Groq, the same repo takes ~5 minutes (subject to rate limits).
- **Test quality:** tests are generated by an LLM and may contain logical errors. Review them before incorporating them into a CI pipeline.
- **Java coverage with compilation errors:** if the Java tests don't compile, JaCoCo doesn't generate the report and coverage is shown as N/A.
- **Generated tests are not version-controlled:** `tests_generados/` is in `.gitignore`. Each run overwrites the previous tests.
- **Repos without external dependencies:** the agent is designed for repositories that use only the language's standard library. If the source code imports external libraries (such as `requests`, `pandas`, `express`, `Spring`, etc.), the generated tests will fail because those dependencies won't be available in the test execution environment.

---

## License

MIT
