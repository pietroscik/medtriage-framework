# MedTriage Framework

Breve descrizione
MedTriage Framework è una libreria/modulo per supportare il triage clinico automatizzato e la gestione dei flussi di valutazione medica. Fornisce componenti riutilizzabili per acquisizione dati, validazione, regole di triage e integrazione con sistemi esterni.

Principali funzionalità
- Modelli dati tipizzati per anamnesi e sintomi
- Motore regole configurabile (regole cliniche)
- API REST minimale per integrazione con frontend/EMR
- Logging e tracciamento eventi
- Suite di test e strumenti per validazione delle regole

Requisiti
- Python 3.10+ (o versione compatibile specificata nel pyproject/requirements)
- Dipendenze elencate in requirements.txt o pyproject.toml
- Windows 10/11 consigliato per ambiente di sviluppo

Installazione rapida (Windows)
1. Clona il repository:
   git clone <repo-url>
2. Crea e attiva virtualenv:
   python -m venv .venv
   .\.venv\Scripts\activate
3. Installa dipendenze:
   pip install -r requirements.txt

Esecuzione locale
- Avvia l'app (esempio):
  python -m medtriage.app
- Esegui test:
  pytest -q

Configurazione
- Variabili d'ambiente: creare un file `.env` o impostare le variabili richieste (DB_URL, SECRET_KEY, LOG_LEVEL, ecc.)
- File di regole: tutte le regole cliniche sono in `config/rules/` (formato YAML/JSON)

Struttura del progetto (sintesi)
- medtriage/         — codice sorgente
- tests/             — test unitari e di integrazione
- config/            — configurazioni e regole
- scripts/           — utility e script di deploy
- docs/              — documentazione aggiuntiva

Contributi
- Apri issue per bug o richieste funzionali
- Usa branch feature/<nome> e apri pull request descrittive
- Segui il file CONTRIBUTING.md per linee guida sul codice

Licenza
Specificare la licenza nel file LICENSE (es. MIT, Apache-2.0)

Contatti
Progetto mantenuto da: Team MedTriage — mantainer@esempio.it