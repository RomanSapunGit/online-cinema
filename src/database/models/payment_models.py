from __future__ import annotations
import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, DateTime, func, Enum, DECIMAL, String
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm import mapped_column

from database.models.base import Base


if TYPE_CHECKING:
    from database.models.order_models import OrderModel, OrderItemModel
    from database.models.user_models import UserModel


class StatusEnum(str, enum.Enum):
    SUCCESSFUL = "Successful"
    CANCELED = "Canceled"
    REFUNDED = "Refunded"


class PaymentModel(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="payments")
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="payments")
    payment_items: Mapped[List["PaymentItemModel"]] = relationship("PaymentItemModel", back_populates="payment")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    status: Mapped[StatusEnum] = mapped_column(Enum(StatusEnum), nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    external_payment_id: Mapped[Optional[str]] = mapped_column(String(500))


class PaymentItemModel(Base):
    __tablename__ = "payment_items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)
    payment: Mapped["PaymentModel"] = relationship("PaymentModel", back_populates="payment_items")
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), nullable=False)
    order_item: Mapped["OrderItemModel"] = relationship("OrderItemModel", back_populates="payment_items")
    price_at_payment: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 2), nullable=False)
