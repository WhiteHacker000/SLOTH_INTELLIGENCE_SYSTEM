# AI pipeline

Steps 1, 2 and 4 are implemented. Decision extraction, retrieval, answers and evaluation are planned.

1. **Ingest:** retrieve repository issues, pull requests, comments, and reviews from the GitHub REST API; preserve IDs, URLs, timestamps, and repository metadata.
2. **Normalize:** clean text without discarding authorship or source relationships, then chunk discussions with stable references.
3. **Extract decisions:** ask Gemma 3 4B through Ollama for structured candidates: decision, context, rationale, alternatives and rejection reasons, trade-offs, status, and evidence. Validate output with Pydantic. Do not assume a merge is an architectural decision.
4. **Embed:** use `BAAI/bge-small-en-v1.5` independently of the chat model and store 384-dimensional vectors in PostgreSQL/pgvector. After each sync, new and edited chunks are embedded in batches of 64. Search queries get the bge query prefix; documents do not.
5. **Retrieve:** combine semantic similarity with repository and source metadata filters; retain the exact discussion/chunk relationship for citations.
6. **Answer:** retrieve evidence before generation; have Gemma produce a concise explanation with direct GitHub links. Return an explicit insufficient-evidence result when support is weak, and surface contradictory sources rather than hiding them.
7. **Evaluate:** build a small, reviewed dataset and measure retrieval relevance, citation correctness, decision extraction quality, and unsupported-claim rate before tuning.

## Model configuration

`GEMMA_MODEL` configures the Ollama chat model. `EMBEDDING_MODEL` configures embeddings separately.

Set up Gemma with `ollama pull gemma3:4b` (about 3.4 GB). It uses about 3.5 GB of memory while loaded.

`backend/app/generation/llm.py` talks to Ollama:

- Every request sends a JSON schema built from a Pydantic model, so Gemma must answer in that shape. Output is validated again with Pydantic.
- Temperature is 0, so the same input gives the same output.
- Bad output (not JSON, or wrong fields) is retried once. A missing model or a stopped Ollama fails at once with a message saying how to fix it.
- Measured locally: about 20 s for the first call while the model loads, then about 1 s for a short prompt.
- Ollama's default context is 4096 tokens, so long threads must be trimmed before they are sent.

## Embedding setup

The embedding model needs PyTorch, which is large, so it has its own requirements file:

```bash
cd backend
python -m pip install -r requirements-embeddings.txt
```

The model (about 130 MB) downloads from Hugging Face on first use. No account or token is needed. Without this file installed, syncs still work and log that embeddings were skipped. Tests and CI use a fake embedder.
