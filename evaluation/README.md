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

| Date | Change | hit@5 | hit@1 | MRR |
| --- | --- | --- | --- | --- |
| 2026-11-17 | Baseline: exact cosine search, `bge-small-en-v1.5` | 0.97 | 0.70 | 0.82 |

Answer metrics are not recorded yet: Gemma 3 4B was too slow on the 8 GB development machine to finish a run.
