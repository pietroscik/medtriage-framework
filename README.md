# MedTriage - WhatsApp Bot per Studi Medici

MedTriage è un sistema progettato per aiutare i medici di base a gestire le comunicazioni con i pazienti tramite WhatsApp. Automatizza la ricezione, la classificazione e la visualizzazione dei messaggi, liberando tempo prezioso e centralizzando le richieste in un'unica dashboard.

## ✨ Funzionalità Principali

-   **🤖 Bot Conversazionale**: Accoglie i pazienti, li registra se non sono in anagrafica e li guida nella formulazione della richiesta.
-   **Triage Automatico**: Classifica le richieste in categorie predefinite (es. "Ricetta", "Consulto").
-   **🗓️ Gestione Orari**: Risponde automaticamente con un messaggio di "studio chiuso" se il paziente scrive fuori orario.
-   **🖥️ Dashboard per il Medico**: Un'interfaccia web (basata su Streamlit) per visualizzare, filtrare e rispondere a tutti i messaggi.
-   **📧 Notifiche Immediate**: Avvisa il medico via email all'arrivo di una nuova richiesta.
-   **🗄️ Backup Automatici**: Esegue backup giornalieri del database per non perdere dati.
-   **🇪🇺 GDPR Light**: Include funzionalità base per la conformità GDPR, come la richiesta di consenso e la cancellazione dei dati.

## 🚀 Stack Tecnologico

-   **Backend**: **FastAPI** per un'API REST veloce e robusta.
-   **Frontend**: **Streamlit** per una dashboard interattiva e facile da usare.
-   **Database**: **SQLAlchemy** con supporto per **SQLite** (default) e **PostgreSQL**.
-   **Integrazione WhatsApp**: **Meta Graph API**.

## 📂 Struttura del Progetto

```
medtriage-framework/
│
├── backend/          # Logica del server FastAPI, modelli DB, triage
├── frontend/         # Codice della dashboard Streamlit
├── scripts/          # Script di utilità (es. backup, seed)
├── backups/          # Directory per i backup automatici del DB
│
├── .env              # File di configurazione (da creare)
├── requirements.txt  # Dipendenze Python
└── README.md         # Questo file
```

## ⚙️ Configurazione e Installazione

1.  **Clona il repository**:
    ```bash
    git clone https://github.com/tuo-utente/medtriage-framework.git
    cd medtriage-framework
    ```

2.  **Crea un ambiente virtuale e attivalo**:
    ```bash
    # Windows
    python -m venv .venv
    .\.venv\Scripts\activate

    # macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Installa le dipendenze**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Crea il file `.env`**:
    Crea un file chiamato `.env` nella directory principale del progetto e copia al suo interno il contenuto seguente, personalizzando i valori.

    ```ini
    # Database (SQLite è il default e non richiede configurazione)
    DATABASE_URL=sqlite:///./medtriage.db

    # WhatsApp API (ottenuti dalla tua App su Meta for Developers)
    VERIFY_TOKEN="IL_TUO_VERIFY_TOKEN_SEGRETO"
    META_APP_SECRET="IL_TUO_APP_SECRET_META" # opzionale, ma consigliato per verificare la firma webhook
    META_ACCESS_TOKEN="IL_TUO_TOKEN_DI_ACCESSO_META"
    META_PHONE_NUMBER_ID="L_ID_DEL_TUO_NUMERO_DI_TELEFONO"

    # Notifiche Email per il medico
    MEDICO_EMAIL="email.del.medico@esempio.com"
    EMAIL_PASSWORD="la_tua_password_per_app_gmail" # Usa una "App Password" se usi Gmail con 2FA
    EMAIL_SMTP_SERVER="smtp.gmail.com"
    EMAIL_SMTP_PORT=587

    # Dashboard
    DASHBOARD_PASSWORD="una_password_robusta_per_la_dashboard"
    ```

## ▶️ Esecuzione

Apri due terminali separati.

1.  **Avvia il Backend (FastAPI)**:
    Nel primo terminale, esegui:
    ```bash
    uvicorn backend.main:app --reload
    ```
    Il server sarà in ascolto su `http://127.0.0.1:8000`.

2.  **Avvia la Dashboard (Streamlit)**:
    Nel secondo terminale, esegui:
    ```bash
    streamlit run frontend/dashboard.py
    ```
    La dashboard sarà accessibile su `http://localhost:8501`.

## Aggiornamenti operativi

- Crittografia (opzionale): se imposti `FERNET_KEY` (base64) i campi sensibili (`anamnesi`, `note`) vengono cifrati. Se non impostata, i campi vengono salvati in chiaro (fallback per compatibilità).
  - Genera chiave: `python - <<'PY'\nfrom cryptography.fernet import Fernet\nprint(Fernet.generate_key().decode())\nPY`
  - Esporta: `set FERNET_KEY=la_tua_chiave` (PowerShell / .env).

- Notifiche Telegram:
  - Imposta `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` per ricevere notifiche su nuove richieste.

- CORS backend:
  - Imposta `CORS_ORIGINS` come lista separata da virgole se devi esporre l’API oltre `localhost`.
  - Default: `http://localhost:8501,http://127.0.0.1:8501`.

- Multi-medico leggero:
  - Nel dashboard (sidebar) seleziona il "Medico corrente". Le query e le assegnazioni useranno `medico_id` quando presente.
  - Quando salvi lo stato di una richiesta, se `medico_id` non è impostato viene assegnato il medico corrente.

- Migrazione rapida:
  - Esegui: `python backend/db_migrate_add_fields.py` per creare colonne `anamnesi`, `note`, `medico_id` e tabelle mancanti.

- Backup DB:
  - Esegui nightly: `python scripts/backup_db.py`
  - Configura `BACKUP_DIR` env var se vuoi un percorso diverso.

- Worker coda WhatsApp:
  - Esegui una volta: `python -m backend.queue --once`
  - Esegui in loop: `python -m backend.queue --interval 30 --batch 50`

## Comandi utili

- Installa dipendenze:
  `pip install -r requirements.txt`

- Migrazione rapida:
  `python backend/db_migrate_add_fields.py`

- Avvio servizi:
  `uvicorn backend.main:app --reload`
  `streamlit run frontend/dashboard.py`
