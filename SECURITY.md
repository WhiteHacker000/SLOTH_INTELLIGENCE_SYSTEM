# Security Policy

This project is in early development.

## Reporting a vulnerability

Please do not report vulnerabilities in public issues. Use GitHub's private vulnerability reporting for this repository if it is enabled. If it is not enabled, contact the repository maintainers privately through GitHub and include only the information needed to reproduce and assess the issue.

Do not include real API tokens, passwords, or other secrets in issues, pull requests, logs, or test fixtures. Rotate any credential that has been exposed.

## GitHub tokens

The app reads public GitHub data and works without a token. A token only raises GitHub's rate limit.

- A token from `GITHUB_TOKEN` in `.env` stays on your machine. `.env` is ignored by Git.
- The GitHub client keeps the token in memory and never writes it to logs.
- A token sent with a sync request is used for that sync only. It is not stored in the database.
- Read-only access to public repositories is enough. Do not use a token with write scopes.
- If you deploy the backend, serve it over HTTPS before accepting tokens from users.

## Sign-in

See [the sign-in decision record](docs/decisions/0001-github-sign-in.md) for the design.

- The session cookie is HttpOnly and SameSite=Lax, and Secure when `PUBLIC_URL` uses HTTPS. The database stores only a SHA-256 hash of it.
- Users' GitHub tokens are encrypted at rest with `TOKEN_ENCRYPTION_KEY` and never sent to the browser.
- The sign-in `state` is checked against a short-lived cookie to stop forged callbacks.
- Sign-out deletes the session on the server, not just the cookie.

Before deploying with sign-in:

- [ ] Serve the site over HTTPS and set `PUBLIC_URL` and `APP_URL` to the HTTPS URLs.
- [ ] Generate `TOKEN_ENCRYPTION_KEY` on the server and keep it out of Git.
- [ ] Set the App's callback URL to `PUBLIC_URL/api/v1/auth/callback` and nothing else.
- [ ] Keep the App client secret only in the server's `.env`.
- [ ] Leave `ADMIN_API_KEY` unset on the public server, or keep it private.
