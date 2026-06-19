import os
import shutil
import sys
from datetime import datetime

# Aggiungi la root del progetto al path per importare i moduli backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from backend.database import DATABASE_URL

def backup_database():
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"medtriage_{timestamp}.db")
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backup del database creato con successo: {backup_path}")
    else:
        print("⚠️ Backup automatico non configurato per database non-SQLite.")
        # Per PostgreSQL, si potrebbe usare: os.system("pg_dump -U user -d dbname -f backups/medtriage_$(date +%Y%m%d).sql")

if __name__ == "__main__":
    backup_database()