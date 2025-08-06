from pydantic import BaseModel
from typing import Optional


class EventCreate(BaseModel):
    name: str
    encsoft_url: str
    cvv: str
