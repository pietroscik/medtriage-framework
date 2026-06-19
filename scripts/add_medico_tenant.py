import argparse
from pathlib import Path

from sqlalchemy import create_engine

from backend.database import SessionLocal, engine
from backend.models import Base, Medico


def create_master_schema():
    Base.metadata.create_all(bind=engine)


def create_sqlite_tenant_db(db_file: Path) -> str:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return db_url


def register_medico(nome: str, email: str | None, telefono: str | None, db_url: str) -> Medico:
    db = SessionLocal()
    try:
        medico = Medico(nome=nome, email=email, telefono=telefono, db_url=db_url)
        db.add(medico)
        db.commit()
        db.refresh(medico)
        return medico
    finally:
        db.close()


if __name__ == "__main__":
    create_master_schema()
    parser = argparse.ArgumentParser(description="Crea un medico e un tenant DB dedicato")
    parser.add_argument("--nome", required=True, help="Nome del medico")
    parser.add_argument("--email", default=None, help="Email del medico")
    parser.add_argument("--telefono", default=None, help="Telefono del medico")
    parser.add_argument("--db-file", required=True, help="Percorso file SQLite tenant, es. ./data/tenant_medico_1.db")
    args = parser.parse_args()

    db_file = Path(args.db_file)
    db_url = create_sqlite_tenant_db(db_file)
    medico = register_medico(args.nome, args.email, args.telefono, db_url)

    print(f"Medico creato: id={medico.id}, nome={medico.nome}, db_url={medico.db_url}")