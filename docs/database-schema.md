# Database schema

Models live in `backend/app/models/entities.py`.

| Table | Purpose | Key columns |
| --- | --- | --- |
| `repositories` | A connected GitHub repository and its sync state | `full_name` (unique), `github_id`, `last_synced_at`, `last_sync_error` |
| `discussions` | An issue or pull request | `kind`, `number` (unique per repository), `state`, `author`, `labels`, `source_url`, `merged_at` |
| `comments` | Issue comments, PR review comments, and PR reviews | `kind`, `github_id` (unique per kind), `author`, `source_url` |
| `document_chunks` | Searchable text with its embedding | `discussion_id`, `comment_id` (NULL for the issue/PR body), `ordinal`, `source_url`, `embedding vector(384)` |
| `decisions` | An extracted technical decision | `title`, `decision`, `rationale`, `alternatives`, `trade_offs`, `status`, `confidence`, `extraction_model` |
| `decision_evidence` | Links a decision to the discussion or comment that supports it | `decision_id`, `discussion_id`, `comment_id`, `excerpt`, `source_url` |

## Notes

- **Idempotent imports.** Discussions are unique on `(repository_id, number)` and comments on `(kind, github_id)`, because GitHub uses a separate id sequence per comment kind. Re-importing updates rows instead of duplicating them.
- **Sync checkpoint.** `repositories.last_synced_at` is the cursor for incremental sync (GitHub's `since` parameter).
- **Embeddings** are stored on `document_chunks` rather than in a separate table, since each chunk has exactly one embedding. The 384 dimensions match `BAAI/bge-small-en-v1.5`. Changing the model means re-embedding.
- **Decision status** is one of proposed, accepted, rejected, unresolved. A merged PR alone is not enough to mark a decision accepted.
- **`confidence`** is the model's own score. It is not a calibrated probability.
- A vector index (HNSW) will be added with the embedding pipeline, once there is data to tune it on.
- PostgreSQL 15+ is required (the chunk unique constraint uses `NULLS NOT DISTINCT`).
