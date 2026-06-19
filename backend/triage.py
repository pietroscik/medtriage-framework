from sqlalchemy.orm import Session
from backend.models import Paziente, Richiesta, Triage
from backend.whatsapp_client import WhatsAppClient

def triage_richiesta(db: Session, richiesta_id: int, whatsapp_client: WhatsAppClient) -> None:
    richiesta = db.query(Richiesta).filter(Richiesta.id == richiesta_id).first()
    if not richiesta:
        return
    
    # Logique de triage
    paziente = db.query(Paziente).filter(Paziente.id == richiesta.paziente_id).first()
    if paziente:
        whatsapp_client.send_message(paziente.numero_telefono, "Votre demande a été traitée")
    
    db.commit()