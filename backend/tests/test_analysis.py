from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas_ai import Finding, GeneratedComparison, PaperAnalysis
from tests.test_documents import pdf_bytes
from tests.test_research import setup_paper


class AnalysisProvider:
    def __init__(self, invalid=False):
        self.calls = 0
        self.invalid = invalid

    async def generate_structured(self, system, messages, schema):
        self.calls += 1
        finding = Finding(
            text="The study evaluates a fictional model.",
            source_ids=["S999" if self.invalid else "S1"],
        )
        return PaperAnalysis(
            title="Invented title",
            authors=["Invented author"],
            research_problem=finding,
            objectives=[],
            methodology=finding,
            datasets=[],
            models=[finding],
            metrics=[],
            key_results=[],
            contributions=[],
            limitations=[],
            future_work=[],
        )


async def test_analysis_summary_cache_and_invalid_sources(client, monkeypatch):
    http, _, _ = client
    provider = AnalysisProvider()
    monkeypatch.setattr("app.services.analysis.get_llm_provider", lambda: provider)
    _, paper, _ = await setup_paper(http)
    endpoint = f"/api/v1/documents/{paper['id']}"
    analyzed = await http.post(endpoint + "/analyze")
    assert analyzed.status_code == 200, analyzed.text
    assert analyzed.json()["analysis"]["title"] == paper["title"]
    assert analyzed.json()["analysis"]["authors"] == []
    assert analyzed.json()["sources"][0]["page_number"] == 1
    summarized = await http.post(endpoint + "/summary")
    assert summarized.status_code == 200
    assert "Methodology" in summarized.json()["summary"]
    assert provider.calls == 1
    monkeypatch.setattr("app.services.analysis.get_llm_provider", lambda: AnalysisProvider(True))
    invalid = await http.post(endpoint + "/analyze?refresh=true")
    assert invalid.status_code == 502


async def test_comparison_validates_each_document(client, monkeypatch):
    http, _, _ = client
    workspace, paper, _ = await setup_paper(http)
    # Different bytes preserve the same fictional text, avoiding duplicate hashes.
    import pymupdf

    with pymupdf.open(stream=pdf_bytes(), filetype="pdf") as pdf:
        pdf.set_metadata({"title": "Second fictional study"})
        second = (
            await http.post(
                f"/api/v1/workspaces/{workspace['id']}/documents",
                files={"file": ("second.pdf", pdf.tobytes(), "application/pdf")},
            )
        ).json()

    class ComparisonProvider:
        async def generate_structured(self, system, messages, schema):
            from app.schemas_ai import ComparisonRow

            rows = []
            import re

            content = messages[0]["content"]
            for document in (paper, second):
                identifier = re.search(
                    r"\[(S\d+)\] Paper: .*?document_id=" + document["id"], content
                ).group(1)
                rows.append(
                    ComparisonRow(
                        document_id=document["id"],
                        paper="Ignored",
                        year="Not stated",
                        objective="Study a fictional model",
                        approach="Fictional model",
                        dataset="Not stated",
                        dataset_size="Not stated",
                        preprocessing="Not stated",
                        training_setup="Not stated",
                        metrics="Not stated",
                        key_result="Not stated",
                        strength="Not stated",
                        limitation="Not stated",
                        computational_requirements="Not stated",
                        source_ids=[identifier],
                    )
                )
            return GeneratedComparison(
                rows=rows,
                narrative="Both studies evaluate fictional models [S1].",
                comparable=False,
                caveats=[],
                source_ids=["S1"],
            )

    monkeypatch.setattr("app.services.analysis.get_llm_provider", lambda: ComparisonProvider())
    endpoint = f"/api/v1/workspaces/{workspace['id']}/compare"
    response = await http.post(endpoint, json={"document_ids": [paper["id"], second["id"]]})
    assert response.status_code == 200, response.text
    assert len(response.json()["rows"]) == 2
    assert response.json()["caveats"]
    duplicate = await http.post(endpoint, json={"document_ids": [paper["id"], paper["id"]]})
    assert duplicate.status_code == 422


async def test_rate_limit_and_api_token(client, monkeypatch):
    http, _, _ = client
    monkeypatch.setenv("API_TOKEN", "test-access")
    get_settings.cache_clear()
    from app.core.security import authorized

    assert not authorized("Bearer invalid-é")
    assert (await http.get("/api/v1/workspaces")).status_code == 401
    cors_response = await http.get(
        "/api/v1/workspaces", headers={"Origin": "http://localhost:3000"}
    )
    assert cors_response.headers["access-control-allow-origin"] == "http://localhost:3000"
    http.headers["Authorization"] = "Bearer test-access"
    _, paper, _ = await setup_paper(http)
    monkeypatch.setenv("AI_REQUESTS_PER_MINUTE", "1")
    get_settings.cache_clear()
    from app.main import app

    app.state.rate_limiter.events.clear()
    monkeypatch.setattr("app.services.analysis.get_llm_provider", lambda: AnalysisProvider())
    assert (await http.post(f"/api/v1/documents/{paper['id']}/analyze")).status_code == 200
    assert (await http.post(f"/api/v1/documents/{paper['id']}/analyze")).status_code == 429


async def test_indexing_failure_retains_text_and_retry_recovers(client, monkeypatch):
    http, _, _ = client

    async def broken(*args, **kwargs):
        raise AppError(503, "EMBEDDING_UNAVAILABLE", "Unavailable")

    monkeypatch.setattr("app.services.documents.ensure_index", broken)
    _, paper, _ = await setup_paper(http)
    assert paper["processing_status"] == "failed"
    assert paper["chunk_count"] > 0
    retry = await http.post(f"/api/v1/documents/{paper['id']}/retry")
    assert retry.status_code == 200, retry.text
    assert retry.json()["processing_status"] == "ready"
