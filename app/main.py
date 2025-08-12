import os
import logging
import math
from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from .db import Event, EventDetails, BotAccount, get_db
from .schemas import EventCreate
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
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
    per_page = 25
    total = db.query(Event).filter(Event.is_active == True).count()
    offset = (page - 1) * per_page
    _events = (
        db.query(Event)
        .filter(Event.is_active == True)
        .order_by(asc(Event.id))
        .offset(offset)
        .limit(per_page)
        .all()
    )

    events = []
    for e in _events:
        e.expire_at = expire_at(e.expire_at)
        events.append(e)

    last_page = (total + per_page - 1) // per_page
    return {
        "items": events,
        "page": page,
        "per_page": per_page,
        "total": total,
        "last_page": last_page,
    }

@app.get("/")
def dashboard():
    return RedirectResponse("/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    page: int = Query(1, ge=1),
    event_id: str = Query(...)
):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "page": page,
            "event_id": event_id,
            "request": request,
            "Event": Event,
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
