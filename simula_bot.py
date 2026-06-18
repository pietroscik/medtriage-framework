import requests
import time

URL = "http://127.0.0.1:8000/webhook"
NUMERO_TEST = "393339988776" # Un numero finto, non presente nel DB

def invia_messaggio(testo):
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "messages": [{
                        "from": NUMERO_TEST,
                        "text": {"body": testo}
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    response = requests.post(URL, json=payload)
    print(f"[Paziente]: {testo} --> Rilevato dal server (Status: {response.status_code})")

print("--- INIZIO SIMULAZIONE FLUSSO WHATSAPP ---")

# Step 1: Il paziente sconosciuto scrive "Ciao" per la prima volta
invia_messaggio("Ciao, vorrei parlare con il medico")
print("--> Controlla il terminale di FastAPI: il bot gli avrà chiesto Nome e Cognome.\n")
time.sleep(3)

# Step 2: Il paziente inserisce il proprio Nome e Cognome
invia_messaggio("Giuseppe Verdi")
print("--> Il bot ha memorizzato il nome temporaneamente e ora chiede il Codice Fiscale.\n")
time.sleep(3)

# Step 3: Il paziente inserisce il Codice Fiscale
invia_messaggio("VRDGPP80A01H501Z")
print("--> Registrazione completata! Il bot mostra il menu (1 per ricette, 2 per consulto).\n")
time.sleep(3)

# Step 4: Il paziente sceglie l'opzione 1 (Ricette)
invia_messaggio("Scelgo la 1")
print("--> Il bot capisce l'intento e chiede il nome del farmaco.\n")
time.sleep(3)

# Step 5: Il paziente scrive il farmaco desiderato
invia_messaggio("Tachipirina 1000mg per favore")
print("--> Fine del Triage! La richiesta è stata creata e il bot si è resettato su START.\n")

print("--- SIMULAZIONE COMPLETATA ---")
print("Ora vai sulla Dashboard di Streamlit e guarda se è comparso Giuseppe Verdi!")