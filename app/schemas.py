from pydantic import BaseModel, constr, HttpUrl


class EventCreate(BaseModel):
    name: constr(min_length=1, max_length=200)
    encsoft_url: HttpUrl
    cvv: constr(pattern=r'^\d{3}$')
