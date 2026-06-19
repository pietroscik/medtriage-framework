import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./medtriage.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

QUICK_REPLIES = [
    "Hello, World!",
    "How are you?",
    "What's up?",
    "Goodbye!",
]

def handle_quick_reply(st):
    quick_reply_count = len(QUICK_REPLIES) if QUICK_REPLIES else 0
    if quick_reply_count > 0:
        cols = st.columns(quick_reply_count)
        for col, reply in zip(cols, QUICK_REPLIES):
            if col.button(reply):
                prompt = reply
                st.write(f"Quick reply: {prompt}")
    else:
        st.write("No quick replies available.")