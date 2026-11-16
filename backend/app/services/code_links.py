"""Connect decisions to the files they touched, and find them again from a PR."""

from collections import defaultdict
from posixpath import dirname
from typing import Any
from uuid import UUID

from sqlalchemy import Select, or_, select, union
from sqlalchemy.orm import Session

from app.models import Comment, Decision, DecisionEvidence, DiscussionFile, Repository
from app.schemas.decisions import CodeReference

SAME_FILE, SAME_FOLDER = 1.0, 0.3


def _changed_files() -> Select[Any]:
    """Files changed by the PRs a decision's evidence comes from."""
    return select(DecisionEvidence.decision_id, DiscussionFile.path).join(
        DiscussionFile, DiscussionFile.discussion_id == DecisionEvidence.discussion_id
    )


def _reviewed_lines() -> Select[Any]:
    """Lines of code that a review comment used as evidence points at."""
    return (
        select(DecisionEvidence.decision_id, Comment.path)
        .join(Comment, Comment.id == DecisionEvidence.comment_id)
        .where(Comment.path.is_not(None))
    )


def code_for(
    session: Session, repository: Repository, decision_ids: list[UUID]
) -> dict[UUID, list[CodeReference]]:
    web, branch = repository.html_url, repository.default_branch or "HEAD"
    refs: dict[UUID, dict[str, CodeReference]] = defaultdict(dict)
    lines = _reviewed_lines().add_columns(Comment.line, Comment.commit_sha)
    for decision_id, path, line, sha in session.execute(
        lines.where(DecisionEvidence.decision_id.in_(decision_ids))
    ):
        url = f"{web}/blob/{sha or branch}/{path}" + (f"#L{line}" if line else "")
        refs[decision_id][path] = CodeReference(path=path, line=line, url=url)
    for decision_id, path in session.execute(
        _changed_files().where(DecisionEvidence.decision_id.in_(decision_ids))
    ):
        refs[decision_id].setdefault(
            path, CodeReference(path=path, url=f"{web}/blob/{branch}/{path}")
        )
    return {d: sorted(r.values(), key=lambda c: c.path) for d, r in refs.items()}


def related_decisions(
    session: Session, repository_id: UUID, files: list[str], limit: int
) -> list[tuple[UUID, list[str], float]]:
    """Decisions that touched the same files, or files in the same folders.

    Returns (decision id, matched files, score), best first.
    """
    wanted = set(files)
    folders = {dirname(f) for f in files if dirname(f)}
    touched = union(_changed_files(), _reviewed_lines()).subquery()
    query = (
        select(touched.c.decision_id, touched.c.path)
        .join(Decision, Decision.id == touched.c.decision_id)
        .where(
            Decision.repository_id == repository_id,
            or_(
                touched.c.path.in_(wanted),
                *(touched.c.path.startswith(f + "/", autoescape=True) for f in folders),
            ),
        )
    )
    matches: dict[UUID, set[str]] = defaultdict(set)
    for decision_id, path in session.execute(query):
        matches[decision_id].add(path)

    def score(paths: set[str]) -> float:
        return sum(SAME_FILE if p in wanted else SAME_FOLDER for p in paths)

    ranked = sorted(matches.items(), key=lambda m: score(m[1]), reverse=True)
    return [
        (decision_id, sorted(paths, key=lambda p: (p not in wanted, p)), score(paths))
        for decision_id, paths in ranked[:limit]
    ]
