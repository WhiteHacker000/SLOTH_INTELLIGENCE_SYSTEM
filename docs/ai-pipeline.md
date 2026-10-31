# Planned AI pipeline

This document describes intended behavior; no model inference, embedding, retrieval, or answer generation is implemented yet.

1. **Ingest:** retrieve repository issues, pull requests, comments, and reviews from the GitHub REST API; preserve IDs, URLs, timestamps, and repository metadata.
2. **Normalize:** clean text without discarding authorship or source relationships, then chunk discussions with stable references.
3. **Extract decisions:** ask Gemma 3 4B through Ollama for structured candidates: decision, context, rationale, alternatives and rejection reasons, trade-offs, status, and evidence. Validate output with Pydantic. Do not assume a merge is an architectural decision.
4. **Embed:** use `BAAI/bge-small-en-v1.5` independently of the chat model and store 384-dimensional vectors in PostgreSQL/pgvector.
5. **Retrieve:** combine semantic similarity with repository and source metadata filters; retain the exact discussion/chunk relationship for citations.
6. **Answer:** retrieve evidence before generation; have Gemma produce a concise explanation with direct GitHub links. Return an explicit insufficient-evidence result when support is weak, and surface contradictory sources rather than hiding them.
7. **Evaluate:** build a small, reviewed dataset and measure retrieval relevance, citation correctness, decision extraction quality, and unsupported-claim rate before tuning.

## Model configuration

`GEMMA_MODEL` configures the Ollama chat model. `EMBEDDING_MODEL` configures embeddings separately. A configured model name does not mean Ollama has downloaded or served it; model acquisition and health checks are future implementation work.
