# Evaluation

Measures how well search finds the right discussion, and how well answers cite it, against a labelled question set.

## Dataset

`datasets/questions.jsonl` has one question per line:

```json
{"repository": "pallets/itsdangerous", "question": "Why are exp and iat kept in the JWS header?", "expected_threads": [73]}
```

- `expected_threads` are the issue or PR numbers that answer the question. Any of them counts as a hit.
- `"answerable": false` with no threads marks a question the repository cannot answer. The right reply is "insufficient evidence".
- The current set has 30 answerable questions across `pallets/itsdangerous`, `pallets-eco/blinker` and `pallets/markupsafe`, plus 5 unanswerable ones.

The labels are a first draft written from thread titles and extracted decisions. They need a human review: some threads that also answer a question are probably missing, which makes the scores look lower than they are. Questions were written after reading the titles, so they share some wording with them, which makes search look better than it would on real users' questions.

## Running

From `backend/`, with the database imported and `requirements-embeddings.txt` installed:

```bash
python -m app.evaluation.retrieval ../evaluation/datasets/questions.jsonl
python -m app.evaluation.retrieval ../evaluation/datasets/questions.jsonl --answers  # also needs Ollama
```

## Metrics

| Metric | Meaning |
| --- | --- |
| `hit@5` | Share of questions with an expected thread in the top 5 results |
| `hit@1` | Same, for the top result only |
| `mrr` | Mean reciprocal rank: 1 if the first result is right, 1/2 if the second is, and so on |
| `answered` | Share of answerable questions that got an answer |
| `citation_precision` | Share of an answer's citations that come from expected threads |
| `abstained` | Share of unanswerable questions that correctly got "insufficient evidence" |

## Results

Every run saved with `--save` is in `results/history.jsonl`. `questions` is the tuning set: changes may be tried against it. `heldout` (27 answerable and 3 unanswerable questions on threads mostly not in the tuning set, phrased without the threads' wording) is only used to report results, so improvements are not tuned to it.

| Date | Change | Set | hit@5 | hit@1 | MRR |
| --- | --- | --- | --- | --- | --- |
| 2026-11-17 | Baseline: vector search on raw comments | questions | 0.97 | 0.70 | 0.82 |
| 2026-11-17 | Baseline: vector search on raw comments | heldout | 0.96 | 0.63 | 0.76 |
| 2026-11-17 | Tried, not kept: fuse with PostgreSQL full-text search (RRF, k=60) | questions | 0.87 | 0.60 | 0.70 |

Full-text search made results worse, so it was not kept. Lowering its weight in the fusion did not recover the baseline, which suggests the vectors already find what keywords would: questions are full sentences, and OR-ing their words mostly adds noise. It may still help for exact identifier lookups, which these sets do not test.

## Improvements so far

| Change | Before | After |
| --- | --- | --- |
| Prompt example | The example decision "Use ruff for linting" was copied into 12 of 318 decisions on threads that never mention ruff | Placeholder example, and copies are dropped. Re-extracting one affected thread gave 3 real decisions and no copy. The 12 were removed with `backend/scripts/remove_copied_decisions.py` |
| Pull request matching | By file path only: a PR touching new files found nothing | Also by meaning: a thread's own decision ranks first for its title 82% of the time, with 1.1% unrelated matches at the 0.70 threshold |
| Long threads | Only the first ~9,000 characters were read, so the final comments, where decisions usually land, were lost | The opening post and the newest replies are kept. Not measured yet |
| Keyword search | Vector search, hit@5 0.97 | Tried hybrid search, hit@5 0.87, so it was not kept |

### Pull request matching threshold

`/pr-context` matches decisions by meaning when cosine similarity is at least 0.70. Measured on 55 PR and issue threads with decisions, comparing each thread's title with its own decisions (124) and with every other decision in the same repository (2,478):

| Threshold | Own decisions kept | Other decisions let through |
| --- | --- | --- |
| 0.70 | 47% | 1.1% |
| 0.75 | 38% | 0.3% |
| 0.80 | 32% | 0.1% |

Other decisions score below 0.62 nine times out of ten. A thread's own decision ranked first 82% of the time.

Answer metrics are not recorded yet: Gemma 3 4B was too slow on the 8 GB development machine to finish a run.
