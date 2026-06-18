import io
import json
import urllib.error
from unittest.mock import patch, MagicMock

import pytest

from agent.llm_client import (
    GroqClient,
    GroqAPIError,
    _parse_groq_retry_seconds,
    _GROQ_RETRY_DEFAULT,
)


# ---------------------------------------------------------------------------
# Tests de _parse_groq_retry_seconds
# ---------------------------------------------------------------------------

def test_parse_retry_seconds_exact_message():
    body = '{"error": {"message": "Please try again in 17.29s"}}'
    assert _parse_groq_retry_seconds(body) == pytest.approx(18.29)


def test_parse_retry_seconds_adds_one_second_margin():
    body = "Rate limit exceeded. Please try again in 5.0s."
    assert _parse_groq_retry_seconds(body) == pytest.approx(6.0)


def test_parse_retry_seconds_integer_value():
    body = "try again in 10s"
    assert _parse_groq_retry_seconds(body) == pytest.approx(11.0)


def test_parse_retry_seconds_case_insensitive():
    body = "Try Again In 3.5s"
    assert _parse_groq_retry_seconds(body) == pytest.approx(4.5)


def test_parse_retry_seconds_no_match_returns_default():
    body = "Unknown error occurred"
    assert _parse_groq_retry_seconds(body) == float(_GROQ_RETRY_DEFAULT)


def test_parse_retry_seconds_empty_body_returns_default():
    assert _parse_groq_retry_seconds("") == float(_GROQ_RETRY_DEFAULT)


def test_parse_retry_seconds_zero_seconds():
    body = "try again in 0.0s"
    assert _parse_groq_retry_seconds(body) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tests de GroqClient.generate — retry 429 con tiempo parseado
# ---------------------------------------------------------------------------

def _make_http_error(code: int, body: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.groq.com/openai/v1/chat/completions",
        code=code,
        msg=str(code),
        hdrs=MagicMock(),
        fp=io.BytesIO(body.encode("utf-8")),
    )


def _make_ok_response(content: str) -> bytes:
    return json.dumps({
        "choices": [{"message": {"content": content}}]
    }).encode("utf-8")


@pytest.fixture(autouse=True)
def set_groq_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")


def test_retry_429_uses_parsed_seconds(monkeypatch):
    ok_resp = MagicMock()
    ok_resp.__enter__ = lambda s: s
    ok_resp.__exit__ = MagicMock(return_value=False)
    ok_resp.read.return_value = _make_ok_response("ok")

    body_429 = '{"error": {"message": "Please try again in 17.29s"}}'
    err_429 = _make_http_error(429, body_429)

    slept: list[float] = []
    calls = [err_429, ok_resp]

    def fake_urlopen(req, **kwargs):
        val = calls.pop(0)
        if isinstance(val, Exception):
            raise val
        return val

    monkeypatch.setattr("agent.llm_client.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("agent.llm_client.time.sleep", lambda s: slept.append(s))

    client = GroqClient()
    result = client.generate("hola")

    assert result == "ok"
    assert len(slept) == 1
    assert slept[0] == pytest.approx(18.29)


def test_retry_429_uses_default_when_no_seconds_in_body(monkeypatch):
    ok_resp = MagicMock()
    ok_resp.__enter__ = lambda s: s
    ok_resp.__exit__ = MagicMock(return_value=False)
    ok_resp.read.return_value = _make_ok_response("ok")

    err_429 = _make_http_error(429, '{"error": "rate limit"}')
    slept: list[float] = []
    calls = [err_429, ok_resp]

    def fake_urlopen(req, **kwargs):
        val = calls.pop(0)
        if isinstance(val, Exception):
            raise val
        return val

    monkeypatch.setattr("agent.llm_client.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("agent.llm_client.time.sleep", lambda s: slept.append(s))

    client = GroqClient()
    result = client.generate("hola")

    assert result == "ok"
    assert slept[0] == pytest.approx(float(_GROQ_RETRY_DEFAULT))


def test_retry_429_raises_after_ten_failures(monkeypatch):
    body_429 = '{"error": {"message": "Please try again in 5.0s"}}'
    # Crear un objeto distinto por intento para que e.read() no se agote
    calls = [_make_http_error(429, body_429) for _ in range(10)]
    slept: list[float] = []

    def fake_urlopen(req, **kwargs):
        raise calls.pop(0)

    monkeypatch.setattr("agent.llm_client.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("agent.llm_client.time.sleep", lambda s: slept.append(s))

    client = GroqClient()
    with pytest.raises(GroqAPIError, match="429"):
        client.generate("hola")

    assert len(slept) == 9


def test_non_429_error_raises_immediately(monkeypatch):
    err_500 = _make_http_error(500, '{"error": "internal server error"}')
    slept: list[float] = []

    monkeypatch.setattr(
        "agent.llm_client.urllib.request.urlopen",
        lambda req, **kw: (_ for _ in ()).throw(err_500),
    )
    monkeypatch.setattr("agent.llm_client.time.sleep", lambda s: slept.append(s))

    client = GroqClient()
    with pytest.raises(GroqAPIError, match="500"):
        client.generate("hola")

    assert slept == []
