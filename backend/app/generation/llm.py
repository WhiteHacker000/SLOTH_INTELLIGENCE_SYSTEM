import json
import logging
from functools import lru_cache
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LanguageModelError(RuntimeError):
    """The model could not be reached or kept returning unusable output."""


class InvalidModelOutput(LanguageModelError):
    """The model answered, but not with a JSON object. Worth retrying."""


class LanguageModel(Protocol):
    def generate_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]: ...


class OllamaModel:
    """Calls a local Ollama model and asks for JSON matching a schema."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._http = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )

    def generate_json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "format": schema,
            "stream": False,
            # Deterministic output makes results repeatable and easier to evaluate.
            "options": {"temperature": 0},
        }
        try:
            response = self._http.post("/api/chat", json=payload)
        except httpx.TransportError as error:
            raise LanguageModelError("Ollama is not running") from error
        if response.status_code == 404:
            raise LanguageModelError(
                f"Model {self.model} is not available. Run: ollama pull {self.model}"
            )
        if response.status_code >= 400:
            raise LanguageModelError(f"Ollama returned {response.status_code}")
        try:
            content = response.json()["message"]["content"]
            data = json.loads(content)
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidModelOutput("Ollama returned invalid JSON") from error
        if not isinstance(data, dict):
            raise InvalidModelOutput("Ollama returned JSON that is not an object")
        return data


def generate_validated(
    model: LanguageModel,
    system: str,
    prompt: str,
    schema: type[SchemaT],
    attempts: int = 2,
) -> SchemaT:
    """Ask for output matching `schema`, retrying when it does not validate."""
    for attempt in range(1, attempts + 1):
        try:
            data = model.generate_json(system, prompt, schema.model_json_schema())
            return schema.model_validate(data)
        except (InvalidModelOutput, ValidationError) as error:
            logger.warning("Model output rejected (attempt %d): %s", attempt, error)
            if attempt == attempts:
                raise LanguageModelError(
                    "The model did not return valid output"
                ) from error
    raise AssertionError("unreachable")


@lru_cache
def get_language_model() -> LanguageModel:
    settings = get_settings()
    return OllamaModel(settings.ollama_base_url, settings.gemma_model)
