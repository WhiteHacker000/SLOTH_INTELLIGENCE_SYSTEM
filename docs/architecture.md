# Architecture

## Current state

The repository is one Git project with independently run `frontend/` and `backend/` applications. The backend is a **modular monolith**: one FastAPI process, with API, configuration, persistence, and domain capabilities separated into packages. Import, chunking, embeddings, decision extraction, search and grounded answers all work end to end, and the frontend covers import, the repository dashboard, the decision explorer and Q&A.

## Request and data flow

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
| `ingestion/` | GitHub REST API access, source preservation, and incremental sync |
| `processing/` | Normalize source text and create retrieval chunks |
| `embeddings/` | Independently configured embedding model integration |
| `extraction/` | Structured decision extraction and validation |
| `retrieval/` | pgvector similarity search and metadata filtering |
| `generation/` | Evidence-grounded answers and uncertainty handling |
| `services/` | Orchestrate use cases without creating separately deployed services |

Keep routes thin and do not add repository abstractions or service layers until a use case needs them.

## Frontend

A small shared component layer, with UI organized by feature: repository import and dashboard, decision explorer, and Q&A. Each feature handles its own loading, error, empty and insufficient-evidence states. There is no routing yet; add it when there are several screens to move between.

## External systems

- GitHub REST API is the initial import source; unauthenticated public access is supported.
- PostgreSQL is the relational store and pgvector extension provides vector search in that same database.
- Ollama serves Gemma 3 4B locally. The embedding model has its own setting and lifecycle.
- Basic CI tests do not require these external systems.

## Schema evolution

Schema changes go through Alembic migrations in `backend/migrations/`. See [database-schema.md](database-schema.md). Keep PostgreSQL and pgvector as the only storage components.
