"""
Clientes LLM para el agente: Ollama (local) y Groq (cloud).

OllamaClient conecta con la API REST local de Ollama.
GroqClient usa la API de Groq con formato OpenAI chat completions.
LLMClient es alias de OllamaClient para compatibilidad con el código existente.
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Optional


OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "deepseek-coder:6.7b"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class OllamaConnectionError(Exception):
    pass


class GroqAPIError(Exception):
    pass


class OllamaClient:
    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Envía un prompt al modelo y devuelve la respuesta completa como string.

        Usa stream=False para recibir la respuesta en un único JSON,
        evitando parseo de línea por línea.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/api/generate"
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                result = json.loads(body)
                return result["response"]
        except urllib.error.URLError as e:
            raise OllamaConnectionError(
                f"No se pudo conectar con Ollama en {self.base_url}. "
                "Verificá que el servicio esté corriendo (`ollama serve`)."
            ) from e

    def is_available(self) -> bool:
        """Verifica que Ollama esté corriendo y el modelo esté cargado."""
        try:
            url = f"{self.base_url}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                models = [m["name"] for m in body.get("models", [])]
                return any(self.model in m for m in models)
        except Exception:
            return False


_GROQ_RETRY_PAT = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)
_GROQ_RETRY_DEFAULT = 20


def _parse_groq_retry_seconds(body: str) -> float:
    """Parsea los segundos de espera del mensaje 429 de Groq y agrega 1s de margen.

    Groq incluye frases como 'Please try again in 17.29s' en el body del error.
    Si no se puede parsear, retorna el valor por defecto de 20s.
    """
    match = _GROQ_RETRY_PAT.search(body)
    if match:
        return float(match.group(1)) + 1.0
    return float(_GROQ_RETRY_DEFAULT)


class GroqClient:
    def __init__(self, model: str = DEFAULT_GROQ_MODEL):
        self.model = model

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        """Envía prompt a Groq usando el formato OpenAI chat completions."""
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise GroqAPIError(
                "GROQ_API_KEY no encontrada. "
                "Exportá la variable de entorno antes de usar --provider groq."
            )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            GROQ_API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )

        last_exc: Exception = GroqAPIError("sin intentos")
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req) as resp:
                    body = resp.read().decode("utf-8")
                    result = json.loads(body)
                    return result["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                if e.code == 429:
                    last_exc = GroqAPIError(f"Error de Groq API ({e.code}): rate limit")
                    if attempt < 2:
                        time.sleep(_parse_groq_retry_seconds(body))
                        continue
                raise GroqAPIError(f"Error de Groq API ({e.code}): {body}") from e
            except urllib.error.URLError as e:
                raise GroqAPIError(f"No se pudo conectar con Groq: {e.reason}") from e
        raise last_exc

    def is_available(self) -> bool:
        """Verifica que GROQ_API_KEY esté seteada en el entorno."""
        return bool(os.environ.get("GROQ_API_KEY"))


# Alias para compatibilidad con todo el código existente
LLMClient = OllamaClient


def create_client(provider: str, model: Optional[str] = None):
    """Retorna el cliente LLM correcto según el proveedor elegido."""
    if provider == "groq":
        return GroqClient(model=model or DEFAULT_GROQ_MODEL)
    return OllamaClient(model=model or DEFAULT_OLLAMA_MODEL)


if __name__ == "__main__":
    client = OllamaClient()

    if not client.is_available():
        print(f"[!] Ollama no disponible o modelo '{client.model}' no encontrado.")
        print("    Ejecutá: ollama pull deepseek-coder:6.7b")
    else:
        sample_code = """
def suma(a, b):
    return a + b
"""
        prompt = f"Generá un test unitario en Python con pytest para esta función:\n{sample_code}"
        print("[*] Enviando prompt al modelo...")
        response = client.generate(prompt)
        print("\n[Respuesta del modelo]\n")
        print(response)
