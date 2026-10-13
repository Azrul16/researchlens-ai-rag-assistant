import json

import httpx
import pytest

from app.core.config import get_settings
from app.core.errors import AppError
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.rag.context import build_context, cited_sources, numbers_supported
from app.schemas_ai import GeneratedAnswer
from tests.test_documents import pdf_bytes


class StubProvider:
    """Test-only responses; normal application code never fabricates AI output."""

    def __init__(self, invalid=False, sufficient=True, fail=False):
        self.invalid, self.sufficient, self.fail = invalid, sufficient, fail
        self.calls = []

    async def generate_structured(self, system, messages, schema):
        self.calls.append((system, messages))
        if self.fail:
            raise AppError(503, "PROVIDER_UNAVAILABLE", "Provider unavailable")
        return schema(
            answer="The study evaluates a fictional model [S1].",
            source_ids=["S999" if self.invalid else "S1"],
            sufficient_evidence=self.sufficient,
        )


async def setup_paper(http):
    workspace = (await http.post("/api/v1/workspaces", json={"name": "Research"})).json()
    paper = (
        await http.post(
            f"/api/v1/workspaces/{workspace['id']}/documents",
            files={"file": ("study.pdf", pdf_bytes(), "application/pdf")},
        )
    ).json()
    conversation = (
        await http.post(f"/api/v1/workspaces/{workspace['id']}/conversations", json={})
    ).json()
    return workspace, paper, conversation


async def test_chat_history_citations_and_deleted_source(client, monkeypatch):
    http, _, _ = client
    provider = StubProvider()
    monkeypatch.setattr("app.rag.pipeline.get_llm_provider", lambda: provider)
    workspace, paper, conversation = await setup_paper(http)
    endpoint = f"/api/v1/conversations/{conversation['id']}"
    response = await http.post(endpoint + "/messages", json={"content": "fictional model"})
    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["page_number"] == 1
    assert response.json()["sources"][0]["document_id"] == paper["id"]
    detail = (await http.get(endpoint)).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["sources"]
    await http.post(endpoint + "/messages", json={"content": "What about the model?"})
    assert len(provider.calls[-1][1]) == 3
    await http.delete(f"/api/v1/documents/{paper['id']}")
    assert len((await http.get(endpoint)).json()["messages"]) == 4
    await http.delete(f"/api/v1/workspaces/{workspace['id']}")
    assert (await http.get(endpoint)).status_code == 404


@pytest.mark.parametrize("invalid,sufficient", [(True, True), (False, False)])
async def test_unsupported_generated_answer_is_refused(client, monkeypatch, invalid, sufficient):
    http, _, _ = client
    monkeypatch.setattr(
        "app.rag.pipeline.get_llm_provider", lambda: StubProvider(invalid, sufficient)
    )
    _, _, conversation = await setup_paper(http)
    response = await http.post(
        f"/api/v1/conversations/{conversation['id']}/messages", json={"content": "fictional model"}
    )
    assert response.status_code == 200
    assert not response.json()["sufficient_evidence"]
    assert response.json()["sources"] == []


async def test_no_evidence_skips_provider_and_failure_does_not_persist(client, monkeypatch):
    http, _, _ = client
    provider = StubProvider(fail=True)
    monkeypatch.setattr("app.rag.pipeline.get_llm_provider", lambda: provider)
    _, _, conversation = await setup_paper(http)
    endpoint = f"/api/v1/conversations/{conversation['id']}"
    response = await http.post(endpoint + "/messages", json={"content": "fictional model"})
    assert response.status_code == 503
    assert (await http.get(endpoint)).json()["messages"] == []
    monkeypatch.setenv("RETRIEVAL_SCORE_THRESHOLD", "1")
    get_settings.cache_clear()
    response = await http.post(endpoint + "/messages", json={"content": "galactic pancakes"})
    assert response.status_code == 200
    assert not response.json()["sufficient_evidence"]
    assert len(provider.calls) == 1


async def test_provider_adapters_validate_wire_format(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    get_settings.cache_clear()
    captured = []

    async def fake_request(method, url, headers, body=None):
        captured.append((url, headers, body))
        answer = {"answer": "Grounded [S1].", "source_ids": ["S1"], "sufficient_evidence": True}
        if "groq" in url:
            return {"choices": [{"message": {"content": json.dumps(answer)}}]}
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}

    monkeypatch.setattr("app.llm.groq_provider.provider_request", fake_request)
    monkeypatch.setattr("app.llm.gemini_provider.provider_request", fake_request)
    for provider in (GroqProvider(), GeminiProvider()):
        result = await provider.generate_structured(
            "Use sources", [{"role": "user", "content": "test"}], GeneratedAnswer
        )
        assert result.source_ids == ["S1"]
    assert captured[0][2]["response_format"]["json_schema"]["strict"] is True
    assert captured[1][2]["generationConfig"]["responseJsonSchema"]
    assert "key=" not in captured[1][0]
    get_settings.cache_clear()


async def test_provider_timeout_is_sanitized(monkeypatch):
    class BrokenClient:
        def __init__(self, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, *args, **kwargs):
            raise httpx.ReadTimeout("secret-content")

    monkeypatch.setattr("app.llm.base.httpx.AsyncClient", BrokenClient)
    from app.llm.base import provider_request

    with pytest.raises(AppError) as error:
        await provider_request("GET", "https://test.example", {})
    assert error.value.status == 503
    assert "secret-content" not in error.value.message


def test_context_budget_and_numeric_guard():
    source = {
        "document_id": "a",
        "document_title": "Study",
        "page_number": 1,
        "chunk_id": "b",
        "section_title": None,
        "excerpt": "F1 is 98.4%.",
        "score": 1.0,
    }
    _, sources = build_context([source], 100)
    assert sources[0]["source_id"] == "S1"
    assert numbers_supported("F1 is 98.4% [S1]", sources)
    assert not numbers_supported("F1 is 98.7% [S1]", sources)
    assert not build_context([source], 1)[1]


def test_grouped_citations_and_sign_changes_are_validated():
    sources = [
        {"source_id": "S1", "excerpt": "The delta is -0.2 and F1 is 98.4%."},
        {"source_id": "S2", "excerpt": "The delta is 0.3."},
    ]
    assert cited_sources("Both sources [S1, S2].", ["S1"], sources) == sources
    assert cited_sources("Unknown [S1, S999].", ["S1"], sources) is None
    assert cited_sources("Malformed [Sfoo].", ["S1"], sources) is None
    assert numbers_supported("F1 is 98.4% [S1; S2].", sources)
    assert not numbers_supported("The delta is 0.2 [S1].", sources)
