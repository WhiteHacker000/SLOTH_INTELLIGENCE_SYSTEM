# Contributing

Thanks for helping make historical project decisions easier to recover. The project is an early foundation: please keep pull requests focused and do not describe planned functionality as implemented.

## Getting started

1. Fork the repository and create a branch from the default branch.
2. Follow the backend and frontend setup instructions in [README.md](README.md).
3. Run the tests relevant to your change before opening a pull request.
4. Keep secrets, local `.env` files, generated assets, and credentials out of commits.

## Pull requests

Prefer a small, reviewable change (roughly 200–300 lines of substantive code where practical; this is guidance, not a limit). A pull request should explain:

- The problem being solved and why it matters.
- The chosen approach and alternatives considered.
- Tests run and evidence that the change works.
- Known limitations and any follow-up work.

Update directly related documentation. Avoid adding infrastructure or dependencies unless the project has a concrete need and the change explains it.

## Testing

- Backend: from `backend/`, run `pytest`.
- Frontend: from `frontend/`, run `npm test` and, for UI or build changes, `npm run build`.

Unit tests should not require real GitHub credentials, a running database, or an Ollama server. Mock external integrations when they are introduced.

## Code of conduct

Be respectful, assume good intent, and give actionable feedback. Harassment, discrimination, personal attacks, and publishing private information are not acceptable. Project maintainers may remove content or contributions that violate these expectations.
