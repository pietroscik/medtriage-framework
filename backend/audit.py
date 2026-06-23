from backend.database import SessionLocal
from backend.models import AuditLog
from backend.time_utils import utc_now_naive

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
                timestamp=utc_now_naive(),
            )
        )
        db.commit()
    finally:
        db.close()
