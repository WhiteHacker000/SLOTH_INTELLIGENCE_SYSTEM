# Database schema

Models live in `backend/app/models/entities.py`. Migrations live in `backend/migrations/` and are managed with Alembic.

| Table | Purpose | Key columns |
| --- | --- | --- |
| `repositories` | A connected GitHub repository and its sync state | `full_name` (unique), `github_id`, `last_synced_at`, `last_sync_error` |
| `discussions` | An issue or pull request | `kind`, `number` (unique per repository), `state`, `author`, `labels`, `source_url`, `merged_at` |
| `comments` | Issue comments, PR review comments, and PR reviews | `kind`, `github_id` (unique per kind), `author`, `source_url` |
| `document_chunks` | Searchable text with its embedding | `discussion_id`, `comment_id` (NULL for the issue/PR body), `ordinal`, `source_url`, `embedding vector(384)` |
| `decisions` | An extracted technical decision | `title`, `decision`, `rationale`, `alternatives`, `trade_offs`, `status`, `confidence`, `extraction_model` |
| `decision_evidence` | Links a decision to the discussion or comment that supports it | `decision_id`, `discussion_id`, `comment_id`, `excerpt`, `source_url` |

## Notes

- **Idempotent imports.** Discussions are unique on `(repository_id, number)` and comments on `(kind, github_id)`, because GitHub uses a separate id sequence per comment kind. Re-importing updates rows instead of duplicating them.
- **Sync checkpoint.** `repositories.last_synced_at` is the cursor for incremental sync (GitHub's `since` parameter).
- **Embeddings** are stored on `document_chunks` rather than in a separate table, since each chunk has exactly one embedding. The 384 dimensions match `BAAI/bge-small-en-v1.5`. Changing the model means re-embedding.
- **Decision status** is one of proposed, accepted, rejected, unresolved. A merged PR alone is not enough to mark a decision accepted.
- **`confidence`** is the model's own score. It is not a calibrated probability.
- A vector index (HNSW) will be added with the embedding pipeline, once there is data to tune it on.
- PostgreSQL 15+ is required (the chunk unique constraint uses `NULLS NOT DISTINCT`).

## Running migrations

The pgvector extension must be installed on the server. The first migration runs `CREATE EXTENSION IF NOT EXISTS vector`, so the database user needs permission to create it, or a superuser can create it once beforehand.

From `backend/`:

```bash
alembic upgrade head      # apply migrations
alembic downgrade -1      # roll back one migration
alembic revision --autogenerate -m "describe change"   # after editing models
alembic check             # fails if models and migrations have drifted
```

`DATABASE_URL` is read from the root `.env`.

## Data access

`backend/app/db/crud.py` has small functions for reading and writing repositories, discussions and comments. `upsert_discussion` and `upsert_comment` use PostgreSQL `ON CONFLICT` on the unique keys above, so re-importing the same GitHub item updates it in place.

## Database tests

Tests in `backend/tests/test_db/` run against a real database and are skipped unless `TEST_DATABASE_URL` is set. Each test runs in a transaction that is rolled back.

```bash
createdb decision_intelligence_test
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/decision_intelligence_test alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/decision_intelligence_test pytest
```

CI installs pgvector on the runner's PostgreSQL and runs these tests on every pull request.
