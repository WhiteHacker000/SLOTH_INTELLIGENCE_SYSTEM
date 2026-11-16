"""Connect decisions to the files they touched."""

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Comment, DecisionEvidence, DiscussionFile, Repository
from app.schemas.decisions import CodeReference


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
