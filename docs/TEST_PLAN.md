# Final acceptance test plan (run *after* installing the unified release)

This checklist is intentionally a **single test phase**. It replaces the earlier incremental test-and-patch cycle.

## Automated checks

Run in the new project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m py_compile app/main.py
```

The CI additionally checks JavaScript syntax with Node. A prepackaging browser smoke test covers the main workflows, but **real local Windows/Ollama testing remains pending**.

## Manual browser acceptance

- [ ] App starts at `http://127.0.0.1:8001` without missing CSS or JS.
- [ ] Overview counts match the imported documents and pending actions.
- [ ] Knowledge Base can add a pasted document, upload `.txt`/`.md`, and upload a text-based `.pdf`.
- [ ] Document filtering, previewing and deleting behave correctly.
- [ ] Asking about remote work returns *three days per week*, with an inspectable source.
- [ ] Asking about an undocumented bonus percentage abstains.
- [ ] A new conversation persists across refresh and can be reopened, deleted and exported.
- [ ] Asking `/calc (12+8)*2` creates **pending** action without executing it.
- [ ] Approving gives `40`; rejecting a different proposal never executes it.
- [ ] All four main pages plus System status look good at desktop and phone widths.
- [ ] Browser developer console shows no JavaScript exceptions.
- [ ] System status accurately reports default mode, and, if configured, Ollama connection readiness.
- [ ] Optional Ollama: actual generated answer cites a document; semantic search handles a reasonable paraphrase.
- [ ] Current `atlas.sqlite` preserved rows from previous Atlas installation.
- [ ] `scripts/backup_db.py` creates a backup that can be opened with SQLite.

## Known limits / no deceptive claims

- A passing test suite is **not** proof that every possible question is answered correctly. Semantic retrieval requires a running local embedding model.
- Browser screenshots were captured with a local in-process API adapter, not a network-hosted public deployment.
- The initial review should use synthetic documents, not real company or personal records.

## Definition of ready for public GitHub

- [ ] All automated tests pass on Saloni's PC.
- [ ] All acceptance steps above pass, or any unsupported optional steps are clearly documented.
- [ ] Live screenshots replace any outdated ones.
- [ ] Real GitHub repository URL and live demo links added once published (do not invent URLs).
- [ ] Local databases, backups, secrets and `.venv` are not tracked (`git status`).
- [ ] Description truthfully states single-user localhost scope; no fake metrics.
