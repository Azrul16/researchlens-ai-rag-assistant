"""Verify real embeddings and the configured LLM with disposable fictional papers."""

import argparse
import json
from pathlib import Path

import httpx
import pymupdf


def fictional_pdf(title, dataset, score):
    with pymupdf.open() as pdf:
        pdf.set_metadata({"title": title, "author": "Fictional Research Team"})
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            f"{title}\nAbstract\nThis fictional study detects server log anomalies.\n"
            "Introduction\nThe objective is to identify abnormal server behavior.\n"
            "Methods\nA neural network classifies sequences of server log events.\n"
            f"Dataset\nThe study uses the fictional {dataset} dataset.\n",
        )
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            f"Results\nThe model reports F1 = {score}% on {dataset}.\n"
            "Limitations\nThe study has not been evaluated across different log formats.\n"
            "Future Work\nFuture work will examine transfer to additional server environments.",
        )
        return pdf.tobytes()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000/api/v1")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = {}
    with httpx.Client(base_url=args.api, timeout=180) as client:
        workspace = client.post("/workspaces", json={"name": "Disposable live verification"})
        workspace.raise_for_status()
        workspace_id = workspace.json()["id"]
        try:
            documents = []
            for title, dataset, score in [
                ("Fictional Log Study Alpha", "AlphaLogs", "98.4"),
                ("Fictional Log Study Beta", "BetaLogs", "94.2"),
            ]:
                uploaded = client.post(
                    f"/workspaces/{workspace_id}/documents",
                    files={
                        "file": (
                            title + ".pdf",
                            fictional_pdf(title, dataset, score),
                            "application/pdf",
                        )
                    },
                )
                uploaded.raise_for_status()
                assert uploaded.json()["processing_status"] == "ready", uploaded.json()
                documents.append(uploaded.json()["id"])
            report["upload_and_embeddings"] = "passed"
            search = client.post(
                f"/workspaces/{workspace_id}/search", json={"query": "server log anomaly detection"}
            )
            search.raise_for_status()
            assert search.json()["results"]
            report["semantic_search"] = "passed"
            conversation = client.post(f"/workspaces/{workspace_id}/conversations", json={}).json()
            answer = client.post(
                f"/conversations/{conversation['id']}/messages",
                json={"content": "Which datasets are used and what F1 scores are reported?"},
            )
            answer.raise_for_status()
            assert answer.json()["sufficient_evidence"], answer.json()
            assert {s["document_id"] for s in answer.json()["sources"]} == set(documents)
            assert "98.4" in answer.json()["answer"] and "94.2" in answer.json()["answer"]
            report["multi_document_rag"] = "passed"
            analysis = client.post(f"/documents/{documents[0]}/analyze")
            analysis.raise_for_status()
            assert analysis.json()["analysis"]["datasets"]
            summary = client.post(f"/documents/{documents[0]}/summary")
            summary.raise_for_status()
            assert "98.4" in summary.json()["summary"]
            report["analysis_and_summary"] = "passed"
            comparison = client.post(
                f"/workspaces/{workspace_id}/compare", json={"document_ids": documents}
            )
            comparison.raise_for_status()
            assert len(comparison.json()["rows"]) == 2
            assert not comparison.json()["comparable"], comparison.json()
            report["comparison_and_protocol_caveat"] = "passed"
            unsupported = client.post(
                f"/conversations/{conversation['id']}/messages",
                json={
                    "content": "Give me a recipe for chocolate pancakes with cooking instructions."
                },
            )
            unsupported.raise_for_status()
            assert not unsupported.json()["sufficient_evidence"]
            report["insufficient_evidence"] = "passed"
            removed = client.delete(f"/documents/{documents[0]}")
            removed.raise_for_status()
            filtered = client.post(
                f"/workspaces/{workspace_id}/search", json={"query": "server log anomaly detection"}
            )
            filtered.raise_for_status()
            assert all(s["document_id"] == documents[1] for s in filtered.json()["results"])
            report["deletion_rebuild"] = "passed"
        finally:
            client.delete(f"/workspaces/{workspace_id}").raise_for_status()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
