# API design

## Implemented

- `GET /api/v1/health` returns `{"status": "ok"}`. It reports process health only; it does not probe PostgreSQL, GitHub, or Ollama.
- Sign-in with GitHub, through the SilS GitHub App. Off until `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET` and `TOKEN_ENCRYPTION_KEY` are set.
  - `GET /api/v1/auth/login` sends the browser to GitHub with a random `state`, also kept in a short-lived cookie.
  - `GET /api/v1/auth/callback` is where GitHub sends the browser back. The `state` must match the cookie, or it returns `400`. It then signs the user in and redirects to `APP_URL`. `502` if GitHub refuses the code.
  - The session is an HttpOnly, SameSite=Lax cookie (Secure when `PUBLIC_URL` is https) that lasts as long as the user's GitHub token, at most 8 hours.
  - `GET /api/v1/auth/me` returns `{"sign_in_enabled": true, "user": {"login": "...", "avatar_url": "..."}}`, with `user` null when signed out.
  - `POST /api/v1/auth/logout` ends the session and returns `204`.
  - Once sign-in is set up, import, sync and extraction need a signed-in user or the admin key, and an unset `ADMIN_API_KEY` no longer leaves them open. Search and ask stay open: signed-in users are limited per account (`SIGNED_IN_QUESTIONS_PER_MINUTE`, default 30), everyone else per IP.
- `POST /api/v1/repositories` registers a public GitHub repository.
  - Body: `{"url": "https://github.com/owner/name", "token": "optional"}`. `owner/name` also works.
  - Checks the repository exists, saves it, and returns an import estimate.
  - When the repository is too large for anonymous access, `estimate.token_recommended` is true and `estimate.message` says to add a GitHub token, for the frontend to show as a small notice.
  - Registering the same repository again returns the existing record.
  - Errors: `422` invalid URL, `404` not on GitHub, `429` rate limit reached, `502` GitHub unavailable.
- `GET /api/v1/repositories` lists registered repositories with their last sync time and error.
- `GET /api/v1/repositories/{id}` returns one repository with its discussion, comment and decision counts, and `extracting` (true while an extraction runs).
- `POST /api/v1/repositories/{id}/sync` queues an import for the background worker and returns `202` straight away. A second request while one is queued or running adds nothing.
  - Body (optional): `{"token": "..."}`. The token is used for this sync only and is not stored or logged. Without it, `GITHUB_TOKEN` from `.env` is used, else the import runs anonymously.
  - Check progress with `GET /api/v1/repositories/{id}`. Counts update while the sync runs, since progress is saved every 100 rows.
  - `sync_status` is one of `never_synced`, `running`, `paused`, `failed`, `synced`. `paused` means the rate limit ran out: `last_sync_error` asks for a token and the next sync continues from the last checkpoint.
- `GET /api/v1/repositories/{id}/decisions` lists extracted decisions with `decision`, `rationale`, `alternatives` and `evidence` (quote plus GitHub link).
  - `code` lists the files the decision touched: files changed by the PRs its evidence comes from, and lines that review comments used as evidence point at. Each has a GitHub link; lines link to the exact commit.
- `POST /api/v1/repositories/{id}/extract` queues Gemma on the 15 most-discussed threads not processed yet, and returns `202` with how many threads it picked. Run it again for the next 15. Each thread takes about 15 seconds. While an extraction is queued or running it returns `threads: 0` and "Extraction is already running". If Ollama fails, the job is retried later and skips threads already done.
- `POST /api/v1/search` returns the threads closest in meaning to a question, best first, each shown by its closest chunk.
  - A thread scores its closest chunk's similarity plus its second closest, so a thread that discusses the question in several places ranks above one that mentions it once.
  - Body: `{"query": "Why was X rejected?", "repository_full_name": "owner/name", "source_types": ["issue", "review"], "limit": 5}`. Only `query` is required; `limit` is 1 to 20.
  - Each result has its text, `similarity` (0 to 1, of that chunk), `source_url`, `source_type`, issue or PR number and title, author and time.
  - Errors: `404` unknown repository, `503` embeddings not installed on the server.
  - Search is exact (no vector index yet), which is fast enough for tens of thousands of chunks. Similarity alone does not mean the evidence answers the question.
- `POST /api/v1/ask` answers a question from imported discussions.
  - Body: `{"question": "Why was X rejected?", "repository_full_name": "owner/name", "limit": 6}`. Only `question` is required.
  - Returns `status` (`answered` or `insufficient_evidence`), `answer`, `citations` (the search results the answer used) and `limitations`.
  - If no result scores at least 0.65 similarity, it returns `insufficient_evidence` without calling the model.
  - Citations are checked against the retrieved results. An answer with no real citation becomes `insufficient_evidence`.
  - Errors: `404` unknown repository, `503` embeddings or Ollama not available.
- `POST /api/v1/pr-context` finds past decisions about the files a pull request changes, or about its topic.
  - Body: `{"repository_full_name": "owner/name", "files": ["src/cache.py"], "title": "...", "body": "...", "limit": 5}`. `files` takes up to 300 paths; `title` and `body` are optional.
  - A decision scores 1 for each file it touched that the PR also changes, and 0.3 for each file in the same folder.
  - With a title or body, decisions whose meaning is close to it (cosine similarity of at least 0.70) also match, adding the similarity to their score. Decisions get their embedding the first time this runs. Without the embedding model installed, matching uses files only.
  - Results are best first, with `matched_files`, `similarity` and the full decision.
  - Errors: `404` unknown repository.
- `GET /api/v1/admin` returns `key_required` and `key_valid` for the `X-Admin-Key` header sent, so the UI knows whether to show import and extract controls.
- When `ADMIN_API_KEY` is set, registering, syncing and extracting need it in the `X-Admin-Key` header, else they return `401`.
- Search and ask allow `QUESTIONS_PER_MINUTE` requests per client IP (default 10), then return `429` with a `Retry-After` header. Limits are kept in memory, so they reset on restart.
- FastAPI generates OpenAPI at `/openapi.json` and interactive docs at `/docs`.

## Planned API areas


Use Pydantic schemas for request and response validation. Return stable source URLs rather than opaque citations. Keep route handlers thin; put multi-step use cases in `services/`. Add endpoints only with a tested use case—this is not a commitment to a particular route shape.
