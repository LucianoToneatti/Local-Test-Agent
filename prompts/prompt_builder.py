"""
Construcción de prompts estructurados para generación de tests.

Diseño: cada lenguaje tiene su propia PromptTemplate. El PromptBuilder
actúa como factory y punto de entrada único. La respuesta se modela
como BuiltPrompt (system + user) para aprovechar el parámetro `system`
de la API de Ollama, que le da al modelo su rol de forma separada del
contenido.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class BuiltPrompt:
    """Prompt listo para enviar al LLM, separado en rol (system) y tarea (user)."""
    system: str
    user: str


class PromptTemplate:
    """Clase base para templates específicos por lenguaje."""

    language: str = "generic"

    def build(
        self,
        code: str,
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> BuiltPrompt:
        raise NotImplementedError(f"Template para '{self.language}' no implementado.")


class PythonPromptTemplate(PromptTemplate):
    """
    Template para generar tests pytest a partir de código Python.

    Instrucciones clave del system prompt:
    - Rol exclusivo: escritor de tests, no explicador de código.
    - Formato de salida: solo código Python válido, sin bloques markdown,
      sin comentarios explicativos, sin texto adicional.
    - Framework obligatorio: pytest.
    - Cobertura mínima: caso feliz, casos borde y caso de error esperado.
    """

    language = "python"

    _SYSTEM = (
        "You are a Python test-writing machine. "
        "You output ONLY raw Python code. Nothing else.\n"
        "ABSOLUTE RULES — never break these:\n"
        "- NO markdown. Never use triple backticks (```) under any circumstances.\n"
        "- NO explanations, NO introductory sentences, NO comments outside the code.\n"
        "- Your entire response must be valid Python that can be saved directly to a .py file.\n"
        "- First line of your response must be an import statement.\n"
        "- Use pytest. Cover: happy path, edge case, and expected exception.\n"
        "- Name tests as: test_<function_name>_<scenario>."
    )

    _USER_TEMPLATE = (
        "Write pytest tests for this Python function:\n\n"
        "{code}\n\n"
        "Function under test: {function_name}\n"
        "Import it with: from {module_name} import {function_name}\n\n"
        "OUTPUT RULES: raw Python code only. "
        "No markdown, no backticks, no explanations. "
        "Start your response directly with 'import'."
    )

    def build(
        self,
        code: str,
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> BuiltPrompt:
        resolved_name = function_name or _extract_function_name(code) or "la_funcion"
        user = self._USER_TEMPLATE.format(
            code=code.strip(),
            function_name=resolved_name,
            module_name=module_name or "module",
        )
        return BuiltPrompt(system=self._SYSTEM, user=user)


# Registro de templates disponibles. Para agregar un nuevo lenguaje:
# 1. Crear una subclase de PromptTemplate con language="<nombre>"
# 2. Registrarla aquí.
_REGISTRY: dict[str, PromptTemplate] = {
    "python": PythonPromptTemplate(),
}


class PromptBuilder:
    """Factory que devuelve el prompt correcto según el lenguaje."""

    @staticmethod
    def build(
        code: str,
        language: str = "python",
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> BuiltPrompt:
        template = _REGISTRY.get(language.lower())
        if template is None:
            supported = ", ".join(_REGISTRY.keys())
            raise ValueError(
                f"Lenguaje '{language}' no soportado. Disponibles: {supported}"
            )
        return template.build(code, function_name, module_name)

    @staticmethod
    def supported_languages() -> list[str]:
        return list(_REGISTRY.keys())


def clean_response(response: str) -> str:
    """
    Limpia el output del LLM eliminando bloques markdown y texto explicativo.

    Estrategia:
    1. Si hay bloques ```...```, extrae solo su contenido (el modelo los incluyó igual).
    2. Si no hay bloques pero hay texto previo al código, descarta todo lo anterior
       a la primera línea que empiece con 'import', 'from' o 'def test_'.
    3. En cualquier caso, elimina backticks sueltos residuales.
    """
    # Paso 1: extraer contenido de bloques markdown si existen
    blocks = re.findall(r"```(?:python)?\n?(.*?)```", response, flags=re.DOTALL)
    if blocks:
        return "\n\n".join(b.strip() for b in blocks)

    # Paso 2: descartar texto explicativo antes del código
    match = re.search(r"^(import |from |def test_)", response, re.MULTILINE)
    if match:
        response = response[match.start():]

    # Paso 3: eliminar backticks sueltos
    response = response.replace("`", "")

    return response.strip()


def _extract_function_name(code: str) -> Optional[str]:
    """Extrae el nombre de la primera función definida en el fragmento de código."""
    match = re.search(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", code, re.MULTILINE)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Prueba de integración: prompt_builder + llm_client
# Ejecutar desde la raíz del proyecto:
#   python -m prompts.prompt_builder
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    from agent.llm_client import LLMClient, OllamaConnectionError

    SAMPLE_CODE = """
def dividir(dividendo, divisor):
    if divisor == 0:
        raise ValueError("El divisor no puede ser cero.")
    return dividendo / divisor
"""

    print("=== Prompt Builder — prueba de integración ===\n")

    prompt = PromptBuilder.build(SAMPLE_CODE, language="python")

    print("[SYSTEM PROMPT]\n")
    print(prompt.system)
    print("\n[USER PROMPT]\n")
    print(prompt.user)
    print("\n" + "=" * 50)

    client = LLMClient()
    if not client.is_available():
        print("\n[!] Ollama no disponible. Verificá que esté corriendo y el modelo descargado.")
        print("    ollama serve  /  ollama pull deepseek-coder:6.7b")
        sys.exit(1)

    print("\n[*] Enviando al modelo...\n")
    try:
        response = client.generate(prompt.user, system=prompt.system)
    except OllamaConnectionError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    cleaned = clean_response(response)

    if cleaned != response:
        print("[!] Output del modelo limpiado (se encontró markdown o texto extra)\n")

    print("[TESTS GENERADOS]\n")
    print(cleaned)

    print("\n[*] Validando estructura básica de pytest...")
    checks = {
        "import pytest": "import pytest" in cleaned,
        "def test_": "def test_" in cleaned,
        "sin bloques markdown": "```" not in cleaned,
        "empieza con import/from": cleaned.lstrip().startswith(("import ", "from ")),
    }
    for check, passed in checks.items():
        status = "OK" if passed else "FALLO"
        print(f"  [{status}] {check}")
