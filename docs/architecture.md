# Architecture

## Current state

The repository is one Git project with independently run `frontend/` and `backend/` applications. The backend is a **modular monolith**: one FastAPI process, with API, configuration, persistence, and future domain capabilities separated into packages. The current backend exposes only a health endpoint and validated data contracts. The frontend is a static foundation page.

## Planned request and data flow

```text
React UI
  └── FastAPI routes and Pydantic schemas
        └── application services
              ├── GitHub ingestion → normalization/chunking
              ├── decision extraction (Gemma 3 via Ollama)
              ├── embeddings (BAAI/bge-small-en-v1.5)
              ├── retrieval (PostgreSQL + pgvector)
              └── grounded answer generation with cited evidence
```

GitHub discussions remain the source of evidence. A decision is not inferred solely from a merged pull request: extraction must preserve context, rationale, alternatives, trade-offs, status, and supporting source links.

## Backend boundaries

| Package | Responsibility |
| --- | --- |
| `api/routes/` | HTTP endpoints, status codes, and dependency wiring |
| `core/` | Environment configuration and shared application settings |
| `db/` | SQLAlchemy metadata, engine, and session lifecycle |
| `models/` | PostgreSQL entities for repositories, discussions, decisions, evidence, and embeddings |
| `schemas/` | Pydantic request/response and domain validation contracts |
| `ingestion/` | GitHub REST API access, source preservation, and future incremental sync |
| `processing/` | Normalize source text and create retrieval chunks |
| `embeddings/` | Independently configured embedding model integration |
| `extraction/` | Structured decision extraction and validation |
| `retrieval/` | pgvector similarity search and metadata filtering |
| `generation/` | Evidence-grounded answers and uncertainty handling |
| `services/` | Orchestrate use cases without creating separately deployed services |

These are module boundaries, not completed implementations. Keep routes thin and do not add repository abstractions or service layers until a use case needs them.

## Frontend plan

Use a small shared component layer and organize substantial UI by feature as it arrives: repository dashboard/import, decision explorer/details, and semantic Q&A. Loading, error, empty, insufficient-evidence, and contradictory-evidence states are part of those features. Avoid adding routing until multiple navigable screens require it.

## External systems

- GitHub REST API is the initial import source; unauthenticated public access is supported.
- PostgreSQL is the relational store and pgvector extension provides vector search in that same database.
- Ollama serves Gemma 3 4B locally. The embedding model has its own setting and lifecycle.
- Basic CI tests do not require these external systems.

## Schema evolution

Schema changes go through Alembic migrations in `backend/migrations/`. See [database-schema.md](database-schema.md). Keep PostgreSQL and pgvector as the only storage components.
