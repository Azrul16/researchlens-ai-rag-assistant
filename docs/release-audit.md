# Pre-publication audit

Audit date: 13 October 2026 (Asia/Dhaka).

The repository was reviewed before publication. No commit or push was performed as part of this audit. The configured origin is `Azrul16/researchlens-ai-rag-assistant` on GitHub.

## Results

| Area | Result |
|---|---|
| Backend tests | 25 passed on SQLite and 25 passed on isolated PostgreSQL 18 schemas |
| Backend lint / environment | Ruff passed; `pip check` found no broken requirements |
| Database migrations | Upgrade to `0003` passed; clean SQLite downgrade/upgrade passed; Alembic schema-drift checks passed on SQLite and PostgreSQL |
| Clean checkout | Copied only publishable source files, excluding `.env`, uploaded papers, indexes, logs and installed dependencies; backend tests and frontend frozen-lockfile installation/build passed |
| Frontend checks | ESLint, strict TypeScript and optimized standalone production build passed |
| Browser tests | All 3 Chromium tests passed against the production server, including paper/source inspection, semantic search, citations, reselecting the active workspace, browser back navigation, live chat/history, mobile layout and dialog focus |
| Live AI | Real embeddings and the configured Groq provider passed multi-paper chat, structured analysis, summary, comparison, insufficient-evidence refusal and deletion/index rebuild checks |
| Restart / recovery | Database and FAISS persistence survived a full process restart; intentional corruption of an isolated test index recovered automatically |
| Retrieval evaluation | CLI ran successfully on fictional fixtures; duplicate-page ranking behavior has a regression test |
| Dependency advisories | `pip-audit` on pinned Python requirements and `pnpm audit --prod` reported no known vulnerabilities at audit time |
| Publication safety | Candidate files and existing Git blobs/commit messages scanned for configured credentials and common token/private-key patterns; no matches found |
| Documentation / assets | All 8 README screenshots exist; README commands, environment examples, MIT license and third-party notices reviewed |
| Docker configuration | Compose `config --quiet` passed; environment variants and runtime/build artifacts excluded from build context |

## Issues fixed during review

- Expanded Git exclusions for database files and FAISS indexes, and Docker exclusions for nested/variant `.env` files.
- Validated grouped citations, malformed source markers, cross-paper citations in comparison rows, comparison caveats and changed numeric signs.
- Kept Unicode characters intact when splitting long chunks and computing overlap.
- Moved workspace/file collection inside the deletion lock and revalidated records after acquiring mutation locks, avoiding stale-record operations and missed uploaded files.
- Reported a deleted conversation as missing if it disappears during generation, rather than trying to persist messages against a deleted record.
- Prevented reselecting the active workspace from clearing its papers, and guarded workspace changes during uploads. New-workspace actions reset previous edit state.
- Disabled indexing retry for scanned papers without extracted chunks.
- Stopped browser tests from overwriting tracked README images; aligned the live-chat test timeout with the provider timeout.
- Applied page deduplication before the evaluation cutoff, so many relevant chunks from one page cannot hide another relevant page; rejected ambiguous filename labels.
- Handled non-ASCII invalid authorization headers safely.
- Documented the distinction between the original code's MIT license and third-party dependency/model licenses.

## Remaining verification limits

There is no Docker engine on this machine, so container image builds and full Compose startup were not executed locally. GitHub Actions has not been pushed/run remotely. The workflow includes actual Docker startup/readiness checks and PostgreSQL-backed tests for those environments.

Groq was verified live; Gemini's adapter was verified using automated tests, without a live Gemini key. No review establishes the absence of all vulnerabilities or proves that every generated statement is faithful. The implemented app uses demo/shared-token access rather than multi-user ownership enforcement, synchronous ingestion rather than a distributed worker queue, and no OCR or streaming, as documented.

PyMuPDF has AGPL/commercial licensing terms. Review [third-party notices](../THIRD_PARTY_NOTICES.md) and [upstream licensing](https://pymupdf.io/licensing) for distribution or deployment of an assembled application; the repository's MIT license does not replace those terms.

## Reproduce publication checks

```powershell
.\.venv\Scripts\python.exe scripts/audit-publication.py
git diff --check
docker compose config --quiet
```

The publication scanner reports paths/counts without printing secret values. Its machine-readable report is written to ignored `.logs/publication-audit.json`. Other disposable verification reports are also stored in `.logs/`.
