# API design

## Implemented

- `GET /api/v1/health` returns `{"status": "ok"}`. It reports process health only; it does not probe PostgreSQL, GitHub, or Ollama.
- `POST /api/v1/repositories` registers a public GitHub repository.
  - Body: `{"url": "https://github.com/owner/name", "token": "optional"}`. `owner/name` also works.
  - Checks the repository exists, saves it, and returns an import estimate.
  - When the repository is too large for anonymous access, `estimate.token_recommended` is true and `estimate.message` says to add a GitHub token, for the frontend to show as a small notice.
  - Registering the same repository again returns the existing record.
  - Errors: `422` invalid URL, `404` not on GitHub, `429` rate limit reached, `502` GitHub unavailable.
- `GET /api/v1/repositories` lists registered repositories with their last sync time and error.
- FastAPI generates OpenAPI at `/openapi.json` and interactive docs at `/docs`.

## Planned API areas

- Repositories: inspect one repository and start a background sync.
- Decisions: list/filter by status, inspect a decision, and include linked evidence.
- Questions: submit a repository-scoped question and return an answer with cited sources and evidence sufficiency/conflict information.

Use Pydantic schemas for request and response validation. Return stable source URLs rather than opaque citations. Keep route handlers thin; put multi-step use cases in `services/`. Add endpoints only with a tested use case—this is not a commitment to a particular route shape.
