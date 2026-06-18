import os
from datetime import datetime, timedelta
from typing import Any, Dict
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Query, Request, Response, status
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import StatoConversazione
from .triage import is_studio_aperto, process_incoming_message
from .whatsapp_client import send_template_blocking_message

load_dotenv()

app = FastAPI(title="MedTriage Framework Backend")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify_token_default")

@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)

def _find_or_create_conversation(db: Session, numero_telefono: str) -> StatoConversazione:
    stato = db.query(StatoConversazione).filter_by(numero_telefono=numero_telefono).first()
    if not stato:
        stato = StatoConversazione(
            numero_telefono=numero_telefono,
            stato_attuale="START",
            ultima_interazione=datetime.utcnow(),
        )
        db.add(stato)
        db.commit()
        db.refresh(stato)
    return stato

@app.get("/webhook")
def webhook_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge or "", media_type="text/plain")
    return Response(status_code=status.HTTP_403_FORBIDDEN, content="Forbidden")

@app.post("/webhook")
async def webhook_payload(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    payload = await request.json()
    entries = payload.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})

            if value.get("message_echoes"):
                to_phone = value.get("metadata", {}).get("display_phone_number", "")
                if to_phone:
                    stato = _find_or_create_conversation(db, to_phone)
                    stato.stato_attuale = "MANUALE"
                    stato.ultima_interazione = datetime.utcnow()
                    db.add(stato)
                    db.commit()
                continue

            messages = value.get("messages", [])
            for message in messages:
                telefono = message.get("from")
                if not telefono:
                    continue

                stato = _find_or_create_conversation(db, telefono)
                if stato.stato_attuale == "MANUALE":
                    ora_limite = stato.ultima_interazione + timedelta(hours=12)
                    if datetime.utcnow() < ora_limite:
                        continue

                if not is_studio_aperto(db):
                    send_template_blocking_message(telefono, template_name="studio_chiuso")
                    continue

                process_incoming_message(db, telefono, message)

    return {"success": True}