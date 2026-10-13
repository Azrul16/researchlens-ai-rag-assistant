# ResearchLens AI

**Research paper analysis and comparison with retrieval-augmented generation.**

ResearchLens AI turns academic PDFs into a searchable research workspace. Upload papers, find relevant passages, ask questions with paper-and-page citations, extract structured research information, and compare methods and reported results across documents.

The application combines a Next.js interface with FastAPI, local Sentence Transformer embeddings, persistent FAISS indexes, and Groq or Gemini generation providers. Document processing, retrieval, context construction, generation, and citation validation are separate components, making the pipeline inspectable and extensible.

[Getting started](#getting-started) | [Screenshots](#screenshots) | [Architecture](#architecture) | [Configuration](#configuration) | [Verification](#verification) | [Documentation](#documentation)

## Capabilities

| Capability | Behavior |
|---|---|
| Research workspaces | Create, rename, and delete collections with persistent papers and conversations. |
| PDF ingestion | Multi-file upload with individual progress, size/page limits, safe UUID storage names, SHA-256 duplicate detection, and readable processing errors. |
| Document processing | Extract page-grounded text and best-effort metadata; create overlapping token chunks with section information. |
| Semantic search | Search a workspace or selected papers with local embeddings, without a generation-provider key. |
| Research chat | Ask evidence-grounded questions, maintain conversation history, and inspect cited passages and original pages. |
| Summaries and analysis | Generate cited summaries and structured methods, datasets, models, metrics, results, limitations, and future-work information. |
| Multi-paper comparison | Compare 2-8 papers using a table, narrative, and caveats about incompatible evaluation protocols. |
| Index recovery | Preserve FAISS indexes across restarts, rebuild after deletions, and recover missing, stale, or corrupted indexes from stored chunks. |
| Retrieval evaluation | Measure page-level Recall@K, Precision@K, and mean reciprocal rank with annotated questions. |

Answers use bounded evidence context, source-ID validation, and numerical checks. If evidence is insufficient, chat returns an explicit insufficient-evidence response. These controls reduce unsupported output but do not establish correctness; inspect sources before relying on a research claim. Test doubles are confined to tests; application workflows do not substitute fabricated AI responses.

## Technology stack

| Layer | Technologies |
|---|---|
| Web application | Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4, Lucide icons |
| API | FastAPI, Pydantic, Uvicorn |
| Persistence | SQLAlchemy async sessions, Alembic, PostgreSQL or SQLite |
| PDF processing | PyMuPDF, recursive token chunking |
| Embeddings | Sentence Transformers; `sentence-transformers/all-MiniLM-L6-v2` by default |
| Retrieval | FAISS CPU, normalized embeddings, optional CrossEncoder reranking |
| Generation | Groq and Gemini backend adapters |
| Quality checks | pytest, Ruff, ESLint, TypeScript, Playwright, GitHub Actions |
| Packaging | Docker Compose, pinned Python requirements, pnpm lockfile |

## Screenshots

Captured from the running application using two generated fictional papers. Chat, analysis and comparison show actual responses from the configured AI provider. Research PDFs and credentials are not bundled.

### Workspace overview

![Workspace overview with indexed papers and research actions](docs/screenshots/overview.png)

### Source-grounded research chat

![Research chat with an evidence-grounded answer and a paper/page citation](docs/screenshots/chat.png)

<details>
<summary>View paper library, search, citations, analysis, comparison and mobile screenshots</summary>

### Paper library

![PDF library with processing status and page counts](docs/screenshots/papers.png)

### Semantic search

![Semantic search results with source passages and similarity scores](docs/screenshots/semantic-search.png)

### Citation evidence

![Citation drawer showing the original source passage and page](docs/screenshots/source-citation.png)

### Structured paper analysis

![Structured research analysis with methods, datasets, results and limitations](docs/screenshots/analysis.png)

### Multi-paper comparison

![Comparison table, narrative and caveats for different evaluation datasets](docs/screenshots/comparison.png)

### Mobile layout

![Research workspace on a mobile viewport](docs/screenshots/mobile.png)

</details>

To refresh these screenshots with both servers running:

```powershell
cd frontend
npx.cmd --yes pnpm@12.11.2 screenshots
```

The capture script creates a disposable workspace with fictional PDFs, captures the actual UI, then removes its fixture data. Live AI screenshots require a configured provider and consume its quota.

## Getting started

### Prerequisites

- **Python 3.14** and **Node.js 24**, matching the verified development environment.
- Git to clone the repository.
- Internet access for dependency installation and the initial embedding-model download.
- A Groq or Gemini API key for chat, summaries, analysis, and comparison. Uploading, indexing, and semantic search do not require a generation-provider key.

The following commands use Windows PowerShell. The double-click launcher is Windows-specific. On other systems, use the equivalent virtual-environment executable with the manual commands, or use Docker Compose.

### 1. Clone and install

```powershell
git clone https://github.com/Azrul16/researchlens-ai-rag-assistant.git
cd researchlens-ai-rag-assistant

# Create only if you do not already have a root .venv.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

cd frontend
npx.cmd --yes pnpm@12.11.2 install --frozen-lockfile
cd ..
```

Reuse an existing `.venv` in an already configured checkout. Activation is optional because the commands use its Python executable directly.

### 2. Configure the environment

Create the root configuration file without overwriting an existing one:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` and choose one provider:

```dotenv
# Option A: Groq
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
```

```dotenv
# Option B: Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
```

Only the selected provider needs a key. Model IDs and other settings are defined in [.env.example](.env.example). Keep credentials in `.env`; do not commit them or place them in frontend configuration.

The frontend defaults to `http://localhost:8000/api/v1`. To change this, copy [frontend/.env.example](frontend/.env.example) to `frontend/.env.local` and edit `NEXT_PUBLIC_API_URL`.

### 3. Launch the application

**For everyday Windows use, double-click [`start.cmd`](start.cmd) in the repository root.**

The launcher opens a terminal, applies migrations, starts both services, waits for readiness, and opens your browser. Keep that terminal open while using the app. Closing it or pressing **Ctrl+C** stops the services and their child processes. This launcher uses the development frontend.

| Service | Address |
|---|---|
| Application | http://localhost:3000 |
| Interactive API documentation | http://localhost:8000/docs |
| Readiness endpoint | http://localhost:8000/api/v1/health |

The embedding model downloads on first use and is cached. The first paper upload can take longer than subsequent uploads. Service logs are stored in the ignored `.logs/` directory.

### Alternative: background startup

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start.ps1
```

This starts services in the background and returns after readiness checks. Services continue running when that terminal closes. Stop them explicitly with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop.ps1
```

The stop script validates recorded process identities before terminating them.

### Alternative: separate development terminals

Backend terminal, starting from the repository root:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend terminal, also starting from the repository root:

```powershell
cd frontend
npx.cmd --yes pnpm@12.11.2 dev
```

Press Ctrl+C in each terminal to stop its service. Backend automatic reload is enabled in this manual mode.

### Optimized frontend

Build the frontend and start the background services with its standalone bundle:

```powershell
cd frontend
npx.cmd --yes pnpm@12.11.2 build
cd ..
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start.ps1 -Production
```

Stop any existing instance before starting another. `-Production` selects the optimized frontend; it does not change backend `APP_ENV` or configure a public deployment.

## Using ResearchLens

1. **Create a workspace** for a research topic or literature review.
2. **Upload text-based PDFs.** Wait until documents are ready. Defaults allow 25 MB and 500 pages per PDF.
3. **Search relevant passages** across the workspace or selected papers. Search does not call a generation provider.
4. **Ask research questions**, such as "Which datasets do these papers use?" or "What limitations are reported for this method?"
5. **Inspect citations** and check the original paper/page before reusing a claim.
6. **Generate a summary or structured analysis** for a paper.
7. **Compare 2-8 papers** and review protocol caveats before interpreting reported metrics.

Conversations and cached analyses persist with the workspace. Deleting a paper removes its file and chunks and rebuilds the index. Deleting a workspace removes its documents, conversations, and index data.

## Architecture

```mermaid
flowchart LR
    U[Researcher] --> W[Next.js interface]
    W --> API[FastAPI backend]
    API --> DB[(SQLite or PostgreSQL)]
    API --> PDF[PDF extraction]
    PDF --> C[Page-aware token chunks]
    C --> E[Local Sentence Transformer]
    E --> V[(Persistent FAISS index)]
    API --> R[Workspace-filtered retrieval]
    V --> R
    R --> RR[Optional reranking]
    RR --> CTX[Bounded evidence context]
    CTX --> LLM[Groq or Gemini]
    LLM --> CHECK[Output and citation validation]
    CHECK --> API
```

### Ingestion and retrieval

PDFs are validated and stored with UUID filenames while their original names remain in metadata. Extraction preserves page provenance. Recursive token chunking retains source and section information, including Unicode text. Local normalized embeddings populate per-workspace FAISS indexes with metadata for detecting incompatible or corrupted artifacts.

Retrieval applies workspace and optional document filters, similarity thresholds, and optional reranking. Context construction respects a token budget rather than sending an entire collection to the generation provider.

### Generation and persistence

Provider adapters handle timeouts, bounded retries, and structured output. The backend maps source IDs to known evidence, validates citations and numerical values, and stores conversations and cached analyses in the database. Invalid provider output is reported rather than replaced with fabricated content.

See [Architecture](docs/architecture.md) and [RAG pipeline](docs/rag-pipeline.md) for implementation details.

### Repository structure

```text
researchlens-ai-rag-assistant/
+-- backend/
|   +-- app/
|   |   +-- api/             # HTTP routes
|   |   +-- core/            # Settings, errors, access controls
|   |   +-- db/              # Models and async sessions
|   |   +-- evaluation/      # Retrieval metrics and CLI
|   |   +-- llm/             # Provider adapters
|   |   +-- rag/             # Retrieval, context, prompts, validation
|   |   +-- services/        # Ingestion, indexes, research workflows
|   +-- alembic/             # Database migrations
|   +-- scripts/             # Live and restart verification
|   +-- tests/               # Backend tests
|   +-- requirements.txt     # Pinned dependencies
+-- frontend/
|   +-- app/                 # Next.js App Router
|   +-- components/          # Research interface
|   +-- hooks/               # Conversation state
|   +-- lib/                 # Typed API client and utilities
|   +-- scripts/             # Screenshots and standalone packaging
|   +-- tests/               # Playwright tests
+-- data/                    # Ignored local research data
+-- docs/                    # Technical documentation and screenshots
+-- scripts/                 # Launch, stop, readiness, publication audit
+-- .github/workflows/ci.yml
+-- .env.example
+-- compose.yaml
+-- start.cmd
+-- THIRD_PARTY_NOTICES.md
+-- LICENSE
```

## Configuration

The backend reads the root `.env`; environment variables can override file settings. See [.env.example](.env.example) for the complete starting configuration.

| Setting | Default / purpose |
|---|---|
| `APP_ENV` | `development`; backend production mode requires `API_TOKEN` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/researchlens.db`; supports `postgresql+asyncpg` |
| `LLM_PROVIDER` | `groq` or `gemini`; defaults to `groq` |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | Backend-only provider credentials |
| `GROQ_MODEL` | `qwen/qwen3.8-27b` |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `LLM_TIMEOUT_SECONDS` | 90-second provider request timeout |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` |
| `EMBEDDING_REVISION` | Optional pinned model revision |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 900 / 120 tokens |
| `RETRIEVAL_TOP_K` / `FINAL_CONTEXT_K` | 8 candidates / 5 final passages |
| `RETRIEVAL_SCORE_THRESHOLD` | 0.3 cosine similarity; calibrate for the corpus |
| `ENABLE_RERANKER` | `false` |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L6-v2` |
| `CONTEXT_TOKEN_BUDGET` | 12000 evidence tokens |
| `CHAT_HISTORY_MESSAGES` | 8 recent messages |
| `MAX_UPLOAD_MB` / `MAX_PDF_PAGES` | 25 MB / 500 pages per PDF |
| `AI_REQUESTS_PER_MINUTE` | 20 expensive requests per client per backend process |
| `API_TOKEN` | Optional shared token; required with `APP_ENV=production` |
| `UPLOAD_DIR` / `VECTOR_INDEX_DIR` | `./data/uploads` / `./data/vector_indexes` |
| `CORS_ORIGINS` | `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | Frontend API address; configured in `frontend/.env.local` or Docker build arguments |

`CHUNK_OVERLAP` must be smaller than `CHUNK_SIZE`; `FINAL_CONTEXT_K` must not exceed `RETRIEVAL_TOP_K`. Relative SQLite/storage paths resolve from the project root. Restart the backend after changing its configuration. Restart the development frontend or rebuild the production bundle after changing its public API URL.

### PostgreSQL

SQLite is the default for local use. To select PostgreSQL, create a database and set the connection URL in `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/researchlens
```

Then apply migrations:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

Use a correctly URL-encoded password. Changing this URL selects another database; it does not transfer existing SQLite data into PostgreSQL.

## Docker Compose

With Docker Engine and Compose available, run from the repository root:

```sh
docker compose config --quiet
docker compose up --build
```

The stack includes PostgreSQL 17, FastAPI, and the optimized Next.js standalone application at ports 8000 and 3000. Application containers run as non-root users and the backend uses CPU PyTorch.

Compose reads provider credentials and selected settings from the root `.env` and explicitly configures other settings in [compose.yaml](compose.yaml). Add environment mappings there when customizing settings not already passed through. The supplied Compose backend uses `APP_ENV=development`; the root `.env` is not copied into the image.

Database data persists in `postgres_data`. Uploads, indexes, and the model cache persist in `research_data`.

```sh
docker compose down
```

This stops containers while retaining volumes. `docker compose down -v` deletes their research data. Replace the default `POSTGRES_PASSWORD` for deployment and review [Security and privacy](#security-and-privacy).

Compose configuration was validated locally. Actual image builds and container startup were not executed on the audited Windows machine because it had no Docker engine; the CI workflow includes these checks.

## API

The base path is `/api/v1`. Interactive schemas are available at http://localhost:8000/docs while the backend runs.

| Area | Representative endpoints |
|---|---|
| Readiness | `GET /health` |
| Workspaces | `GET/POST /workspaces`, `GET/PATCH/DELETE /workspaces/{id}` |
| Documents | `GET/POST /workspaces/{id}/documents`, `GET/DELETE /documents/{id}` |
| Evidence | `GET /documents/{id}/file`, `GET /documents/{id}/chunks` |
| Search | `POST /workspaces/{id}/search` |
| Conversations | `GET/POST /workspaces/{id}/conversations`, `GET/DELETE /conversations/{id}` |
| Chat | `POST /conversations/{id}/messages` |
| Research | `POST /documents/{id}/summary`, `POST /documents/{id}/analyze` |
| Comparison | `POST /workspaces/{id}/compare` |
| Recovery | `POST /documents/{id}/retry`, `POST /workspaces/{id}/rebuild-index` |

Upload uses multipart form data with a `file` field. Multiple selected files are uploaded sequentially by the interface. Errors use a consistent envelope:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": null
  }
}
```

With `API_TOKEN` configured, send `Authorization: Bearer YOUR_ACCESS_TOKEN` to protected routes. The frontend access-token control stores it for the browser session. Enter the application token there, never a provider key. Basic readiness remains unauthenticated.

See the [API guide](docs/api.md) for request conventions, status codes, and processing behavior.

## Verification

### Backend and frontend

From the repository root:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic check
cd ..\frontend
npx.cmd --yes pnpm@12.11.2 lint
npx.cmd --yes pnpm@12.11.2 typecheck
npx.cmd --yes pnpm@12.11.2 build
cd ..
```

Backend tests generate fictional PDFs and use test-only embeddings and mocked generation. They need neither provider keys nor model downloads.

For a dedicated PostgreSQL test database:

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@localhost:5432/researchlens_test'
cd backend
..\.venv\Scripts\python.exe -m pytest
cd ..
Remove-Item Env:TEST_DATABASE_URL
```

Tests create/remove isolated schemas; the account needs schema-creation permission.

### Browser and live AI

With both application services running:

```powershell
cd frontend
npx.cmd --yes pnpm@12.11.2 exec playwright install chromium
npx.cmd --yes pnpm@12.11.2 test:e2e
cd ..
```

Browser chat uses live generation when credentials are configured. For broader live-provider and real-embedding checks:

```powershell
cd backend
..\.venv\Scripts\python.exe scripts/verify_live.py --report ../.logs/live-verification.json
cd ..
```

For isolated restart persistence, corruption recovery, and evaluation checks:

```powershell
cd backend
..\.venv\Scripts\python.exe -m scripts.verify_restart
cd ..
```

Live checks use disposable fictional papers and consume provider quota. Verification reports and temporary artifacts are stored under ignored paths.

### Recorded results

The [13 October 2026 release audit](docs/release-audit.md) recorded:

- 25 backend tests passing on SQLite and isolated PostgreSQL 18 schemas.
- Three Chromium browser tests passing against the optimized frontend.
- Successful frontend lint, strict TypeScript, production build, clean-checkout installation, and migration checks.
- Live Groq verification of chat, summary, analysis, comparison, insufficient evidence, and deletion/index rebuild.
- Successful restart persistence and intentional index-corruption recovery.
- No known dependency vulnerabilities or detected credentials in the publication scan at audit time.

Gemini was verified with mocked responses, without a live key. Remote GitHub Actions had not run at audit time. These are dated results rather than a guarantee about every subsequent revision or deployment.

### CI and publication checks

[GitHub Actions](.github/workflows/ci.yml) defines PostgreSQL-backed backend checks, frontend lint/types/build, and Docker startup/readiness checks for pushes and pull requests. CI does not require provider keys.

Before publication:

```powershell
.\.venv\Scripts\python.exe scripts/audit-publication.py
git diff --check
```

The scanner checks publication candidates and existing Git history for configured credentials, common token/private-key patterns, and runtime artifacts. It verifies README image paths and writes a sanitized report to `.logs/publication-audit.json`.

## Retrieval evaluation and maintenance

Prepare annotated questions using [the example dataset](backend/evaluation/example.json), then run from the repository root:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.evaluation.run --workspace WORKSPACE_UUID --dataset evaluation/example.json --k 5
```

Evaluation reports page-level Recall@K, Precision@K, and mean reciprocal rank, deduplicating pages before the cutoff. It does not call an LLM. Fictional fixture scores verify the evaluator; they are not a benchmark of real research-answer quality. See [methodology](docs/rag-pipeline.md).

From the same backend directory, rebuild an index with:

```powershell
..\.venv\Scripts\python.exe -m app.cli rebuild-index WORKSPACE_UUID
```

Back up the database and uploaded files together before destructive operations. FAISS indexes can be regenerated from stored chunks. Local runtime data defaults to `data/`; Compose uses named volumes.

The [Makefile](Makefile) provides `dev`, `up`, `down`, `backend-test`, `frontend-test`, `lint`, `migrate`, and `rebuild-index WORKSPACE=UUID` where GNU Make, Python, and pnpm are configured.

## Troubleshooting

| Symptom | Suggested action |
|---|---|
| Launcher cannot find `.venv` | Complete the dependency setup in [Getting started](#getting-started). |
| Port 3000 or 8000 is occupied | Close an existing launcher or use `scripts/stop.ps1` for a background instance. Check other applications before terminating unrelated processes. |
| First upload is slow | Allow time for model download and CPU embeddings; inspect backend logs if processing fails. |
| Provider error, timeout, or rate limit | Check the selected provider, key, model, quota, and connectivity. Indexed papers remain available for search. |
| Scanned PDF cannot be indexed | Use a text-based PDF or perform OCR externally before uploading. |
| Duplicate file rejected | Use the existing document or a different workspace. |
| API returns 401 | Enter the configured `API_TOKEN` in the frontend access-token control. |
| Frontend cannot reach the API | Check readiness, `NEXT_PUBLIC_API_URL`, and `CORS_ORIGINS`; rebuild if the production frontend URL changed. |
| Production build missing | Build the frontend before starting with `-Production`. |
| Insufficient evidence | Verify papers are ready, select relevant documents, and ask a specific question. Calibrate retrieval with representative examples. |

For scripted launches, inspect `.logs/backend.log`, `.logs/backend-error.log`, `.logs/frontend.log`, and `.logs/frontend-error.log`.

## Security and privacy

Files, extracted text, conversations, and indexes are stored in the configured database and filesystem. Embeddings are computed locally. Generation sends selected evidence excerpts and conversation context to the configured Groq or Gemini service. This is not an entirely offline workflow; assess provider policies before processing confidential material.

Provider credentials remain backend-only. Environment files, uploaded PDFs, databases, indexes, logs, and build artifacts are excluded from publication. Upload validation, workspace-scoped retrieval, shared-token protection, CORS controls, and per-process rate limiting are implemented.

The application uses a single-tenant/shared-token model. It does not provide account-level document ownership, OAuth, or tenant isolation. Public hosting requires deployment-specific access controls, HTTPS, secret management, backups, and resource limits. `APP_ENV=production` requires an access token but does not supply those infrastructure controls.

Upload your own papers. No copyrighted research PDFs or private documents are bundled.

## Limitations and future work

- **PDF extraction:** No OCR. Complex tables, formulas, and reading order may be reconstructed imperfectly; metadata is best effort.
- **Evidence coverage:** Long-paper analysis may use partial context. Citation and numerical guards do not prove semantic correctness or experimental comparability.
- **Processing scale:** Ingestion is synchronous with thread-pool work. Distributed queues, object storage, and distributed rate limiting are not implemented.
- **Identity:** Shared-token access is available; multi-user ownership and authorization are not implemented.
- **Responses:** Generation returns JSON rather than streaming tokens.
- **Deployment verification:** Actual Docker execution and remote CI were outside the recorded local audit.

Potential extensions include OCR, improved table extraction, hybrid keyword/vector retrieval, OAuth and ownership enforcement, worker queues, S3-compatible storage, distributed rate limiting, pgvector or Qdrant, local generation providers, and broader answer-faithfulness evaluation.

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Component boundaries, persistence, service responsibilities |
| [RAG pipeline](docs/rag-pipeline.md) | Processing, retrieval, context, grounding, evaluation |
| [API guide](docs/api.md) | Routes, request conventions, errors, authentication |
| [Milestone verification](docs/verification.md) | Development verification history |
| [Release audit](docs/release-audit.md) | Dated publication checks, fixes, verification limits |
| [Project specification](PROJECT_SPEC.md) | Original requirements and intended direction; current behavior is documented above |
| [Third-party notices](THIRD_PARTY_NOTICES.md) | Dependency and model licensing considerations |

## Contributing

Describe the problem, implementation, and relevant verification in a pull request. Keep credentials and private papers out of commits. Use fictional test fixtures, preserve source provenance in research features, and run the appropriate backend or frontend checks before submitting changes.

## License

Original repository code is licensed under [MIT](LICENSE). Dependencies and models retain their respective licenses.

PyMuPDF has AGPL v3 or Artifex commercial licensing terms. Review [third-party notices](THIRD_PARTY_NOTICES.md) and [upstream licensing](https://pymupdf.io/licensing) before distributing or hosting the assembled application. The repository's MIT license does not replace those terms.
