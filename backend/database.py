from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import threading

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./medtriage.db")

Base = declarative_base()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_tenant_engines: dict[str, object] = {}
_tenant_lock = threading.Lock()


def get_tenant_session_for_medico(medico_id: int):
    from backend.models import Medico

    master_db = SessionLocal()
    try:
        medico = master_db.query(Medico).filter(Medico.id == medico_id).first()
        if not medico or not medico.db_url:
            raise RuntimeError("Medico non trovato o db_url non configurato")
        tenant_url = medico.db_url
    finally:
        master_db.close()

    with _tenant_lock:
        tenant_engine = _tenant_engines.get(tenant_url)
        if tenant_engine is None:
            connect_args = {"check_same_thread": False} if tenant_url.startswith("sqlite") else {}
            tenant_engine = create_engine(tenant_url, connect_args=connect_args)
            _tenant_engines[tenant_url] = tenant_engine

    TenantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
    return TenantSessionLocal()