import os
import json
import requests
from typing import Any, Dict
from dotenv import load_dotenv
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import redis
from .time_utils import utc_now_naive

logger = logging.getLogger(__name__)
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

class WhatsAppSendError(Exception):
    pass


def _resolve_meta_config() -> tuple[str | None, str | None]:
    phone_number_id = os.getenv("META_PHONE_NUMBER_ID") or os.getenv("META_WHATSAPP_PHONE_NUMBER_ID")
    api_url = os.getenv("META_WHATSAPP_API_URL")
    if not api_url:
        if phone_number_id:
            api_url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"

    token = os.getenv("META_ACCESS_TOKEN") or os.getenv("META_WHATSAPP_TOKEN")
    return api_url, token


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30),
       retry=retry_if_exception_type(WhatsAppSendError))
def _send_via_api(payload: dict):
    meta_api_url, meta_token = _resolve_meta_config()
    if not meta_api_url:
        raise WhatsAppSendError("Endpoint WhatsApp non configurato: imposta META_PHONE_NUMBER_ID o META_WHATSAPP_API_URL")
    if not meta_token:
        raise WhatsAppSendError("Token WhatsApp non configurato: imposta META_ACCESS_TOKEN o META_WHATSAPP_TOKEN")

    headers = {"Authorization": f"Bearer {meta_token}", "Content-Type": "application/json"}
    resp = requests.post(meta_api_url, json=payload, headers=headers, timeout=10)
    if resp.status_code >= 400:
        raise WhatsAppSendError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.json()

def enqueue_message(
    phone: str,
    text: str | None,
    meta: dict | None = None,
    *,
    kind: str = "text",
    template_name: str | None = None,
    components: list | None = None,
) -> None:
    item = {
        "phone": phone,
        "text": text,
        "meta": meta or {},
        "kind": kind,
        "template_name": template_name,
        "components": components,
        "ts": utc_now_naive().isoformat(),
    }
    try:
        redis_client.rpush("whatsapp:outbox", json.dumps(item))
    except Exception as exc:
        logger.warning("Redis outbox non disponibile, messaggio non accodato: %s", exc)

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
        enqueue_message(phone, text, meta, kind="text")
        logger.warning("Invio WhatsApp fallito, messaggio accodato: %s", e)
        return {"queued": True, "error": str(e)}

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
        enqueue_message(
            phone,
            None,
            meta,
            kind="template",
            template_name=template_name,
            components=components,
        )
        logger.warning("Invio template WhatsApp fallito, messaggio accodato: %s", e)
        return {"error": str(e)}

def process_outbox(batch: int = 50) -> int:
    """
    Process up to `batch` messages from Redis outbox. Returns number processed.
    Call this from a periodic worker (cron, service, or background task).
    """
    processed = 0
    for _ in range(batch):
        try:
            raw = redis_client.lpop("whatsapp:outbox")
        except Exception as exc:
            logger.warning("Redis outbox non disponibile, process_outbox sospeso: %s", exc)
            break
        if not raw:
            break
        try:
            item = json.loads(raw)
        except Exception:
            continue
        try:
            if item.get("kind") == "template":
                template_name = item.get("template_name")
                if template_name:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": item.get("phone"),
                        "type": "template",
                        "template": {
                            "name": template_name,
                            "language": {"code": "it"},
                        },
                    }
                    components = item.get("components")
                    if components:
                        payload["template"]["components"] = components
                else:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": item.get("phone"),
                        "type": "text",
                        "text": {"body": item.get("text") or "[TEMPLATE]"},
                    }
            else:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": item.get("phone"),
                    "type": "text",
                    "text": {"body": item.get("text")},
                }
            _send_via_api(payload)
            processed += 1
        except Exception:
            # push back to queue tail for retry later
            try:
                redis_client.rpush("whatsapp:outbox", raw)
            except Exception as exc:
                logger.warning("Impossibile reinserire in coda il messaggio WhatsApp: %s", exc)
            break
    return processed
