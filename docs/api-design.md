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
- `GET /api/v1/repositories/{id}` returns one repository with its discussion and comment counts.
- `POST /api/v1/repositories/{id}/sync` starts an import in the background and returns `202` straight away.
  - Body (optional): `{"token": "..."}`. The token is used for this sync only and is not stored or logged. Without it, `GITHUB_TOKEN` from `.env` is used, else the import runs anonymously.
  - Check progress with `GET /api/v1/repositories/{id}`. Counts update while the sync runs, since progress is saved every 100 rows.
  - `sync_status` is one of `never_synced`, `running`, `paused`, `failed`, `synced`. `paused` means the rate limit ran out: `last_sync_error` asks for a token and the next sync continues from the last checkpoint.
- `POST /api/v1/search` returns the discussion chunks closest in meaning to a question.
  - Body: `{"query": "Why was X rejected?", "repository_full_name": "owner/name", "source_types": ["issue", "review"], "limit": 5}`. Only `query` is required; `limit` is 1 to 20.
  - Each result has its text, `similarity` (0 to 1), `source_url`, `source_type`, issue or PR number and title, author and time.
  - Errors: `404` unknown repository, `503` embeddings not installed on the server.
  - Search is exact (no vector index yet), which is fast enough for tens of thousands of chunks. Similarity alone does not mean the evidence answers the question.
- FastAPI generates OpenAPI at `/openapi.json` and interactive docs at `/docs`.

## Planned API areas

- Decisions: list/filter by status, inspect a decision, and include linked evidence.
- Questions: submit a repository-scoped question and return an answer with cited sources and evidence sufficiency/conflict information.

Use Pydantic schemas for request and response validation. Return stable source URLs rather than opaque citations. Keep route handlers thin; put multi-step use cases in `services/`. Add endpoints only with a tested use case—this is not a commitment to a particular route shape.
