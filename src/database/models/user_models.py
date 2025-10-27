from __future__ import annotations
import enum
from datetime import datetime, date
from typing import List, TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Boolean, Integer, String, func, Enum, Text, Date, UniqueConstraint, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship

from database.models.base import Base
from database.models.movie_models import MovieRatingModel
from schemas import validators
from security.passwords import hash_password, verify_password

if TYPE_CHECKING:
    from database import MovieModel, ActivationTokenModel, PasswordResetTokenModel, RefreshTokenModel
    from database.models.movie_models import CommentModel
    from database.models.order_models import OrderModel
    from database.models.payment_models import PaymentModel
    from database.models.cart_models import CartModel


class GenderEnum(str, enum.Enum):
    MAN = "man"
    WOMAN = "woman"


class UserGroupEnum(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class UserGroupModel(Base):
    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[UserGroupEnum] = mapped_column(Enum(UserGroupEnum), nullable=False, unique=True)

    users: Mapped[List["UserModel"]] = relationship("UserModel", back_populates="group")

    def __repr__(self):
        return f"<UserGroupModel(id={self.id}, name={self.name})>"


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    _hashed_password: Mapped[str] = mapped_column("hashed_password", String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    cart: Mapped["CartModel"] = relationship("CartModel", back_populates="user")
    orders: Mapped[List["OrderModel"]] = relationship(
        "OrderModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    payments: Mapped[List["PaymentModel"]] = relationship("PaymentModel", back_populates="user")
    group_id: Mapped[int] = mapped_column(ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False)
    group: Mapped["UserGroupModel"] = relationship("UserGroupModel", back_populates="users")

    activation_token: Mapped[Optional["ActivationTokenModel"]] = relationship(
        "ActivationTokenModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    password_reset_token: Mapped[Optional["PasswordResetTokenModel"]] = relationship(
        "PasswordResetTokenModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    refresh_tokens: Mapped[List["RefreshTokenModel"]] = relationship(
        "RefreshTokenModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    profile: Mapped[Optional["UserProfileModel"]] = relationship(
        "UserProfileModel",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    comments: Mapped[List["CommentModel"]] = relationship(
        "CommentModel",
        back_populates="user",
    )

    ratings: Mapped[List["MovieRatingModel"]] = relationship(
        "MovieRatingModel",
        back_populates="user"
    )

    def __repr__(self):
        return f"<UserModel(id={self.id}, email={self.email}, is_active={self.is_active})>"

    @classmethod
    def create(cls, email: str, raw_password: str, group_id: int | Mapped[int]) -> "UserModel":
        user = cls(email=email, group_id=group_id)
        user.password = raw_password
        return user

    @property
    def password(self) -> None:
        raise AttributeError("Password is write-only. Use the setter to set the password.")

    @password.setter
    def password(self, raw_password: str) -> None:
        validators.validate_password_strength(raw_password)
        self._hashed_password = hash_password(raw_password)

    def verify_password(self, raw_password: str) -> bool:
        return verify_password(raw_password, self._hashed_password)


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    avatar: Mapped[Optional[str]] = mapped_column(String(255))
    gender: Mapped[Optional[GenderEnum]] = mapped_column(Enum(GenderEnum))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    info: Mapped[Optional[str]] = mapped_column(Text)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True)
    user: Mapped[UserModel] = relationship("UserModel", back_populates="profile")

    __table_args__ = (UniqueConstraint("user_id"),)

    def __repr__(self):
        return (
            f"<UserProfileModel(id={self.id}, first_name={self.first_name}, last_name={self.last_name}, "
            f"gender={self.gender}, date_of_birth={self.date_of_birth})>"
        )
