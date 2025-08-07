from pydantic import BaseModel, constr, HttpUrl


class EventCreate(BaseModel):
    fields: list
