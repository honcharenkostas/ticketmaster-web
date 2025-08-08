import discord
import os
import logging
from datetime import datetime
from .db import Event, EventDetails, BotAccount, get_db
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
db = get_db()
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Required to read message text
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")

@client.event
async def on_message(msg):
    if msg.channel.id == os.getenv("DISCORD_CHANNEL_ID") and not msg.author.bot:
        logger.info(f"[{msg.author}] {msg.content}")

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


client.run(os.getenv("DISCORD_BOT_TOKEN"))
