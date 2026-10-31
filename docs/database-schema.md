# Database schema plan

## Current state

SQLAlchemy models describe the initial PostgreSQL entities in `backend/app/models/entities.py`. They are not yet wired to API workflows, and the application does not create tables automatically. The basic test suite inspects contracts without connecting to a database.

| Entity | Purpose | Important relationships/data |
| --- | --- | --- |
| `repositories` | Imported repository identity and sync cursor | Full name, GitHub URL, default branch, last sync time |
| `discussions` | Source issue, pull request, comment, or review discussion | Repository, GitHub ID/type, timestamps, title/body, canonical source URL |
| `decisions` | Extracted technical decision | Repository, context, rationale, alternatives, trade-offs, status |
| `evidence_references` | Link a decision to supporting source material | Decision, discussion, excerpt, source URL |
| `discussion_chunks` | Retrieval-ready text and embedding | Discussion, chunk order/text, 384-dimensional vector |

Decision status is constrained to proposed, accepted, rejected, or unresolved. A merged pull request is not sufficient evidence to mark a decision accepted.

## PostgreSQL and pgvector

Configure `DATABASE_URL` in the root `.env`. The example uses Psycopg 3 and a local PostgreSQL database. The database must have the pgvector extension available before embedding persistence is used. No database server is started by this repository.

The embedding column uses 384 dimensions, matching the planned `BAAI/bge-small-en-v1.5` model. Keep the model identifier and dimensionality aligned if the embedding model changes; existing vectors would need re-embedding.

## Migrations

Alembic is not included yet: there is no deployed schema to migrate, and adding a migration history now would add setup without a concrete schema lifecycle. Introduce Alembic before sharing a mutable schema or deploying the database, and use migrations to enable the pgvector extension and create/update tables. Do not rely on `metadata.create_all` in production.

## Future data integrity work

- Make GitHub source identity unique within its repository and source type.
- Preserve immutable source identifiers and canonical URLs.
- Make synchronization idempotent and record a cursor or timestamp per repository.
- Keep evidence references navigable back to original GitHub material.
- Add indexes based on measured query patterns before optimizing.
