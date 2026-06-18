from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict
from sqlalchemy.orm import Session
from .models import Paziente, StatoConversazione, Richiesta, TipoRichiesta, StatoRichiesta, ChiusuraStraordinaria, OrarioStudio
from .whatsapp_client import send_text_message

def is_studio_aperto(db: Session) -> bool:
    from .models import ChiusuraStraordinaria, OrarioStudio
    ora_attuale = datetime.utcnow()
    
    # 1. Controllo Ferie / Chiusure straordinarie
    in_chiusura = db.query(ChiusuraStraordinaria).filter(
        ChiusuraStraordinaria.data_inizio <= ora_attuale,
        ChiusuraStraordinaria.data_fine >= ora_attuale
    ).first()
    if in_chiusura:
        return False

    # 2. Controllo Orario Settimanale
    giorno_oggi = ora_attuale.weekday()
    if giorno_oggi > 4:
        return False # Sabato e Domenica sempre chiuso

    # SALVAGUARDIA PER IL TEST LOCALE: Se il medico non ha ancora configurato gli orari 
    # dalla dashboard, lasciamo lo studio APERTO per consentire l'esecuzione dei test dei webhook.
    if db.query(OrarioStudio).count() == 0:
        return True

    orario = db.query(OrarioStudio).filter_by(giorno_settimana=giorno_oggi).first()
    if not orario:
        return False

    ora_str = ora_attuale.strftime("%H:%M")
    return orario.ora_apertura <= ora_str <= orario.ora_chiusura

def process_incoming_message(db: Session, numero_telefono: str, message_payload: Dict[str, Any]) -> None:
    testo_paziente = message_payload.get("text", {}).get("body", "").strip()
    
    # Cerca se il paziente esiste nell'anagrafica dello studio
    paziente = db.query(Paziente).filter_by(numero_telefono=numero_telefono).first()
    stato_conv = db.query(StatoConversazione).filter_by(numero_telefono=numero_telefono).first()

    # Se lo stato non esiste, lo creiamo (START)
    if not stato_conv:
        stato_conv = StatoConversazione(numero_telefono=numero_telefono, stato_attuale="START")
        db.add(stato_conv)
        db.commit()

    # -------------------------------------------------------------------------
    # STATO: START -> Il bot accoglie il paziente
    # -------------------------------------------------------------------------
    if stato_conv.stato_attuale == "START":
        if not paziente:
            # Paziente sconosciuto: avviamo la registrazione
            send_text_message(numero_telefono, "Benvenuto nello studio medico. Non trovo il tuo numero in archivio. Per favore, digita il tuo NOME e COGNOME per registrarti:")
            stato_conv.stato_attuale = "REGISTRAZIONE_NOME"
        else:
            # Paziente riconosciuto: diamo il menu principale
            send_text_message(numero_telefono, f"Bentornato/a {paziente.nome_cognome}.\nCome posso aiutarti oggi?\n\nDigita:\n1️⃣ per Richiesta Ricette\n2️⃣ per un Consulto Medico")
            stato_conv.stato_attuale = "ATTESA_SCELTA"
        
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # -------------------------------------------------------------------------
    # STATO: REGISTRAZIONE_NOME (Per nuovi pazienti)
    # -------------------------------------------------------------------------
    if stato_conv.stato_attuale == "REGISTRAZIONE_NOME":
        stato_conv.dati_temporanei = testo_paziente # Salviamo temporaneamente il nome
        send_text_message(numero_telefono, "Grazie. Ora digita il tuo CODICE FISCALE per completare la scheda:")
        stato_conv.stato_attuale = "REGISTRAZIONE_CF"
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    if stato_conv.stato_attuale == "REGISTRAZIONE_CF":
        # Creiamo definitivamente il paziente nel DB
        nuovo_paziente = Paziente(
            numero_telefono=numero_telefono,
            nome_cognome=stato_conv.dati_temporanei,
            codice_fiscale=testo_paziente.upper()
        )
        db.add(nuovo_paziente)
        db.flush() # Otteniamo l'ID
        
        send_text_message(numero_telefono, f"Registrazione completata, {nuovo_paziente.nome_cognome}!\n\nCome posso aiutarti oggi?\nDigita:\n1️⃣ per Richiesta Ricette\n2️⃣ per un Consulto Medico")
        stato_conv.stato_attuale = "ATTESA_SCELTA"
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # -------------------------------------------------------------------------
    # STATO: ATTESA_SCELTA (Smistamento tra Ricetta e Consulto)
    # -------------------------------------------------------------------------
    if stato_conv.stato_attuale == "ATTESA_SCELTA":
        if "1" in testo_paziente:
            stato_conv.dati_temporanei = "RICETTA"
            send_text_message(numero_telefono, "Hai selezionato: Richiesta Ricette.\nScrivi qui sotto il NOME DEL FARMACO e il DOSAGGIO che ti serve:")
            stato_conv.stato_attuale = "ATTESA_DETTAGLI"
        elif "2" in testo_paziente:
            stato_conv.dati_temporanei = "CONSULTO"
            send_text_message(numero_telefono, "Hai selezionato: Consulto Medico.\nDescrivi brevemente i tuoi SINTOMI o il motivo della richiesta:")
            stato_conv.stato_attuale = "ATTESA_DETTAGLI"
        else:
            send_text_message(numero_telefono, "Scelta non valida. Digita 1 per Ricette o 2 per Consulto.")
        
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return

    # -------------------------------------------------------------------------
    # STATO: ATTESA_DETTAGLI -> Raccoglie il testo e crea la richiesta sulla Dash
    # -------------------------------------------------------------------------
    if stato_conv.stato_attuale == "ATTESA_DETTAGLI":
        tipo_richiesta = TipoRichiesta.RICETTA if stato_conv.dati_temporanei == "RICETTA" else TipoRichiesta.CONSULTO
        
        # Recuperiamo il paziente (ora esiste sicuramente)
        paziente_corrente = db.query(Paziente).filter_by(numero_telefono=numero_telefono).first()
        
        # Creiamo la richiesta nel database
        nuova_richiesta = Richiesta(
            paziente_id=paziente_corrente.id,
            tipo=tipo_richiesta,
            stato=StatoRichiesta.NUOVA,
            dettagli=testo_paziente
        )
        db.add(nuova_richiesta)
        
        # Inviamo messaggio di chiusura al paziente
        send_text_message(numero_telefono, "Perfetto! La tua richiesta è stata presa in carico ed è stata inviata sul PC della Dottoressa. Verrai notificato qui appena sarà pronta.")
        
        # Resettiamo il bot per la prossima volta
        stato_conv.stato_attuale = "START"
        stato_conv.dati_temporanei = None
        stato_conv.ultima_interazione = datetime.utcnow()
        db.commit()
        return