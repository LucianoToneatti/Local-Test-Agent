# Local-Test-Agent

Agente local de generación automática de tests para repositorios Python, impulsado por un modelo LLM local (Ollama + DeepSeek Coder 6.7b).

## Descripción

`Local-Test-Agent` analiza el código fuente de un repositorio Python y genera automáticamente tests unitarios e de integración sin depender de servicios en la nube. Todo el procesamiento ocurre localmente, garantizando privacidad del código y funcionamiento offline.

## Requisitos previos

- **Sistema operativo:** Linux (probado en Debian/Ubuntu)
- **Python:** 3.10 o superior
- **RAM:** mínimo 8 GB (el modelo ocupa ~4 GB en RAM )
- **Espacio en disco:** ~4 GB para el modelo

## Instalación

### 1. Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verificar que el servicio quedó activo:

```bash
ollama --version
```

Ollama corre como servicio del sistema. Si necesitás iniciarlo manualmente:

```bash
ollama serve
```

### 2. Descargar el modelo

```bash
ollama pull deepseek-coder:6.7b
```

La descarga es ~3.8 GB. Verificar que quedó disponible:

```bash
ollama list
```

Deberías ver `deepseek-coder:6.7b` en la lista.

### 3. Clonar el repositorio

```bash
git clone <url-del-repo>
cd Local-Test-Agent
```

### 4. Crear entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate
```

> Por ahora el proyecto no tiene dependencias externas (usa solo stdlib de Python). El entorno virtual queda listo para cuando se agreguen.

### 5. Correr el agente sobre el repositorio de ejemplo

```bash
python3 agent.py --repo ./examples
```

El agente analiza `examples/calculadora.py`, extrae sus funciones (`sumar`, `restar`, `multiplicar`, `dividir`, `potencia`) y genera tests unitarios para cada una. El resultado se guarda en:

```
tests_generados/unit/test_calculadora.py
```

Si Ollama no está corriendo al momento de ejecutar:

```bash
# En una terminal aparte (o en background):
ollama serve

# Luego volver a correr:
python3 agent.py --repo ./examples
```

## Uso básico

```bash
python3 agent.py --repo ./examples
```

Reemplazá `./examples` por la ruta a cualquier carpeta con archivos `.py`. El agente genera un archivo `test_<nombre>.py` por cada archivo fuente encontrado, guardados en `tests_generados/unit/`.

## Estructura del proyecto

```
Local-Test-Agent/
├── agent/                  # Módulos del agente
│   └── llm_client.py       # Cliente HTTP para la API local de Ollama
├── prompts/                # Templates de prompts para el LLM
│   └── prompt_builder.py   # Construcción y limpieza de prompts
├── tests_generados/        # Tests producidos por el agente
│   ├── unit/
│   └── integration/
├── tests/                  # Tests del propio agente
├── docs/                   # Documentación adicional
├── context/                # Notas de diseño y decisiones técnicas
│   └── marco_teorico_notas.md
├── agent.py                # Punto de entrada principal
└── README.md
```

## Verificar los tests generados

Después de ejecutar el agente, los tests quedan en `tests_generados/unit/`. Para correrlos con pytest:

### 1. Instalar pytest (si no está instalado)

```bash
pip install pytest
```

### 2. Correr los tests generados

```bash
pytest tests_generados/unit/test_calculadora.py -v
```

El flag `-v` muestra cada test individualmente con su resultado. El `conftest.py` que el agente genera automáticamente en esa carpeta se encarga de agregar el directorio del repositorio al `sys.path`, por lo que pytest puede importar los módulos bajo test sin configuración adicional.

### 3. Salida esperada

```
tests_generados/unit/test_calculadora.py::test_sumar_happy_path PASSED
tests_generados/unit/test_calculadora.py::test_sumar_negative_numbers PASSED
...
============= N passed in X.XXs =============
```

> Los tests son generados por un LLM y pueden contener errores lógicos ocasionales. Revisarlos antes de incorporarlos a un pipeline de CI.

## Estado del proyecto

En desarrollo activo. Ver `context/marco_teorico_notas.md` para decisiones de diseño y justificaciones técnicas.
