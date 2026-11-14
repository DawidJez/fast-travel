import pytest

from app import config
from app.api import parse as parse_api
from app.services.parsing import DemoClient, GeminiClient, LLMError, ParsedTrip
from tests.conftest import FakeLLM


def test_parse_demo_mode(client):
    response = client.post("/api/parse", json={"text": "Do pracy: z Oliwa do Wrzeszcz"})
    assert response.status_code == 200
    assert response.json() == {"name": "Do pracy", "origin": "Oliwa", "destination": "Wrzeszcz", "source": "demo"}


def test_parse_ai_answer(client, llm):
    llm.client = FakeLLM(ParsedTrip(origin="Oliwa", destination="Politechnika Gdańska"))
    response = client.post("/api/parse", json={"text": "  z Oliwy na Polibudę  "})
    assert response.status_code == 200
    assert response.json() == {"name": None, "origin": "Oliwa", "destination": "Politechnika Gdańska", "source": "ai"}
    assert llm.client.calls == ["z Oliwy na Polibudę"]  # stripped before it reaches the LLM


def test_parse_llm_failure_falls_back_to_demo(client, llm):
    llm.client = FakeLLM(error=LLMError("Gemini returned HTTP 503"))
    response = client.post("/api/parse", json={"text": "z Oliwa do Wrzeszcz"})
    assert response.status_code == 200
    assert (response.json()["source"], response.json()["origin"]) == ("demo", "Oliwa")


def test_parse_no_route_is_422(client):
    response = client.post("/api/parse", json={"text": "jutro rano"})
    assert response.status_code == 422
    assert response.json() == {"detail": "No route found in the text"}


def test_parse_writes_nothing_to_the_database(client):
    client.post("/api/parse", json={"text": "z Oliwa do Wrzeszcz"})
    assert client.get("/api/trips").json() == []


@pytest.mark.parametrize(
    "body",
    [{}, {"text": ""}, {"text": "   "}, {"text": 5}, {"text": "x" * (config.PARSE_TEXT_MAX_LENGTH + 1)}],
)
def test_parse_rejects_invalid_input(client, llm, body):
    llm.client = FakeLLM()
    assert client.post("/api/parse", json=body).status_code == 422
    assert llm.client.calls == []


def test_parse_accepts_text_at_the_length_limit(client):
    text = "z Oliwa do Wrzeszcz " + "x" * (config.PARSE_TEXT_MAX_LENGTH - 20)
    assert len(text) == config.PARSE_TEXT_MAX_LENGTH
    response = client.post("/api/parse", json={"text": text})
    assert response.status_code == 200
    assert (response.json()["origin"], response.json()["destination"]) == ("Oliwa", None)  # no 500 on a long fragment


def test_get_llm_client_demo_without_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    assert isinstance(parse_api.get_llm_client(), DemoClient)


def test_get_llm_client_gemini_with_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-x")
    client = parse_api.get_llm_client()
    assert isinstance(client, GeminiClient)
    assert (client.api_key, client.model) == ("k", "gemini-x")
