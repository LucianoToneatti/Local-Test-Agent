# Local-Test-Agent

Agente local de generación automática de tests para repositorios Python, impulsado por un modelo LLM local (Ollama + DeepSeek Coder 6.7b). Todo el procesamiento ocurre en la máquina, sin depender de servicios en la nube.

## Qué hace

El agente recibe la ruta a un repositorio Python y realiza automáticamente los siguientes pasos:

1. **Explora** el repositorio y encuentra todos los archivos `.py`
2. **Extrae** funciones, clases y métodos usando análisis de AST
3. **Genera tests unitarios** para cada función y método encontrado
4. **Genera tests de integración** para pares de módulos relacionados por imports
5. **Ejecuta los tests** generados con pytest
6. **Autocorrige** los tests fallidos (hasta 3 intentos por test, consultando al LLM)
7. **Genera un reporte** `reporte.md` con el resumen de resultados, cobertura de código y tiempo total

Los tests se guardan en `tests_generados/unit/` y `tests_generados/integration/`. Cada directorio incluye un `conftest.py` generado automáticamente que agrega el repositorio analizado al `sys.path`.

## Requisitos previos

- **Sistema operativo:** Linux (probado en Debian/Ubuntu)
- **Python:** 3.10 o superior
- **RAM:** mínimo 8 GB recomendados (el modelo ocupa ~4 GB en RAM)
- **Espacio en disco:** ~4 GB para el modelo
- **Ollama** instalado y corriendo
- **Modelo** `deepseek-coder:6.7b` descargado

## Instalación

Usá el script de instalación que crea el venv, instala dependencias y verifica Ollama en un solo paso:

```bash
git clone <url-del-repo>
cd Local-Test-Agent
bash install.sh
```

El script realiza automáticamente:
1. Crea el entorno virtual `venv/` si no existe
2. Instala `pytest`, `pytest-cov` y `requests`
3. Verifica que Ollama esté instalado
4. Descarga el modelo `deepseek-coder:6.7b` si no está disponible

### Instalación manual (alternativa)

Si preferís hacerlo paso a paso:

```bash
# 1. Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Descargar el modelo (~3.8 GB)
ollama pull deepseek-coder:6.7b

# 3. Clonar el repositorio
git clone <url-del-repo>
cd Local-Test-Agent

# 4. Crear entorno virtual e instalar dependencias
python3 -m venv venv
source venv/bin/activate
pip install pytest pytest-cov requests
```

## Uso

# Activar el entorno virtual (requerido)
```bash
source venv/bin/activate
```
```bash
python3 agent.py --repo ./ruta/al/repo
```

Podés usar rutas relativas, absolutas o con `~`:

```bash
python3 agent.py --repo ./examples
python3 agent.py --repo ~/codigo-para-testear
python3 agent.py --repo /home/usuario/proyectos/mi-app
```

### Salida esperada

```
+-----------------------------+
|  Local-Test-Agent v1.0     |
+-----------------------------+

[*] Analizando repositorio 'examples'...
[*] Generando tests unitarios (2 archivo(s))...
  [=============================>] 100% estadistica.py
[OK] tests_generados/unit/

[*] Generando tests de integracion...
  [=============================>] 100% estadistica+calculadora
[OK] tests_generados/integration/

[*] Ejecutando tests generados...
  [PASS] tests_generados/unit/test_calculadora.py::test_sumar
  [PASS] tests_generados/unit/test_calculadora.py::test_restar
  [FAIL] tests_generados/unit/test_estadistica.py::test_promedio
  [PASS] tests_generados/integration/test_estadistica_calculadora.py::test_flujo

[*] Autocorrigiendo 1 test(s) fallido(s) (hasta 3 intentos)...
[OK] Autocorreccion: 1 resuelto(s), 0 sin resolver

[*] Generando reporte...
[OK] Reporte generado: reporte.md

+--- Resumen final ---+
  Passed:       4
  Failed:       0
  Sin resolver: 0
  Total:        4
  Cobertura:    78%
  Tiempo:       3m 42s
```

### Correr los tests generados manualmente

```bash
pytest tests_generados/ -v
```

### Correr con cobertura manualmente

```bash
pytest tests_generados/ -v --cov=./ruta/al/repo --cov-report=term-missing
```

## Qué genera el agente

| Archivo | Descripción |
|---|---|
| `tests_generados/unit/test_<modulo>.py` | Tests unitarios por archivo fuente |
| `tests_generados/unit/conftest.py` | Agrega el repo al `sys.path` para pytest |
| `tests_generados/integration/test_<a>_<b>.py` | Tests de integración para pares de módulos relacionados |
| `tests_generados/integration/conftest.py` | Ídem, para la carpeta de integración |
| `reporte.md` | Resumen de resultados: passed, failed, sin resolver, cobertura y tiempo total |

## Estructura del proyecto

```
Local-Test-Agent/
├── agent/
│   ├── ast_extractor.py        # Extracción de funciones/clases con AST
│   ├── autocorrector.py        # Autocorrección de tests fallidos
│   ├── integration_generator.py # Generación de tests de integración
│   ├── llm_client.py           # Cliente HTTP para la API local de Ollama
│   ├── report_generator.py     # Generación de reporte.md
│   ├── repo_explorer.py        # Exploración de archivos .py del repositorio
│   ├── terminal_ui.py          # Interfaz de terminal con colores ANSI
│   ├── test_generator.py       # Generación de tests unitarios
│   └── test_runner.py          # Ejecución de tests con pytest y coverage
├── prompts/
│   └── prompt_builder.py       # Construcción de prompts para el LLM
├── examples/                   # Repositorio de ejemplo (calculadora, estadistica)
├── tests/                      # Tests del propio agente
├── tests_generados/            # Output: tests generados (no versionar)
│   ├── unit/
│   └── integration/
├── context/                    # Notas de diseño y decisiones técnicas
├── agent.py                    # Punto de entrada
├── install.sh                  # Script de instalación
├── reporte.md                  # Reporte del último run (generado automáticamente)
└── README.md
```

## Limitaciones conocidas

- **Tiempo de ejecución:** el agente llama al LLM una vez por función/método encontrado. Un repositorio con 50 funciones puede tardar 15-30 minutos dependiendo del hardware. Repositorios grandes pueden tardar horas.
- **Calidad de los tests:** los tests son generados por un LLM y pueden contener errores lógicos ocasionales. Revisarlos antes de incorporarlos a un pipeline de CI.
- **Un modelo a la vez:** Ollama sirve un modelo a la vez. Si tenés otro modelo corriendo en paralelo puede afectar la performance.
- **Cobertura solo para Python:** `pytest-cov` solo reporta cobertura para los archivos Python analizados. Los tests JavaScript no contribuyen al porcentaje de cobertura.
- **Tests generados no se versionan:** `tests_generados/` está en `.gitignore`. Cada ejecución sobreescribe los tests anteriores para el mismo repo.
