# Atlas Agent architecture and design decisions

## Principle: one coherent product, minimal stack

The application keeps all normal flows in a small FastAPI backend (`app/main.py`), a single SQLite database, and a responsive dependency-free frontend (`web`). This intentionally avoids a React/npm pipeline and a separate vector database for an application whose core workload fits in local SQLite.

### Request and evidence flow

1. Documents are validated (extension, size, PDF page count, extracted length) and stored as text.
2. A question is matched to passages using conservative lexical rules, or optional local Ollama embeddings (`/api/embed`); embeddings are cached per document/part/model.
3. If no passage passes relevance rules, Atlas abstains before calling any LLM.
4. Otherwise, offline mode returns quoted source excerpts. Ollama/OpenAI mode asks the configured model to use **only** the provided sources.
5. Model responses must cite indices that exist in the evidence. Obvious unsupported numbers trigger a fallback to raw excerpts. **These guards cannot establish general semantic truthfulness**.
6. Messages and a snapshot of their sources are saved to SQLite; source cards allow inspection even when the document was deleted (the archived excerpt remains).

### Tool execution flow

- Only explicit `/calc EXPR` chat commands or the Action Center form can propose arithmetic.
- Expressions are parsed with an allowlisted AST (numbers, `+`, `-`, `*`, `/`, parentheses).
- The proposal is stored as `pending` before evaluation. No arbitrary shell, network, Python, file or SQL command is exposed to the assistant.
- Approval and rejection are separate endpoints; a SQLite transaction and status check prevent double decisions.
- The result and decision time are recorded for auditing.
- This is a *controlled tool-use demonstration*, **not** general autonomous agent functionality.

### SQLite data model

- `documents`: ID, title, content, kind, created timestamp.
- `conversations`: ID, first-question title, timestamps.
- `messages`: role, text, source JSON snapshot, answer mode, optional action ID.
- `actions`: proposed arithmetic expression, decision state, result and timestamps.
- `chunk_embeddings`: cached vector per document chunk/model; removed when source document is deleted.

Migrations are additive (`CREATE TABLE IF NOT EXISTS` and one `ALTER TABLE` for historical chat rows). The separate `scripts/migrate_db.py` tool copies an existing database using SQLite's backup API and verifies the destination.

### Trust boundary and failure handling

- All server operations run on loopback in the recommended native install; `TrustedHostMiddleware` and Origin checks defend against obvious browser cross-origin writes. They are **not** authentication.
- Document input is treated as untrusted context. The UI uses `textContent` to avoid injecting HTML; prompt-injection defenses are best-effort.
- Provider errors return API status codes and clear UI messages; old data remains in SQLite.
- OpenAI requires user-supplied API key and sends selected excerpts to the vendor. Local Ollama is restricted to local HTTP hosts.
- Sensitive data should not be uploaded. Production use needs account security, HTTPS, access control, rate limits, operational metrics and security review.

### Decision trade-offs

- **No automatic model download:** user control over hardware and disk costs.
- **No OCR:** avoids heavyweight native libraries; scanned PDFs receive a transparent error.
- **No streaming:** reduces code and request state complexity; answers are short.
- **No agent framework dependency:** prevents opaque tool access; one deterministic, auditable planner illustrates safe approval workflows.
- **No public hosting credentials:** matches honest portfolio scope.
