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
        "- Do NOT include any import statements. Output ONLY test functions (def test_...).\n"
        "- Do NOT include any comments (no # lines).\n"
        "- Use pytest. Cover: happy path, edge case, and expected exception.\n"
        "- Name tests as: test_<function_name>_<scenario>."
    )

    _USER_TEMPLATE = (
        "Write pytest tests for this Python function:\n\n"
        "{code}\n\n"
        "Function under test: {function_name}\n"
        "Available as: from {module_name} import {function_name} "
        "(do NOT include this import in your output).\n\n"
        "OUTPUT RULES: raw Python code only. "
        "No markdown, no backticks, no explanations, no import statements. "
        "Start your response directly with 'def test_'."
    )

    _USER_TEMPLATE_METHOD = (
        "Write pytest tests for this Python method:\n\n"
        "{code}\n\n"
        "Method under test: {function_name} (instance method of class {class_name})\n"
        "Available as: from {module_name} import {class_name} "
        "(do NOT include this import in your output).\n"
        "Instantiate the class before calling the method.\n\n"
        "OUTPUT RULES: raw Python code only. "
        "No markdown, no backticks, no explanations, no import statements. "
        "Start your response directly with 'def test_'."
    )

    def build(
        self,
        code: str,
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> BuiltPrompt:
        resolved_name = function_name or _extract_function_name(code) or "la_funcion"
        if class_name:
            user = self._USER_TEMPLATE_METHOD.format(
                code=code.strip(),
                function_name=resolved_name,
                module_name=module_name or "module",
                class_name=class_name,
            )
        else:
            user = self._USER_TEMPLATE.format(
                code=code.strip(),
                function_name=resolved_name,
                module_name=module_name or "module",
            )
        return BuiltPrompt(system=self._SYSTEM, user=user)


class JsPromptTemplate(PromptTemplate):
    """
    Template para generar tests Jest a partir de código JavaScript/TypeScript.

    Instrucciones clave del system prompt:
    - Rol exclusivo: escritor de tests Jest, no explicador de código.
    - Formato de salida: solo código JavaScript válido, sin bloques markdown,
      sin comentarios explicativos, sin texto adicional.
    - Framework obligatorio: Jest.
    - Cobertura mínima: caso feliz, casos borde y caso de error esperado.
    - Imports: CommonJS require() — el agente los provee en el header.
    """

    language = "javascript"

    _SYSTEM = (
        "You are a JavaScript test-writing machine. "
        "You output ONLY raw JavaScript code. Nothing else.\n"
        "ABSOLUTE RULES — never break these:\n"
        "- NO markdown. Never use triple backticks (```) under any circumstances.\n"
        "- NO explanations, NO introductory sentences, NO comments outside the code.\n"
        "- Your entire response must be valid JavaScript that can be saved directly to a .test.js file.\n"
        "- Do NOT include any require() or import statements. Output ONLY test blocks.\n"
        "- Do NOT include any comments (no // lines).\n"
        "- Use Jest. Cover: happy path, edge case, and expected exception.\n"
        "- Use test() or describe()/it() blocks.\n"
        "- Name tests descriptively."
    )

    _USER_TEMPLATE = (
        "Write Jest tests for this JavaScript function:\n\n"
        "{code}\n\n"
        "Function under test: {function_name}\n"
        "Available as: const {{ {function_name} }} = require('./{module_name}') "
        "(do NOT include this require in your output).\n\n"
        "OUTPUT RULES: raw JavaScript code only. "
        "No markdown, no backticks, no explanations, no require/import statements. "
        "Start your response directly with 'test(' or 'describe('."
    )

    _USER_TEMPLATE_METHOD = (
        "Write Jest tests for this JavaScript method:\n\n"
        "{code}\n\n"
        "Method under test: {function_name} (method of class {class_name})\n"
        "Available as: const {{ {class_name} }} = require('./{module_name}') "
        "(do NOT include this require in your output).\n"
        "Instantiate the class before calling the method.\n\n"
        "OUTPUT RULES: raw JavaScript code only. "
        "No markdown, no backticks, no explanations, no require/import statements. "
        "Start your response directly with 'test(' or 'describe('."
    )

    def build(
        self,
        code: str,
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> BuiltPrompt:
        resolved_name = function_name or "la_funcion"
        if class_name:
            user = self._USER_TEMPLATE_METHOD.format(
                code=code.strip(),
                function_name=resolved_name,
                module_name=module_name or "module",
                class_name=class_name,
            )
        else:
            user = self._USER_TEMPLATE.format(
                code=code.strip(),
                function_name=resolved_name,
                module_name=module_name or "module",
            )
        return BuiltPrompt(system=self._SYSTEM, user=user)


class IntegrationPromptTemplate(PromptTemplate):
    """
    Template para generar tests de integración entre pares de módulos Python.

    Se llama una vez por par (A importa B). Pasa al LLM:
    (1) código fuente completo de A, (2) firmas de funciones de B, (3) nombres de módulos.
    """

    language = "python_integration"

    _SYSTEM = (
        "You are a Python integration test-writing machine. "
        "You output ONLY raw Python code. Nothing else.\n"
        "ABSOLUTE RULES — never break these:\n"
        "- NO markdown. Never use triple backticks (```) under any circumstances.\n"
        "- NO explanations, NO introductory sentences, NO comments outside the code.\n"
        "- Your entire response must be valid Python that can be saved directly to a .py file.\n"
        "- First line of your response must be an import statement.\n"
        "- All imports must appear ONCE at the top of the file. Never repeat imports inside "
        "test functions or classes.\n"
        "- Use pytest. ONLY test functions from module A that internally depend on module B. "
        "NEVER test functions from module B in isolation.\n"
        "- No mocks. Tests must exercise the real interaction between A and B.\n"
        "- Assert with concrete expected values (e.g., assert promedio([1, 2, 3]) == 2.0).\n"
        "- Before including a test, verify: does it call a function from A? Does that function "
        "use B internally? If no → exclude it."
    )

    _USER_TEMPLATE = (
        "Write pytest integration tests for module A, which depends on module B.\n\n"
        "# Module A (the module under test): {module_a_name}.py\n"
        "{module_a_source}\n\n"
        "# Module B function signatures (used internally by A): {module_b_name}.py\n"
        "{module_b_sigs}\n\n"
        "STRICT RULES:\n"
        "1. Test ONLY functions from {module_a_name}. "
        "Import them with: from {module_a_name} import <function>\n"
        "2. DO NOT write tests for functions from {module_b_name} in isolation.\n"
        "3. No mocks — let A call B for real.\n"
        "4. Define all imports once at the top of the file. "
        "Do not repeat import statements inside test functions.\n"
        "5. Assert with concrete expected values.\n\n"
        "OUTPUT RULES: raw Python code only. "
        "No markdown, no backticks, no explanations. "
        "Start your response directly with 'import'."
    )

    def build(
        self,
        code: str,
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
        class_name: Optional[str] = None,
        module_b_sigs: str = "",
    ) -> BuiltPrompt:
        user = self._USER_TEMPLATE.format(
            module_a_name=module_name or "module_a",
            module_a_source=code.strip(),
            module_b_name=class_name or "module_b",
            module_b_sigs=module_b_sigs or "(no signatures available)",
        )
        return BuiltPrompt(system=self._SYSTEM, user=user)


class CorrectionPromptTemplate(PromptTemplate):
    """
    Template para corregir una función de test pytest que falló.

    Envía al LLM: (1) código de la función fallida, (2) traceback del error,
    (3) firmas del módulo bajo test.
    """

    language = "python_correction"

    _SYSTEM = (
        "You are a Python test-fixing machine. "
        "You output ONLY the corrected test function as raw Python code. Nothing else.\n"
        "ABSOLUTE RULES — never break these:\n"
        "- NO markdown. Never use triple backticks (```) under any circumstances.\n"
        "- NO explanations, NO introductory sentences, NO comments outside the code.\n"
        "- Output ONLY the single corrected test function (def test_...).\n"
        "- Do NOT output the full test file — only the function.\n"
        "- The function must be valid pytest: start with 'def test_', use assert statements.\n"
        "- Return only the corrected test function, no explanations."
    )

    _USER_TEMPLATE = (
        "Fix the following failing pytest test function.\n\n"
        "# Failing test function:\n"
        "{test_function_code}\n\n"
        "# Error traceback:\n"
        "{traceback}\n\n"
        "# Module under test — function signatures:\n"
        "{module_signatures}\n\n"
        "OUTPUT RULES: return ONLY the corrected test function (def test_...). "
        "Raw Python code only. No markdown, no backticks, no explanations."
    )

    def build(
        self,
        code: str,
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
        traceback: str = "",
        module_signatures: str = "",
    ) -> BuiltPrompt:
        user = self._USER_TEMPLATE.format(
            test_function_code=code.strip(),
            traceback=traceback.strip() or "(no traceback available)",
            module_signatures=module_signatures.strip() or "(no signatures available)",
        )
        return BuiltPrompt(system=self._SYSTEM, user=user)


# Registro de templates disponibles. Para agregar un nuevo lenguaje:
# 1. Crear una subclase de PromptTemplate con language="<nombre>"
# 2. Registrarla aquí.
_REGISTRY: dict[str, PromptTemplate] = {
    "python": PythonPromptTemplate(),
    "javascript": JsPromptTemplate(),
    "python_integration": IntegrationPromptTemplate(),
    "python_correction": CorrectionPromptTemplate(),
}


class PromptBuilder:
    """Factory que devuelve el prompt correcto según el lenguaje."""

    @staticmethod
    def build(
        code: str,
        language: str = "python",
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> BuiltPrompt:
        template = _REGISTRY.get(language.lower())
        if template is None:
            supported = ", ".join(_REGISTRY.keys())
            raise ValueError(
                f"Lenguaje '{language}' no soportado. Disponibles: {supported}"
            )
        return template.build(code, function_name, module_name, class_name)

    @staticmethod
    def supported_languages() -> list[str]:
        return list(_REGISTRY.keys())


def clean_response(response: str, *, strip_imports: bool = False, language: str = "python") -> str:
    """
    Limpia el output del LLM eliminando bloques markdown y texto explicativo.

    Estrategia:
    1. Si hay bloques ```...```, extrae solo su contenido (el modelo los incluyó igual).
    2. Si no hay bloques pero hay texto previo al código, descarta todo lo anterior
       a la primera línea que empiece con el patrón de inicio para el lenguaje dado.
    3. En cualquier caso, elimina backticks sueltos residuales.
    4. Si strip_imports=True, elimina líneas de import según el lenguaje.
    """
    # Paso 1: extraer contenido de bloques markdown si existen
    blocks = re.findall(
        r"```(?:python|javascript|js|ts|typescript)?\n?(.*?)```",
        response,
        flags=re.DOTALL,
    )
    if blocks:
        response = "\n\n".join(b.strip() for b in blocks)

    # Paso 2: descartar texto explicativo antes del código
    if language == "javascript":
        match = re.search(r"^(test\s*\(|describe\s*\(|it\s*\()", response, re.MULTILINE)
    else:
        match = re.search(r"^(import |from |def test_)", response, re.MULTILINE)
    if match:
        response = response[match.start():]

    # Paso 3: eliminar backticks sueltos
    response = response.replace("`", "")

    # Paso 4: eliminar líneas de import si el agente provee el header
    if strip_imports:
        if language == "javascript":
            response = "\n".join(
                line for line in response.splitlines()
                if not _is_js_import_line(line)
            )
        else:
            response = "\n".join(
                line for line in response.splitlines()
                if not line.lstrip().startswith(("import ", "from "))
            )

    return response.strip()


def _is_js_import_line(line: str) -> bool:
    stripped = line.lstrip()
    if stripped.startswith("import "):
        return True
    if stripped.startswith(("const ", "let ", "var ")) and "require(" in line:
        return True
    return False


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
