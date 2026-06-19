from datetime import datetime
from typing import Any, Dict
from sqlalchemy.orm import Session
from .models import (
    Paziente, StatoConversazione, Richiesta,
    TipoRichiesta, StatoRichiesta, OrarioStudio, ChiusuraStraordinaria, Tag
)
from .whatsapp_client import send_text_message, send_template_blocking_message
from .notifications import notify_medico, notify_new_request
from .audit import record_audit
import logging
from pydantic import BaseModel, constr, validator, ValidationError
import re

logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?39?\d{9,12}$")  # adattare al formato desiderato

class PatientPayload(BaseModel):
    nome_cognome: constr(min_length=2)
    numero_telefono: constr(min_length=6)
    codice_fiscale: constr(min_length=11, max_length=16) | None
    dettagli: constr(min_length=1)

    @validator("numero_telefono")
    def check_phone(cls, v):
        if not PHONE_RE.match(v):
            raise ValueError("Numero di telefono non valido")
        return v

# --- Funzioni di supporto ---
def is_studio_aperto(db: Session) -> bool:
    """Controlla se lo studio è aperto (orari + chiusure straordinarie)."""
    ora_attuale = datetime.utcnow()

    # 1. Controllo chiusure straordinarie
    in_chiusura = db.query(ChiusuraStraordinaria).filter(
        ChiusuraStraordinaria.data_inizio <= ora_attuale,
        ChiusuraStraordinaria.data_fine >= ora_attuale
    ).first()
    if in_chiusura:
        return False

    # 2. Controllo giorno (Sabato/Domenica sempre chiuso)
    giorno_oggi = ora_attuale.weekday()  # 0=Lunedì, 6=Domenica
    if giorno_oggi > 4:  # Sabato (5) e Domenica (6)
        return False

    # Salvaguardia per test: se non ci sono orari, lasciamo aperto
    if db.query(OrarioStudio).count() == 0:
        return True

    orario = db.query(OrarioStudio).filter_by(giorno_settimana=giorno_oggi).first()
    if not orario:
        return False

    ora_str = ora_attuale.strftime("%H:%M")
    return orario.ora_apertura <= ora_str <= orario.ora_chiusura

def _get_or_create_tag(db: Session, nome: str) -> Tag:
    """Recupera o crea un tag."""
    tag = db.query(Tag).filter_by(nome=nome).first()
    if not tag:
        tag = Tag(nome=nome)
        db.add(tag)
        db.flush()
    return tag

# --- Flusso principale ---
def process_incoming_message(db: Session, numero_telefono: str, message_payload: Dict[str, Any]) -> None:
    """Processa un messaggio in entrata da WhatsApp."""
    testo_paziente = message_payload.get("text", {}).get("body", "").strip()

    # Recupera paziente e stato conversazione
    paziente = db.query(Paziente).filter_by(numero_telefono=numero_telefono).first()
    stato_conv = db.query(StatoConversazione).filter_by(numero_telefono=numero_telefono).first()

    # Crea stato se non esiste
    if not stato_conv:
        stato_conv = StatoConversazione(
            numero_telefono=numero_telefono,
            stato_attuale="START",
            dati_temporanei={},
            ultima_interazione=datetime.utcnow()
        )
        db.add(stato_conv)
        db.commit()

    # ========== STATO: START ==========
    if stato_conv.stato_attuale == "START":
        if not paziente:
            send_text_message(
                numero_telefono,
                "👋 Benvenuto nello studio medico! Non trovo il tuo numero in archivio. "
                "Per favore, digita il tuo **NOME e COGNOME** per registrarti:"
            )
            stato_conv.stato_attuale = "REGISTRAZIONE_NOME"
        else:
            send_text_message(
                numero_telefono,
                f"👋 Bentornato/a, {paziente.nome_cognome}!\n\n"
                "Come posso aiutarti oggi?\n\n"
                "🔢 Digita:\n"
                "1️⃣ per **Richiesta Ricette**\n"
                "2️⃣ per **Consulto Medico**\n"
                "3️⃣ per **Prenotare Appuntamento**\n"
                "4️⃣ per **Altro**"
            )
            stato_conv.stato_attuale = "ATTESA_SCELTA"

        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # ========== STATO: REGISTRAZIONE_NOME ==========
    if stato_conv.stato_attuale == "REGISTRAZIONE_NOME":
        stato_conv.dati_temporanei = {"nome_cognome": testo_paziente}
        send_text_message(
            numero_telefono,
            "✅ Grazie. Per continuare, è necessario accettare il **trattamento dei dati personali** "
            "secondo la normativa GDPR.\n\n"
            "Digita **'SI'** per accettare e procedere con la registrazione."
        )
        stato_conv.stato_attuale = "ATTESA_CONSENSO"
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # ========== STATO: ATTESA_CONSENSO ==========
    if stato_conv.stato_attuale == "ATTESA_CONSENSO":
        if "si" in testo_paziente.lower():
            send_text_message(
                numero_telefono,
                "✅ Consenso accettato! Ora digita il tuo **CODICE FISCALE** per completare la registrazione."
            )
            stato_conv.stato_attuale = "REGISTRAZIONE_CF"
        else:
            send_text_message(
                numero_telefono,
                "⚠️ Per utilizzare il servizio è **obbligatorio** fornire il consenso. "
                "Se cambi idea, digita **'ANNULLA'**."
            )
            stato_conv.stato_attuale = "START"
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # ========== STATO: REGISTRAZIONE_CF ==========
    if stato_conv.stato_attuale == "REGISTRAZIONE_CF":
        # Validazione CF (16 caratteri, formato corretto)
        if len(testo_paziente) != 16 or not testo_paziente.isalnum():
            send_text_message(
                numero_telefono,
                "❌ **Codice fiscale non valido**. Deve essere di 16 caratteri (es: RSSMRA85A01H501W)."
            )
            return

        # Crea paziente
        nuovo_paziente = Paziente(
            numero_telefono=numero_telefono,
            nome_cognome=stato_conv.dati_temporanei.get("nome_cognome"),
            codice_fiscale=testo_paziente.upper()
        )
        db.add(nuovo_paziente)
        db.flush()  # Per ottenere l'ID

        send_text_message(
            numero_telefono,
            f"✅ **Registrazione completata**, {nuovo_paziente.nome_cognome}!\n\n"
            "Come posso aiutarti oggi?\n\n"
            "🔢 Digita:\n"
            "1️⃣ per **Richiesta Ricette**\n"
            "2️⃣ per **Consulto Medico**\n"
            "3️⃣ per **Prenotare Appuntamento**\n"
            "4️⃣ per **Altro**"
        )
        stato_conv.stato_attuale = "ATTESA_SCELTA"
        stato_conv.dati_temporanei = {}
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # ========== STATO: ATTESA_SCELTA ==========
    if stato_conv.stato_attuale == "ATTESA_SCELTA":
        if "1" in testo_paziente:
            stato_conv.dati_temporanei = {"tipo": "RICETTA"}
            send_text_message(
                numero_telefono,
                "💊 Hai selezionato: **Richiesta Ricette**.\n\n"
                "Scrivi qui sotto il **NOME DEL FARMACO** e il **DOSAGGIO** che ti serve:\n"
                "Esempio: *Cardioaspirina 100mg - 1 confezione*"
            )
            stato_conv.stato_attuale = "ATTESA_DETTAGLI"
        elif "2" in testo_paziente:
            stato_conv.dati_temporanei = {"tipo": "CONSULTO"}
            send_text_message(
                numero_telefono,
                "🩺 Hai selezionato: **Consulto Medico**.\n\n"
                "Descrivi **brevemente** i tuoi sintomi o il motivo della richiesta:\n"
                "Esempio: *Ho mal di testa da 2 giorni e febbre*"
            )
            stato_conv.stato_attuale = "ATTESA_DETTAGLI"
        elif "3" in testo_paziente:
            stato_conv.dati_temporanei = {"tipo": "PRENOTAZIONE"}
            send_text_message(
                numero_telefono,
                "📅 Hai selezionato: **Prenotare Appuntamento**.\n\n"
                "Digita la **data preferita** (es: *15/07/2026*) e il **motivo** (es: *Visita di controllo*)."
            )
            stato_conv.stato_attuale = "ATTESA_PRENOTAZIONE"
        elif "4" in testo_paziente or "altro" in testo_paziente.lower():
            stato_conv.dati_temporanei = {"tipo": "ALTRO"}
            send_text_message(
                numero_telefono,
                "❓ Hai selezionato: **Altro**.\n\n"
                "Descrivi la tua richiesta:"
            )
            stato_conv.stato_attuale = "ATTESA_DETTAGLI"
        else:
            send_text_message(
                numero_telefono,
                "❌ **Scelta non valida**. Digita:\n"
                "1️⃣ per Ricette\n"
                "2️⃣ per Consulto\n"
                "3️⃣ per Prenotazione\n"
                "4️⃣ per Altro"
            )
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # ========== STATO: ATTESA_PRENOTAZIONE ==========
    if stato_conv.stato_attuale == "ATTESA_PRENOTAZIONE":
        # Estrai data e motivo (es: "15/07/2026 Visita di controllo")
        parti = testo_paziente.split()
        data_str = parti[0] if parti else ""
        motivo = " ".join(parti[1:]) if len(parti) > 1 else "Non specificato"

        # Crea richiesta
        paziente_corrente = db.query(Paziente).filter_by(numero_telefono=numero_telefono).first()
        nuova_richiesta = Richiesta(
            paziente_id=paziente_corrente.id,
            tipo=TipoRichiesta.CONSULTO,  # Prenotazioni = Consulto
            stato=StatoRichiesta.NUOVA,
            dettagli=f"Prenotazione per: {data_str} - Motivo: {motivo}",
            tags=[_get_or_create_tag(db, "PRENOTAZIONE")]
        )
        db.add(nuova_richiesta)
        db.flush()

        # Notifica medico
        notify_medico(nuova_richiesta)

        send_text_message(
            numero_telefono,
            "✅ **Prenotazione richiesta!** La tua richiesta è stata inviata al medico. "
            "Verrai contattato per confermare l'appuntamento."
        )
        stato_conv.stato_attuale = "START"
        stato_conv.dati_temporanei = {}
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # ========== STATO: ATTESA_DETTAGLI ==========
    if stato_conv.stato_attuale == "ATTESA_DETTAGLI":
        tipo_richiesta = TipoRichiesta.RICETTA if stato_conv.dati_temporanei.get("tipo") == "RICETTA" else TipoRichiesta.CONSULTO
        paziente_corrente = db.query(Paziente).filter_by(numero_telefono=numero_telefono).first()

        # Aggiungi tag automatico
        tags = []
        if "RICETTA" in stato_conv.dati_temporanei.get("tipo", ""):
            tags.append(_get_or_create_tag(db, "RICETTA"))
        else:
            tags.append(_get_or_create_tag(db, "CONSULTO"))

        # Crea richiesta
        nuova_richiesta = Richiesta(
            paziente_id=paziente_corrente.id,
            tipo=tipo_richiesta,
            stato=StatoRichiesta.NUOVA,
            dettagli=testo_paziente,
            tags=tags
        )
        db.add(nuova_richiesta)
        db.flush()  # Assicura che la richiesta abbia un ID

        # Notifica medico
        notify_medico(nuova_richiesta)

        send_text_message(
            numero_telefono,
            "✅ **Richiesta ricevuta!** La tua richiesta è stata presa in carico e inviata al medico. "
            "Verrai notificato qui non appena sarà pronta."
        )

        # Reset stato
        stato_conv.stato_attuale = "START"
        stato_conv.dati_temporanei = {}
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # Helper: crea Richiesta, commit e notifica medico + audit
    def create_richiesta(db, richiesta_data: dict, created_by: str = "system"):
        """
        Esempio helper: crea Richiesta, commit e notifica medico + audit
        """
        richiesta = Richiesta(
            paziente_id=richiesta_data.get("paziente_id"),
            dettagli=richiesta_data.get("dettagli"),
            tipo=richiesta_data.get("tipo"),
            stato=richiesta_data.get("stato") or StatoRichiesta.NUOVA,
            data_creazione=datetime.utcnow(),
            # medico_id può essere passato in richiesta_data
            medico_id=richiesta_data.get("medico_id")
        )
        db.add(richiesta)
        db.commit()
        db.refresh(richiesta)

        # record audit
        try:
            record_audit("Richiesta", richiesta.id, "create", created_by, details=str(richiesta_data))
        except Exception:
            pass

        # notifiche (telegram)
        try:
            notify_new_request(richiesta)
        except Exception:
            pass

        return richiesta

def create_richiesta_for_medico(medico_id: int, richiesta_data: dict):
    db = get_tenant_session_for_medico(medico_id)
    try:
        richiesta = Richiesta(
            paziente_id=richiesta_data.get("paziente_id"),
            dettagli=richiesta_data.get("dettagli"),
            tipo=richiesta_data.get("tipo"),
            stato=richiesta_data.get("stato") or StatoRichiesta.NUOVA,
            data_creazione=datetime.utcnow(),
            medico_id=medico_id,
        )
        db.add(richiesta)
        db.commit()
        db.refresh(richiesta)
        return richiesta
    finally:
        db.close()


def fetch_richieste_for_medico(medico_id: int, stato: str | None = None):
    db = get_tenant_session_for_medico(medico_id)
    try:
        query = db.query(Richiesta).order_by(Richiesta.data_creazione.desc())
        if stato:
            query = query.filter(Richiesta.stato == stato)
        return query.all()
    finally:
        db.close()