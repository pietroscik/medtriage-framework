import streamlit as st
from sqlalchemy import create_engine, or_, text
from sqlalchemy.orm import Session, sessionmaker
from streamlit_autorefresh import st_autorefresh
import os

# Configuration de la base de données
DATABASE_URL = "sqlite:///./medtriage.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Configuration de l'auto-refresh
st_autorefresh(interval=5000, key="datarefresh")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def main():
    st.title("MedTriage Dashboard")
    st.write("Bienvenue sur la dashboard de MedTriage")
    
    # Affichage des dernières demandes
    db = next(get_db())
    richieste = db.query(Richiesta).order_by(Richiesta.data_creazione.desc()).limit(10).all()
    
    st.subheader("Dernières demandes")
    for richiesta in richieste:
        st.write(f"{richiesta.data_creazione}: {richiesta.testo}")

if __name__ == "__main__":
    # Vérification de l'authentification
    password = st.text_input("Mot de passe", type="password")
    if password == os.getenv("DASHBOARD_PASSWORD"):
        main()
    elif password:
        st.error("Mot de passe incorrect")
    else:
        st.warning("Veuillez entrer le mot de passe")