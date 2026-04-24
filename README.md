# Local-Test-Agent

Agente local de generación automática de tests para repositorios Python, impulsado por un modelo LLM local (Ollama + DeepSeek Coder 6.7b).

## Descripción

`local-test-agent` analiza el código fuente de un repositorio Python y genera automáticamente tests unitarios e de integración sin depender de servicios en la nube. Todo el procesamiento ocurre localmente, garantizando privacidad del código y funcionamiento offline.

## Requisitos previos

- **Sistema operativo:** Linux (Ubuntu 22.04+ recomendado)
- **Python:** 3.10 o superior
- **Ollama:** instalado y corriendo localmente ([ollama.com](https://ollama.com))
- **Modelo:** `deepseek-coder:6.7b` descargado en Ollama
  ```bash
  ollama pull deepseek-coder:6.7b
  ```

## Instalación

> Los pasos de instalación se irán completando a medida que avanza el desarrollo.

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd local-test-agent

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env según sea necesario
```

## Uso básico

> El flujo de uso se documentará al completar las primeras historias de usuario.

```bash
# Ejecutar el agente sobre un repositorio
python agent.py --repo /ruta/al/repositorio
```

## Estructura del proyecto

```
local-test-agent/
├── agent/              # Módulos del agente
├── prompts/            # Templates de prompts para el LLM
├── tests_generados/    # Tests producidos por el agente
│   ├── unit/
│   └── integration/
├── tests/              # Tests del propio agente
├── docs/               # Documentación adicional
├── context/            # Notas de diseño y decisiones técnicas
├── agent.py            # Punto de entrada principal
└── README.md
```

## Estado del proyecto

En desarrollo activo. Ver `context/marco_teorico_notas.md` para decisiones de diseño y justificaciones técnicas.
