import os
import sys
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from streamlit_autorefresh import st_autorefresh # Aggiungi questo import in cima al file

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend import models  # noqa: E402
from backend.database import DATABASE_URL  # noqa: E402

load_dotenv()

st.set_page_config(page_title="MedTriage Dashboard", layout="wide")
PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")

ENGINE = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)

def authenticate() -> bool:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated:
        return True

    st.title("MedTriage Framework")
    password_input = st.text_input("Password", type="password")
    if st.button("Accedi"):
        if password_input == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Password errata")
    return False

def get_db_session() -> Session:
    return SessionLocal()

def render_sidebar(paziente: models.Paziente | None, db: Session) -> None:
    st.sidebar.title("Dettagli Paziente")
    if not paziente:
        st.sidebar.info("Seleziona una richiesta per visualizzare i dettagli")
        return

    st.sidebar.subheader(paziente.nome_cognome)
    st.sidebar.write(f"Numero: {paziente.numero_telefono}")
    st.sidebar.write(f"Codice fiscale: {paziente.codice_fiscale}")

    note = (
        db.query(models.NotaAnamnesi)
        .filter_by(paziente_id=paziente.id)
        .order_by(models.NotaAnamnesi.data_evento.desc())
        .all()
    )

    if note:
        st.sidebar.markdown("### Timeline Anamnestica")
        for evento in note:
            st.sidebar.write(
                f"- **{evento.data_evento.strftime('%Y-%m-%d')}** · {evento.categoria}: {evento.contenuto}"
            )

    allergie = [n for n in note if "allerg" in n.categoria.lower() or "allerg" in n.contenuto.lower()]
    if allergie:
        st.sidebar.error("Attenzione: paziente con allergie note")

def main() -> None:
    if not authenticate():
        return

    db = get_db_session()

    # All'interno di main(), subito dopo db = get_db_session():
    st_autorefresh(interval=15000, key="datarefresh") # Ricarica i dati da sola ogni 15 secondi

    st.title("MedTriage Dashboard")
    st.markdown("Gestione delle richieste attive e archivio delle pratiche")

    richieste_ricette = db.query(models.Richiesta).filter(models.Richiesta.tipo == models.TipoRichiesta.RICETTA, models.Richiesta.stato != models.StatoRichiesta.EVASA).all()
    richieste_consulti = db.query(models.Richiesta).filter(models.Richiesta.tipo == models.TipoRichiesta.CONSULTO, models.Richiesta.stato != models.StatoRichiesta.EVASA).all()
    richieste_evasati = db.query(models.Richiesta).filter(models.Richiesta.stato == models.StatoRichiesta.EVASA).all()

tab_ricette, tab_consulti, tab_archivio, tab_studio = st.tabs(
    ["💊 Ricette da fare", "🩺 Consulti", "✅ Archivio Evasati", "⚙️ Gestione Studio"])

    with tab_ricette:
        st.subheader("Richieste di ricetta in attesa")
        for richiesta in richieste_ricette:
            paziente = richiesta.paziente
            if st.button(f"{paziente.nome_cognome} – {richiesta.dettagli or 'Nessun dettaglio'}", key=f"ricetta_{richiesta.id}"):
                st.session_state.selected_request = richiesta.id

    with tab_consulti:
        st.subheader("Richieste di consulto in attesa")
        for richiesta in richieste_consulti:
            paziente = richiesta.paziente
            if st.button(f"{paziente.nome_cognome} – {richiesta.dettagli or 'Nessun dettaglio'}", key=f"consulto_{richiesta.id}"):
                st.session_state.selected_request = richiesta.id

    with tab_archivio:
        st.subheader("Richieste evase")
        for richiesta in richieste_evasati:
            paziente = richiesta.paziente
            st.write(f"{richiesta.data_creazione.strftime('%Y-%m-%d')} · {paziente.nome_cognome} · {richiesta.tipo.value} · {richiesta.dettagli or 'Nessun dettaglio'}")
    
    with tab_studio:
        st.subheader("Configurazione Apertura e Chiusure dello Studio")
        
        # Sezione FERIE / CHIUSURE
        st.markdown("### 🏖️ Gestione Ferie e Chiusure Straordinarie")
        col_inizio, col_fine, col_motivo = st.columns(3)
        with col_inizio:
            data_in = st.date_input("Inizio Chiusura", value=datetime.today())
        with col_fine:
            data_fi = st.date_input("Fine Chiusura", value=datetime.today())
        with col_motivo:
            motivo_txt = st.text_input("Motivo (opzionale)", placeholder="Es: Ferie estive")
            
        if st.button("Imposta Chiusura Studio"):
            # Salviamo la chiusura nel DB
            nuova_chiusura = models.ChiusuraStraordinaria(
                data_inizio=datetime.combine(data_in, datetime.min.time()),
                data_fine=datetime.combine(data_fi, datetime.max.time()),
                motivo=motivo_txt
            )
            db.add(nuova_chiusura)
            db.commit()
            st.success(f"Studio impostato come CHIUSO dal {data_in} al {data_fi}")
            st.experimental_rerun()
            
        # Mostra le chiusure attive
        chiusure_attive = db.query(models.ChiusuraStraordinaria).filter(models.ChiusuraStraordinaria.data_fine >= datetime.utcnow()).all()
        if chiusure_attive:
            st.info("📌 Periodi di chiusura pianificati:")
            for c in chiusure_attive:
                st.write(f"- Dal {c.data_inizio.strftime('%d/%m/%Y')} al {c.data_fine.strftime('%d/%m/%Y')} ({c.motivo or 'Nessun motivo specificato'})")

        st.markdown("---")
        
        # Sezione ORARI SETTIMANALI
        st.markdown("### ⏰ Orario di Ricevimento Ambulatorio")
        giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]
        
        for i, giorno in enumerate(giorni):
            st.write(f"**{giorno}**")
            # Cerca se c'è già un orario salvato
            orario_esistente = db.query(models.OrarioStudio).filter_by(giorno_settimana=i).first()
            
            val_apertura = "08:00" if not orario_esistente else orario_esistente.ora_apertura
            val_chiusura = "12:00" if not orario_esistente else orario_esistente.ora_chiusura
            
            c_ap, c_ch, c_salva = st.columns([2, 2, 1])
            with c_ap:
                ora_ap = st.text_input("Ora Apertura", value=val_apertura, key=f"ap_{i}")
            with c_ch:
                ora_ch = st.text_input("Ora Chiusura", value=val_chiusura, key=f"ch_{i}")
            with c_salva:
                st.write("") # Spazio per allineamento
                if st.button("Salva", key=f"btn_{i}"):
                    if not orario_esistente:
                        orario_esistente = models.OrarioStudio(giorno_settimana=i)
                    orario_esistente.ora_apertura = ora_ap
                    orario_esistente.ora_chiusura = ora_ch
                    db.add(orario_esistente)
                    db.commit()
                    st.success(f"Orario di {giorno} aggiornato!")

    selected_request_id = st.session_state.get("selected_request")
    selected_paziente = None

    if selected_request_id:
        selected_request = db.query(models.Richiesta).filter_by(id=selected_request_id).first()
        if selected_request:
            selected_paziente = selected_request.paziente
            st.markdown("### Richiesta selezionata")
            st.write(f"Tipo: {selected_request.tipo.value}")
            st.write(f"Stato: {selected_request.stato.value}")
            st.write(f"Dettagli: {selected_request.dettagli or 'Nessun dettaglio'}")

            if st.button("Segna come evasa"):
                selected_request.stato = models.StatoRichiesta.EVASA
                db.add(selected_request)
                db.commit()
                st.success("Richiesta marcata come evasa")
                st.rerun()

    render_sidebar(selected_paziente, db)

if __name__ == "__main__":
    main()