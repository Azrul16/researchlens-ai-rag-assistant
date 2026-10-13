from functools import lru_cache

from app.core.config import get_settings


@lru_cache
def get_reranker():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(get_settings().reranker_model, device="cpu", trust_remote_code=False)


def rerank(query: str, sources: list[dict]) -> list[dict]:
    """Reorder candidates without replacing cosine scores used by the evidence guard."""
    scores = get_reranker().predict([(query, source["excerpt"]) for source in sources])
    return [
        source
        for _, source in sorted(
            zip(scores, sources, strict=True), key=lambda item: float(item[0]), reverse=True
        )
    ]
