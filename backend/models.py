import os
from cryptography.fernet import Fernet, InvalidToken
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SAEnum, Table, JSON
from sqlalchemy.orm import relationship
from .database import Base
from .time_utils import utc_now_naive

# --- Enums ---
class TipoRichiesta(Enum):
    RICETTA = "RICETTA"
    CONSULTO = "CONSULTO"

class StatoRichiesta(Enum):
    NUOVA = "NUOVA"
    IN_LAVORAZIONE = "IN_LAVORAZIONE"
    EVASA = "EVASA"

# --- Modelli ---
class Medico(Base):
    __tablename__ = "medici"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True)
    telefono = Column(String(50), nullable=True)
    # URL del database del singolo medico (es: sqlite:///./tenant_medico_123.db o postgresql://...)
    db_url = Column(String(1024), nullable=True, unique=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    richieste = relationship("Richiesta", back_populates="medico")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(String(100), nullable=False)
    changed_by = Column(String(200), nullable=False)
    timestamp = Column(DateTime, default=utc_now_naive, nullable=False)
    details = Column(Text, nullable=True)

class Paziente(Base):
    __tablename__ = "pazienti"
    id = Column(Integer, primary_key=True, index=True)
    numero_telefono = Column(String(32), unique=True, index=True, nullable=False)
    nome_cognome = Column(String(256), nullable=False)
    codice_fiscale = Column(String(32), unique=True, nullable=False)
    data_registrazione = Column(DateTime, default=utc_now_naive, nullable=False)
    # store ciphertext/plaintext in DB column "anamnesi"; access via property `anamnesi`
    anamnesi_encrypted = Column("anamnesi", Text, nullable=True)

    @property
    def anamnesi(self) -> str | None:
        return _decrypt_text(self.anamnesi_encrypted)

    @anamnesi.setter
    def anamnesi(self, value: str | None):
        self.anamnesi_encrypted = _encrypt_text(value)

    richieste = relationship("Richiesta", back_populates="paziente", cascade="all, delete-orphan")
    farmaci_cronici = relationship("FarmacoCronico", back_populates="paziente", cascade="all, delete-orphan")
    note_anamnesi = relationship("NotaAnamnesi", back_populates="paziente", cascade="all, delete-orphan")

# Associazione molti-a-molti per Tag
richiesta_tag_association = Table(
    'richiesta_tag',
    Base.metadata,
    Column('richiesta_id', Integer, ForeignKey('richieste.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class Richiesta(Base):
    __tablename__ = "richieste"
    id = Column(Integer, primary_key=True, index=True)
    paziente_id = Column(Integer, ForeignKey("pazienti.id"), nullable=False)
    tipo = Column(SAEnum(TipoRichiesta), nullable=False)
    stato = Column(SAEnum(StatoRichiesta), default=StatoRichiesta.NUOVA, nullable=False)
    dettagli = Column(Text, nullable=True)
    data_creazione = Column(DateTime, default=utc_now_naive, nullable=False)
    risposta = Column(Text, nullable=True)  # ✅ Nuovo campo
    data_risposta = Column(DateTime, nullable=True)  # ✅ Nuovo campo
    paziente = relationship("Paziente", back_populates="richieste")
    tags = relationship("Tag", secondary=richiesta_tag_association, back_populates="richieste")
    note_encrypted = Column("note", Text, nullable=True)
    medico_id = Column(Integer, ForeignKey("medici.id"), nullable=True, index=True)
    medico = relationship("Medico", back_populates="richieste")

    @property
    def note(self) -> str | None:
        return _decrypt_text(self.note_encrypted)

    @note.setter
    def note(self, value: str | None):
        self.note_encrypted = _encrypt_text(value)

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(50), unique=True, nullable=False)
    richieste = relationship("Richiesta", secondary=richiesta_tag_association, back_populates="tags")

class FarmacoCronico(Base):
    __tablename__ = "farmaci_cronici"
    id = Column(Integer, primary_key=True, index=True)
    paziente_id = Column(Integer, ForeignKey("pazienti.id"), nullable=False)
    nome_farmaco = Column(String(256), nullable=False)
    data_ultimo_rinnovo = Column(DateTime, default=utc_now_naive, nullable=False)
    paziente = relationship("Paziente", back_populates="farmaci_cronici")

class NotaAnamnesi(Base):
    __tablename__ = "note_anamnesi"
    id = Column(Integer, primary_key=True, index=True)
    paziente_id = Column(Integer, ForeignKey("pazienti.id"), nullable=False)
    data_evento = Column(DateTime, default=utc_now_naive, nullable=False)
    categoria = Column(String(128), nullable=False)
    contenuto = Column(Text, nullable=False)
    paziente = relationship("Paziente", back_populates="note_anamnesi")

class StatoConversazione(Base):
    __tablename__ = "stati_conversazione"
    numero_telefono = Column(String(32), primary_key=True, index=True)
    stato_attuale = Column(String(64), default="START", nullable=False)
    dati_temporanei = Column(JSON, nullable=True)  # ✅ Fix: ora è JSON
    ultima_interazione = Column(DateTime, default=utc_now_naive, nullable=False)

class RispostaRapida(Base):
    __tablename__ = "risposte_rapide"
    id = Column(Integer, primary_key=True, index=True)
    label = Column(String(128), unique=True, nullable=False)
    testo = Column(Text, nullable=False)

class OrarioStudio(Base):
    __tablename__ = "orari_studio"
    id = Column(Integer, primary_key=True)
    giorno_settimana = Column(Integer, unique=True, nullable=False)  # 0 = Lunedì
    ora_apertura = Column(String(8), nullable=False)  # Es: "09:00"
    ora_chiusura = Column(String(8), nullable=False)  # Es: "18:00"

class ChiusuraStraordinaria(Base):
    __tablename__ = "chiusure_straordinarie"
    id = Column(Integer, primary_key=True)
    data_inizio = Column(DateTime, nullable=False)
    data_fine = Column(DateTime, nullable=False)
    motivo = Column(String(256), nullable=True)

def _get_fernet():
    key = os.getenv("FERNET_KEY")
    if not key:
        return None
    return Fernet(key.encode())

def _encrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    f = _get_fernet()
    if f is None:
        # no key configured: store plaintext (backward compatible)
        return value
    return f.encrypt(value.encode("utf-8")).decode("utf-8")

def _decrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    f = _get_fernet()
    if f is None:
        # no key: assume plaintext
        return value
    try:
        return f.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # not encrypted or wrong key -> return raw value
        return value
