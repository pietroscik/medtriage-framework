from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from .models import (
    Paziente, StatoConversazione, Richiesta,
    TipoRichiesta, StatoRichiesta, OrarioStudio, ChiusuraStraordinaria, Tag
)
from .database import get_tenant_session_for_medico
from .whatsapp_client import send_text_message
from .notifications import notify_medico, notify_new_request
from .audit import record_audit
from .time_utils import utc_now_naive
import logging
from pydantic import BaseModel, constr, validator
import re

logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?39?\d{9,12}$")  # adattare al formato desiderato
ROME_TZ = ZoneInfo("Europe/Rome")


def _now_rome_naive() -> datetime:
    return datetime.now(ROME_TZ).replace(tzinfo=None)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _is_affirmative(value: str) -> bool:
    return _normalize_text(value) in {"si", "sì", "s"}


def _matches_choice(value: str, choice: str) -> bool:
    normalized = _normalize_text(value)
    return bool(re.match(rf"^{re.escape(choice)}(?=\D|$)", normalized))

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
    ora_attuale = _now_rome_naive()

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
            ultima_interazione=utc_now_naive()
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

        stato_conv.ultima_interazione = utc_now_naive()
        db.commit()
        return

    # ========== STATO: REGISTRAZIONE_NOME ==========
    if stato_conv.stato_attuale == "REGISTRAZIONE_NOME":
        if not testo_paziente:
            send_text_message(
                numero_telefono,
                "⚠️ Per registrarti, scrivi il tuo **NOME e COGNOME** in un messaggio di testo."
            )
            return
        stato_conv.dati_temporanei = {"nome_cognome": testo_paziente}
        send_text_message(
            numero_telefono,
            "✅ Grazie. Per continuare, è necessario accettare il **trattamento dei dati personali** "
            "secondo la normativa GDPR.\n\n"
            "Digita **'SI'** per accettare e procedere con la registrazione."
        )
        stato_conv.stato_attuale = "ATTESA_CONSENSO"
        stato_conv.ultima_interazione = utc_now_naive()
        db.commit()
        return

    # ========== STATO: ATTESA_CONSENSO ==========
    if stato_conv.stato_attuale == "ATTESA_CONSENSO":
        if not testo_paziente:
            send_text_message(
                numero_telefono,
                "⚠️ Rispondi con **SI** per proseguire con la registrazione, oppure **ANNULLA** per interrompere."
            )
            return
        if _is_affirmative(testo_paziente):
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
        stato_conv.ultima_interazione = utc_now_naive()
        db.commit()
        return

    # ========== STATO: REGISTRAZIONE_CF ==========
    if stato_conv.stato_attuale == "REGISTRAZIONE_CF":
        if not testo_paziente:
            send_text_message(
                numero_telefono,
                "⚠️ Invia il tuo **CODICE FISCALE** in un messaggio di testo per completare la registrazione."
            )
            return
        # Validazione CF (16 caratteri, formato corretto)
        if len(testo_paziente) != 16 or not testo_paziente.isalnum():
            send_text_message(
                numero_telefono,
                "❌ **Codice fiscale non valido**. Deve essere di 16 caratteri (es: RSSMRA85A01H501W)."
            )
            return

        cf_normalizzato = testo_paziente.upper()
        if db.query(Paziente).filter_by(numero_telefono=numero_telefono).first():
            send_text_message(
                numero_telefono,
                "⚠️ Il tuo numero risulta già registrato. Se hai bisogno di assistenza, invia direttamente la tua richiesta."
            )
            stato_conv.stato_attuale = "ATTESA_SCELTA"
            stato_conv.ultima_interazione = utc_now_naive()
            db.commit()
            return

        if db.query(Paziente).filter_by(codice_fiscale=cf_normalizzato).first():
            send_text_message(
                numero_telefono,
                "⚠️ Questo codice fiscale risulta già registrato. Contatta lo studio per verificare i dati anagrafici."
            )
            stato_conv.stato_attuale = "START"
            stato_conv.dati_temporanei = {}
            stato_conv.ultima_interazione = utc_now_naive()
            db.commit()
            return

        # Crea paziente
        nuovo_paziente = Paziente(
            numero_telefono=numero_telefono,
            nome_cognome=stato_conv.dati_temporanei.get("nome_cognome"),
            codice_fiscale=cf_normalizzato
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
        stato_conv.ultima_interazione = utc_now_naive()
        db.commit()
        return

    # ========== STATO: ATTESA_SCELTA ==========
    if stato_conv.stato_attuale == "ATTESA_SCELTA":
        if _matches_choice(testo_paziente, "1"):
            stato_conv.dati_temporanei = {"tipo": "RICETTA"}
            send_text_message(
                numero_telefono,
                "💊 Hai selezionato: **Richiesta Ricette**.\n\n"
                "Scrivi qui sotto il **NOME DEL FARMACO** e il **DOSAGGIO** che ti serve:\n"
                "Esempio: *Cardioaspirina 100mg - 1 confezione*"
            )
            stato_conv.stato_attuale = "ATTESA_DETTAGLI"
        elif _matches_choice(testo_paziente, "2"):
            stato_conv.dati_temporanei = {"tipo": "CONSULTO"}
            send_text_message(
                numero_telefono,
                "🩺 Hai selezionato: **Consulto Medico**.\n\n"
                "Descrivi **brevemente** i tuoi sintomi o il motivo della richiesta:\n"
                "Esempio: *Ho mal di testa da 2 giorni e febbre*"
            )
            stato_conv.stato_attuale = "ATTESA_DETTAGLI"
        elif _matches_choice(testo_paziente, "3"):
            stato_conv.dati_temporanei = {"tipo": "PRENOTAZIONE"}
            send_text_message(
                numero_telefono,
                "📅 Hai selezionato: **Prenotare Appuntamento**.\n\n"
                "Digita la **data preferita** (es: *15/07/2026*) e il **motivo** (es: *Visita di controllo*)."
            )
            stato_conv.stato_attuale = "ATTESA_PRENOTAZIONE"
        elif _matches_choice(testo_paziente, "4") or "altro" in _normalize_text(testo_paziente):
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
        stato_conv.ultima_interazione = utc_now_naive()
        db.commit()
        return

    # ========== STATO: ATTESA_PRENOTAZIONE ==========
    if stato_conv.stato_attuale == "ATTESA_PRENOTAZIONE":
        if not testo_paziente:
            send_text_message(
                numero_telefono,
                "⚠️ Scrivi la **data preferita** e il **motivo** dell'appuntamento in un messaggio di testo."
            )
            return
        # Estrai data e motivo (es: "15/07/2026 Visita di controllo")
        parti = testo_paziente.split()
        data_str = parti[0] if parti else ""
        motivo = " ".join(parti[1:]) if len(parti) > 1 else "Non specificato"

        paziente_corrente = db.query(Paziente).filter_by(numero_telefono=numero_telefono).first()
        if not paziente_corrente:
            send_text_message(
                numero_telefono,
                "⚠️ Non trovo il tuo profilo registrato. Scrivi un messaggio qualsiasi per ripartire dalla registrazione."
            )
            stato_conv.stato_attuale = "START"
            stato_conv.dati_temporanei = {}
            stato_conv.ultima_interazione = utc_now_naive()
            db.commit()
            return

        # Crea richiesta
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
        stato_conv.ultima_interazione = utc_now_naive()
        db.commit()
        return

    # ========== STATO: ATTESA_DETTAGLI ==========
    if stato_conv.stato_attuale == "ATTESA_DETTAGLI":
        if not testo_paziente:
            send_text_message(
                numero_telefono,
                "⚠️ Scrivi i dettagli della tua richiesta in un messaggio di testo."
            )
            return
        tipo_richiesta = TipoRichiesta.RICETTA if stato_conv.dati_temporanei.get("tipo") == "RICETTA" else TipoRichiesta.CONSULTO
        paziente_corrente = db.query(Paziente).filter_by(numero_telefono=numero_telefono).first()

        if not paziente_corrente:
            send_text_message(
                numero_telefono,
                "⚠️ Non trovo il tuo profilo registrato. Scrivi un messaggio qualsiasi per ripartire dalla registrazione."
            )
            stato_conv.stato_attuale = "START"
            stato_conv.dati_temporanei = {}
            stato_conv.ultima_interazione = utc_now_naive()
            db.commit()
            return

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
        stato_conv.ultima_interazione = utc_now_naive()
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
            data_creazione=utc_now_naive(),
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
            data_creazione=utc_now_naive(),
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
            stato_enum = StatoRichiesta(stato) if isinstance(stato, str) else stato
            query = query.filter(Richiesta.stato == stato_enum)
        return query.all()
    finally:
        db.close()
