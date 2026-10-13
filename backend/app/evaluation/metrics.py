def retrieval_metrics(retrieved: list[tuple[str, int]], relevant: set[tuple[str, int]], k: int):
    """Measure unique document/page relevance while preserving rank for reciprocal rank."""
    if k < 1 or not relevant:
        raise ValueError("Use k >= 1 and at least one relevant document/page")
    ranked = list(dict.fromkeys(retrieved))[:k]
    hits = sum(item in relevant for item in ranked)
    return {
        "recall_at_k": hits / len(relevant),
        "precision_at_k": hits / k,
        "mrr": next((1 / (i + 1) for i, item in enumerate(ranked) if item in relevant), 0.0),
    }
