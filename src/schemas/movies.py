from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class CertificationSchema(BaseModel):
    id: int
    name: str
    name: Optional[str]

    model_config = {
        "from_attributes": True,
    }


class MovieRatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=10)


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class StarSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class MovieBaseSchema(BaseModel):
    name: str = Field(..., max_length=255)
    year: int
    time: int
    meta_score: float = Field(..., ge=0, le=100)
    description: str
    gross: float = Field(..., ge=0)
    price: float = Field(..., ge=0)

    model_config = {
        "from_attributes": True
    }


class MovieDetailSchema(MovieBaseSchema):
    id: int
    genres: List[GenreSchema]
    stars: List[StarSchema]
    directors: List[DirectorSchema]
    certification: CertificationSchema

    model_config = {
        "from_attributes": True,
    }


class CommentReadSchema(BaseModel):
    id: int
    text: str
    created_at: datetime
    user_id: int
    movie_id: int

    model_config = {
        "from_attributes": True,
    }


class CommentCreateSchema(BaseModel):
    text: str


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    year: int
    time: int
    imdb: float
    meta_score: float
    description: str

    model_config = {
        "from_attributes": True,
    }


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True,
    }


class MovieCreateSchema(BaseModel):
    name: str
    year: int
    time: int
    votes: int
    meta_score: float = Field(..., ge=0, le=100)
    imdb: float = Field(..., ge=0, le=5)
    description: str
    gross: float = Field(..., ge=0)
    price: float = Field(..., ge=0)
    genres: List[str]
    stars: List[str]
    directors: List[str]
    certification: str

    model_config = {
        "from_attributes": True,
    }

    @field_validator("certification", mode="before")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.upper()

    @field_validator("genres", "stars", "directors", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: List[str]) -> List[str]:
        return [item.title() for item in value]


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    time: Optional[int] = None
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    description: Optional[str] = None
    gross: Optional[float] = Field(None, ge=0)
    price: Optional[float] = Field(None, ge=0)

    model_config = {
        "from_attributes": True,
    }


class FavoriteStatusSchema(BaseModel):
    movie_id: int
    is_favorite: bool
    movie_name: str
    model_config = {"from_attributes": True}
