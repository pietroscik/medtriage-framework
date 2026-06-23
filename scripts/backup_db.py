import os
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from backend.time_utils import utc_now_naive

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./medtriage.db")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def backup_sqlite(url: str) -> Path:
    if url.startswith("sqlite:///"):
        source = Path(url.replace("sqlite:///", ""))
    elif url.startswith("sqlite://"):
        source = Path(url.replace("sqlite://", ""))
    else:
        raise ValueError("URL SQLite non valido")
    if not source.exists():
        raise FileNotFoundError(f"DB SQLite non trovato: {source}")
    target = BACKUP_DIR / f"medtriage_sqlite_{utc_now_naive():%Y%m%d_%H%M%S}.db"
    shutil.copy2(source, target)
    return target

def backup_postgres(url: str) -> Path:
    filename = BACKUP_DIR / f"medtriage_postgres_{utc_now_naive():%Y%m%d_%H%M%S}.sql"
    subprocess.run(
        ["pg_dump", "--file", str(filename), url],
        check=True,
    )
    return filename

if __name__ == "__main__":
    if DATABASE_URL.startswith("sqlite"):
        out = backup_sqlite(DATABASE_URL)
    elif DATABASE_URL.startswith("postgresql"):
        out = backup_postgres(DATABASE_URL)
    else:
        raise RuntimeError(f"Database non supportato per backup: {DATABASE_URL}")
    print(f"Backup creato in: {out}")
