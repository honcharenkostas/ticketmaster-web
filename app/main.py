import os
import logging
from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .db import Event, get_db
from .schemas import EventCreate
from fastapi.templating import Jinja2Templates
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
templates = Jinja2Templates(directory="templates")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    total = db.query(Event).filter(Event.is_active==True).count()
    events = db.query(Event) \
        .filter(Event.is_active==True) \
        .order_by(desc(Event.created_at)) \
        .offset(offset) \
        .limit(limit) \
        .all()
    events = db.query(Event).offset(offset).limit(limit).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "events": events,
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    )

@app.post("/event")
def create_event(request: EventCreate, db: Session = Depends(get_db)):
    event = Event(
        name=request.name,
        encsoft_url=str(request.encsoft_url),
        cvv=request.cvv,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {"id": event.id}

@app.post("/buy-ticket/{event_id}")
def buy_ticket(event_id: int, db: Session = Depends(get_db)):
    return {}

@app.delete("/event/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        return {}
    try:
        event.is_active = False
        db.add(event)
        db.commit()
        return {"success": True}
    except Exception as e:
        logger.error(e)
        db.rollback()
        return {}, 500
