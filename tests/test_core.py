import hashlib
import hmac
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SITE_PACKAGES = Path(__file__).resolve().parents[1] / ".venv" / "Lib" / "site-packages"
if SITE_PACKAGES.exists():
    sys.path.append(str(SITE_PACKAGES))

TEST_DB = Path(tempfile.gettempdir()) / "medtriage_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

backend_database = importlib.import_module("backend.database")
backend_models = importlib.import_module("backend.models")
backend_main = importlib.import_module("backend.main")
backend_triage = importlib.import_module("backend.triage")
backend_whatsapp = importlib.import_module("backend.whatsapp_client")
backend_time_utils = importlib.import_module("backend.time_utils")

Base = backend_database.Base
SessionLocal = backend_database.SessionLocal
engine = backend_database.engine


def _make_message(body: str) -> dict:
    return {"text": {"body": body}}


class CoreSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_webhook_signature_verification(self):
        body = b'{"entry":[]}'
        secret = "super-secret"
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        with patch.object(backend_main, "META_APP_SECRET", secret):
            self.assertTrue(backend_main._verify_meta_signature(body, f"sha256={signature}"))
            self.assertFalse(backend_main._verify_meta_signature(body, "sha256=badsignature"))
            self.assertFalse(backend_main._verify_meta_signature(body, None))

    def test_registration_flow_creates_patient(self):
        phone = "393331234567"
        sent_messages: list[str] = []

        with patch.object(backend_triage, "send_text_message", side_effect=lambda _phone, text, meta=None: sent_messages.append(text)):
            backend_triage.process_incoming_message(self.db, phone, _make_message("ciao"))
            stato = self.db.query(backend_models.StatoConversazione).filter_by(numero_telefono=phone).first()
            self.assertIsNotNone(stato)
            self.assertEqual(stato.stato_attuale, "REGISTRAZIONE_NOME")
            self.assertTrue(any("NOME e COGNOME" in message for message in sent_messages))

            backend_triage.process_incoming_message(self.db, phone, _make_message("Mario Rossi"))
            stato = self.db.query(backend_models.StatoConversazione).filter_by(numero_telefono=phone).first()
            self.assertEqual(stato.stato_attuale, "ATTESA_CONSENSO")

            backend_triage.process_incoming_message(self.db, phone, _make_message("SI"))
            stato = self.db.query(backend_models.StatoConversazione).filter_by(numero_telefono=phone).first()
            self.assertEqual(stato.stato_attuale, "REGISTRAZIONE_CF")

            backend_triage.process_incoming_message(self.db, phone, _make_message("RSSMRA85A01H501W"))
            paziente = self.db.query(backend_models.Paziente).filter_by(numero_telefono=phone).first()
            stato = self.db.query(backend_models.StatoConversazione).filter_by(numero_telefono=phone).first()
            self.assertIsNotNone(paziente)
            self.assertEqual(paziente.nome_cognome, "Mario Rossi")
            self.assertEqual(stato.stato_attuale, "ATTESA_SCELTA")

    def test_date_like_message_does_not_trigger_menu_choice(self):
        phone = "393331112222"
        paziente = backend_models.Paziente(
            numero_telefono=phone,
            nome_cognome="Mario Rossi",
            codice_fiscale="RSSMRA85A01H501W",
        )
        stato = backend_models.StatoConversazione(
            numero_telefono=phone,
            stato_attuale="ATTESA_SCELTA",
            dati_temporanei={"tipo": "RICETTA"},
            ultima_interazione=backend_time_utils.utc_now_naive(),
        )
        self.db.add(paziente)
        self.db.add(stato)
        self.db.commit()

        sent_messages: list[str] = []
        with patch.object(backend_triage, "send_text_message", side_effect=lambda _phone, text, meta=None: sent_messages.append(text)):
            backend_triage.process_incoming_message(self.db, phone, _make_message("15/07/2026 visita di controllo"))

        stato = self.db.query(backend_models.StatoConversazione).filter_by(numero_telefono=phone).first()
        richieste = self.db.query(backend_models.Richiesta).filter_by(paziente_id=paziente.id).all()
        self.assertEqual(stato.stato_attuale, "ATTESA_SCELTA")
        self.assertEqual(richieste, [])
        self.assertTrue(any("Scelta non valida" in message for message in sent_messages))

    def test_whatsapp_enqueue_gracefully_handles_redis_failure(self):
        with patch.object(backend_whatsapp.redis_client, "rpush", side_effect=RuntimeError("redis down")):
            result = backend_whatsapp.enqueue_message("393331234567", "msg di test")
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
