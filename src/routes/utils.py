from typing import Optional, Literal
from urllib.parse import urlencode

from sqlalchemy import select, func, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from database import MovieModel, StarModel, DirectorModel
from schemas import MovieListResponseSchema, MovieListItemSchema


async def fetch_movie_catalog(
    db: AsyncSession,
    base_stmt=None,
    page: int = 1,
    per_page: int = 5,
    search: Optional[str] = None,
    release_year: Optional[int] = None,
    min_rating: Optional[float] = None,
    max_rating: Optional[float] = None,
    sort_by: Optional[Literal["price", "release_date", "popularity", "rating"]] = None,
    sort_order: Optional[Literal["asc", "desc"]] = "asc",
    base_url: str = "/cinema/movies/",
) -> MovieListResponseSchema:
    """
    Fetches a paginated catalog of movies from the database with optional filtering and sorting.

    This function allows filtering by release year, rating range, and search term (matching movie names,
    descriptions, stars, or directors). Sorting can be applied on price, release date, popularity, or rating.
    Pagination is handled via `page` and `per_page` parameters, and previous/next page URLs are generated
    automatically.

    Args:
        db (AsyncSession): Async SQLAlchemy session used to query the database.
        base_stmt (Optional[select]): Optional SQLAlchemy select statement to start from.
        page (int, optional): Page number to fetch (1-based). Defaults to 1.
        per_page (int, optional): Number of movies per page. Defaults to 5.
        search (Optional[str], optional): Search term to filter movies, stars, and directors. Defaults to None.
        release_year (Optional[int], optional): Filter movies by release year. Defaults to None.
        min_rating (Optional[float], optional): Minimum meta score for filtering movies. Defaults to None.
        max_rating (Optional[float], optional): Maximum meta score for filtering movies. Defaults to None.
        sort_by (Optional[Literal["price", "release_date", "popularity", "rating"]], optional):
        Column to sort by. Defaults to None.
        sort_order (Optional[Literal["asc", "desc"]], optional): Sorting order, either ascending or
        descending. Defaults to "asc".
        base_url (str, optional): Base URL for building pagination links. Defaults to "/cinema/movies/".

    Returns:
        MovieListResponseSchema: A Pydantic schema containing:
            - movies: List of `MovieListItemSchema` for the current page
            - prev_page: URL for the previous page or None
            - next_page: URL for the next page or None
            - total_pages: Total number of pages
            - total_items: Total number of movies matching the filters

    Raises:
        HTTPException 404: If no movies match the filters or if `page` exceeds the total number of pages.
    """
    offset = (page - 1) * per_page
    stmt = base_stmt if base_stmt is not None else select(MovieModel).distinct()

    filters = []
    if release_year is not None:
        filters.append(MovieModel.year == release_year)
    if min_rating is not None:
        filters.append(MovieModel.meta_score >= min_rating)
    if max_rating is not None:
        filters.append(MovieModel.meta_score <= max_rating)

    if filters:
        stmt = stmt.where(*filters)

    if search:
        search_term = f"%{search}%"
        stmt = (
            stmt.outerjoin(MovieModel.stars)
            .outerjoin(MovieModel.directors)
            .where(
                (MovieModel.name.ilike(search_term))
                | (MovieModel.description.ilike(search_term))
                | (StarModel.name.ilike(search_term))
                | (DirectorModel.name.ilike(search_term))
            )
        )

    total_items = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if not total_items:
        raise HTTPException(status_code=404, detail="No movies found.")

    if sort_by:
        sort_col = getattr(MovieModel, sort_by, None)
        if sort_col is not None:
            stmt = stmt.order_by(asc(sort_col) if sort_order == "asc" else desc(sort_col))
    else:
        default_order = MovieModel.default_order_by()
        if default_order:
            stmt = stmt.order_by(*default_order)

    stmt = stmt.offset(offset).limit(per_page)
    result = await db.execute(stmt)
    movies = result.scalars().all()
    total_pages = (total_items + per_page - 1) // per_page
    if page > total_pages:
        raise HTTPException(
            detail="param page exceeds max",
            status_code=404,
        )

    def build_url(page_number: int) -> Optional[str]:
        if not (1 <= page_number <= total_pages):
            return None
        params = {
            "page": page_number,
            "per_page": per_page,
            "search": search,
            "release_year": release_year,
            "min_rating": min_rating,
            "max_rating": max_rating,
            "sort_by": sort_by,
            "sort_order": sort_order if sort_by else None,
        }
        query = urlencode({k: v for k, v in params.items() if v is not None})
        return f"{base_url}?{query}"

    return MovieListResponseSchema(
        movies=[MovieListItemSchema.model_validate(m) for m in movies],
        prev_page=build_url(page - 1),
        next_page=build_url(page + 1),
        total_pages=total_pages,
        total_items=total_items,
    )
