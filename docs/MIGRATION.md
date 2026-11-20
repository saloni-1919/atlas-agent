# One-time migration: preserve documents and conversations

**Reason:** This release is a clean installation. You should not keep overwriting source files inside a working project.

1. Stop the old Atlas server with `Ctrl+C`.
2. In the *old* project folder, find `atlas.sqlite`. It is usually next to `requirements.txt`.
3. Extract the release archive into a **new folder**; do not replace the existing folder.
4. In the new project root, create a Python virtual environment and install requirements as described in `README.md`.
5. Before starting the new app, run the migration tool:
   ```powershell
   .\.venv\Scripts\python.exe scripts\migrate_db.py --from "C:\Users\ASUS\OneDrive\Desktop\Saloni Profile building projects\atlas-agent-recreated-saloni\atlas-agent\atlas.sqlite"
   ```
   This is a **worked example**, not guaranteed to be your exact path. Use the real file location.
6. The tool checks that the source exists and contains Atlas tables, creates a consistent snapshot using SQLite's backup API, and verifies the new database. It never modifies the source.
7. Start the new release. Any missing additive schema columns/tables are created at startup. Existing documents, actions, chats and evidence snapshots are preserved.

### If it says the destination already exists

The safe default is to stop rather than overwrite data. If that new database contains important data, back it up first. To intentionally replace it, add `--replace`: it first moves the existing destination to a timestamped `.backup-*` file. Never run this without understanding which database you're replacing.

### Privacy and Git

Do not upload `atlas.sqlite`, `.sqlite.backup-*` or screenshots of private documents to GitHub. These are ignored by `.gitignore` but check `git status` before every push.
