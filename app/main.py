import os
import logging
import math
import random
from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from .db import Event, EventDetails, BotAccount, get_db
from .schemas import EventCreate
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import case, func
import requests
from datetime import datetime
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
PER_PAGE = 25


def expire_at(target_time: datetime) -> str:
    now = datetime.now()
    diff = target_time - now

    if diff.total_seconds() <= 0:
        return "expired"

    hours, remainder = divmod(int(diff.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours:02}:{minutes:02}:{seconds:02}"


@app.get("/items/")
def get_items(db: Session = Depends(get_db), page: int = Query(1, ge=1), event_id: str = Query(...)):
    offset = (page - 1) * PER_PAGE
    query = db.query(Event).filter(Event.is_active == True)
    if event_id and event_id != "Any":
        query = query.filter(Event.event_id == event_id)
    total = query.count()
    
    query = db.query(Event) \
        .filter(Event.is_active == True)
    if event_id and event_id != "Any":
        query = query.filter(Event.event_id == event_id)
        
    _events = query.order_by(asc(Event.id)) \
        .order_by(asc(Event.created_at)) \
        .offset(offset) \
        .limit(PER_PAGE)  \
        .all()

    event_details = db.query(EventDetails).all()
    event_details = { row.event_id : row.event_name for row in event_details }

    events = []
    for e in _events:
        e.expire_at = expire_at(e.expire_at)
        e.event_name = event_details.get(e.event_id)
        events.append(e)

    return {
        "items": events,
        "page": page,
        "per_page": PER_PAGE,
        "total": total,
    }


@app.get("/events/")
def get_items(db: Session = Depends(get_db), page: int = Query(1, ge=1)):
    offset = (page - 1) * PER_PAGE
    total = db.query(Event.event_id) \
        .distinct() \
        .count()
    
    _events = (
        db.query(
            Event.event_id,
            Event.event_name,
            func.coalesce(
                func.sum(
                    case(
                        (Event.status == Event.STATUS_SCHEDULED, Event.full_price),
                        else_=0
                    )
                ),
                0
            ).label("full_price_total")
        )
        .group_by(Event.event_id, Event.event_name)
        .order_by(asc(Event.event_name)) \
        .limit(PER_PAGE)
        .offset(offset)
        .all()
    )

    event_details = db.query(EventDetails).all()
    event_details = { row.event_id : row.event_name for row in event_details }
    events = [
        {"event_id": eid, "event_name": event_details.get(eid), "full_price_total": round(total, 2)}
        for eid, name, total in _events
    ]

    return {
        "events": events,
        "page": page,
        "per_page": PER_PAGE,
        "total": total,
    }


@app.get("/")
def index():
    return RedirectResponse("/tickets?page=1&event_id=Any")

@app.get("/tickets", response_class=HTMLResponse)
def tickets(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    event_id: str = Query(...)
):
    offset = (page - 1) * PER_PAGE
    query = db.query(Event).filter(Event.is_active == True)
    if event_id and event_id != "Any":
        query = query.filter(Event.event_id == event_id)
    total = query.count()

    query = db.query(Event) \
        .filter(Event.is_active == True)
    if event_id and event_id != "Any":
        query = query.filter(Event.event_id == event_id)
        
    _events = query.order_by(asc(Event.id)) \
        .order_by(asc(Event.created_at)) \
        .offset(offset) \
        .limit(PER_PAGE)  \
        .all()
    
    event_details = db.query(EventDetails).all()
    event_details = { row.event_id : row.event_name for row in event_details }

    events = []
    for e in _events:
        e.expire_at = expire_at(e.expire_at)
        e.event_name = event_details.get(e.event_id)
        events.append(e)

    unique_events = (
        db.query(Event)
        .distinct(Event.event_name)
        .order_by(asc(Event.event_name))
        .all()
    )

    return templates.TemplateResponse(
        "tickets.html",
        {
            "unique_events": unique_events,
            "events": events,
            "total": total,
            "per_page": PER_PAGE,
            "page": page,
            "event_id": event_id,
            "request": request,
            "Event": Event,
            "active_page": "tickets"
        },
    )


@app.get("/events", response_class=HTMLResponse)
def events(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
):
    offset = (page - 1) * PER_PAGE
    total = (
        db.query(Event.event_id)
        .distinct()
        .count()
    )
    _events = (
        db.query(
            Event.event_id,
            Event.event_name,
            func.coalesce(
                func.sum(
                    case(
                        (Event.status == Event.STATUS_SCHEDULED, Event.full_price),
                        else_=0
                    )
                ),
                0
            ).label("full_price_total")
        )
        .group_by(Event.event_id, Event.event_name)
        .order_by(asc(Event.event_name)) \
        .limit(PER_PAGE)
        .offset(offset)
        .all()
    )

    event_details = db.query(EventDetails).all()
    event_details = { row.event_id : row.event_name for row in event_details }
    events = [
        {"event_id": eid, "event_name": event_details.get(eid), "full_price_total": round(total, 2)}
        for eid, name, total in _events
    ]

    return templates.TemplateResponse(
        "events.html",
        {
            "events": events,
            "total": total,
            "per_page": PER_PAGE,
            "page": page,
            "request": request,
            "active_page": "events"
        },
    )


@app.post("/event")
def create_event(request: EventCreate, db: Session = Depends(get_db)):
    try:
        data = dict()
        try:
            for row in request.fields:
                name = row.get("name")
                val = row.get("value")
                if name and val:
                    data[name] = val
        except Exception as e:
            logger.error(e)
            return JSONResponse({"error":  "Invalid request fields"}, 500)

        required = {
            "Event ID",
            "Account",
            "Section",
            "Row",
            "Price",
            "Full price",
            "Amount",
            "Expiration",
            "Full checkout"
        }
        for k in required:
            if not data.get(k):
                error = f"Field {k} is required"
                logger.error(error)
                return JSONResponse({"error": error}, 500)

        event_details = db.query(EventDetails).filter(EventDetails.event_id == data["Event ID"]).first()
        event_name = event_details.event_name if event_details else None

        bot = db.query(BotAccount).filter(BotAccount.email == data["Account"]).first()
        cvv = bot.cvv if bot else None

        full_price = round(float(data["Full price"]), 2)
        amount = int(data["Amount"])
        if not full_price or not amount:
            error = "Invalid full price or amount"
            logger(error)
            return JSONResponse({"error": error}, 500)
        price_plus_fees = round(full_price / amount, 2)

        expire_at = None
        try:
            expire_at = datetime.fromtimestamp(int(data["Expiration"].replace("<t:", "").replace(":R>", "")))
        except Exception as e:
            logger.error(e)
            return JSONResponse({"error": "Internal server error"}, 500)

        event = Event(
            event_id=data["Event ID"],
            event_name=event_name,
            bot_email=data["Account"],
            section=data["Section"],
            row=data["Row"],
            price=float(data["Price"]),
            amount=int(data["Amount"]),
            full_price=float(data["Full price"]),
            price_plus_fees=price_plus_fees,
            expire_at=expire_at,
            encsoft_url=data["Full checkout"],
            cvv=cvv,
            status=Event.STATUS_NEW
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        return {"id": event.id}
    except Exception as e:
        logger.error(e)

    return JSONResponse({"error": "Internal server error"}, 500)

@app.post("/buy-ticket/{event_id}")
def buy_ticket(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event or event.status != Event.STATUS_NEW: # prevent duplicated request from miltiple users
        return {}

    if not event.encsoft_url or not event.cvv:
        return JSONResponse({"error": "Event checkout url or CVV is empty"}, 500)
    
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

    return JSONResponse({"error":  "Internal server error"}, 500)

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
        return JSONResponse({"error":  "Internal server error"}, 500)
