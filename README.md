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