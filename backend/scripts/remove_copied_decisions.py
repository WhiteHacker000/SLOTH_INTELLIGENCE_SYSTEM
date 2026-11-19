"""Remove decisions copied from the old extraction prompt's example.

The prompt used to show "Use ruff for linting" as an example, and the model
copied it into threads that never mention ruff. This deletes decisions that
mention ruff when the thread they came from does not, and clears those threads'
extracted mark so the next extraction redoes them with the fixed prompt.

From backend/:

    python -m scripts.remove_copied_decisions          # show what would go
    python -m scripts.remove_copied_decisions --apply  # delete
"""

import argparse

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Comment, Decision, DecisionEvidence, Discussion, Repository

WORD = "%ruff%"


def find_copies(session: Session) -> list[tuple[Decision, Discussion, str]]:
    """Decisions that mention ruff although their thread never does."""
    thread_mentions = or_(
        Discussion.body.ilike(WORD),
        Discussion.title.ilike(WORD),
        exists().where(
            Comment.discussion_id == Discussion.id, Comment.body.ilike(WORD)
        ),
    )
    query = (
        select(Decision, Discussion, Repository.full_name)
        .join(DecisionEvidence, DecisionEvidence.decision_id == Decision.id)
        .join(Discussion, Discussion.id == DecisionEvidence.discussion_id)
        .join(Repository, Repository.id == Decision.repository_id)
        .where(
            or_(Decision.title.ilike(WORD), Decision.decision.ilike(WORD)),
            ~thread_mentions,
        )
        .distinct()
    )
    return [(d, t, r) for d, t, r in session.execute(query)]


def remove(session: Session, found: list[tuple[Decision, Discussion, str]]) -> None:
    session.execute(
        delete(Decision).where(Decision.id.in_({d.id for d, _, _ in found}))
    )
    for _, thread, _ in found:
        thread.decisions_extracted_at = None
    session.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="delete them")
    apply = parser.parse_args().apply
    with SessionLocal() as session:
        found = find_copies(session)
        for decision, thread, repo in found:
            print(f"{repo}#{thread.number}: {decision.title!r}")
        print(f"{len(found)} copied decisions found.")
        if not found:
            return
        if not apply:
            print("Run again with --apply to delete them.")
            return
        remove(session, found)
        session.commit()
        print("Deleted. Run Extract decisions again to redo those threads.")


if __name__ == "__main__":
    main()
