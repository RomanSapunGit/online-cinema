import random

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from database import MovieModel, UserGroupEnum, CartItemModel, CartModel
from database.models.movie_models import CommentModel, MovieRatingModel, IsLikeEnum
from tests.utils import get_csrf_cookie_and_headers


@pytest.mark.asyncio
async def test_get_movies_empty_database(client):
    response = await client.get("/api/v1/cinema/movies/")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    expected_detail = {"detail": "No movies found."}
    assert response.json() == expected_detail, f"Expected {expected_detail}, got {response.json()}"


@pytest.mark.asyncio
async def test_get_movies_default_parameters(client, seed_database):
    response = await client.get("/api/v1/cinema/movies/")
    assert response.status_code == 200, "Expected status code 200, but got a different value"

    response_data = response.json()

    assert len(response_data["movies"]) == 5, "Expected 10 movies in the response, but got a different count"

    assert response_data["total_pages"] > 0, "Expected total_pages > 0, but got a non-positive value"
    assert response_data["total_items"] > 0, "Expected total_items > 0, but got a non-positive value"

    assert response_data["prev_page"] is None, "Expected prev_page to be None on the first page, but got a value"

    if response_data["total_pages"] > 1:
        assert response_data["next_page"] is not None, (
            "Expected next_page to be present when total_pages > 1, but got None"
        )

@pytest.mark.asyncio
async def test_mutate_operations_on_movies(client, db_session, jwt_manager, seed_user_groups, seed_users):
    user = seed_users["user"]
    access_token = jwt_manager.create_access_token({"user_id": user.id, "role": UserGroupEnum.USER})
    headers = {"Authorization": f"Bearer {access_token}"}
    movie_data = {
        "name": "New Movie",
        "year": 2000,
        "time": 12,
        "meta_score": 85.5,
        "imdb": 2.0,
        "votes": 50,
        "gross": 1000000.00,
        "price": 5000000.00,
        "description": "An amazing movie.",
        "genres": ["Action", "Adventure"],
        "stars": ["John Doe", "Jane Doe"],
        "directors": ["Hello"],
        "certification": "testing one"
    }
    response = await client.post(f"/api/v1/cinema/movies/", headers=headers, json=movie_data)
    assert response.status_code == 403, f"Expected status code forbidden (403), got {response.status_code}"

    access_token = jwt_manager.create_access_token({"user_id": user.id, "role": UserGroupEnum.MODERATOR})
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await client.post(f"/api/v1/cinema/movies/", headers=headers, json=movie_data)
    assert response.status_code == 201, f"Expected status code OK (200), got {response.status_code}"
    response_data = response.json()
    assert response_data["name"] == movie_data["name"], "Movie name does not match."
    assert response_data["year"] == movie_data["year"], "Movie year does not match."
    assert response_data["description"] == movie_data["description"], "Movie description does not match."


@pytest.mark.asyncio
async def test_create_comment(
        client,
        db_session,
        jwt_manager,
        seed_database,
        seed_users,
    mock_email_sender
):
    comments_data = {"text": "Great movie!"}
    user = seed_users["user"]
    access_token = jwt_manager.create_access_token({"user_id": user.id, "role": UserGroupEnum.USER})
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post(
        f"/api/v1/cinema/movies/1/comments",
        headers=headers,
        json=comments_data,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    created_comment = (await db_session.execute(select(CommentModel).where(CommentModel.text == "Great movie!"))).first()
    assert created_comment, "Expected comment to be created"



@pytest.mark.asyncio
@pytest.mark.parametrize("page, per_page, expected_detail", [
    (0, 10, "Input should be greater than or equal to 1"),
    (1, 0, "Input should be greater than or equal to 1"),
    (0, 0, "Input should be greater than or equal to 1"),
])
async def test_invalid_page_and_per_page(client, page, per_page, expected_detail):
    headers, cookies = await get_csrf_cookie_and_headers(client)

    response = await client.get(f"/api/v1/cinema/movies/?page={page}&per_page={per_page}", headers=headers, cookies=cookies)

    assert response.status_code == 422, (
        f"Expected status code 422 for invalid parameters, but got {response.status_code}"
    )

    response_data = response.json()

    assert "detail" in response_data, "Expected 'detail' in the response, but it was missing"

    assert any(expected_detail in error["msg"] for error in response_data["detail"]), (
        f"Expected error message '{expected_detail}' in the response details, but got {response_data['detail']}"
    )


@pytest.mark.asyncio
async def test_per_page_maximum_allowed_value(client, seed_database):
    response = await client.get("/api/v1/cinema/movies/?page=1&per_page=20")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."
    assert len(response_data["movies"]) <= 20, (
        f"Expected at most 20 movies, but got {len(response_data['movies'])}"
    )


@pytest.mark.asyncio
async def test_page_exceeds_maximum(client, db_session, seed_database):
    per_page = 10

    count_stmt = select(func.count(MovieModel.id))
    result = await db_session.execute(count_stmt)
    total_movies = result.scalar_one()

    max_page = (total_movies + per_page - 1) // per_page

    response = await client.get(f"/api/v1/cinema/movies/?page={max_page + 1}&per_page={per_page}")

    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"
    response_data = response.json()

    assert "detail" in response_data, "Response missing 'detail' field."


@pytest.mark.asyncio
async def test_movies_sorted_by_id_desc(client, db_session, seed_database):
    response = await client.get("/api/v1/cinema/movies/?page=1&per_page=10")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.id.desc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `id` in descending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movie_list_with_pagination(client, db_session, seed_database):
    page = 2
    per_page = 2
    offset = (page - 1) * per_page

    response = await client.get(f"/api/v1/cinema/movies/?page={page}&per_page={per_page}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    count_stmt = select(func.count(MovieModel.id))
    count_result = await db_session.execute(count_stmt)
    total_items = count_result.scalar_one()

    total_pages = (total_items + per_page - 1) // per_page

    assert response_data["total_items"] == total_items, "Total items mismatch."
    assert response_data["total_pages"] == total_pages, "Total pages mismatch."

    stmt = (
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert expected_movie_ids == returned_movie_ids, "Movies on the page mismatch."

    expected_prev_page = f"/cinema/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
    expected_next_page = f"/cinema/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None

    assert response_data["prev_page"] == expected_prev_page, "Previous page link mismatch."
    assert response_data["next_page"] == expected_next_page, "Next page link mismatch."


@pytest.mark.asyncio
async def test_movies_fields_match_schema(client, db_session, seed_database):
    response = await client.get("/api/v1/cinema/movies/?page=1&per_page=10")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."

    expected_fields = {"id", "name", "year", "imdb", "time", "meta_score", "description"}

    for movie in response_data["movies"]:
        assert set(movie.keys()) == expected_fields, (
            f"Movie fields do not match schema. "
            f"Expected: {expected_fields}, but got: {set(movie.keys())}"
        )


@pytest.mark.asyncio
async def test_get_movie_by_id_not_found(client):
    movie_id = 1

    response = await client.get(f"/api/v1/cinema/movies/{movie_id}/")
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    assert response_data == {"detail": "Movie with the given ID was not found."}, (
        f"Expected error message not found. Got: {response_data}"
    )


@pytest.mark.asyncio
async def test_get_movie_by_id_valid(client, db_session, seed_database):
    stmt_min = select(MovieModel.id).order_by(MovieModel.id.asc()).limit(1)
    result_min = await db_session.execute(stmt_min)
    min_id = result_min.scalars().first()

    stmt_max = select(MovieModel.id).order_by(MovieModel.id.desc()).limit(1)
    result_max = await db_session.execute(stmt_max)
    max_id = result_max.scalars().first()

    random_id = random.randint(min_id, max_id)

    stmt_movie = select(MovieModel).where(MovieModel.id == random_id)
    result_movie = await db_session.execute(stmt_movie)
    expected_movie = result_movie.scalars().first()
    assert expected_movie is not None, "Movie not found in database."

    response = await client.get(f"/api/v1/cinema/movies/{random_id}/")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert response_data["id"] == expected_movie.id, "Returned ID does not match the requested ID."
    assert response_data["name"] == expected_movie.name, "Returned name does not match the expected name."


@pytest.mark.asyncio
async def test_get_movie_by_id_fields_match_database(client, db_session, seed_database):
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.certification),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
        )
        .limit(1)
    )
    result = await db_session.execute(stmt)
    random_movie = result.scalars().first()
    assert random_movie is not None, "No movies found in the database."

    response = await client.get(f"/api/v1/cinema/movies/{random_movie.id}/")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert response_data["id"] == random_movie.id, "ID does not match."
    assert response_data["name"] == random_movie.name, "Name does not match."
    assert response_data["year"] == random_movie.year, "Year does not match."
    assert response_data["meta_score"] == random_movie.meta_score, "Meta score does not match."
    assert response_data["description"] == random_movie.description, "Description does not match."
    assert response_data["price"] == float(random_movie.price), "Price does not match."
    assert response_data["gross"] == random_movie.gross, "Revenue does not match."

    assert response_data["certification"]["id"] == random_movie.certification.id, "Certification ID does not match."
    assert response_data["certification"]["name"] == random_movie.certification.name, "Certification name does not match."

    actual_genres = sorted(response_data["genres"], key=lambda x: x["id"])
    expected_genres = sorted(
        [{"id": genre.id, "name": genre.name} for genre in random_movie.genres],
        key=lambda x: x["id"]
    )
    assert actual_genres == expected_genres, "Genres do not match."

    actual_actors = sorted(response_data["stars"], key=lambda x: x["id"])
    expected_actors = sorted(
        [{"id": actor.id, "name": actor.name} for actor in random_movie.stars],
        key=lambda x: x["id"]
    )
    assert actual_actors == expected_actors, "Stars do not match."

    actual_directors = sorted(response_data["directors"], key=lambda x: x["id"])
    expected_directors = sorted(
        [{"id": lang.id, "name": lang.name} for lang in random_movie.directors],
        key=lambda x: x["id"]
    )
    assert actual_directors == expected_directors, "Directors do not match."


@pytest.mark.asyncio
async def test_create_movie_duplicate_error(client, db_session, seed_database, jwt_manager):
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    existing_movie = result.scalars().first()
    assert existing_movie is not None, "No existing movies found in the database."

    movie_data = {
        "name": existing_movie.name,
        "year": existing_movie.year,
        "time": existing_movie.time,
        "meta_score": 90.0,
        "imdb": 2,
        "description": "Duplicate movie test.",
        "gross": 2000000.00,
        "price": 8000000.00,
        "certification": "PG-13",
        "votes": 10,
        "genres": ["Drama"],
        "stars": ["New Actor"],
        "directors": ["Spanio"]
    }

    access_token = jwt_manager.create_access_token({"user_id": 1, "role": UserGroupEnum.USER})
    client.headers.update({"Authorization": f"Bearer {access_token}"})

    response = await client.post("/api/v1/cinema/movies/", json=movie_data)
    assert response.status_code == 403, f"Expected status code 403, got {response.status_code}"

    access_token = jwt_manager.create_access_token({"user_id": 1, "role": UserGroupEnum.MODERATOR})
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    response = await client.post("/api/v1/cinema/movies/", json=movie_data)
    assert response.status_code == 409, f"Expected status code 409, but got {response.status_code}"

    response_data = response.json()
    expected_detail = (
        f"A movie with the name '{movie_data['name']}' and release date '{movie_data['year']}' already exists."
    )
    assert response_data["detail"] == expected_detail, (
        f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
    )


@pytest.mark.asyncio
async def test_delete_movie_success(client, db_session, seed_database, jwt_manager):
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    assert movie is not None, "No movies found in the database to delete."

    movie_id = movie.id
    access_token = jwt_manager.create_access_token({"user_id": 1, "role": UserGroupEnum.MODERATOR})
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    response = await client.delete(f"/api/v1/cinema/movies/{movie_id}")
    assert response.status_code == 200, f"Expected status code 204, but got {response.status_code}"

    stmt_check = select(MovieModel).where(MovieModel.id == movie_id)
    result_check = await db_session.execute(stmt_check)
    deleted_movie = result_check.scalars().first()
    assert deleted_movie is None, f"Movie with ID {movie_id} was not deleted."


@pytest.mark.asyncio
async def test_delete_movie_not_found(client, jwt_manager):
    non_existent_id = 99999
    access_token = jwt_manager.create_access_token({"user_id": 1, "role": UserGroupEnum.MODERATOR})
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    response = await client.delete(f"/api/v1/cinema/movies/{non_existent_id}")
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie with the given ID was not found."
    assert response_data["detail"] == expected_detail, (
        f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
    )


@pytest.mark.asyncio
async def test_update_movie_success(client, db_session, seed_database, jwt_manager):
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalars().first()
    assert movie is not None, "No movies found in the database to update."

    movie_id = movie.id
    update_data = {
        "name": "Updated Movie Name",
        "meta_score": 95.0,
    }
    access_token = jwt_manager.create_access_token({"user_id": 1, "role": UserGroupEnum.MODERATOR})
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    response = await client.patch(f"/api/v1/cinema/movies/{movie_id}/", json=update_data)
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()
    assert response_data["detail"] == "Movie updated successfully.", (
        f"Expected detail message: 'Movie updated successfully.', but got: {response_data['detail']}"
    )

    await db_session.rollback()

    stmt_check = select(MovieModel).where(MovieModel.id == movie_id)
    result_check = await db_session.execute(stmt_check)
    updated_movie = result_check.scalars().first()

    assert updated_movie.name == update_data["name"], "Movie name was not updated."
    assert updated_movie.meta_score == update_data["meta_score"], "Movie meta_score was not updated."


@pytest.mark.asyncio
async def test_update_movie_not_found(client, jwt_manager):
    non_existent_id = 99999
    update_data = {
        "name": "Non-existent Movie",
        "score": 90.0
    }
    access_token = jwt_manager.create_access_token({"user_id": 1, "role": UserGroupEnum.MODERATOR})
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    response = await client.patch(f"/api/v1/cinema/movies/{non_existent_id}/", json=update_data)
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie with the given ID was not found."
    assert response_data["detail"] == expected_detail, (
        f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
    )

@pytest.mark.asyncio
async def test_add_to_favorites_creates_new_entry(client, db_session, seed_database, seed_users, jwt_manager, mock_email_sender):
    user = seed_users["user"]
    movie = await db_session.get(MovieModel, 1)

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/cinema/movies/{movie.id}/favorite", headers=headers)
    assert response.status_code == 200

    rating = await db_session.scalar(
        select(MovieRatingModel).where(MovieRatingModel.user_id == user.id, MovieRatingModel.movie_id == movie.id)
    )
    assert rating is not None
    assert rating.is_favorite is True

    mock_email_sender.send_notification_email.assert_awaited_once()
    args, kwargs = mock_email_sender.send_notification_email.call_args
    assert "Inception" in kwargs["notification_text"]


@pytest.mark.asyncio
async def test_add_to_favorites_updates_existing_entry(client, db_session, seed_database, seed_users, jwt_manager, mock_email_sender):
    user = seed_users["user"]
    movie = await db_session.get(MovieModel, 1)

    rating = MovieRatingModel(movie_id=movie.id, user_id=user.id, is_favorite=False)
    db_session.add(rating)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/cinema/movies/{movie.id}/favorite", headers=headers)
    assert response.status_code == 200
    await db_session.refresh(rating)

    updated = await db_session.scalar(
        select(MovieRatingModel).where(MovieRatingModel.user_id == user.id, MovieRatingModel.movie_id == movie.id)
    )
    assert updated.is_favorite is True

    mock_email_sender.send_notification_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_to_favorites_movie_not_found(client, db_session, seed_database, seed_users, jwt_manager, mock_email_sender):
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/cinema/movies/9999/favorite", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found."

    mock_email_sender.send_notification_email.assert_not_awaited()

@pytest.mark.asyncio
async def test_remove_from_favorites_success(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.scalar(select(MovieModel).limit(1))

    rating = MovieRatingModel(movie_id=movie.id, user_id=user.id, is_favorite=True)
    db_session.add(rating)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/cinema/movies/{movie.id}/favorite", headers=headers)

    assert response.status_code == 200

    data = response.json()
    assert data["movie_id"] == movie.id
    assert data["movie_name"] == movie.name
    assert data["is_favorite"] is False
    await db_session.refresh(rating)
    updated_rating = await db_session.scalar(select(MovieRatingModel).where(MovieRatingModel.movie_id == movie.id, MovieRatingModel.user_id == user.id))
    assert updated_rating.is_favorite is False


@pytest.mark.asyncio
async def test_remove_from_favorites_not_in_favorites(client: AsyncClient, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.scalar(select(MovieModel).limit(1))

    rating = MovieRatingModel(movie_id=movie.id, user_id=user.id, is_favorite=False)
    db_session.add(rating)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/cinema/movies/{movie.id}/favorite", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found in favorites."


@pytest.mark.asyncio
async def test_remove_from_favorites_no_rating_entry(client: AsyncClient, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.scalar(select(MovieModel).limit(1))

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/cinema/movies/{movie.id}/favorite", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found in favorites."

@pytest.mark.asyncio
async def test_get_favorite_movies_success(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["admin"]

    movie = await db_session.get(MovieModel, 1)

    db_session.add(
        MovieRatingModel(movie_id=movie.id, user_id=user.id, is_favorite=True)
    )
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/cinema/movies/favorites", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 1
    assert data["movies"][0]["name"] == movie.name

@pytest.mark.asyncio
async def test_like_movie_creates_new_rating(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.get(MovieModel, 1)

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/cinema/movie/{movie.id}/like", headers=headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Movie like successfully."

    rating = await db_session.scalar(
        select(MovieRatingModel).where(
            MovieRatingModel.movie_id == movie.id,
            MovieRatingModel.user_id == user.id
        )
    )
    assert rating is not None
    assert rating.is_liked == IsLikeEnum.LIKE


@pytest.mark.asyncio
async def test_like_movie_updates_existing_rating(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.get(MovieModel, 1)

    rating = MovieRatingModel(
        movie_id=movie.id,
        user_id=user.id,
        is_liked=IsLikeEnum.DISLIKE
    )
    db_session.add(rating)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/cinema/movie/{movie.id}/like", headers=headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Movie like successfully."
    await db_session.refresh(rating)
    updated_rating = await db_session.scalar(
        select(MovieRatingModel).where(
            MovieRatingModel.movie_id == movie.id,
            MovieRatingModel.user_id == user.id
        )
    )
    assert updated_rating.is_liked == IsLikeEnum.LIKE


@pytest.mark.asyncio
async def test_dislike_movie(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.get(MovieModel, 1)

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/cinema/movie/{movie.id}/like?is_liked=Dislike",
        headers=headers
    )
    print(response.json())
    assert response.status_code == 200
    assert response.json()["message"] == "Movie dislike successfully."

    rating = await db_session.scalar(
        select(MovieRatingModel).where(
            MovieRatingModel.movie_id == movie.id,
            MovieRatingModel.user_id == user.id
        )
    )
    assert rating.is_liked == IsLikeEnum.DISLIKE


@pytest.mark.asyncio
async def test_like_movie_user_not_found(client, db_session, jwt_manager):
    fake_user_id = 999
    token = jwt_manager.create_access_token({"user_id": fake_user_id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/v1/cinema/movie/1/like", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found."

@pytest.mark.asyncio
async def test_rate_movie_creates_new_rating(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.get(MovieModel, 1)

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"rating": 8}

    response = await client.post(
        f"/api/v1/cinema/movie/{movie.id}/rate",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Movie rated 8/10 successfully."

    rating_entry = await db_session.scalar(
        select(MovieRatingModel).where(
            MovieRatingModel.user_id == user.id,
            MovieRatingModel.movie_id == movie.id,
        )
    )
    assert rating_entry is not None
    assert rating_entry.rating == 8


@pytest.mark.asyncio
async def test_rate_movie_updates_existing_rating(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.get(MovieModel, 1)

    # Seed existing rating
    existing = MovieRatingModel(movie_id=movie.id, user_id=user.id, rating=6)
    db_session.add(existing)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"rating": 9}

    response = await client.post(
        f"/api/v1/cinema/movie/{movie.id}/rate",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Movie rated 9/10 successfully."
    await db_session.refresh(existing)
    updated = await db_session.scalar(
        select(MovieRatingModel).where(
            MovieRatingModel.user_id == user.id,
            MovieRatingModel.movie_id == movie.id,
        )
    )
    assert updated.rating == 9


@pytest.mark.asyncio
async def test_rate_movie_user_not_found(client, db_session, jwt_manager):
    fake_user_id = 999
    token = jwt_manager.create_access_token({"user_id": fake_user_id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"rating": 7}

    response = await client.post(
        "/api/v1/cinema/movie/1/rate",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found."


@pytest.mark.asyncio
async def test_rate_movie_invalid_rating(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie_id = 1

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/cinema/movie/{movie_id}/rate",
        json={"rating": 15},
        headers=headers,
    )

    assert response.status_code == 422

@pytest.mark.asyncio
async def test_delete_movie_sends_email_if_movie_in_carts(client, db_session, seed_database, seed_users, jwt_manager, mock_email_sender):
    # Arrange
    admin = seed_users["admin"]
    movie = await db_session.get(MovieModel, 1)
    cart = CartModel(user_id=admin.id)
    db_session.add(cart)
    await db_session.flush()
    db_session.add(CartItemModel(cart_id=cart.id, movie_id=movie.id))
    await db_session.commit()
    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/cinema/movies/{movie.id}", headers=headers)

    assert response.status_code == 200

    call_args = mock_email_sender.send_notification_email.call_args.kwargs
    assert call_args["email"] == "test_moderator@example.com"
    assert "Inception" in call_args["notification_text"]
