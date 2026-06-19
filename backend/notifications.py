import os
import smtplib
import requests
from email.mime.text import MIMEText
from .models import Richiesta
import logging

logger = logging.getLogger(__name__)

# --- Email ---
def send_email_notification(richiesta: Richiesta):
    medico_email = os.getenv("MEDICO_EMAIL")
    email_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", 587))

    if not all([medico_email, email_password]):
        logger.warning("Variabili d'ambiente per email non configurate. Notifica saltata.")
        return

    msg = MIMEText(f"""
    📩 Nuova richiesta da {richiesta.paziente.nome_cognome} ({richiesta.paziente.numero_telefono}):

    Tipo: {richiesta.tipo.value}
    Dettagli: "{richiesta.dettagli}"

    Visualizza la dashboard: http://localhost:8501
    """)
    msg["Subject"] = f"🏥 Nuova richiesta MedTriage: {richiesta.tipo.value}"
    msg["From"] = f"MedTriage <{os.getenv('EMAIL_USER', medico_email)}>"
    msg["To"] = medico_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(os.getenv('EMAIL_USER', medico_email), email_password)
            server.send_message(msg)
        logger.info(f"✅ Notifica email inviata a {medico_email} per richiesta ID {richiesta.id}")
    except Exception as e:
        logger.error(f"❌ Errore invio email: {e}", exc_info=True)

# --- Telegram (opzionale) ---
def send_telegram_notification(richiesta: Richiesta):
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    message = f"""
    📩 *Nuova richiesta* da *{richiesta.paziente.nome_cognome}* ({richiesta.paziente.numero_telefono}):

    *Tipo*: {richiesta.tipo.value}
    *Dettagli*: {richiesta.dettagli[:200]}...
    *Dashboard*: http://localhost:8501
    """
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
        logger.info(f"✅ Notifica Telegram inviata per richiesta ID {richiesta.id}")
    except Exception as e:
        logger.error(f"❌ Errore invio Telegram: {e}")

# --- Funzione unificata ---
def notify_medico(richiesta: Richiesta):
    """Invia notifica sia via email che Telegram (se configurato)."""
    send_email_notification(richiesta)
    send_telegram_notification(richiesta)

# --- Funzione per invio Telegram ---
def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    response = requests.post(url, json=payload, timeout=10)
    return response.ok

# --- Funzione per notifica di nuova richiesta ---
def notify_new_request(richiesta) -> bool:
    testo = (
        f"*Nuova richiesta*\n"
        f"{richiesta.paziente.nome_cognome} · {richiesta.paziente.numero_telefono}\n"
        f"Tipo: {richiesta.tipo.value}\n"
        f"Stato: {richiesta.stato.value}\n\n"
        f"{richiesta.dettagli}"
    )
    return send_telegram_message(testo)