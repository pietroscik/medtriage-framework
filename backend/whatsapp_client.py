import os
import json
import requests
from typing import Any, Dict
from dotenv import load_dotenv
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import redis
from datetime import datetime

logger = logging.getLogger(__name__)
load_dotenv()

META_API_URL = os.getenv("META_WHATSAPP_API_URL", "https://graph.facebook.com/v17.0/YOUR_PHONE_ID/messages")
META_TOKEN = os.getenv("META_WHATSAPP_TOKEN")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

class WhatsAppSendError(Exception):
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30),
       retry=retry_if_exception_type(WhatsAppSendError))
def _send_via_api(payload: dict):
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    resp = requests.post(META_API_URL, json=payload, headers=headers, timeout=10)
    if resp.status_code >= 400:
        raise WhatsAppSendError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.json()

def enqueue_message(phone: str, text: str, meta: dict | None = None) -> None:
    item = {"phone": phone, "text": text, "meta": meta or {}, "ts": datetime.utcnow().isoformat()}
    redis_client.rpush("whatsapp:outbox", json.dumps(item))

def send_text_message(phone: str, text: str, meta: dict | None = None) -> dict:
    """
    Tries to send immediately with retry; on final failure enqueues in Redis outbox.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text}
    }
    try:
        return _send_via_api(payload)
    except Exception as e:
        # enqueue for later processing
        enqueue_message(phone, text, meta)
        raise RuntimeError(f"Enqueueing message after failure: {e}")

def send_template_blocking_message(phone: str, template_name: str, components: list | None = None, meta: dict | None = None) -> dict:
    """
    Send a template message via WhatsApp API. Tries immediate send with retry; on final failure enqueues.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "it"},
        },
    }
    if components:
        payload["template"]["components"] = components

    try:
        return _send_via_api(payload)
    except Exception as e:
        # fallback: enqueue a brief placeholder so it can be retried by process_outbox
        enqueue_message(phone, f"[TEMPLATE:{template_name}]", meta)
        return {"error": str(e)}

def process_outbox(batch: int = 50) -> int:
    """
    Process up to `batch` messages from Redis outbox. Returns number processed.
    Call this from a periodic worker (cron, service, or background task).
    """
    processed = 0
    for _ in range(batch):
        raw = redis_client.lpop("whatsapp:outbox")
        if not raw:
            break
        try:
            item = json.loads(raw)
        except Exception:
            continue
        try:
            _send_via_api({
                "messaging_product": "whatsapp",
                "to": item.get("phone"),
                "type": "text",
                "text": {"body": item.get("text")}
            })
            processed += 1
        except Exception:
            # push back to queue tail for retry later
            redis_client.rpush("whatsapp:outbox", raw)
            break
    return processed