
import os
from datetime import datetime as dt
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base


load_dotenv()
DATABASE_URL = f"postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}"
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
    name = Column(String)
    encsoft_url = Column(String)
    cvv = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=dt.utcnow)
    updated_at = Column(DateTime, default=dt.utcnow, onupdate=dt.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
