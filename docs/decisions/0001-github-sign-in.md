# 1. Sign in with the SilS GitHub App

Date: 2026-11-24 · Status: accepted

## Context

A shared admin key could not tell users apart. Anyone with the key could import any repository, run extraction on it, and spend the server's GitHub rate limit. A public demo needs per-user limits and a way to let only a project's maintainers run extraction on it.

## Decision

- Users sign in with the SilS GitHub App (owned by the SilSapp org) using GitHub's web flow. Its user tokens expire after 8 hours and carry no scopes beyond what the App is granted.
- The session lives in the database. The browser holds a random token in an HttpOnly, SameSite=Lax cookie, and the database stores only its SHA-256 hash. The user's GitHub token is encrypted with Fernet (`TOKEN_ENCRYPTION_KEY`). A session ends when the GitHub token expires.
- Browsing, search and ask stay open to everyone. Import and sync need a signed-in user. Extraction needs push access to the repository, checked with the user's own token and cached for 5 minutes.
- Imports use the signed-in user's token, so each user spends their own 5,000-call hourly limit. Each user can run one import at a time and start 20 a day. A new repository with over 5,000 issues and PRs is refused.
- Signed-in users can ask 30 questions a minute; everyone else 10 per IP.
- The admin key stays for local use and overrides these limits.

## Alternatives considered

- **OAuth App instead of a GitHub App:** OAuth tokens do not expire and ask for broad scopes. The GitHub App is also needed later for webhooks and PR comments.
- **Signed cookies without a session table:** simpler, but a stolen cookie could not be revoked on sign-out.
- **A fixed number of repositories per user:** easy to explain, but blocks normal use. Size, concurrency and daily limits bound the cost instead.

## Consequences

- Deployments need `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEY`, `PUBLIC_URL` and `APP_URL`. Without them, sign-in is off and the admin-key rules apply.
- Rotating `TOKEN_ENCRYPTION_KEY` signs everyone out, since stored tokens can no longer be read.
- Expired sessions stay in the table until a cleanup job is added.
