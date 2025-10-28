from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CheckoutUrlResponse(BaseModel):
    checkout_url: str


class PaymentHistoryItemSchema(BaseModel):
    id: int
    created_at: datetime
    amount: Decimal
    status: str

    model_config = {
        "from_attributes": True
    }
