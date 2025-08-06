import os
import logging
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .db import Event, get_db
from .schemas import EventCreate
from dotenv import load_dotenv


load_dotenv()
os.makedirs(os.getenv("LOG_DIR"), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.getenv("LOG_DIR"), "app.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
app = FastAPI()


@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    logger.info("test")
    return "todo"

@app.get("/events")
def get_events(limit: int, offset: int, db: Session = Depends(get_db)):
    return []

@app.post("/event")
def create_event(request: EventCreate, db: Session = Depends(get_db)):
    return {}

@app.post("/buy-ticket/{event_id}")
def buy_ticket(event_id: int, db: Session = Depends(get_db)):
    return {}

@app.delete("/event/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    return {}
