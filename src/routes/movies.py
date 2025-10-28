from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from config import get_accounts_email_notificator
from database import get_db, MovieModel, UserModel, UserGroupModel, UserGroupEnum
from database import (
    CertificationModel,
    GenreModel,
    StarModel,
    DirectorModel
)
from database.models.cart_models import CartItemModel
from database.models.movie_models import IsLikeEnum, MovieRatingModel, CommentModel
from notifications import EmailSenderInterface
from routes.utils import fetch_movie_catalog
from schemas import (
    MovieListResponseSchema,
    MovieDetailSchema, MessageResponseSchema
)
from schemas.movies import MovieCreateSchema, MovieUpdateSchema, CommentCreateSchema, CommentReadSchema, \
    MovieRatingRequest, FavoriteStatusSchema
from security.dependenices import require_moderator_or_admin, require_authentication

router = APIRouter()


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movie_list(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20),
        search: Optional[str] = None,
        release_year: Optional[int] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        sort_by: Optional[Literal["price", "release_date", "popularity", "rating"]] = None,
        sort_order: Optional[Literal["asc", "desc"]] = "asc",
        db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    """
    Get a paginated list of movies.

    Args:
        page (int, optional): Page number. Default is 1.
        per_page (int, optional): Number of movies per page. Default is 10, max is 20.
        search (str, optional): Search term for movie name.
        release_year (int, optional): Filter movies by release year.
        min_rating (float, optional): Filter movies with minimum rating.
        max_rating (float, optional): Filter movies with maximum rating.
        sort_by (str, optional): Field to sort by. One of ["price", "release_date", "popularity", "rating"].
        sort_order (str, optional): Sort order. Either "asc" or "desc". Default is "asc".
        db (AsyncSession): Database session (injected by FastAPI).

    Returns:
        MovieListResponseSchema: Paginated list of movies.
    """
    return await fetch_movie_catalog(
        db=db,
        page=page,
        per_page=per_page,
        search=search,
        release_year=release_year,
        min_rating=min_rating,
        max_rating=max_rating,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/movies/{movie_id}/favorite", status_code=200)
async def add_to_favorites(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
):
    """
    Add a movie to the authenticated user's favorites list.

    Args:
        movie_id (int): ID of the movie to add to favorites.
        db (AsyncSession): Database session.
        user_id (int): ID of the authenticated user (injected by dependency).
        email_sender (EmailSenderInterface): Email sender dependency.

    Returns:
        FavoriteStatusSchema: Information about the favorite status of the movie.

    Raises:
        HTTPException 404: If the movie does not exist.
    """
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    stmt = select(MovieRatingModel).where(
        MovieRatingModel.movie_id == movie_id,
        MovieRatingModel.user_id == user_id
    )
    result = await db.execute(stmt)
    rating_entry = result.scalar_one_or_none()

    if rating_entry:
        rating_entry.is_favorite = True
    else:
        rating_entry = MovieRatingModel(
            movie_id=movie_id,
            user_id=user_id,
            is_favorite=True
        )
        db.add(rating_entry)
    await db.commit()
    user = await db.get(UserModel, user_id)
    title = "Favorites list change"
    await email_sender.send_notification_email(
        email=user.email,
        subject=title,
        notification_text=f"Movie with name {movie.name} is now in your favorite list!",
        notification_title=title
    )
    return FavoriteStatusSchema(
        movie_id=movie.id, is_favorite=rating_entry.is_favorite, movie_name=movie.name
    )


@router.delete("/movies/{movie_id}/favorite", status_code=200)
async def remove_from_favorites(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
) -> FavoriteStatusSchema:
    """
    Remove a movie from the authenticated user's favorites list.

    Args:
        movie_id (int): ID of the movie to remove from favorites.
        db (AsyncSession): Database session.
        user_id (int): ID of the authenticated user.

    Returns:
        FavoriteStatusSchema: Updated favorite status of the movie.

    Raises:
        HTTPException 404: If the movie is not found in the user's favorites.
    """
    stmt = (select(MovieRatingModel)
            .options(selectinload(MovieRatingModel.movie))
            .where(MovieRatingModel.movie_id == movie_id,
                   MovieRatingModel.user_id == user_id
                   ))
    result = await db.execute(stmt)
    rating_entry = result.scalar_one_or_none()

    if not rating_entry or not rating_entry.is_favorite:
        raise HTTPException(status_code=404, detail="Movie not found in favorites.")

    rating_entry.is_favorite = False
    await db.commit()

    return FavoriteStatusSchema(
        movie_id=rating_entry.movie.id, is_favorite=rating_entry.is_favorite, movie_name=rating_entry.movie.name
    )


@router.get("/movies/favorites", response_model=MovieListResponseSchema)
async def get_favorite_movies(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20),
        search: Optional[str] = None,
        release_year: Optional[int] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        sort_by: Optional[Literal["price", "release_date", "popularity", "rating"]] = None,
        sort_order: Optional[Literal["asc", "desc"]] = "asc",
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
) -> MovieListResponseSchema:
    """
    Get a paginated list of the authenticated user's favorite movies.

    Args:
        page (int, optional): Page number. Defaults to 1.
        per_page (int, optional): Number of movies per page. Defaults to 10, max 20.
        search (str, optional): Search movies by name.
        release_year (int, optional): Filter movies by release year.
        min_rating (float, optional): Minimum movie rating filter.
        max_rating (float, optional): Maximum movie rating filter.
        sort_by (str, optional): Sort by one of ["price", "release_date", "popularity", "rating"].
        sort_order (str, optional): Sort order "asc" or "desc". Defaults to "asc".
        db (AsyncSession): Database session.
        user_id (int): Authenticated user ID.

    Returns:
        MovieListResponseSchema: List of favorite movies with pagination.
    """
    base_stmt = (
        select(MovieModel)
        .join(MovieRatingModel, MovieRatingModel.movie_id == MovieModel.id)
        .where(
            MovieRatingModel.user_id == user_id,
            MovieRatingModel.is_favorite.is_(True)
        )
        .distinct()
    )

    return await fetch_movie_catalog(
        db=db,
        base_stmt=base_stmt,
        page=page,
        per_page=per_page,
        search=search,
        release_year=release_year,
        min_rating=min_rating,
        max_rating=max_rating,
        sort_by=sort_by,
        sort_order=sort_order,
        base_url="/theater/movies/favorites",
    )


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    status_code=201
)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db),
        _: int = Depends(require_moderator_or_admin)
) -> MovieDetailSchema:
    """
    Create a new movie. Requires moderator or admin permissions.

    Args:
        movie_data (MovieCreateSchema): Movie creation data
        including name, year, genres, stars, directors, price,
        rating, etc.
        db (AsyncSession): Database session.
        _ (int): Placeholder for authorization dependency.

    Returns:
        MovieDetailSchema: Full details of the created movie.

    Raises:
        HTTPException 409: If a movie with the same name and year already exists.
        HTTPException 400: If input data is invalid.
    """
    existing_stmt = select(MovieModel).where(
        (MovieModel.name == movie_data.name),
        (MovieModel.year == movie_data.year)
    )
    existing_result = await db.execute(existing_stmt)
    existing_movie = existing_result.scalars().first()

    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A movie with the name '{movie_data.name}' and release date "
                f"'{movie_data.year}' already exists."
            )
        )

    try:
        cert_stmt = select(CertificationModel).where(CertificationModel.name == movie_data.certification)
        cert_result = await db.execute(cert_stmt)
        certification = cert_result.scalars().first()
        if not certification:
            certification = CertificationModel(name=movie_data.certification)
            db.add(certification)
            await db.flush()

        genres = []
        for genre_name in movie_data.genres:
            genre_stmt = select(GenreModel).where(GenreModel.name == genre_name)
            genre_result = await db.execute(genre_stmt)
            genre = genre_result.scalars().first()

            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                await db.flush()
            genres.append(genre)

        stars = []
        for star_name in movie_data.stars:
            star_stmt = select(StarModel).where(StarModel.name == star_name)
            star_result = await db.execute(star_stmt)
            actor = star_result.scalars().first()

            if not actor:
                actor = StarModel(name=star_name)
                db.add(actor)
                await db.flush()
            stars.append(actor)

        directors = []
        for director_name in movie_data.directors:
            dir_stmt = select(DirectorModel).where(DirectorModel.name == director_name)
            dir_result = await db.execute(dir_stmt)
            director = dir_result.scalars().first()

            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                await db.flush()
            directors.append(director)

        movie = MovieModel(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            description=movie_data.description,
            gross=movie_data.gross,
            price=movie_data.price,
            directors=directors,
            genres=genres,
            stars=stars,
            certification=certification,
        )
        db.add(movie)
        await db.commit()
        await db.refresh(movie, ["genres", "stars", "directors"])

        return MovieDetailSchema.model_validate(movie)

    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid input data: {e}")


@router.post("/movie/{movie_id}/like", status_code=200)
async def like_movie(
        movie_id: int,
        is_liked: IsLikeEnum = IsLikeEnum.LIKE,
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
) -> MessageResponseSchema:
    """
    Like or dislike a movie.

    Args:
        movie_id (int): ID of the movie to like/dislike.
        is_liked (IsLikeEnum): LIKE or DISLIKE. Defaults to LIKE.
        db (AsyncSession): Database session.
        user_id (int): Authenticated user ID.

    Returns:
        MessageResponseSchema: Confirmation message.

    Raises:
        HTTPException 404: If the user does not exist.
    """
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    current_user = result.scalar_one_or_none()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found.")

    stmt = select(MovieRatingModel).where(
        MovieRatingModel.movie_id == movie_id,
        MovieRatingModel.user_id == current_user.id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.is_liked = is_liked
    else:
        new_rating = MovieRatingModel(
            movie_id=movie_id,
            user_id=current_user.id,
            is_liked=is_liked
        )
        db.add(new_rating)

    await db.commit()
    return MessageResponseSchema(message=f"Movie {is_liked.value.lower()} successfully.")


@router.post("/movie/{movie_id}/rate", status_code=200)
async def rate_movie(
        movie_id: int,
        payload: MovieRatingRequest,
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
) -> MessageResponseSchema:
    """
    Rate a movie.

    Args:
        movie_id (int): ID of the movie to rate.
        payload (MovieRatingRequest): Rating data (0-10).
        db (AsyncSession): Database session.
        user_id (int): Authenticated user ID.

    Returns:
        MessageResponseSchema: Confirmation message with the rating.

    Raises:
        HTTPException 404: If the user does not exist.
    """
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    current_user = result.scalar_one_or_none()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found.")

    stmt = select(MovieRatingModel).where(
        MovieRatingModel.movie_id == movie_id,
        MovieRatingModel.user_id == current_user.id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.rating = payload.rating
    else:
        new_rating = MovieRatingModel(
            movie_id=movie_id,
            user_id=current_user.id,
            rating=payload.rating
        )
        db.add(new_rating)

    await db.commit()

    return MessageResponseSchema(message=f"Movie rated {payload.rating}/10 successfully.")


@router.post("/movies/{movie_id}/comments", response_model=CommentReadSchema)
async def add_comment(
        movie_id: int,
        payload: CommentCreateSchema,
        db: AsyncSession = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
        user_id: int = Depends(require_authentication),
) -> CommentReadSchema:
    """
    Add a comment to a movie. Sends notification email to the user.

    Args:
        movie_id (int): ID of the movie.
        payload (CommentCreateSchema): Comment text.
        db (AsyncSession): Database session.
        email_sender (EmailSenderInterface): Email sender dependency.
        user_id (int): Authenticated user ID.

    Returns:
        CommentReadSchema: Details of the created comment.

    Raises:
        HTTPException 404: If movie or user does not exist.
    """
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    user = await db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    comment = CommentModel(text=payload.text, movie_id=movie_id, user_id=user_id)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    title = f"Comment for '{movie.name}'"
    await email_sender.send_notification_email(
        email=user.email,
        subject=title,
        notification_title="Your comment was published!",
        notification_text=f"Your comment on '{movie.name}' was posted successfully!"
    )

    return CommentReadSchema.model_validate(comment)


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    """
    Retrieve detailed information about a movie by its ID.

    Args:
        movie_id (int): ID of the movie.
        db (AsyncSession): Database session.

    Returns:
        MovieDetailSchema: Full details of the movie including genres, directors, stars, certification, and comments.

    Raises:
        HTTPException 404: If the movie does not exist.
    """
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.certification),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
            joinedload(MovieModel.comments)
        )
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )
    return MovieDetailSchema.model_validate(movie)


@router.delete(
    "/movies/{movie_id}",
    status_code=200
)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        _: int = Depends(require_moderator_or_admin),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Delete a movie. Requires moderator or admin permissions.
    Sends email notifications if the movie exists in user carts.

    Args:
        movie_id (int): ID of the movie to delete.
        db (AsyncSession): Database session.
        _ (int): Placeholder for authorization dependency.
        email_sender (EmailSenderInterface): Email sender dependency.

    Returns:
        MessageResponseSchema: Confirmation message of deletion.

    Raises:
        HTTPException 404: If the movie does not exist.
    """
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )
    exists_query = select(
        exists().where(CartItemModel.movie_id == movie_id)
    )
    result = await db.execute(exists_query)
    movie_in_carts = result.scalar()
    if movie_in_carts:
        moderators_group = await db.execute(
            select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.MODERATOR))
        moderators_group = moderators_group.scalar()
        moderators_result = await db.execute(
            select(UserModel).where(UserModel.group == moderators_group)
        )
        moderators = moderators_result.scalars().all()
        title = "Moderator alert: Movie deletion"
        for moderator in moderators:
            await email_sender.send_notification_email(
                email=moderator.email,
                subject=title,
                notification_text=(
                    f"The movie '{movie.name}' (ID: {movie.id}) is being deleted, "
                    f"but currently exists in  user carts."
                ),
                notification_title=title
            )
    await db.delete(movie)
    await db.commit()

    return MessageResponseSchema(message="Movie deleted successfully.")


@router.patch(
    "/movies/{movie_id}/",
)
async def update_movie(
        movie_id: int,
        movie_data: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db),
        _: int = Depends(require_moderator_or_admin)
) -> dict:
    """
    Update movie information. Only provided fields will be updated. Requires moderator or admin permissions.

    Args:
        movie_id (int): ID of the movie to update.
        movie_data (MovieUpdateSchema): Fields to update.
        db (AsyncSession): Database session.
        _ (int): Placeholder for authorization dependency.

    Returns:
        dict: Detail message confirming the update.

    Raises:
        HTTPException 404: If the movie does not exist.
        HTTPException 400: If input data is invalid.
    """
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Movie updated successfully."}
