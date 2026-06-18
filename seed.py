from backend.database import SessionLocal, engine, Base
from backend import models
from datetime import datetime

print("Inizializzazione popolamento dati di test...")

# Forza la creazione delle tabelle se non presenti
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # 1. Controlla se il paziente esiste già per evitare duplicati
    paziente_test = db.query(models.Paziente).filter_by(codice_fiscale="RSSMRA85A01H501W").first()
    
    if not paziente_test:
        # Creiamo un paziente finto (es. Mario Rossi)
        paziente_test = models.Paziente(
            numero_telefono="393331234567",
            nome_cognome="Mario Rossi",
            codice_fiscale="RSSMRA85A01H501W"
        )
        db.add(paziente_test)
        db.commit()
        db.refresh(paziente_test)
        print(f"✔️ Paziente inserito: {paziente_test.nome_cognome}")
        
        # 2. Aggiungiamo lo storico clinico (Timeline Anamnestica)
        nota_allergia = models.NotaAnamnesi(
            paziente_id=paziente_test.id,
            categoria="Allergia",
            contenuto="Allergia severa nota alla Penicillina e derivati."
        )
        nota_cronica = models.NotaAnamnesi(
            paziente_id=paziente_test.id,
            categoria="Patologia",
            contenuto="Ipertensione arteriosa in trattamento dal 2024."
        )
        db.add_all([nota_allergia, nota_cronica])
        print("✔️ Note anamnestiche storiche inserite.")
    
    # 3. Creiamo una richiesta di ricetta transitoria (quella che arriverebbe da WhatsApp)
    nuova_ricetta = models.Richiesta(
        paziente_id=paziente_test.id,
        tipo=models.TipoRichiesta.RICETTA,
        stato=models.StatoRichiesta.NUOVA,
        dettagli="Rinnovo Cardioaspirina 100mg - 1 Confezione"
    )
    db.add(nuova_ricetta)
    db.commit()
    print(f"✔️ Nuova richiesta di ricetta creata per {paziente_test.nome_cognome}!")

except Exception as e:
    print(f"❌ Errore durante il seed: {e}")
finally:
    db.close()