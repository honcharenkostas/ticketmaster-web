import requests
import os
import time
import logging
import re
from datetime import datetime
from db import SessionLocal, Event, EventDetails, BotAccount, AutoAprovalRules
from dotenv import load_dotenv


load_dotenv()
os.makedirs(os.getenv("LOG_DIR"), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.getenv("LOG_DIR"), "discrord_listener.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
db = SessionLocal()
ids = set()
start_time = datetime.now()
EVENT_ROWS_MAPPER = {
    "A": 1, 
    "B": 2, 
    "C": 3, 
    "D": 4, 
    "E": 5, 
    "F": 6, 
    "G": 7, 
    "H": 8, 
    "I": 9, 
    "J": 10,
    "K": 11, 
    "L": 12, 
    "M": 13, 
    "N": 14, 
    "O": 15, 
    "P": 16, 
    "Q": 17, 
    "R": 18, 
    "S": 19,
    "T": 20, 
    "U": 21, 
    "V": 22, 
    "W": 23, 
    "X": 24, 
    "Y": 25, 
    "Z": 26, 
    "AA": 27, 
    "BB": 28,
    "CC": 29, 
    "DD": 30, 
    "EE": 31, 
    "FF": 32, 
    "GG": 33, 
    "HH": 34,
    "II": 35, 
    "JJ": 36,
    "KK": 37, 
    "LL": 38, 
    "MM": 39, 
    "NN": 40, 
    "OO": 41, 
    "PP": 42, 
    "QQ": 43, 
    "RR": 44,
    "SS": 45, 
    "TT": 46, 
    "UU": 47, 
    "VV": 48, 
    "WW": 49, 
    "XX": 50, 
    "YY": 51, 
    "ZZ": 52
}

def range_to_x(num):
    if 100 <= num <= 599:
        return f"{(num // 100) * 100}x"
    return None


def is_high_quality_ticket(event):
    section = int(event.section.strip()) if event.section else None
    section = range_to_x(section) if section else None
    row = event.row.strip() if event.row else None
    if row and not re.match(r'[0-9]+', row):
        row = EVENT_ROWS_MAPPER.get(row)
    try:
        row = int(row)
    except:
        row = None

    if not section or not row:
        return False
    
    rule = db.query(AutoAprovalRules).filter(
        AutoAprovalRules.row >= row,
        AutoAprovalRules.section == str(section)
    ).first()

    return True if rule else False


def schedule_to_buy(event):
    if not event.encsoft_url or not event.cvv:
        logger.error("Empty encsoft_url or cvv")
        return False
    
    try:
        resp = requests.post(
            url=os.getenv("CHECKOUT_BOT_API_URL"),
            json={
                "encsoft_url": event.encsoft_url,
                "cvv": event.cvv,
            }
        )

        if resp.status_code == 200:
            return True
    except Exception as e:
        logger.error(e)

    return False


def run():
    try:
        # TODO: check paginated result
        response = requests.get(os.getenv('DISCORD_SERVER_SIDE_URL'))

        if response.status_code == 200:
            messages = response.json()
            for msg in messages:
                id = msg.get("messageId")
                try:
                    posted_at = int(msg.get("timestamp"))
                except:
                    posted_at = None

                if not id:
                    continue

                if not id or not posted_at or posted_at < start_time.timestamp():
                    continue

                if id in ids:
                    continue

                ids.add(id)

                # prepare data
                data = dict()
                try:
                    for row in msg["embeds"][0]["fields"]:
                        name = row.get("name")
                        val = row.get("value")
                        if name and val:
                            data[name] = val
                except Exception as e:
                    logger.error(e)
                    return
                
                # validate
                required = {"Event ID", "Account", "Section", "Row", "Price", "Full price", "Amount", "Expiration", "Full checkout"}
                for k in required:
                    if not data.get(k):
                        logger.error(f"Field {k} is required")
                        return

                # enrich
                event_details = db.query(EventDetails).filter(EventDetails.event_id == data["Event ID"]).first()
                event_name = event_details.event_name if event_details else None
                bot = db.query(BotAccount).filter(BotAccount.email == data["Account"]).first()
                cvv = bot.cvv if bot else None
                full_price = round(float(data["Full price"]), 2)
                amount = int(data["Amount"])
                if not full_price or not amount:
                    logger.error("Invalid full price or amount")
                    return
                
                price_plus_fees = round(full_price / amount, 2)
                expire_at = None
                try:
                    expire_at = datetime.fromtimestamp(int(data["Expiration"].replace("<t:", "").replace(":R>", "")))
                except Exception as e:
                    logger.error(e)
                    return

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

                # Auto aproval stuff
                if is_high_quality_ticket(event):
                    if schedule_to_buy(event):
                        event.status = Event.STATUS_SCHEDULED
                    else:
                        event.status = Event.STATUS_FAILED

                db.add(event)
                db.commit()
                db.refresh(event)
        else:
            logger.error("Error:", response.status_code, response.text)
    except Exception as e:
        logger.error(e)


def _run():
    '''
    @deprecated method because of discord rate limit issue
    '''
    try:
        url = f"https://discord.com/api/v10/channels/{os.getenv('DISCORD_CHANNEL_ID')}/messages"
        headers = {
            "Authorization": f"Bot {os.getenv('DISCORD_BOT_TOKEN')}"
        }
        params = {
            "limit": 50  # how many messages to fetch, max 100
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            messages = response.json()
            for msg in messages:
                id = msg.get("id")
                try:
                    posted_at = datetime.fromisoformat(msg.get("timestamp"))
                except:
                    posted_at = None

                if not id or not posted_at or posted_at.timestamp() < start_time.timestamp():
                    continue

                if id in ids:
                    continue

                ids.add(id)

                # prepare data
                data = dict()
                try:
                    for row in msg["embeds"][0]["fields"]:
                        name = row.get("name")
                        val = row.get("value")
                        if name and val:
                            data[name] = val
                except Exception as e:
                    logger.error(e)
                    return
                
                # validate
                required = {"Event ID", "Account", "Section", "Row", "Price", "Full price", "Amount", "Expiration", "Full checkout"}
                for k in required:
                    if not data.get(k):
                        logger.error(f"Field {k} is required")
                        return

                # enrich
                event_details = db.query(EventDetails).filter(EventDetails.event_id == data["Event ID"]).first()
                event_name = event_details.event_name if event_details else None
                bot = db.query(BotAccount).filter(BotAccount.email == data["Account"]).first()
                cvv = bot.cvv if bot else None
                full_price = round(float(data["Full price"]), 2)
                amount = int(data["Amount"])
                if not full_price or not amount:
                    logger.error("Invalid full price or amount")
                    return
                
                price_plus_fees = round(full_price / amount, 2)
                expire_at = None
                try:
                    expire_at = datetime.fromtimestamp(int(data["Expiration"].replace("<t:", "").replace(":R>", "")))
                except Exception as e:
                    logger.error(e)
                    return

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
        else:
            logger.error("Error:", response.status_code, response.text)
    except Exception as e:
        logger.error(e)

try:
    while True:
        logger.info("Get messages...")
        run()
        time.sleep(3)
except KeyboardInterrupt:
    logger.info("Shutting down ...")
