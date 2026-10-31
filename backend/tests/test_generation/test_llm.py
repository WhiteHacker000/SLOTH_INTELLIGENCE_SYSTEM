import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from app.generation.llm import LanguageModelError, OllamaModel, generate_validated

Handler = Callable[[httpx.Request], httpx.Response]


class Answer(BaseModel):
    text: str


def ollama(handler: Handler) -> OllamaModel:
    return OllamaModel(
        "http://ollama", "gemma3:4b", transport=httpx.MockTransport(handler)
    )


def reply(content: Any) -> httpx.Response:
    text = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(200, json={"message": {"content": text}})


def test_sends_schema_and_zero_temperature() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return reply({"text": "ok"})

    result = generate_validated(ollama(handler), "system", "prompt", Answer)

    assert result == Answer(text="ok")
    assert sent[0]["format"] == Answer.model_json_schema()
    assert sent[0]["options"] == {"temperature": 0}
    assert [m["role"] for m in sent[0]["messages"]] == ["system", "user"]


@pytest.mark.parametrize("bad", ["not json", {"wrong": "field"}, "[1, 2]"])
def test_retries_once_after_bad_output(bad: Any) -> None:
    replies = iter([reply(bad), reply({"text": "fixed"})])

    result = generate_validated(ollama(lambda _: next(replies)), "s", "p", Answer)

    assert result.text == "fixed"


def test_gives_up_after_repeated_bad_output() -> None:
    with pytest.raises(LanguageModelError, match="valid output"):
        generate_validated(ollama(lambda _: reply("nope")), "s", "p", Answer)


def test_missing_model_says_how_to_fix_it() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, json={"error": "model not found"})

    with pytest.raises(LanguageModelError, match="ollama pull gemma3:4b"):
        generate_validated(ollama(handler), "s", "p", Answer)
    assert calls == 1


def test_ollama_not_running() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LanguageModelError, match="not running"):
        generate_validated(ollama(handler), "s", "p", Answer)
