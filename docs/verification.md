# Milestone verification

Verification was performed locally on Windows with Python 3.14, Node.js 24 and the existing `.venv`. Only generated fictional research PDFs were used. Credentials were read from ignored `.env` and were never included in reports or committed files.

| Milestone | Verification |
|---|---|
| Foundation and documents | Workspace CRUD, upload/extraction, safe filenames, duplicate rejection, malformed/scanned PDFs, size limits, cascading deletion and Alembic migrations. |
| Embeddings and retrieval | Seven initial tests; real normalized 384-dimensional embeddings; persisted index loading, corrupted/stale index detection and document/workspace filtering. |
| RAG and research analysis | Eighteen initial backend tests covering cited chat/history, evidence refusals, invalid citations, sanitized provider failures, both provider wire formats, analysis caching, summary, comparison, rate limits and indexing retry. |
| PostgreSQL and evaluation | Twenty-one backend tests on SQLite and on isolated PostgreSQL 18 schemas. Migration upgrade to `0003`; UTC timestamp incompatibility found and fixed. Metric calculations checked with known rankings. |
| Frontend | ESLint, strict TypeScript and production build passed. All three Chromium tests passed against the optimized standalone server, covering source passages, semantic search, citation drawer, browser back navigation, live chat/history, mobile layout and dialog focus. |
| Live AI workflow | Actual Groq generation with real embeddings verified across multi-paper questions, cited summary/analysis, comparison with incompatible-dataset caveats, insufficient evidence and deletion rebuild. |
| Deployment configuration | Official standalone Docker Compose CLI checksum checked; `config --quiet` passed. CPU PyTorch wheel availability checked. |

Live checks encountered a provider quota response during one run. The application reported a sanitized upstream error. Bounded retries and improved follow-up retrieval were implemented, and the complete live check subsequently passed. Browser checks also found a dialog-focus issue and duplicate React form keys; both were corrected and reverified.

Machine-readable disposable reports are under ignored `.logs/`: `live-verification.json` and `restart-verification.json`. Run the maintenance checks with:

```powershell
cd backend
..\.venv\Scripts\python.exe scripts/verify_live.py --report ../.logs/live-verification.json
..\.venv\Scripts\python.exe -m scripts.verify_restart
```

The restart check launches isolated temporary backend processes, uses real embeddings, verifies database/index persistence after a full process restart, corrupts only its disposable index and checks automatic recovery, then runs the real retrieval-evaluation CLI. Its fixture corpus is deliberately tiny; those metrics do not establish retrieval quality on arbitrary academic papers.

## Verification limits

The machine has no Docker engine, so local container builds/startup could not be executed. The CI workflow includes actual Docker build/start/readiness checks for an environment with Docker. GitHub Actions was not pushed or run remotely. Gemini's request/response adapter is tested without credentials; live generation was verified with the configured Groq account. OCR, multi-user authentication, distributed workers and streaming are explicitly outside the implemented MVP, as permitted by the specification.
