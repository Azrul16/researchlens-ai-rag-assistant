# API

Swagger: http://localhost:8000/docs. Base path: `/api/v1`.

| Resource | Endpoints |
|---|---|
| Health | `GET /health`, `GET /provider/health` |
| Workspaces | `GET/POST /workspaces`, `GET/PATCH/DELETE /workspaces/{id}` |
| Papers | `GET/POST /workspaces/{id}/documents`, `GET/DELETE /documents/{id}` |
| Source evidence | `GET /documents/{id}/file`, `GET /documents/{id}/chunks?offset=0&limit=50` |
| Processing | `POST /documents/{id}/retry`, `POST /workspaces/{id}/rebuild-index` |
| Search | `POST /workspaces/{id}/search` with `query`, optional `document_ids`, `top_k` |
| Conversations | `GET/POST /workspaces/{id}/conversations`, `GET/DELETE /conversations/{id}` |
| Chat | `POST /conversations/{id}/messages` with `content`, optional `document_ids` |
| Research | `POST /documents/{id}/summary`, `POST /documents/{id}/analyze` |
| Comparison | `POST /workspaces/{id}/compare` with 2–8 distinct `document_ids`, optional `focus` |

PDF upload is multipart with one `file` field. The UI accepts multiple PDFs and uploads them sequentially with individual progress. Ingestion returns `201` after indexing completes; the document reports `ready` or a recoverable `failed` status. Scanned PDFs are stored as failed with an OCR explanation. Malformed PDFs, unsupported file types and oversized files are rejected before persistence.

Errors use `{"error":{"code":"...","message":"...","details":null}}`. Expected statuses include 404 missing resources, 409 duplicate/non-ready documents, 413 size/page limits, 415 unsupported file types, 422 invalid input, 429 local rate limiting, 502 invalid/ungrounded provider output and 503 upstream provider failure. Refusals with insufficient evidence are successful chat responses with `sufficient_evidence=false` and no sources.

With `API_TOKEN` configured, send `Authorization: Bearer YOUR_ACCESS_TOKEN` to all data routes. The frontend's access-token control stores this token for the current browser session. LLM provider keys remain backend-only and must never be entered into that control. The basic `/health` route is available without a token for container readiness; provider diagnostics require the access token.
