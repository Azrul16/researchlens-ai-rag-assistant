"""Exercise real embeddings, restart persistence, index recovery and evaluation in isolation."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

from app.core.config import ROOT
from scripts.verify_live import fictional_pdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=ROOT / ".logs/restart-verification.json")
    args = parser.parse_args()
    folder = ROOT / ".logs" / f"restart-{uuid4().hex}"
    folder.mkdir(parents=True)
    env = {
        **os.environ,
        "APP_ENV": "test",
        "API_TOKEN": "",
        "DATABASE_URL": f"sqlite+aiosqlite:///{(folder / 'check.db').as_posix()}",
        "UPLOAD_DIR": str(folder / "uploads"),
        "VECTOR_INDEX_DIR": str(folder / "indexes"),
    }
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    log = (folder / "server.log").open("w", encoding="utf-8")
    process = None

    def stop():
        nonlocal process
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            process = None

    def start():
        nonlocal process
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Verification backend exited; inspect its isolated log")
            try:
                if httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=1).is_success:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise TimeoutError("Verification backend did not become ready")

    report = {}
    try:
        start()
        with httpx.Client(base_url=f"http://127.0.0.1:{port}/api/v1", timeout=180) as client:
            workspace = client.post("/workspaces", json={"name": "Isolated restart test"}).json()
            uploaded = client.post(
                f"/workspaces/{workspace['id']}/documents",
                files={
                    "file": (
                        "fictional.pdf",
                        fictional_pdf("Fictional Restart Study", "AlphaLogs", "98.4"),
                        "application/pdf",
                    )
                },
            )
            uploaded.raise_for_status()
            assert uploaded.json()["processing_status"] == "ready"
            query = {"query": "What F1 score is reported?"}
            endpoint = f"/workspaces/{workspace['id']}/search"
            before = client.post(endpoint, json=query).json()["results"]
            assert before
            index = folder / "indexes" / workspace["id"] / "index.faiss"
            original = hashlib.sha256(index.read_bytes()).hexdigest()
            modified = index.stat().st_mtime_ns
            stop()
            start()
            after = client.post(endpoint, json=query)
            after.raise_for_status()
            assert [s["chunk_id"] for s in after.json()["results"]] == [
                s["chunk_id"] for s in before
            ]
            assert hashlib.sha256(index.read_bytes()).hexdigest() == original
            assert index.stat().st_mtime_ns == modified
            report["database_and_faiss_restart_persistence"] = "passed"
            index.write_bytes(b"intentional corruption in disposable verification data")
            recovered = client.post(endpoint, json=query)
            recovered.raise_for_status()
            assert recovered.json()["results"]
            assert hashlib.sha256(index.read_bytes()).hexdigest() == original
            report["automatic_corruption_recovery"] = "passed"
            dataset = folder / "evaluation.json"
            dataset.write_text(
                json.dumps(
                    [
                        {
                            "question": "What F1 score is reported?",
                            "relevant_document": "fictional.pdf",
                            "relevant_pages": [2],
                        }
                    ]
                )
            )
            evaluated = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "app.evaluation.run",
                    "--workspace",
                    workspace["id"],
                    "--dataset",
                    str(dataset),
                    "--k",
                    "3",
                ],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            report["retrieval_evaluation"] = json.loads(evaluated.stdout)["metrics"]
            client.delete(f"/workspaces/{workspace['id']}").raise_for_status()
    finally:
        stop()
        log.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
