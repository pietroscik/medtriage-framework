"""Compatibilità con il modulo notifiche del package backend."""

from backend.notifications import (
    notify_medico,
    notify_new_request,
    send_email_notification,
    send_telegram_message,
    send_telegram_notification,
)
