"""Safe one-time migration of an Atlas SQLite database into a fresh release."""
import argparse
import sqlite3
from contextlib import closing
from urllib.parse import quote
from datetime import datetime
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "atlas.sqlite"


def migrate(source: Path, destination: Path = TARGET, replace: bool = False) -> Path:
    source, destination = source.expanduser().resolve(), destination.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Source database does not exist: {source}")
    if source == destination:
        raise ValueError("Source and destination must be different files.")
    if destination.exists() and not replace:
        raise ValueError(f"Destination already exists: {destination}. Use --replace only if intentional.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".migrating")
    temporary.unlink(missing_ok=True)
    with closing(sqlite3.connect(f"file:{quote(source.as_posix(), safe='/:')}?mode=ro", uri=True)) as old:
        tables = {row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"documents", "actions"}.issubset(tables):
            raise ValueError("This doesn't look like an Atlas Agent database (required tables missing).")
        with closing(sqlite3.connect(temporary)) as new:
            old.backup(new)
            status = new.execute("PRAGMA integrity_check").fetchone()[0]
            if status != "ok":
                raise ValueError("SQLite integrity verification failed")
    if destination.exists():
        backup = destination.with_name(destination.name + ".backup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        destination.replace(backup)
        print(f"Saved existing destination backup: {backup}")
    temporary.replace(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="source", type=Path, required=True, help="Path to existing atlas.sqlite")
    parser.add_argument("--to", dest="destination", type=Path, default=TARGET, help="New project atlas.sqlite path")
    parser.add_argument("--replace", action="store_true", help="Back up and replace an existing destination")
    arguments = parser.parse_args()
    try:
        result = migrate(arguments.source, arguments.destination, arguments.replace)
        print(f"Migration complete: {result}")
        print("Your source database is unchanged. Start Atlas to apply additive schema updates.")
    except (ValueError, sqlite3.DatabaseError, OSError) as exc:
        parser.exit(1, f"Migration stopped safely: {exc}\n")
