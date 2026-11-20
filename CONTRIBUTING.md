# Contributing to Atlas Agent

Thanks for improving Atlas. This project is intentionally kept small and comprehensible. Favor focused changes, standard-library code, and measurable improvements over additional dependencies.

1. Create a branch (`feat/…` or `fix/…`).
2. Open an issue with steps to reproduce bugs.
3. Add tests for changes to retrieval, approvals, data migrations, and security controls.
4. Run `python -m pytest -q` and `node --check web/app.js`.
5. Describe UI behavior and screenshots in pull requests.

**Security:** Do not submit real employee documents, credentials, or local SQLite databases. Do not claim the app is secure for public deployment. See `SECURITY.md`.

**Coding style:** Clear names, small functions, parameterized queries, predictable errors, and accessible UI. Keep the architecture lean; not every new feature needs a framework.
