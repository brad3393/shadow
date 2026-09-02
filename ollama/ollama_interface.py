"""
Ollama Interface — HTTP API adapter for local Ollama instances.
Provides text generation, chat, model listing, and model pulling.
Uses standard library urllib and json only.
"""

import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from config.config import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TIMEOUT
from logging.logger import ShadowLogger

logger = ShadowLogger.get("shadow.ollama")


class OllamaInterface:
    """Interface for interacting with a local or remote Ollama HTTP API server."""

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        raw_host = host or OLLAMA_HOST
        self.host = raw_host.rstrip("/") if raw_host else "http://localhost:11434"
        self.model = model or OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else OLLAMA_TIMEOUT
        logger.info(f"OllamaInterface initialized with host={self.host}, model={self.model}, timeout={self.timeout}s")

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.host}{endpoint}"
        req_timeout = timeout if timeout is not None else self.timeout

        headers = {}
        data_bytes = None

        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as response:
                if response.status == 200:
                    body = response.read().decode("utf-8")
                    if not body:
                        return {}
                    return json.loads(body)
                else:
                    logger.warning(f"Ollama request to {endpoint} returned status {response.status}")
                    return None
        except urllib.error.HTTPError as e:
            logger.warning(f"Ollama HTTP error {e.code} for {endpoint}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            logger.warning(f"Ollama URL error for {endpoint}: {e.reason}")
            return None
        except (TimeoutError, OSError) as e:
            logger.warning(f"Ollama connection/timeout error for {endpoint}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to decode JSON response from {endpoint}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error communicating with Ollama at {endpoint}: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Ollama service is reachable via GET /api/tags."""
        logger.debug("Checking Ollama availability...")
        res = self._make_request("/api/tags", method="GET")
        available = res is not None
        if available:
            logger.info("Ollama service is available.")
        else:
            logger.warning("Ollama service is unavailable.")
        return available

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """POST /api/generate, returns the text response. Returns empty string on failure."""
        target_model = model or self.model
        logger.info(f"Sending generate request with model '{target_model}'")

        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            },
        }
        if system:
            payload["system"] = system

        res = self._make_request("/api/generate", method="POST", payload=payload)
        if res and isinstance(res, dict) and "response" in res:
            logger.info("Generate response received successfully.")
            return str(res["response"])

        logger.warning("Failed to generate response from Ollama.")
        return ""

    def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """POST /api/chat, returns assistant message content."""
        target_model = model or self.model
        logger.info(f"Sending chat request to model '{target_model}' ({len(messages)} messages)")

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            },
        }

        res = self._make_request("/api/chat", method="POST", payload=payload)
        if res and isinstance(res, dict):
            msg = res.get("message", {})
            if isinstance(msg, dict) and "content" in msg:
                logger.info("Chat response received successfully.")
                return str(msg["content"])

        logger.warning("Failed to get chat response from Ollama.")
        return ""

    def list_models(self) -> list:
        """GET /api/tags, returns list of model names."""
        logger.info("Fetching list of Ollama models...")
        res = self._make_request("/api/tags", method="GET")
        if res and isinstance(res, dict) and "models" in res:
            models = res.get("models", [])
            if isinstance(models, list):
                model_names = [m.get("name") for m in models if isinstance(m, dict) and "name" in m]
                logger.info(f"Retrieved {len(model_names)} models.")
                return model_names

        logger.warning("Failed to retrieve model list from Ollama.")
        return []

    def pull_model(self, model_name: str) -> bool:
        """POST /api/pull, pulls a model."""
        logger.info(f"Pulling model '{model_name}'...")
        payload = {
            "name": model_name,
            "stream": False
        }
        res = self._make_request("/api/pull", method="POST", payload=payload)
        if res is not None:
            logger.info(f"Pull request for model '{model_name}' completed.")
            return True

        logger.warning(f"Failed to pull model '{model_name}'.")
        return False


def self_test() -> bool:
    """Run self-tests for OllamaInterface."""
    logger.info("Starting OllamaInterface self-test...")
    interface = OllamaInterface()

    # Test is_available
    available = interface.is_available()
    assert isinstance(available, bool), "is_available must return bool"

    # Test list_models
    models = interface.list_models()
    assert isinstance(models, list), "list_models must return list"

    # Test generate
    gen_res = interface.generate("Test prompt")
    assert isinstance(gen_res, str), "generate must return str"

    # Test chat
    chat_res = interface.chat([{"role": "user", "content": "Hello"}])
    assert isinstance(chat_res, str), "chat must return str"

    # Test pull_model
    pull_res = interface.pull_model("test_model")
    assert isinstance(pull_res, bool), "pull_model must return bool"

    logger.info("OllamaInterface self-test completed successfully.")
    return True


if __name__ == "__main__":
    success = self_test()
    print("Self-test result:", "SUCCESS" if success else "FAILED")
