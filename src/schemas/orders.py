from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel


class MovieInOrderSchema(BaseModel):
    id: int
    name: str
    year: int
    price: Decimal

    model_config = {
        "from_attributes": True,
    }


class OrderResponseSchema(BaseModel):
    id: int
    created_at: datetime
    status: str
    user_id: int
    total_amount: Decimal
    movies: List[MovieInOrderSchema]

    model_config = {
        "from_attributes": True,
    }


class OrderItemSchema(BaseModel):
    id: int
    movie: MovieInOrderSchema
    model_config = {
        "from_attributes": True,
    }


class CreatedOrderResponseSchema(BaseModel):
    id: int
    created_at: datetime
    status: str
    user_id: int
    total_amount: Decimal
    order_items: List[OrderItemSchema]
    model_config = {
        "from_attributes": True,
    }
