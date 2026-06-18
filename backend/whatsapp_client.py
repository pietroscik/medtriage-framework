import os
from typing import Any, Dict
import requests
from dotenv import load_dotenv

load_dotenv()

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
BASE_URL = f"https://graph.facebook.com/v17.0/{META_PHONE_NUMBER_ID}/messages"

def build_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

def send_text_message(telefono: str, testo: str) -> Dict[str, Any]:
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": testo},
    }
    try:
        # Se siamo in test locale con credenziali finte, stampiamo a schermo ed evitiamo il crash
        if "mock" in META_ACCESS_TOKEN or not META_ACCESS_TOKEN:
            print(f"\n[🤖 BOT OUTGOING TEXT]: Alla chat {telefono} -> '{testo}'\n")
            return {"success": True, "mock": True}
            
        response = requests.post(BASE_URL, json=payload, headers=build_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"\n[⚠️ Errore Invio Meta API]: {e}")
        print(f"[🤖 MESSAGGIO PERSO]: {testo}\n")
        return {"success": False, "error": str(e)}

def send_template_blocking_message(telefono: str, template_name: str = "studio_chiuso") -> Dict[str, Any]:
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "it_IT"},
        },
    }
    try:
        if "mock" in META_ACCESS_TOKEN or not META_ACCESS_TOKEN:
            print(f"\n[🤖 BOT OUTGOING TEMPLATE]: Inviato avviso '{template_name}' allo studio (Risulta CHIUSO)\n")
            return {"success": True, "mock": True}
            
        response = requests.post(BASE_URL, json=payload, headers=build_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"\n[⚠️ Errore Invio Template Meta]: {e}\n")
        return {"success": False, "error": str(e)}