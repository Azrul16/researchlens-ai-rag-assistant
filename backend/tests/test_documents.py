from io import BytesIO

import httpx
import pymupdf
import pytest
from fastapi import UploadFile
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import Chunk, Document
from app.services.documents import upload_document
from app.services.pdf import clean_text, parse_pdf, split_page


def pdf_bytes(scanned=False):
    with pymupdf.open() as pdf:
        first = pdf.new_page()
        if not scanned:
            first.insert_text(
                (72, 72), "Fictional Research Study\n\nMethods\nWe evaluate a fictional model."
            )
            second = pdf.new_page()
            second.insert_text(
                (72, 72), "Results\nThe fictional evaluation reports improved accuracy."
            )
        return pdf.tobytes()


async def test_workspace_upload_extract_delete(client):
    http, sessions, path = client
    response = await http.post("/api/v1/workspaces", json={"name": "  Test research  "})
    assert response.status_code == 201
    workspace = response.json()
    assert workspace["name"] == "Test research"
    endpoint = f"/api/v1/workspaces/{workspace['id']}/documents"
    payload = pdf_bytes()
    response = await http.post(
        endpoint, files={"file": ("../study.pdf", payload, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    paper = response.json()
    assert paper["processing_status"] == "ready"
    assert paper["page_count"] == 2
    assert paper["original_filename"] == "study.pdf"
    chunks = (await http.get(f"/api/v1/documents/{paper['id']}/chunks")).json()
    assert {chunk["page_number"] for chunk in chunks} == {1, 2}
    duplicate = await http.post(endpoint, files={"file": ("other.pdf", payload, "application/pdf")})
    assert duplicate.status_code == 409
    assert len(list((path / "uploads").glob("*.pdf"))) == 1
    file_response = await http.get(f"/api/v1/documents/{paper['id']}/file")
    assert file_response.content == payload
    assert (await http.delete(f"/api/v1/documents/{paper['id']}")).status_code == 204
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Chunk)) == 0
        assert await db.scalar(select(func.count()).select_from(Document)) == 0
    assert not list((path / "uploads").glob("*.pdf"))


async def test_invalid_pdf_and_scanned(client):
    http, _, _ = client
    workspace = (await http.post("/api/v1/workspaces", json={"name": "PDF validation"})).json()
    endpoint = f"/api/v1/workspaces/{workspace['id']}/documents"
    invalid = await http.post(endpoint, files={"file": ("fake.pdf", b"not pdf", "application/pdf")})
    assert invalid.status_code == 415
    malformed = await http.post(
        endpoint, files={"file": ("bad.pdf", b"%PDF- broken", "application/pdf")}
    )
    assert malformed.status_code == 422
    scanned = await http.post(
        endpoint, files={"file": ("scan.pdf", pdf_bytes(True), "application/pdf")}
    )
    assert scanned.json()["processing_status"] == "failed"
    assert "OCR" in scanned.json()["processing_error"]
    assert scanned.json()["chunk_count"] == 0


async def test_workspace_deletion_and_validation(client):
    http, sessions, path = client
    assert (await http.post("/api/v1/workspaces", json={"name": "  "})).status_code == 422
    assert (await http.get("/api/v1/workspaces/not-a-uuid")).status_code == 422
    workspace = (await http.post("/api/v1/workspaces", json={"name": "Delete me"})).json()
    await http.post(
        f"/api/v1/workspaces/{workspace['id']}/documents",
        files={"file": ("study.pdf", pdf_bytes(), "application/pdf")},
    )
    assert (await http.delete(f"/api/v1/workspaces/{workspace['id']}")).status_code == 204
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Chunk)) == 0
    assert not list((path / "uploads").glob("*.pdf"))


async def test_upload_size_limit(client, monkeypatch):
    _, sessions, _ = client
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    async with sessions() as db:
        with pytest.raises(AppError) as error:
            await upload_document(
                db,
                "unused",
                UploadFile(
                    BytesIO(b"%PDF-" + b"x" * 1024 * 1024),
                    filename="big.pdf",
                    headers=httpx.Headers({"content-type": "application/pdf"}),
                ),
            )
        assert error.value.status == 413


def test_cleaning_and_page_boundaries():
    assert clean_text("multi-\nhead  attention\x00") == "multihead attention"
    passages = split_page("One sentence. " * 200, 7, 50, 10)
    assert all(p.page_number == 7 and p.token_count <= 50 for p in passages)
    assert len(passages) > 1
    parsed = parse_pdf(pdf_bytes(), 900, 120)
    assert parsed["passages"][0].page_number == 1
    with pytest.raises(ValueError):
        Settings(chunk_size=100, chunk_overlap=100)


async def test_patch_keeps_omitted_workspace_fields(client):
    http, _, _ = client
    workspace = (
        await http.post("/api/v1/workspaces", json={"name": "Original", "description": "Keep"})
    ).json()
    updated = await http.patch(
        f"/api/v1/workspaces/{workspace['id']}", json={"description": "Changed"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Original"
    assert updated.json()["description"] == "Changed"
    assert (
        await http.patch(f"/api/v1/workspaces/{workspace['id']}", json={"name": None})
    ).status_code == 422


def test_recursive_tokens_and_section_continuity():
    chunks = split_page(
        "Methods\n"
        + "A complicated neural architecture is evaluated. " * 100
        + "\nResults\nF1 = 98.4%.",
        1,
        60,
        10,
    )
    assert all(chunk.token_count <= 60 for chunk in chunks)
    assert chunks[0].section_title == "Methods"
    assert chunks[-1].section_title == "Results"
    assert "98.4%" in chunks[-1].content


def test_unicode_chunk_boundaries_preserve_source_text():
    text = "🧬" * 75
    chunks = split_page(text, 1, 50, 0)
    assert "".join(chunk.content for chunk in chunks) == text
    assert all(chunk.token_count <= 50 for chunk in chunks)
    overlapping = split_page(text, 1, 50, 10)
    assert all("\ufffd" not in chunk.content for chunk in overlapping)


async def test_workspace_deletion_collects_files_after_acquiring_lock(client, monkeypatch):
    from contextlib import asynccontextmanager
    from uuid import uuid4

    from app.services.vector_store import workspace_lock

    http, sessions, path = client
    workspace = (await http.post("/api/v1/workspaces", json={"name": "Concurrent upload"})).json()
    added_file = path / "late-upload.pdf"

    @asynccontextmanager
    async def interleaved_lock(workspace_id):
        # Simulate an upload completing just before deletion obtains its workspace lock.
        added_file.write_bytes(pdf_bytes())
        async with sessions() as db:
            db.add(
                Document(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    original_filename="late-upload.pdf",
                    stored_filename="late-upload.pdf",
                    file_path=str(added_file),
                    file_hash="a" * 64,
                    file_size=added_file.stat().st_size,
                    processing_status="failed",
                )
            )
            await db.commit()
        async with workspace_lock(workspace_id):
            yield

    monkeypatch.setattr("app.api.routes.workspace_lock", interleaved_lock)
    response = await http.delete(f"/api/v1/workspaces/{workspace['id']}")
    assert response.status_code == 204, response.text
    assert not added_file.exists()
