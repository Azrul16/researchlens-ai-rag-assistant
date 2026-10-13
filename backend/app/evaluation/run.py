import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.db.models import Document, Workspace
from app.db.session import Session
from app.evaluation.metrics import retrieval_metrics
from app.services.vector_store import retrieve


async def evaluate(workspace_id: str, dataset: Path, k: int):
    records = json.loads(dataset.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("Evaluation data must contain a nonempty list")
    results = []
    async with Session() as db:
        if await db.get(Workspace, workspace_id) is None:
            raise ValueError("Workspace not found")
        documents = (
            await db.scalars(select(Document).where(Document.workspace_id == workspace_id))
        ).all()
        names = {document.id: document.original_filename for document in documents}
        for record in records:
            relevant = {
                (record["relevant_document"], int(page)) for page in record["relevant_pages"]
            }
            if record["relevant_document"] not in names.values():
                raise ValueError(f"Missing evaluation paper: {record['relevant_document']}")
            if list(names.values()).count(record["relevant_document"]) != 1:
                raise ValueError("Evaluation filenames must identify one uploaded paper uniquely")
            matches = await retrieve(
                db,
                workspace_id,
                record["question"],
                top_k=sum(document.chunk_count for document in documents) or k,
                apply_threshold=False,
            )
            ranked = [(names[source["document_id"]], source["page_number"]) for source in matches]
            results.append(
                {"question": record["question"], **retrieval_metrics(ranked, relevant, k)}
            )
    metrics = {
        key: sum(result[key] for result in results) / len(results)
        for key in ("recall_at_k", "precision_at_k", "mrr")
    }
    return {"k": k, "questions": len(results), "metrics": metrics, "results": results}


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate workspace retrieval without calling an LLM"
    )
    parser.add_argument("--workspace", required=True, type=UUID)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.k <= 10:
        parser.error("Use k between 1 and 10")
    print(json.dumps(asyncio.run(evaluate(str(args.workspace), args.dataset, args.k)), indent=2))


if __name__ == "__main__":
    main()
