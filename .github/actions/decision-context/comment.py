"""Comment on a pull request with past decisions about the files it changes.

Runs in GitHub Actions with only the Python standard library. It never checks
out or runs the pull request's code, so it is safe under pull_request_target.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

MARKER = "<!-- decision-context -->"
MAX_FILES = 300
GITHUB_API = "https://api.github.com"


def request(method: str, url: str, token: str | None = None, body=None):
    headers = {"Accept": "application/json", "User-Agent": "decision-context"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read() or "null")


def pages(path: str, token: str):
    for page in range(1, 31):
        items = request("GET", f"{GITHUB_API}{path}?per_page=100&page={page}", token)
        yield from items
        if len(items) < 100:
            return


def clean(text: str, limit: int = 300) -> str:
    """Make discussion text safe to post: no HTML, no @mentions, one line."""
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"@(?=\w)", "@​", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render(related: list[dict]) -> str | None:
    if not related:
        return None
    lines = [MARKER, "### Past decisions about the files in this PR", ""]
    for item in related:
        d = item["decision"]
        files = ", ".join(f"`{clean(f, 120)}`" for f in item["matched_files"][:3])
        lines.append(f"**{clean(d['title'], 120)}** · {files}")
        lines.append(f"> {clean(d['decision'])}")
        if d["rationale"]:
            lines.append(f"- Why: {clean('; '.join(d['rationale'][:2]))}")
        for alt in d["alternatives"][:2]:
            rejected = f"{alt['approach']}: {alt['rejection_reason']}"
            lines.append(f"- Rejected: {clean(rejected)}")
        links = dict.fromkeys(e["source_url"] for e in d["evidence"])
        sources = " · ".join(f"[source {i}]({u})" for i, u in enumerate(links, 1))
        lines += [f"- {sources}", ""]
    lines.append(
        "<sub>Found in past issues and PRs by Decision Intelligence. "
        "Check the sources before relying on it.</sub>"
    )
    return "\n".join(lines)


def find_comment(repo: str, number: int, token: str) -> int | None:
    for comment in pages(f"/repos/{repo}/issues/{number}/comments", token):
        if MARKER in (comment.get("body") or ""):
            return comment["id"]
    return None


def main() -> int:
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"]))
    repo, token = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
    server = os.environ["DECISION_SERVER_URL"].rstrip("/")
    indexed = os.environ.get("DECISION_REPOSITORY") or repo
    number = event["pull_request"]["number"]
    try:
        files = [
            f["filename"] for f in pages(f"/repos/{repo}/pulls/{number}/files", token)
        ]
        if not files:
            return 0
        context = request(
            "POST",
            f"{server}/api/v1/pr-context",
            body={"repository_full_name": indexed, "files": files[:MAX_FILES]},
        )
        body = render(context["decisions"])
        existing = find_comment(repo, number, token)
        if existing:
            body = body or f"{MARKER}\nNo past decisions found for these files."
            url = f"{GITHUB_API}/repos/{repo}/issues/comments/{existing}"
            request("PATCH", url, token, {"body": body})
        elif body:
            url = f"{GITHUB_API}/repos/{repo}/issues/{number}/comments"
            request("POST", url, token, {"body": body})
    except (urllib.error.URLError, KeyError, ValueError) as error:
        # Never block a pull request because the server is down.
        print(f"::warning::Decision context skipped: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
