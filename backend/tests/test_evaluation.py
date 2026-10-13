import pytest

from app.evaluation.metrics import retrieval_metrics


def test_recall_precision_mrr_and_duplicate_pages():
    result = retrieval_metrics(
        [("irrelevant", 1), ("study", 3), ("study", 3), ("study", 4)],
        {("study", 3), ("study", 4)},
        3,
    )
    assert result == {"recall_at_k": 1, "precision_at_k": 2 / 3, "mrr": 0.5}
    assert retrieval_metrics([], {("study", 1)}, 3)["mrr"] == 0
    with pytest.raises(ValueError):
        retrieval_metrics([], set(), 3)


async def test_evaluation_deduplicates_pages_before_truncating(client, monkeypatch):
    import json

    from app.db.models import Chunk, Document
    from app.evaluation.run import evaluate
    from tests.test_research import setup_paper

    http, sessions, path = client
    workspace, paper, _ = await setup_paper(http)
    async with sessions() as db:
        document = await db.get(Document, paper["id"])
        document.chunk_count += 65
        for index in range(65):
            db.add(
                Chunk(
                    document_id=document.id,
                    workspace_id=workspace["id"],
                    chunk_index=index + 2,
                    page_number=1,
                    content="fictional model",
                    token_count=2,
                )
            )
        await db.commit()
    dataset = path / "labels.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "question": "fictional model",
                    "relevant_document": "study.pdf",
                    "relevant_pages": [2],
                }
            ]
        )
    )
    monkeypatch.setattr("app.evaluation.run.Session", sessions)
    report = await evaluate(workspace["id"], dataset, 3)
    assert report["metrics"]["recall_at_k"] == 1
    assert report["metrics"]["mrr"] == 0.5
