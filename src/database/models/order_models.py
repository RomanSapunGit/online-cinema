from __future__ import annotations
import enum
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import ForeignKey, DateTime, func, Enum, DECIMAL
from sqlalchemy.orm import mapped_column, Mapped, relationship

from database.models.base import Base


if TYPE_CHECKING:
    from database import MovieModel
    from database.models.payment_models import PaymentModel, PaymentItemModel
    from database.models.user_models import UserModel


class OrderStatusEnum(str, enum.Enum):
    PENDING = "Pending"
    PAID = "Paid"
    CANCELED = "Canceled"


class OrderModel(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="orders",
        cascade="all, delete-orphan"
    )
    order_items: Mapped[List["OrderItemModel"]] = relationship("OrderItemModel", back_populates="orders")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    status: Mapped[OrderStatusEnum] = mapped_column(Enum(OrderStatusEnum), nullable=False)
    total_amount: Mapped[Optional[DECIMAL]] = mapped_column(DECIMAL(10, 2))
    payments: Mapped[List["PaymentModel"]] = relationship("PaymentModel", back_populates="order")


class OrderItemModel(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="order_item")
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="order_item")
    payment_items: Mapped[List["PaymentItemModel"]] = relationship("PaymentItemModel", back_populates="order_item")
    price_at_order: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 2), nullable=False)
