import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_REQUESTS_PER_MINUTE", "1000")
    monkeypatch.setenv("API_TOKEN", "")
    monkeypatch.setenv("APP_ENV", "test")
    app.state.rate_limiter.events.clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VECTOR_INDEX_DIR", str(tmp_path / "indexes"))
    from tests.helpers import FakeEmbeddings

    monkeypatch.setattr(
        "app.services.vector_store.get_embedding_provider", lambda: FakeEmbeddings()
    )
    get_settings.cache_clear()
    database_url = os.environ.get("TEST_DATABASE_URL")
    schema = f"test_{uuid4().hex}"
    admin = None
    if database_url:
        admin = create_async_engine(database_url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(
            database_url, connect_args={"server_settings": {"search_path": schema}}
        )
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)

    async def override():
        async with session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, session, tmp_path
    app.dependency_overrides.clear()
    await engine.dispose()
    if admin:
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
    get_settings.cache_clear()
