# Atlas Agent — Finalized product scope

**One complete release, one subsequent acceptance phase.** This document records the project decisions so maintenance stays focused rather than becoming an endless update cycle.

## Included in this release

- Responsive overview, Knowledge Base, AI Assistant, Action Center, System status.
- Text, Markdown and text-based PDF ingestion, preview, filtering and deletion.
- Conservative lexical retrieval, evidence-backed source citations, abstention behavior.
- Optional Ollama embeddings with SQLite cache, local LLM responses and optional OpenAI provider.
- Persistent conversations, source inspector, transcript export, deletion.
- Deterministic `/calc` tool proposals requiring human approve/reject, auditable results.
- Security headers and input validation within the explicit single-user local trust boundary.
- Database migration/backup, comprehensive README, CI, tests and screenshots.

## Intentionally excluded

- Public multi-user hosting, payments, social sign-in and multi-tenancy.
- Arbitrary autonomous tools or unrestricted code execution.
- OCR for scanned PDFs, streaming tokens and large-corpus production search.
- Enterprise compliance claims or broad LLM accuracy guarantees.

These exclusions make the portfolio claims accurate and keep the codebase small. Follow-up work should be **bug fixes or explicitly scoped features**, not arbitrary version increments. See `TEST_PLAN.md` for acceptance criteria.
