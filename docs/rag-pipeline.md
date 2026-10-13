# RAG pipeline and evaluation

1. Validate the PDF MIME type, magic header, readable structure, encryption, size and page limits. Hash bytes for duplicate detection.
2. Extract text by page. Clean whitespace, null characters and reasonable broken hyphenation; retain scientific symbols and bibliography text. Detect title, PDF author metadata and abstract where available.
3. Detect common section headings. Recursively split at paragraph, line, sentence and word boundaries within the configured token limit. Overlap neighboring chunks without crossing sections or pages. Token counts use `cl100k_base`, independent of the generation provider.
4. Embed each chunk with Sentence Transformers on CPU. Long chunks are divided into model-token windows, mean-pooled, then normalized, avoiding silent model truncation.
5. Persist a FAISS FlatIP index for cosine similarity with authoritative chunk ordering and integrity metadata.
6. Embed the query and retrieve candidate chunks with workspace/document filters. Exclude references unless the query asks about citations or references. Optional CrossEncoder reranking changes ranking but retains cosine scores for the evidence guard.
7. Keep the configured final context count and total evidence-token budget. Assign source IDs only to passages actually sent to the provider.
8. Generate using the selected backend provider. Uploaded content is marked untrusted and must not override system rules. History is bounded and used only to interpret follow-ups; research evidence always comes from fresh retrieval.
9. Validate Pydantic structured output, source IDs and numeric values against the supplied evidence. Refuse unsupported answers rather than exposing ungrounded claims. Citation pages and excerpts always come from stored chunk metadata.

Similarity thresholds are heuristic and need calibration for a corpus. Schema validation, citation checks and numeric guards reduce errors but cannot prove semantic faithfulness or eliminate prompt injection. Users should inspect original sources. The number guard rejects changed numeric values while allowing formatting such as a percentage marker or thousands separator; it cannot validate every unit or experimental interpretation.

## Summaries and comparisons

Analysis prioritizes section coverage within a context budget. Responses explicitly indicate whether all extracted passages were included. Every substantive analysis finding carries source IDs; unsupported fields say "Not clearly stated in the paper." Results are cached by source hash, provider/model, context budget and analysis version. `?refresh=true` regenerates analysis.

Comparison allocates evidence budget to every selected paper and validates one row per paper with citations belonging to that paper. It presents original reported metrics and warns when experimental protocols differ. It never creates normalized rankings across incompatible measurements.

## Retrieval evaluation

Annotate questions with the relevant PDF filename and page numbers. Use your own papers; `backend/evaluation/example.json` demonstrates the format.

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.evaluation.run --workspace WORKSPACE_UUID --dataset evaluation/example.json --k 5
```

The evaluator uses actual embeddings/retrieval without calling an LLM. It ranks unique document/page pairs, preserving the first occurrence of each, and disables the normal score threshold to measure ranking quality. Recall@K is retrieved relevant pages divided by all annotated relevant pages. Precision@K divides relevant hits by K, treating missing results as misses. MRR is the reciprocal rank of the first relevant page, averaged across questions. These are page-level metrics, not chunk-level scores or answer-quality scores. Evaluate on a held-out dataset and record model, revision, chunking, K, threshold and reranker configuration for reproducibility.

An optional offline answer evaluation can separately score faithfulness, answer relevance and context relevance. Do not run expensive judge models on every user question. No automatic judge is included in the request path.
