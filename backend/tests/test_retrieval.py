import json

import numpy as np

from app.services.vector_store import load_index, write_index
from tests.helpers import FakeEmbeddings
from tests.test_documents import pdf_bytes


def test_index_persistence_and_corruption(tmp_path):
    provider = FakeEmbeddings()
    vectors = provider.embed_documents(["model accuracy", "ocean biology"])
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-6)
    write_index(tmp_path, ["a", "b"], vectors, provider.identity)
    index = load_index(tmp_path, ["a", "b"], provider.identity)
    scores, positions = index.search(np.array([provider.embed_query("model accuracy")]), 2)
    assert positions[0][0] == 0
    assert scores[0][0] > 0.99
    assert load_index(tmp_path, ["a"], provider.identity) is None
    assert load_index(tmp_path, ["a", "b"], "changed-model") is None
    (tmp_path / "index.faiss").write_bytes(b"broken")
    assert load_index(tmp_path, ["a", "b"], provider.identity) is None


async def test_search_recovers_index_and_filters(client):
    http, _, path = client
    workspace = (await http.post("/api/v1/workspaces", json={"name": "Retrieval"})).json()
    paper = (
        await http.post(
            f"/api/v1/workspaces/{workspace['id']}/documents",
            files={"file": ("study.pdf", pdf_bytes(), "application/pdf")},
        )
    ).json()
    endpoint = f"/api/v1/workspaces/{workspace['id']}/search"
    result = await http.post(
        endpoint, json={"query": "fictional model", "document_ids": [paper["id"]]}
    )
    assert result.status_code == 200
    assert result.json()["results"][0]["document_id"] == paper["id"]
    folder = path / "indexes" / workspace["id"]
    (folder / "index.faiss").write_bytes(b"corrupted")
    recovered = await http.post(endpoint, json={"query": "fictional model"})
    assert recovered.status_code == 200
    assert recovered.json()["results"]
    assert json.loads((folder / "metadata.json").read_text())["ids"]
    other = (await http.post("/api/v1/workspaces", json={"name": "Other"})).json()
    wrong = await http.post(
        f"/api/v1/workspaces/{other['id']}/search",
        json={"query": "model", "document_ids": [paper["id"]]},
    )
    assert wrong.status_code == 404
