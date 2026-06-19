import os
import smtplib
from email.mime.text import MIMEText
from .models import Richiesta

def send_email_notification(richiesta: Richiesta):
    medico_email = os.getenv("MEDICO_EMAIL")
    email_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", 587))

    if not all([medico_email, email_password]):
        print("⚠️ [Notifica Email] Variabili d'ambiente per l'invio email non configurate. Salto notifica.")
        return

    msg = MIMEText(f"""
    Nuova richiesta da {richiesta.paziente.nome_cognome} ({richiesta.paziente.numero_telefono}):
    "{richiesta.dettagli}"

    Tipo: {richiesta.tipo.value}
    """)
    msg["Subject"] = f"Nuova richiesta MedTriage: {richiesta.tipo.value}"
    msg["From"] = "notifiche@medtriage.com"
    msg["To"] = medico_email

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(medico_email, email_password)
        server.send_message(msg)