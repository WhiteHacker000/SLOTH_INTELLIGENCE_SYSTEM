"""Connect decisions to the files they touched, and find them again from a PR."""

from collections import defaultdict
from dataclasses import dataclass, field
from posixpath import dirname
from typing import Any
from uuid import UUID

from sqlalchemy import Select, or_, select, union
from sqlalchemy.orm import Session

from app.models import Comment, Decision, DecisionEvidence, DiscussionFile, Repository
from app.schemas.decisions import CodeReference

SAME_FILE, SAME_FOLDER = 1.0, 0.3
# Measured on the dev data: PR titles score below 0.62 against 90% of unrelated
# decisions, and 0.70 keeps about half of the right ones with 1% wrong.
MIN_SIMILARITY = 0.70


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


@dataclass
class Match:
    decision_id: UUID
    files: list[str] = field(default_factory=list)
    similarity: float | None = None

    def score(self, wanted: set[str]) -> float:
        files = sum(SAME_FILE if f in wanted else SAME_FOLDER for f in self.files)
        return files + (self.similarity or 0.0)


def related_decisions(
    session: Session,
    repository_id: UUID,
    files: list[str],
    limit: int,
    query_vector: list[float] | None = None,
) -> list[tuple[Match, float]]:
    """Decisions that touched the same files or folders, or mean the same thing.

    Returns matches with their score, best first.
    """
    wanted = set(files)
    matches: dict[UUID, Match] = {}
    for decision_id, path in _file_matches(session, repository_id, files):
        matches.setdefault(decision_id, Match(decision_id)).files.append(path)
    if query_vector is not None:
        for decision_id, similarity in _meaning_matches(
            session, repository_id, query_vector
        ):
            matches.setdefault(decision_id, Match(decision_id)).similarity = similarity
    for match in matches.values():
        match.files.sort(key=lambda p: (p not in wanted, p))
    ranked = sorted(matches.values(), key=lambda m: m.score(wanted), reverse=True)
    return [(m, m.score(wanted)) for m in ranked[:limit]]


def _file_matches(
    session: Session, repository_id: UUID, files: list[str]
) -> list[tuple[UUID, str]]:
    if not files:
        return []
    folders = {dirname(f) for f in files if dirname(f)}
    touched = union(_changed_files(), _reviewed_lines()).subquery()
    query = (
        select(touched.c.decision_id, touched.c.path)
        .join(Decision, Decision.id == touched.c.decision_id)
        .where(
            Decision.repository_id == repository_id,
            or_(
                touched.c.path.in_(files),
                *(touched.c.path.startswith(f + "/", autoescape=True) for f in folders),
            ),
        )
    )
    return [(d, p) for d, p in session.execute(query)]


def _meaning_matches(
    session: Session, repository_id: UUID, query_vector: list[float]
) -> list[tuple[UUID, float]]:
    distance = Decision.embedding.cosine_distance(query_vector)
    query = select(Decision.id, distance).where(
        Decision.repository_id == repository_id,
        Decision.embedding.is_not(None),
        distance <= 1 - MIN_SIMILARITY,
    )
    return [(d, 1 - dist) for d, dist in session.execute(query)]
