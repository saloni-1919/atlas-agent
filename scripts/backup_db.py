"""Copy a consistent snapshot of the local Atlas database (server may be running)."""
from datetime import datetime
from pathlib import Path
import sqlite3
from contextlib import closing
from urllib.parse import quote
import os

root = Path(__file__).resolve().parents[1]
source = Path(os.getenv('ATLAS_DB', root / 'atlas.sqlite')).expanduser()
if not source.exists():
    raise SystemExit(f"No database at {source}. Open Atlas and add a document first.")
backup = root / 'backups' / f"atlas-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
backup.parent.mkdir(exist_ok=True)
with closing(sqlite3.connect(f'file:{quote(source.resolve().as_posix(), safe="/:")}?mode=ro', uri=True)) as old:
    with closing(sqlite3.connect(backup)) as output:
        old.backup(output)
print(f"Backup created: {backup}")
