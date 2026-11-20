# Security model

Atlas is **not a multi-user or public-hosted application**. It is designed to be started on `127.0.0.1`, and anybody with access to that local session or database may view stored data. There is no login system, encryption-at-rest, per-user isolation, or production access control.

Included safeguards:
- Loopback host guidance, TrustedHost host allowlist and cross-origin write rejection.
- Restrictive CSP, anti-embedding and nosniff headers.
- Input and document size validation, only supported file extensions, PDF page limit.
- SQL parameters, plain-text DOM rendering instead of HTML interpolation.
- Arithmetic using AST allowlisting; proposed calculations require explicit approval.
- Optional Ollama URL restricted to a local HTTP host.
- Local persistence; `.gitignore` excludes database and `.env`.

**Limitations:** API callers on the same machine can still call the unauthenticated endpoints. Prompt injection remains a risk for LLM output; document text is untrusted reference material. Semantic similarity alone does not verify answerability. Numeric and citation checks catch some failures but not all. Never upload confidential data for a demo. OpenAI mode sends selected document excerpts to that provider. Local Ollama models require separate installation.

For a public deployment, add real authentication/authorization, TLS termination, CSRF strategy, rate limiting, stricter data retention, structured logging, secrets management, tests, and threat modeling before exposure.
