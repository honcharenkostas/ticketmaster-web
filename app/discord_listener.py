import requests
import os
import time
import logging
from datetime import datetime
from db import Event, EventDetails, BotAccount, SessionLocal
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


def run():
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
