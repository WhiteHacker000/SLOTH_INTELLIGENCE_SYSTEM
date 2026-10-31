# Security Policy

This project is in early development.

## Reporting a vulnerability

Please do not report vulnerabilities in public issues. Use GitHub's private vulnerability reporting for this repository if it is enabled. If it is not enabled, contact the repository maintainers privately through GitHub and include only the information needed to reproduce and assess the issue.

Do not include real API tokens, passwords, or other secrets in issues, pull requests, logs, or test fixtures. Rotate any credential that has been exposed.

## GitHub tokens

The app reads public GitHub data and works without a token. A token only raises GitHub's rate limit.

- A token from `GITHUB_TOKEN` in `.env` stays on your machine. `.env` is ignored by Git.
- The GitHub client keeps the token in memory and never writes it to logs.
- Read-only access to public repositories is enough. Do not use a token with write scopes.
- If you deploy the backend, serve it over HTTPS before accepting tokens from users.
