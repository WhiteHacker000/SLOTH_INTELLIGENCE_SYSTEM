# Open-Source Decision Intelligence and Knowledge Recovery

An open-source project to recover technical decisions and their rationale from GitHub discussions. The planned system will answer contributor questions with evidence-grounded explanations and direct links to the original discussions.

**Current status:** this repository contains the initial project foundation, configuration, API health endpoint, typed data contracts, and smoke tests. GitHub synchronization, database persistence, model inference, retrieval, and decision answering are not implemented yet.

## Technology

- **Frontend:** React, TypeScript, Vite, Tailwind CSS v4, shadcn/ui
- **Backend:** Python, FastAPI, Pydantic
- **AI (planned):** Gemma 3 4B through Ollama; `BAAI/bge-small-en-v1.5` for embeddings; retrieval-augmented generation (RAG)
- **Storage (planned):** PostgreSQL and pgvector
- **Source integration (planned):** GitHub REST API
- **Tests and CI:** Pytest, Vitest, React Testing Library, GitHub Actions

The backend is one modular FastAPI application (a modular monolith), not a collection of services. No Docker, Redis, Celery, separate vector store, or AI orchestration framework is part of this foundation.

## Repository layout

```text
.
├── backend/
│   ├── app/
│   │   ├── api/routes/       # HTTP endpoints and route composition
│   │   ├── core/             # Settings and cross-cutting configuration
│   │   ├── db/               # SQLAlchemy base, engine, and sessions
│   │   ├── models/           # PostgreSQL persistence models, including pgvector
│   │   ├── schemas/          # Validated API and domain data contracts
│   │   ├── ingestion/        # GitHub import and synchronization boundary
│   │   ├── processing/       # Discussion normalization and chunking boundary
│   │   ├── embeddings/       # Embedding-model integration boundary
│   │   ├── extraction/       # Structured decision extraction boundary
│   │   ├── retrieval/        # Semantic search and evidence selection boundary
│   │   ├── generation/       # Grounded answer generation boundary
│   │   ├── services/         # Use-case orchestration within the monolith
│   │   └── main.py           # FastAPI application entry point
│   ├── tests/                # Unit and API tests; no external services required
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/       # Shared interface components
│   │   ├── features/         # Future repository, decision, and Q&A features
│   │   ├── pages/            # Page-level composition
│   │   ├── types/            # Shared frontend domain types
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/
│   └── package.json
├── evaluation/               # Future datasets and retrieval/answer metrics
├── docs/                     # Architecture, API, database, and AI pipeline notes
├── .github/workflows/        # CI
├── .env.example
├── CONTRIBUTING.md
├── HACKATHON.md
├── SECURITY.md
└── LICENSE
```

Module directories are boundaries for future work, not claims that those features already exist. See [docs/architecture.md](docs/architecture.md) for the planned responsibilities.

## Development setup

### Prerequisites

- Python 3.11 or newer
- Node.js 22 or newer and npm
- For future database-backed work: PostgreSQL with the pgvector extension available
- For future local inference: Ollama with the configured models pulled

The current smoke tests do not require PostgreSQL, GitHub credentials, Ollama, or downloaded models.

### Environment

Copy `.env.example` to `.env` at the repository root and adjust local values if needed. Public GitHub repositories can be read without a token; `GITHUB_TOKEN` is optional and only increases API rate limits. Keep credentials in `.env`, which is ignored by Git.

The default PostgreSQL URL is a local placeholder, not a working credential. The health endpoint does not connect to the database.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-embeddings.txt  # optional, for search
uvicorn app.main:app --reload
```

The API health check is at `http://localhost:8000/api/v1/health`. FastAPI provides interactive OpenAPI documentation at `http://localhost:8000/docs` and the schema at `http://localhost:8000/openapi.json`.

Run backend lint and tests from `backend/`:

```bash
ruff check .
ruff format --check .
pytest
```

`LOG_LEVEL` in `.env` controls application log verbosity.

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Run frontend lint, tests, and a production build from `frontend/`:

```bash
npm run lint
npm test
npm run build
```

During development, Vite proxies `/api` requests to the backend at `http://localhost:8000`, so the frontend needs no CORS configuration.

The initial screen is intentionally a foundation/status page; it does not yet call the backend or claim that repository import, decisions, or question answering work.

## Configuration and dependencies

Backend runtime dependencies are listed in `backend/requirements.txt`; test-only dependencies are in `backend/requirements-dev.txt`. `backend/pyproject.toml` configures the package and pytest. Frontend dependencies and scripts are managed with npm and `frontend/package-lock.json`.

SQLAlchemy, Psycopg 3, and pgvector handle PostgreSQL persistence, and Alembic manages schema migrations. Run `alembic upgrade head` from `backend/` after setting `DATABASE_URL`. See [docs/database-schema.md](docs/database-schema.md). The frontend's `components.json` configures shadcn/ui generation; shadcn components are added as needed rather than installing a large UI bundle up front.

## Planned implementation stages

1. Import public GitHub issues, pull requests, comments, and reviews; preserve their URLs, IDs, timestamps, and repository context.
2. Normalize discussions and define stable chunk/evidence boundaries; support incremental synchronization later.
3. Persist repositories, discussions, decisions, evidence, and 384-dimensional embeddings in PostgreSQL/pgvector.
4. Extract proposed, accepted, rejected, and unresolved decisions without treating a merged pull request as proof of a decision.
5. Retrieve relevant evidence and use Gemma 3 via Ollama to answer with source citations, including explicit insufficient- or conflicting-evidence responses.
6. Build repository dashboard/import, decision explorer/details, semantic Q&A, and loading/error/empty states in the frontend.
7. Add evaluation datasets and measurable retrieval and answer-quality checks.

More detail: [database schema](docs/database-schema.md), [AI pipeline](docs/ai-pipeline.md), and [API design](docs/api-design.md).

## Contributions

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request. Changes should be focused, tested, and clear about what is implemented versus planned.
