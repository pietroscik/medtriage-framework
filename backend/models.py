from datetime import datetime
from enum import Enum
from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from .database import Base

class TipoRichiesta(Enum):
    RICETTA = "RICETTA"
    CONSULTO = "CONSULTO"

class StatoRichiesta(Enum):
    NUOVA = "NUOVA"
    IN_LAVORAZIONE = "IN_LAVORAZIONE"
    EVASA = "EVASA"

class Paziente(Base):
    __tablename__ = "pazienti"

    id = Column(Integer, primary_key=True, index=True)
    numero_telefono = Column(String(32), unique=True, index=True, nullable=False)
    nome_cognome = Column(String(256), nullable=False)
    codice_fiscale = Column(String(32), unique=True, nullable=False)
    data_registrazione = Column(DateTime, default=datetime.utcnow, nullable=False)

    richieste = relationship("Richiesta", back_populates="paziente", cascade="all, delete-orphan")
    farmaci_cronici = relationship("FarmacoCronico", back_populates="paziente", cascade="all, delete-orphan")
    note_anamnesi = relationship("NotaAnamnesi", back_populates="paziente", cascade="all, delete-orphan")

class Richiesta(Base):
    __tablename__ = "richieste"

    id = Column(Integer, primary_key=True, index=True)
    paziente_id = Column(Integer, ForeignKey("pazienti.id"), nullable=False)
    tipo = Column(SAEnum(TipoRichiesta), nullable=False)
    stato = Column(SAEnum(StatoRichiesta), default=StatoRichiesta.NUOVA, nullable=False)
    dettagli = Column(Text, nullable=True)
    data_creazione = Column(DateTime, default=datetime.utcnow, nullable=False)

    paziente = relationship("Paziente", back_populates="richieste")

class FarmacoCronico(Base):
    __tablename__ = "farmaci_cronici"

    id = Column(Integer, primary_key=True, index=True)
    paziente_id = Column(Integer, ForeignKey("pazienti.id"), nullable=False)
    nome_farmaco = Column(String(256), nullable=False)
    data_ultimo_rinnovo = Column(DateTime, default=datetime.utcnow, nullable=False)

    paziente = relationship("Paziente", back_populates="farmaci_cronici")

class NotaAnamnesi(Base):
    __tablename__ = "note_anamnesi"

    id = Column(Integer, primary_key=True, index=True)
    paziente_id = Column(Integer, ForeignKey("pazienti.id"), nullable=False)
    data_evento = Column(DateTime, default=datetime.utcnow, nullable=False)
    categoria = Column(String(128), nullable=False)
    contenuto = Column(Text, nullable=False)

    paziente = relationship("Paziente", back_populates="note_anamnesi")

class StatoConversazione(Base):
    __tablename__ = "stati_conversazione"

    numero_telefono = Column(String(32), primary_key=True, index=True)
    stato_attuale = Column(String(64), default="START", nullable=False)
    dati_temporanei = Column(Text, nullable=True)
    ultima_interazione = Column(DateTime, default=datetime.utcnow, nullable=False)


class OrarioStudio(Base):
    __tablename__ = "orari_studio"

    id = Column(Integer, primary_key=True)
    giorno_settimana = Column(Integer, unique=True, nullable=False) # 0 = Lunedì, 1 = Martedì...
    ora_apertura = Column(String(8), nullable=False)  # Es: "15:30"
    ora_chiusura = Column(String(8), nullable=False)  # Es: "18:30"

class ChiusuraStraordinaria(Base):
    __tablename__ = "chiusure_straordinarie"

    id = Column(Integer, primary_key=True)
    data_inizio = Column(DateTime, nullable=False)
    data_fine = Column(DateTime, nullable=False)
    motivo = Column(String(256), nullable=True) # Es: "Ferie estive" o "Malattia"