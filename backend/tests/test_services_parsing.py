"""AI trip parsing tests. Gemini HTTP goes through httpx.MockTransport — no network, no real key."""

import json

import httpx
import pytest

from app import config
from app.services import parsing
from app.services.parsing import (
    DemoClient, GeminiClient, LLMError, NoRouteFoundError, ParsedTrip, parse_demo, parse_trip_text,
)
from tests.conftest import FakeLLM

# Demo parser: sentence -> expected (name, origin, destination).
DEMO_CASES = [
    ("z Oliwa do Wrzeszcz",                                         (None, "Oliwa", "Wrzeszcz")),
    ("Z Gdańsk Oliwa do Politechnika Gdańska",                      (None, "Gdańsk Oliwa", "Politechnika Gdańska")),
    ("ze Sopot do Gdynia",                                          (None, "Sopot", "Gdynia")),
    ("od Pomorska 18 do Żabka Subisława",                           (None, "Pomorska 18", "Żabka Subisława")),
    ("Do pracy: z Oliwa do Wrzeszcz",                               ("Do pracy", "Oliwa", "Wrzeszcz")),
    ("codziennie z Oliwa na Politechnika Gdańska o 8:00 rowerem",   (None, "Oliwa", "Politechnika Gdańska")),
    ("z Oliwa do Wrzeszcz, potem zakupy",                           (None, "Oliwa", "Wrzeszcz")),
    ("z ul. Grunwaldzka 5 do Wrzeszcz.",                            (None, "ul. Grunwaldzka 5", "Wrzeszcz")),
    ("from Sopot to Gdynia at 9",                                   (None, "Sopot", "Gdynia")),
    ("Oliwa -> Wrzeszcz",                                           (None, "Oliwa", "Wrzeszcz")),
    ("Oliwa → Wrzeszcz",                                            (None, "Oliwa", "Wrzeszcz")),
    ("Oliwa - Wrzeszcz",                                            (None, "Oliwa", "Wrzeszcz")),
    ("Bielsko-Biała - Kraków",                                      (None, "Bielsko-Biała", "Kraków")),
    ("jutro rano",                                                  (None, None, None)),
    ("8:00 rowerem",                                                (None, None, None)),
    ("Siłownia: jutro",                                             ("Siłownia", None, None)),
    ("z Oliwa do " + "x" * 300,                                     (None, "Oliwa", None)),  # too long for a place
]


def _answer(**fields) -> str:
    return json.dumps({"name": None, "origin": None, "destination": None, **fields})


# --- ParsedTrip validation ----------------------------------------------------------------------

def test_parsed_trip_strips_and_turns_blank_into_none():
    trip = ParsedTrip.model_validate({"name": "  ", "origin": " Oliwa ", "destination": ""})
    assert trip == ParsedTrip(name=None, origin="Oliwa", destination=None)


@pytest.mark.parametrize("bad", [5, 5.5, True, ["Oliwa"], {"x": 1}])
def test_parsed_trip_rejects_non_text_values(bad):
    with pytest.raises(ValueError):
        ParsedTrip.model_validate({"origin": bad})


def test_parsed_trip_enforces_trip_length_limits():
    with pytest.raises(ValueError):
        ParsedTrip.model_validate({"origin": "x" * (config.TRIP_PLACE_MAX_LENGTH + 1)})
    with pytest.raises(ValueError):
        ParsedTrip.model_validate({"name": "x" * (config.TRIP_NAME_MAX_LENGTH + 1)})


def test_parsed_trip_ignores_unknown_fields():
    trip = ParsedTrip.model_validate({"origin": "Oliwa", "time": "8:00", "mode": "bike", "cost": 5})
    assert trip.model_dump() == {"name": None, "origin": "Oliwa", "destination": None}


# --- demo parser / DemoClient ------------------------------------------------------------------

@pytest.mark.parametrize(("text", "expected"), DEMO_CASES)
def test_parse_demo_cases(text, expected):
    trip = parse_demo(text)
    assert (trip.name, trip.origin, trip.destination) == expected


def test_demo_client_uses_the_rule_parser_and_is_marked_demo():
    client = DemoClient()
    assert client.source == "demo"
    assert client.parse_trip("z Oliwa do Wrzeszcz") == parse_demo("z Oliwa do Wrzeszcz")


# --- parse_trip_text (service) -----------------------------------------------------------------

def test_demo_client_result_is_marked_demo():
    result = parse_trip_text("z Oliwa do Wrzeszcz", DemoClient())
    assert result.source == "demo"
    assert (result.trip.origin, result.trip.destination) == ("Oliwa", "Wrzeszcz")


def test_ai_result_is_used_and_marked_ai():
    llm = FakeLLM(ParsedTrip(name="Do pracy", origin="Oliwa", destination="Politechnika Gdańska"))
    result = parse_trip_text("rano z Oliwy na Polibudę", llm)
    assert result.source == "ai"
    assert result.trip == ParsedTrip(name="Do pracy", origin="Oliwa", destination="Politechnika Gdańska")
    assert llm.calls == ["rano z Oliwy na Polibudę"]


def test_partial_route_is_returned():
    result = parse_trip_text("na uczelnię", FakeLLM(ParsedTrip(destination="Politechnika Gdańska")))
    assert (result.source, result.trip.origin, result.trip.destination) == ("ai", None, "Politechnika Gdańska")


def test_llm_error_falls_back_to_demo(caplog):
    result = parse_trip_text("z Oliwa do Wrzeszcz", FakeLLM(error=LLMError("Gemini returned HTTP 429")))
    assert result.source == "demo"
    assert result.trip.origin == "Oliwa"
    assert "HTTP 429" in caplog.text


def test_user_text_is_not_logged_on_fallback(caplog):
    parse_trip_text("z Tajnej 1 do Prywatnej 2", FakeLLM(error=LLMError("Gemini answer rejected: ValidationError")))
    assert "rejected" in caplog.text
    assert "Tajnej" not in caplog.text


@pytest.mark.parametrize("client", [DemoClient(), FakeLLM(ParsedTrip(name="Do pracy"))])
def test_no_route_raises(client):
    with pytest.raises(NoRouteFoundError, match="No route found"):
        parse_trip_text("jutro rano", client)


def test_no_route_after_fallback_raises():
    with pytest.raises(NoRouteFoundError):
        parse_trip_text("jutro rano", FakeLLM(error=LLMError("down")))


def test_other_errors_are_not_swallowed():
    with pytest.raises(RuntimeError):
        parse_trip_text("x", FakeLLM(error=RuntimeError("bug")))


# --- GeminiClient ------------------------------------------------------------------------------

def _envelope(text: str) -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}


GEMINI_OK = _envelope(_answer(name="Do pracy", origin="Oliwa", destination="Wrzeszcz"))


def _gemini(handler) -> GeminiClient:
    return GeminiClient(api_key="test-key", model="gemini-test", client=httpx.Client(transport=httpx.MockTransport(handler)))


def _json(body, status=200):
    return lambda request: httpx.Response(status, json=body)


def test_gemini_client_is_marked_ai():
    assert GeminiClient(api_key="k", model="m").source == "ai"


def test_gemini_sends_structured_output_request():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=GEMINI_OK)

    _gemini(handler).parse_trip("z Oliwy do Wrzeszcza")

    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == config.GEMINI_URL_TEMPLATE.format(model="gemini-test")
    assert "key=" not in str(request.url)  # key only in a header
    assert request.headers["x-goog-api-key"] == "test-key"
    assert request.extensions["timeout"]["read"] == config.LLM_TIMEOUT_SECONDS
    body = json.loads(request.content)
    assert body["contents"] == [{"role": "user", "parts": [{"text": "z Oliwy do Wrzeszcza"}]}]
    assert body["systemInstruction"]["parts"][0]["text"] == parsing.SYSTEM_PROMPT
    assert body["generationConfig"] == {
        "temperature": 0,
        "responseMimeType": "application/json",
        "responseJsonSchema": parsing.RESPONSE_SCHEMA,
    }


def test_response_schema_allows_only_nullable_strings():
    props = parsing.RESPONSE_SCHEMA["properties"]
    assert set(props) == {"name", "origin", "destination"}
    assert all(p["type"] == ["string", "null"] for p in props.values())
    assert parsing.RESPONSE_SCHEMA["additionalProperties"] is False


def test_gemini_returns_validated_trip():
    assert _gemini(_json(GEMINI_OK)).parse_trip("x") == ParsedTrip(name="Do pracy", origin="Oliwa", destination="Wrzeszcz")


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[1, 2]",
        "42",
        _answer(origin=12),           # a number: the LLM never produces numbers
        _answer(origin="x" * 500),    # too long
    ],
)
def test_gemini_invalid_answer_raises_llm_error(text):
    with pytest.raises(LLMError, match="answer rejected"):
        _gemini(_json(_envelope(text))).parse_trip("x")


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
def test_gemini_http_error_raises_llm_error(status):
    with pytest.raises(LLMError, match=f"HTTP {status}"):
        _gemini(_json({"error": {"message": "nope"}}, status)).parse_trip("x")


def test_gemini_timeout_raises_llm_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMError, match="did not answer within 10 s"):
        _gemini(handler).parse_trip("x")


def test_gemini_connection_error_raises_llm_error():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(LLMError, match="unreachable"):
        _gemini(handler).parse_trip("x")


def test_gemini_invalid_json_envelope_raises_llm_error():
    with pytest.raises(LLMError, match="unexpected response"):
        _gemini(lambda request: httpx.Response(200, content=b"<html>")).parse_trip("x")


@pytest.mark.parametrize(
    "body",
    [
        {"promptFeedback": {"blockReason": "SAFETY"}},          # blocked: no candidates
        {"candidates": []},
        {"candidates": [{"finishReason": "SAFETY"}]},           # no content
        {"candidates": [{"content": {"parts": []}}]},
        [],
    ],
)
def test_gemini_without_text_raises_llm_error(body):
    with pytest.raises(LLMError, match="no text"):
        _gemini(_json(body)).parse_trip("x")


def test_gemini_without_client_uses_own_client(monkeypatch):
    transport = httpx.MockTransport(_json(GEMINI_OK))
    real_client = httpx.Client
    monkeypatch.setattr(parsing.httpx, "Client", lambda: real_client(transport=transport))
    assert GeminiClient(api_key="k", model="m").parse_trip("x").origin == "Oliwa"


def test_gemini_failure_through_service_falls_back_to_demo():
    client = _gemini(_json({"error": {}}, 503))
    result = parse_trip_text("z Oliwa do Wrzeszcz", client)
    assert (result.source, result.trip.origin) == ("demo", "Oliwa")
