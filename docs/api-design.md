# API design

## Implemented

- `GET /api/v1/health` returns `{"status": "ok"}`. It reports process health only; it does not probe PostgreSQL, GitHub, or Ollama.
- FastAPI generates OpenAPI at `/openapi.json` and interactive docs at `/docs`.

## Planned API areas

- Repositories: import, list, inspect sync state, and request synchronization.
- Decisions: list/filter by status, inspect a decision, and include linked evidence.
- Questions: submit a repository-scoped question and return an answer with cited sources and evidence sufficiency/conflict information.

Use Pydantic schemas for request and response validation. Return stable source URLs rather than opaque citations. Keep route handlers thin; put multi-step use cases in `services/`. Add endpoints only with a tested use case—this is not a commitment to a particular route shape.
