from datetime import datetime
from backend.database import SessionLocal
from backend.models import AuditLog

def record_audit(entity: str, entity_id: int, action: str, changed_by: str, details: str | None = None):
    db = SessionLocal()
    try:
        db.add(
            AuditLog(
                entity=entity,
                entity_id=entity_id,
                action=action,
                changed_by=changed_by,
                details=details,
                timestamp=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()