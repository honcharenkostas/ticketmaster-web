import os
import logging
from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .db import Event, get_db
from .schemas import EventCreate
from fastapi.templating import Jinja2Templates
import requests
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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    total = db.query(Event).filter(Event.is_active==True).count()
    events = db.query(Event) \
        .filter(Event.is_active==True) \
        .offset(offset) \
        .limit(limit) \
        .all()
    
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
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        return {}
    
    if not event.encsoft_url or not event.cvv:
        return {"error": "Event checkout url or CVV is empty"}, 500
    
    try:
        resp = requests.post(
            url=os.getenv("CHECKOUT_BOT_API_URL"),
            json={
                "encsoft_url": event.encsoft_url,
                "cvv": event.cvv,
            }
        )

        if resp.status_code == 200:
            event.status = Event.STATUS_SCHEDULED
            db.add(event)
            db.commit()

            return {}
    except Exception as e:
        logger.error(e)
        db.rollback()

        event.status = Event.STATUS_FAILED
        db.add(event)
        db.commit()

    return {}, 500

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
