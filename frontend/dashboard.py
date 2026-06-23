import os
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from dotenv import load_dotenv

from backend.database import SessionLocal, get_tenant_session_for_medico
from backend.models import Medico, Richiesta, Paziente, StatoRichiesta

load_dotenv()

PASSWORD_FILE = Path(".dashboard_password")


def load_dashboard_password() -> str | None:
    if PASSWORD_FILE.exists():
        return PASSWORD_FILE.read_text().strip()
    return os.getenv("DASHBOARD_PASSWORD")


def format_telefono(telefono: str) -> str:
    if telefono.startswith("39"):
        return f"+{telefono}"
    return telefono


def rerun_app() -> None:
    rerun_fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if rerun_fn:
        rerun_fn()


def show_login():
    st.title("🔒 Accesso alla Dashboard")
    st.write("Inserisci la password per accedere alla dashboard di gestione.")
    password = st.text_input("Password", type="password")
    if st.button("Accedi"):
        current_password = load_dashboard_password()
        if current_password and password == current_password:
            st.session_state["authenticated"] = True
            if "current_medico_id" not in st.session_state:
                st.session_state["current_medico_id"] = None
            rerun_app()
        else:
            st.error("❌ Password errata! Riprova.")

    if not load_dashboard_password():
        st.info(
            "Nessuna password configurata. Crea un file `.dashboard_password` nella root del progetto "
            "contenente la password oppure imposta `DASHBOARD_PASSWORD`."
        )


def main():
    st.set_page_config(
        layout="wide",
        page_title="MedTriage Dashboard",
        page_icon="🏥",
        initial_sidebar_state="expanded",
    )

    st_autorefresh(interval=20_000, key="auto_refresh")

    if not st.session_state.get("authenticated", False):
        show_login()
        return

    master_db = SessionLocal()
    try:
        render_medica_tab(master_db)
    finally:
        master_db.close()


def render_medica_tab(master_db):
    st.sidebar.header("Studio medico")
    medici = master_db.query(Medico).order_by(Medico.nome).all()

    if not medici:
        st.warning(
            "Nessun medico configurato nel database master. Crea prima un medico "
            "con lo script `scripts/add_medico_tenant.py`."
        )
        return

    medico_choices = {
        f"{m.nome} ({m.email or m.telefono or m.id})": m.id for m in medici
    }
    labels = list(medico_choices.keys())

    default_index = 0
    if st.session_state.get("current_medico_label") in labels:
        default_index = labels.index(st.session_state["current_medico_label"])

    selected_label = st.sidebar.selectbox(
        "Medico corrente",
        labels,
        index=default_index,
        help="Ogni medico usa il proprio database dedicato. Selezionare sempre il medico corretto."
    )
    current_medico_id = medico_choices[selected_label]
    st.session_state["current_medico_id"] = current_medico_id
    st.session_state["current_medico_label"] = selected_label

    st.sidebar.markdown(
        "Ogni medico ha un tenant DB separato:\n\n"
        "- i dati non vengono condivisi tra studi diversi\n"
        "- ogni studio ha il proprio spazio riservato\n"
        "- usa il medico corretto prima di lavorare"
    )

    try:
        tenant_db = get_tenant_session_for_medico(current_medico_id)
    except Exception as exc:
        st.error(f"Errore tenant DB: {exc}")
        return

    with tenant_db as db:
        render_richieste_tenant(db, current_medico_id)


def render_richieste_tenant(db, current_medico_id: int):
    st.title("Area Medica")
    st.markdown("Qui gestisci le richieste e lo storico del medico selezionato.")

    with st.expander("Filtri e ricerca", expanded=True):
        stato_filter = st.selectbox(
            "Stato",
            ["Tutti"] + [s.value for s in StatoRichiesta],
            index=0,
        )
        search_text = st.text_input(
            "Cerca testo o nome paziente",
            placeholder="Es: Tachipirina, Mario Rossi"
        )
        solo_aperte = st.checkbox("Mostra solo richieste aperte", value=True)

    query = db.query(Richiesta).options(joinedload(Richiesta.paziente)).order_by(desc(Richiesta.data_creazione))

    if stato_filter != "Tutti":
        query = query.filter(Richiesta.stato == StatoRichiesta(stato_filter))

    if solo_aperte:
        query = query.filter(Richiesta.stato != StatoRichiesta.EVASA)

    if search_text:
        query = query.join(Paziente).filter(
            (Paziente.nome_cognome.ilike(f"%{search_text}%"))
            | (Richiesta.dettagli.ilike(f"%{search_text}%"))
        )

    richieste = query.limit(200).all()

    st.subheader(f"Richieste ({len(richieste)})")
    if not richieste:
        st.info("Nessuna richiesta trovata con i filtri selezionati.")
        return

    for richiesta in richieste:
        with st.expander(
            f"{richiesta.paziente.nome_cognome} — {richiesta.tipo.value} — {richiesta.stato.value}",
            expanded=False
        ):
            st.markdown(f"**Paziente:** {richiesta.paziente.nome_cognome}")
            st.markdown(f"**Telefono:** {format_telefono(richiesta.paziente.numero_telefono)}")
            st.markdown(f"**Stato:** {richiesta.stato.value}")
            st.markdown(f"**Dettagli:** {richiesta.dettagli}")
            if richiesta.note:
                st.markdown(f"**Note:** {richiesta.note}")
            if richiesta.risposta:
                st.markdown(f"**Risposta:** {richiesta.risposta}")
            if richiesta.data_creazione:
                st.markdown(f"**Creato il:** {richiesta.data_creazione}")

            col1, col2 = st.columns(2)
            with col1:
                nuovo_stato = st.selectbox(
                    "Cambia stato",
                    [s.value for s in StatoRichiesta],
                    index=[s.value for s in StatoRichiesta].index(richiesta.stato.value),
                    key=f"stato_{richiesta.id}"
                )
            with col2:
                note_corrente = st.text_area(
                    "Note interne",
                    value=richiesta.note or "",
                    key=f"note_{richiesta.id}",
                    height=120,
                )

            if st.button("Salva modifiche", key=f"salva_{richiesta.id}"):
                richiesta.stato = StatoRichiesta(nuovo_stato)
                richiesta.note = note_corrente.strip() or None
                if richiesta.medico_id is None:
                    richiesta.medico_id = current_medico_id
                db.commit()
                st.success("Modifiche salvate")
                rerun_app()


if __name__ == "__main__":
    main()
