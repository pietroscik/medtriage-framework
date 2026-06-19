import requests
from typing import Dict, Any

class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = "https://graph.facebook.com/v18.0"

    def send_message(self, recipient: str, message: str) -> Dict[str, Any]:
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {
                "body": message
            }
        }
        response = requests.post(url, headers=headers, json=payload)
        return response.json()