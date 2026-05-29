#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}${CYAN}+--------------------------------+${NC}"
echo -e "${BOLD}${CYAN}|  Local-Test-Agent  v1.0        |${NC}"
echo -e "${BOLD}${CYAN}|  Script de instalacion         |${NC}"
echo -e "${BOLD}${CYAN}+--------------------------------+${NC}"
echo ""

# 1. Crear venv si no existe
if [ ! -d "venv" ]; then
    echo -e "${CYAN}[*]${NC} Creando entorno virtual..."
    python3 -m venv venv
    echo -e "${GREEN}[OK]${NC} Entorno virtual creado en ./venv"
else
    echo -e "${GREEN}[OK]${NC} Entorno virtual ya existe en ./venv"
fi

# 2. Activar venv
source venv/bin/activate

# 3. Instalar dependencias
echo -e "${CYAN}[*]${NC} Instalando dependencias Python (pytest, pytest-cov, requests)..."
pip install --quiet pytest pytest-cov requests
echo -e "${GREEN}[OK]${NC} Dependencias instaladas"

# 4. Verificar Ollama
echo -e "${CYAN}[*]${NC} Verificando Ollama..."
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Ollama no esta instalado."
    echo "    Instalalo con: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Ollama encontrado: $(ollama --version 2>/dev/null || echo 'version desconocida')"

# 5. Verificar que Ollama esta corriendo (intentar iniciarlo si no)
if ! ollama list &>/dev/null; then
    echo -e "${YELLOW}[!]${NC} Ollama no esta corriendo. Intentando iniciar..."
    ollama serve &>/dev/null &
    sleep 3
fi

# 6. Verificar modelo deepseek-coder:6.7b
echo -e "${CYAN}[*]${NC} Verificando modelo deepseek-coder:6.7b..."
if ! ollama list 2>/dev/null | grep -q "deepseek-coder:6.7b"; then
    echo -e "${YELLOW}[!]${NC} Modelo no encontrado. Descargando (~3.8 GB)..."
    ollama pull deepseek-coder:6.7b
fi
echo -e "${GREEN}[OK]${NC} Modelo deepseek-coder:6.7b listo"

echo ""
echo -e "${BOLD}${GREEN}+--- Instalacion completa ---+${NC}"
echo ""
echo "  Para usar el agente:"
echo ""
echo -e "    ${CYAN}source venv/bin/activate${NC}"
echo -e "    ${CYAN}python3 agent.py --repo ./ruta/al/repositorio${NC}"
echo ""
echo "  Ejemplos:"
echo -e "    ${CYAN}python3 agent.py --repo ./examples${NC}"
echo -e "    ${CYAN}python3 agent.py --repo ~/codigo-para-testear${NC}"
echo ""
