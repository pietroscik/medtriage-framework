import os
from datetime import datetime, timedelta
from typing import Any, Dict
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Query, Request, Response, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging

from .database import Base, engine, get_db
from .models import StatoConversazione, Paziente
from .triage import is_studio_aperto, process_incoming_message
from .whatsapp_client import send_template_blocking_message

# Configura logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="MedTriage Framework Backend")

# CORS (per dashboard e frontend esterni)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify_token_default")

@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Backend avviato!")

def _find_or_create_conversation(db: Session, numero_telefono: str) -> StatoConversazione:
    """Recupera o crea una conversazione per un numero di telefono."""
    stato = db.query(StatoConversazione).filter_by(numero_telefono=numero_telefono).first()
    if not stato:
        stato = StatoConversazione(
            numero_telefono=numero_telefono,
            stato_attuale="START",
            dati_temporanei={},
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
    """Verifica il webhook per Meta."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("✅ Webhook verificato con Meta")
        return Response(content=hub_challenge or "", media_type="text/plain")
    logger.warning("⚠️ Tentativo di verifica webhook fallito")
    return Response(status_code=status.HTTP_403_FORBIDDEN, content="Forbidden")

@app.post("/webhook")
async def webhook_payload(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Elabora i messaggi in entrata da WhatsApp."""
    payload = await request.json()
    logger.info(f"📥 Ricevuto payload da WhatsApp: {len(payload.get('entry', []))} entries")

    entries = payload.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})

            # Gestione message_echoes (messaggi inviati dal bot)
            if value.get("message_echoes"):
                to_phone = value.get("metadata", {}).get("display_phone_number", "")
                if to_phone:
                    stato = _find_or_create_conversation(db, to_phone)
                    stato.stato_attuale = "MANUALE"
                    stato.ultima_interazione = datetime.utcnow()
                    db.add(stato)
                    db.commit()
                    logger.info(f"🔄 Messaggio echo da {to_phone} → stato MANUALE")
                continue

            # Gestione messaggi in entrata
            messages = value.get("messages", [])
            for message in messages:
                telefono = message.get("from")
                if not telefono:
                    continue

                # Controlla timeout globale (24h)
                stato = _find_or_create_conversation(db, telefono)
                if stato.ultima_interazione < datetime.utcnow() - timedelta(hours=24):
                    stato.stato_attuale = "START"
                    stato.dati_temporanei = {}
                    db.commit()
                    logger.info(f"⏳ Reset stato per {telefono} (timeout 24h)")

                # Controlla se lo studio è aperto
                if not is_studio_aperto(db):
                    send_template_blocking_message(telefono, template_name="studio_chiuso")
                    logger.info(f"🚪 Studio chiuso → messaggio a {telefono}")
                    continue

                # Processa il messaggio
                process_incoming_message(db, telefono, message)
                logger.info(f"📝 Messaggio processato da {telefono}")

    return {"success": True, "messages_processed": len(messages)}

@app.post("/gdpr/delete/{paziente_id}")
def gdpr_delete(paziente_id: int, db: Session = Depends(get_db)):
    """Cancella un paziente e i suoi dati (GDPR)."""
    paziente = db.query(Paziente).filter(Paziente.id == paziente_id).first()
    if not paziente:
        logger.warning(f"❌ Tentativo di cancellazione paziente inesistente (ID: {paziente_id})")
        raise HTTPException(status_code=404, detail="Paziente non trovato")

    nome = paziente.nome_cognome
    db.delete(paziente)
    db.commit()
    logger.info(f"🗑️ Paziente cancellato: {nome} (ID: {paziente_id})")
    return {"status": "deleted", "paziente": nome}

@app.get("/health")
def health_check():
    """Endpoint per monitoraggio."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}