import logging
import threading
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Normalized document and query embeddings for interchangeable models."""

    identity: str

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class SentenceTransformerEmbeddings:
    """Lazy CPU model with window pooling to avoid silently truncating long chunks."""

    def __init__(self, model_name: str, revision: str | None = None):
        self.identity = f"{model_name}@{revision or 'main'}:window-mean-v1"
        self.model_name = model_name
        self.revision = revision
        self._model = None
        self._lock = threading.RLock()

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(
                    self.model_name, revision=self.revision, device="cpu", trust_remote_code=False
                )
            except Exception as exc:
                logger.error("embedding_model_load_failed type=%s", type(exc).__name__)
                raise AppError(
                    503,
                    "EMBEDDING_UNAVAILABLE",
                    "The embedding model could not be loaded."
                    " Check network access or download the model into the local cache.",
                ) from exc
        return self._model

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            model = self._load()
            if not texts:
                return np.empty((0, model.get_sentence_embedding_dimension()), dtype="float32")
            windows, ranges = [], []
            window_size = max(32, model.max_seq_length - 8)
            for text in texts:
                ids = model.tokenizer.encode(text, add_special_tokens=False)
                start = len(windows)
                for offset in range(0, max(1, len(ids)), window_size):
                    windows.append(model.tokenizer.decode(ids[offset : offset + window_size]))
                ranges.append((start, len(windows)))
            embeddings = model.encode(
                windows, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
            )
            pooled = np.array([embeddings[a:b].mean(axis=0) for a, b in ranges], dtype="float32")
            pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
            return np.ascontiguousarray(pooled)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return SentenceTransformerEmbeddings(settings.embedding_model, settings.embedding_revision)
