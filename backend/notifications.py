import os
import smtplib
from email.mime.text import MIMEText
from .models import Richiesta
import logging

logger = logging.getLogger(__name__)

def send_email_notification(richiesta: Richiesta):
    medico_email = os.getenv("MEDICO_EMAIL")
    email_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", 587))

    if not all([medico_email, email_password]):
        logger.warning("Variabili d'ambiente per l'invio email non configurate. Salto notifica.")
        return

    msg = MIMEText(f"""
    Nuova richiesta da {richiesta.paziente.nome_cognome} ({richiesta.paziente.numero_telefono}):
    "{richiesta.dettagli}"

    Tipo: {richiesta.tipo.value}
    """)
    msg["Subject"] = f"Nuova richiesta MedTriage: {richiesta.tipo.value}"
    msg["From"] = f"MedTriage Notifiche <{os.getenv('EMAIL_USER', medico_email)}>"
    msg["To"] = medico_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(os.getenv('EMAIL_USER', medico_email), email_password)
            server.send_message(msg)
            logger.info(f"Notifica email inviata con successo a {medico_email} per richiesta id {richiesta.id}")
    except Exception as e:
        logger.error(f"Errore durante l'invio della notifica email: {e}", exc_info=True)