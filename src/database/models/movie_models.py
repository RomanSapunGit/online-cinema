from __future__ import annotations
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DECIMAL, ForeignKey, UniqueConstraint, Table, Column
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
import uuid

from database.models.base import Base


if TYPE_CHECKING:
    from database.models.order_models import OrderItemModel
    from database.models.cart_models import CartItemModel


movie_genres = Table(
    "movies_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id"), primary_key=True),
)

movie_stars = Table(
    "movies_stars",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("star_id", ForeignKey("stars.id"), primary_key=True),
)

movie_directors = Table(
    "movies_directors",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id"), primary_key=True),
    Column("director_id", ForeignKey("directors.id"), primary_key=True),
)

class GenreModel(Base):
    __tablename__ = "genres"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    movies: Mapped[List["MovieModel"]] = relationship(
        "MovieModel",
        secondary=movie_genres,
        back_populates="genres"
    )


class StarModel(Base):
    __tablename__ = "stars"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    movies: Mapped[List["MovieModel"]] = relationship(
        "MovieModel",
        secondary=movie_stars,
        back_populates="stars"
    )


class DirectorModel(Base):
    __tablename__ = "directors"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    movies: Mapped[List["MovieModel"]] = relationship(
        "MovieModel",
        secondary=movie_directors,
        back_populates="directors"
    )


class CertificationModel(Base):
    __tablename__ = "certifications"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    movies: Mapped[List["MovieModel"]] = relationship(
        "MovieModel",
        back_populates="certification",
    )


class MovieModel(Base):
    __tablename__ = "movies"
    id: Mapped[int] = mapped_column(primary_key=True, unique=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    year: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[int] = mapped_column(nullable=False)
    imdb: Mapped[float] = mapped_column(nullable=False)
    votes: Mapped[int] = mapped_column(nullable=False)
    meta_score: Mapped[float] = mapped_column(nullable=True)
    gross: Mapped[float] = mapped_column(nullable=True)
    description: Mapped[str] = mapped_column(nullable=False)
    price: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 2), nullable=False)
    certification_id: Mapped[int] = mapped_column(ForeignKey("certifications.id"), nullable=False)
    certification: Mapped["CertificationModel"] = relationship(
        "CertificationModel",
        back_populates="movie",
        cascade="all, delete-orphan"
    )
    cart_items: Mapped[List["CartItemModel"]] = relationship(
        "CartItemModel",
        back_populates="movie",
        cascade="all, delete-orphan"
    )
    order_items: Mapped[List["OrderItemModel"]] = relationship("OrderItemModel", back_populates="movies")
    genres: Mapped[list["GenreModel"]] = relationship(
        "GenreModel",
        secondary=movie_genres,
        back_populates="movies"
    )
    stars: Mapped[list["StarModel"]] = relationship(
        "StarModel",
        secondary=movie_stars,
        back_populates="movies"
    )
    directors: Mapped[list["DirectorModel"]] = relationship(
        "DirectorModel",
        secondary=movie_directors,
        back_populates="movies"
    )
    __table_args__ = (
        UniqueConstraint("name", "year", "time"),
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.desc()]

    def __repr__(self) -> str:
        return f"Movie(id={self.id!r}, name={self.name!r}, price={self.price!r})"
