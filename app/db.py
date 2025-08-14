
import os
from datetime import datetime as dt
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.orm import sessionmaker, declarative_base


load_dotenv()
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


# Models
class Event(Base):
    __tablename__ = "events"

    STATUS_NEW = "new"
    STATUS_SCHEDULED = "scheduled"
    STATUS_FAILED = "failed"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String)
    event_name = Column(String)
    bot_email = Column(String)
    section = Column(String)
    row = Column(String)
    price = Column(Float)
    amount = Column(Integer)
    full_price = Column(Float)
    price_plus_fees = Column(Float)
    expire_at = Column(DateTime)
    encsoft_url = Column(String)
    cvv = Column(String)
    status = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=dt.utcnow)
    updated_at = Column(DateTime, default=dt.utcnow, onupdate=dt.utcnow)

class EventDetails(Base):
    __tablename__ = "event_details"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String)
    event_name = Column(String)

class BotAccount(Base):
    __tablename__ = "bot_accounts"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String)
    cvv = Column(String)

class AutoAprovalRules(Base):
    __tablename__ = "auto_aproval_rules"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String)
    event_name = Column(String)
    section = Column(String)
    row = Column(String)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
