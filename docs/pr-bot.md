# Pull request bot

The `decision-context` GitHub Action comments on a pull request with past decisions about the files it changes. It reads the PR's changed files, calls `POST /api/v1/pr-context` on a Decision Intelligence server, and posts one comment. Later pushes update that comment instead of adding new ones. If nothing matches, it stays quiet.

## Setup

1. Import and sync the repository on a server that GitHub can reach, then run extraction. See [deployment.md](deployment.md).
2. In the repository's settings, add a variable `DECISION_SERVER_URL`, for example `https://decisions.example.com`.
3. Add `.github/workflows/decision-context.yml`:

```yaml
name: Decision context
on:
  pull_request_target:
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
jobs:
  comment:
    runs-on: ubuntu-latest
    steps:
      - uses: WhiteHacker000/SLOTH_INTELLIGENCE_SYSTEM/.github/actions/decision-context@main
        with:
          server-url: ${{ vars.DECISION_SERVER_URL }}
          # repository: owner/name  # if the server imported it under another name
```

## Notes

- `pull_request_target` is needed to comment on PRs from forks. It is safe because the action never checks out or runs the PR's code; it only reads the list of changed files.
- Decision text comes from public discussions, so the comment strips HTML and breaks `@mentions` so nobody gets pinged.
- If the server is down or the repository is not imported, the action logs a warning and passes. It never blocks a pull request.
- The server's `/pr-context` endpoint is public and does not call the model, so it needs no admin key.
