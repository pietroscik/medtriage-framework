import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, engine, Base
from backend.models import (
    Paziente, Richiesta, StatoRichiesta, TipoRichiesta,
    OrarioStudio, ChiusuraStraordinaria, RispostaRapida, Tag
)
from datetime import datetime, timedelta, timezone
import random
from backend.time_utils import utc_now_naive

print("🌱 Inizializzazione seed dati di test...")

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    # 1. Orari studio (Lunedì-Venerdì 9:00-18:00)
    if db.query(OrarioStudio).count() == 0:
        for giorno in range(5):
            orario = OrarioStudio(
                giorno_settimana=giorno,
                ora_apertura="09:00",
                ora_chiusura="18:00"
            )
            db.add(orario)
        db.commit()
        print("✅ Orari studio predefiniti inseriti.")

    # 2. Risposte rapide
    if db.query(RispostaRapida).count() == 0:
        risposte = [
            {"label": "Ricevuto", "testo": "La tua richiesta è stata ricevuta. Ti risponderemo al più presto."},
            {"label": "In Lavorazione", "testo": "Stiamo lavorando alla tua richiesta. Ti aggiorneremo presto."},
            {"label": "Emergenza", "testo": "Per emergenze, chiama il 118 o recati al pronto soccorso."},
            {"label": "Ricetta Pronta", "testo": "La tua ricetta è pronta! Puoi passare a ritirarla in studio."},
            {"label": "Appuntamento Confermato", "testo": "Il tuo appuntamento è stato confermato. Ti invieremo un promemoria il giorno prima."}
        ]
        for r in risposte:
            db.add(RispostaRapida(**r))
        db.commit()
        print("✅ Risposte rapide inserite.")

    # 3. Tag predefiniti
    if db.query(Tag).count() == 0:
        tags = ["RICETTA", "CONSULTO", "URGENTE", "PRENOTAZIONE", "FOLLOW_UP"]
        for tag in tags:
            db.add(Tag(nome=tag))
        db.commit()
        print("✅ Tag predefiniti inseriti.")

    # 4. Chiusure straordinarie (esempio: ferie estive)
    if db.query(ChiusuraStraordinaria).count() == 0:
        chiusure = [
            {
                "data_inizio": datetime.now() + timedelta(days=30),
                "data_fine": datetime.now() + timedelta(days=45),
                "motivo": "Ferie estive"
            },
            {
                "data_inizio": datetime.now() + timedelta(days=60),
                "data_fine": datetime.now() + timedelta(days=62),
                "motivo": "Congresso medico"
            }
        ]
        for c in chiusure:
            db.add(ChiusuraStraordinaria(**c))
        db.commit()
        print("✅ Chiusure straordinarie inserite.")

    # 5. Pazienti e richieste di test
    nomi = ["Mario Rossi", "Anna Bianchi", "Luigi Verdi", "Maria Neri", "Giovanni Blu"]
    farmaci = ["Tachipirina 1000mg", "Cardioaspirina 100mg", "Oki 400mg", "Ventolin", "Augmentin"]
    sintomi = [
        "Mal di testa e febbre da 2 giorni",
        "Dolore al petto (non urgente)",
        "Rinnovo ricetta per ipertensione",
        "Controllo annuale",
        "Tosse persistente"
    ]

    for nome in nomi:
        cf = f"{nome.split()[1].upper()[:3]}{nome.split()[0].upper()[:3]}{random.randint(0, 99):02d}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(0, 99):02d}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(0, 999):03d}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"
        telefono = f"39333{random.randint(1000000, 9999999)}"

        if not db.query(Paziente).filter_by(codice_fiscale=cf).first():
            paziente = Paziente(
                numero_telefono=telefono,
                nome_cognome=nome,
                codice_fiscale=cf
            )
            db.add(paziente)
            db.flush()

            # Aggiungi 1-3 richieste per paziente
            for _ in range(random.randint(1, 3)):
                tipo = random.choice([TipoRichiesta.RICETTA, TipoRichiesta.CONSULTO])
                stato = random.choice([StatoRichiesta.NUOVA, StatoRichiesta.IN_LAVORAZIONE, StatoRichiesta.EVASA])
                giorni_fa = random.randint(0, 30)
                dettagli = random.choice(farmaci) if tipo == TipoRichiesta.RICETTA else random.choice(sintomi)

                richiesta = Richiesta(
                    paziente_id=paziente.id,
                    tipo=tipo,
                    stato=stato,
                    dettagli=dettagli,
                    data_creazione=utc_now_naive() - timedelta(days=giorni_fa)
                )
                db.add(richiesta)

                # Aggiungi tag casuali
                if tipo == TipoRichiesta.RICETTA:
                    richiesta.tags.append(db.query(Tag).filter_by(nome="RICETTA").first())
                else:
                    richiesta.tags.append(db.query(Tag).filter_by(nome="CONSULTO").first())

                # Aggiungi risposta se evasa
                if stato == StatoRichiesta.EVASA:
                    richiesta.risposta = f"Risposta a {dettagli}"
                    richiesta.data_risposta = datetime.now(timezone.utc) - timedelta(days=giorni_fa - 1)

            db.commit()
            print(f"✅ Paziente {nome} e richieste inseriti.")

    print("🎉 Seed completato con successo!")

except Exception as e:
    print(f"❌ Errore durante il seed: {e}")
    db.rollback()
finally:
    db.close()
