from datetime import datetime
from typing import List

from pydantic import BaseModel


class MovieInCartSchema(BaseModel):
    id: int
    name: str
    price: float
    genres: List[str]
    release_year: int

    model_config = {
        "from_attributes": True,
    }


class CartResponseSchema(BaseModel):
    movies: List[MovieInCartSchema]

    model_config = {
        "from_attributes": True,
    }


class AdminCartSchema(BaseModel):
    id: int
    user_email: str
    items_count: int
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class CartDetailSchema(BaseModel):
    movies: List[MovieInCartSchema]
    total_price: float

    model_config = {
        "from_attributes": True,
    }
