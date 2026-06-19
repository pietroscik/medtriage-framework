from sqlalchemy import inspect, text
from backend.database import engine
from backend.models import Base, Paziente, Richiesta, Medico, AuditLog

def _add_column_if_missing(conn, table_name: str, column_name: str, column_type_sql: str):
    inspector = inspect(conn)
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    if column_name in cols:
        print(f"- Colonna '{column_name}' già presente in '{table_name}'")
        return False

    dialect = conn.dialect.name
    if dialect == "sqlite":
        sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type_sql}'
    else:
        if dialect == "postgresql":
            sql = f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{column_name}" {column_type_sql}'
        else:
            sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type_sql}'

    print(f"- Aggiungo colonna '{column_name}' a '{table_name}' ({dialect}): {sql}")
    conn.execute(text(sql))
    return True

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Base.metadata.create_all eseguito")

    with engine.connect() as conn:
        # inizializza gli schemi master se non esistono
        Base.metadata.create_all(bind=engine)
        paziente_table = Paziente.__table__.name
        richiesta_table = Richiesta.__table__.name
        medici_table = Medico.__table__.name

        added = False
        added |= _add_column_if_missing(conn, paziente_table, "anamnesi", "TEXT")
        added |= _add_column_if_missing(conn, richiesta_table, "note", "TEXT")
        added |= _add_column_if_missing(conn, richiesta_table, "medico_id", "INTEGER")
        added |= _add_column_if_missing(conn, medici_table, "db_url", "VARCHAR(1024)")

        if added:
            print("Migration completata: nuove colonne aggiunte.")
        else:
            print("Nessuna modifica necessaria.")