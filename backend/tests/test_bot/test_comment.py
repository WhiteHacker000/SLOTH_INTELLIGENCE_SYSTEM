import importlib.util
import json
import urllib.error
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / ".github/actions/decision-context/comment.py"
spec = importlib.util.spec_from_file_location("comment", SCRIPT)
assert spec and spec.loader
comment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comment)

RELATED = {
    "matched_files": ["src/cache.py", "src/lock.py"],
    "score": 1.3,
    "decision": {
        "title": "Remove the cache lock",
        "decision": "Stop locking the cache, ask @maintainer",
        "rationale": ["The GIL already protects it", "Locks were slow", "Third"],
        "alternatives": [{"approach": "RLock", "rejection_reason": "Still slow"}],
        "evidence": [
            {"excerpt": "a", "source_url": "https://github.com/a/b/pull/7"},
            {"excerpt": "b", "source_url": "https://github.com/a/b/pull/7"},
        ],
    },
}


def test_clean_removes_html_mentions_and_long_text() -> None:
    assert comment.clean("<img src=x>Hi @bob\n\nthere") == "Hi @​bob there"
    assert comment.clean("a@b.com") == "a@​b.com"
    assert comment.clean("x" * 50, limit=10) == "x" * 9 + "…"


def test_render_lists_the_decision_with_its_sources() -> None:
    body = comment.render([RELATED])

    assert body is not None
    assert body.startswith(comment.MARKER)
    assert "**Remove the cache lock** · `src/cache.py`, `src/lock.py`" in body
    assert "@​maintainer" in body
    assert "- Why: The GIL already protects it; Locks were slow" in body
    assert "- Rejected: RLock: Still slow" in body
    assert body.count("https://github.com/a/b/pull/7") == 1


def test_nothing_to_say_renders_nothing() -> None:
    assert comment.render([]) is None


@pytest.fixture
def github(tmp_path, monkeypatch):
    """Fake GitHub and server; records every write the script makes."""
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {"pull_request": {"number": 9, "title": "Drop the lock", "body": None}}
        )
    )
    for key, value in {
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_REPOSITORY": "a/b",
        "GITHUB_TOKEN": "t",
        "DECISION_SERVER_URL": "https://server/",
    }.items():
        monkeypatch.setenv(key, value)
    state = {"decisions": [RELATED], "comments": [], "writes": [], "down": False}

    def pages(path, token):
        if path.endswith("/files"):
            return iter([{"filename": "src/cache.py"}])
        return iter(state["comments"])

    def request(method, url, token=None, body=None):
        if url.startswith("https://server"):
            if state["down"]:
                raise urllib.error.URLError("refused")
            state["sent"] = body
            return {"decisions": state["decisions"]}
        state["writes"].append((method, url, body["body"]))

    monkeypatch.setattr(comment, "pages", pages)
    monkeypatch.setattr(comment, "request", request)
    return state


def test_posts_a_new_comment(github) -> None:
    assert comment.main() == 0

    [(method, url, body)] = github["writes"]
    assert (method, url) == (
        "POST",
        f"{comment.GITHUB_API}/repos/a/b/issues/9/comments",
    )
    assert "Remove the cache lock" in body
    assert github["sent"]["title"] == "Drop the lock"
    assert github["sent"]["body"] == ""


def test_updates_its_own_comment_instead_of_adding_another(github) -> None:
    github["comments"] = [{"id": 1, "body": "LGTM"}, {"id": 5, "body": comment.MARKER}]
    github["decisions"] = []

    comment.main()

    [(method, url, body)] = github["writes"]
    assert method == "PATCH" and url.endswith("/issues/comments/5")
    assert "No past decisions" in body


def test_stays_quiet_when_there_is_nothing_to_say(github) -> None:
    github["decisions"] = []

    comment.main()

    assert github["writes"] == []


def test_server_down_never_fails_the_pull_request(github, capsys) -> None:
    github["down"] = True

    assert comment.main() == 0
    assert "::warning::" in capsys.readouterr().out
    assert github["writes"] == []
