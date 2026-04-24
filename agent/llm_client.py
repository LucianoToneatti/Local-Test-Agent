"""
Cliente para el modelo LLM local servido por Ollama.

Ollama expone una API REST en http://localhost:11434.
El endpoint /api/generate recibe un prompt y devuelve la respuesta
del modelo de forma streaming (un JSON por línea) o completa.
"""

import json
import urllib.request
import urllib.error
from typing import Optional


OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "deepseek-coder:6.7b"


class OllamaConnectionError(Exception):
    pass


class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_BASE_URL):
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


if __name__ == "__main__":
    client = LLMClient()

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
