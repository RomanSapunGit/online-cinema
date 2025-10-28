import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import MovieModel, UserGroupEnum, GenreModel
from database.models.cart_models import CartItemModel, CartModel
from database.models.order_models import OrderItemModel, OrderStatusEnum, OrderModel
from database.models.payment_models import StatusEnum, PaymentModel, PaymentItemModel


@pytest.mark.asyncio
async def test_add_movie_to_cart_success(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    user_id = user.id

    movie_result = await db_session.execute(select(MovieModel).limit(1))
    movie = movie_result.scalar_one()

    access_token = jwt_manager.create_access_token({"user_id": user_id})
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post(f"/api/v1/carts/movies/{movie.id}", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["message"] == "Movie added to cart successfully."

    result = await db_session.execute(
        select(CartItemModel).where(CartItemModel.movie_id == movie.id)
    )
    item = result.scalar_one_or_none()
    assert item, "Expected new CartItemModel to be created"


@pytest.mark.asyncio
async def test_add_movie_to_cart_already_in_cart(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    await db_session.refresh(cart)

    movie = await db_session.scalar(select(MovieModel).limit(1))
    existing_item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
    db_session.add(existing_item)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": cart.user_id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/carts/movies/{movie.id}", headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Movie already in cart."


@pytest.mark.asyncio
async def test_add_movie_to_cart_already_purchased(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.scalar(select(MovieModel).limit(1))

    order = OrderModel(user_id=user.id, status=OrderStatusEnum.PAID)
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)

    order_item = OrderItemModel(order_id=order.id, movie_id=movie.id, price_at_order=movie.meta_score)
    payment = PaymentModel(user_id=user.id, order_id=order.id, status=StatusEnum.SUCCESSFUL, amount=movie.meta_score)
    payment_item = PaymentItemModel(payment_id=None, order_item_id=None, price_at_payment=movie.meta_score)

    db_session.add_all([order, order_item, payment])
    await db_session.flush()
    await db_session.refresh(payment)

    payment_item.payment_id = payment.id
    payment_item.order_item_id = order_item.id
    db_session.add(payment_item)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/carts/movies/{movie.id}", headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "You have already purchased this movie. Repeat purchases are not allowed."
    )

@pytest.mark.asyncio
async def test_remove_movie_from_cart_success(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]

    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    await db_session.refresh(cart)

    movie = await db_session.scalar(select(MovieModel).limit(1))

    cart_item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
    db_session.add(cart_item)
    await db_session.commit()
    await db_session.refresh(cart_item)

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    # Act
    response = await client.delete(f"/api/v1/carts/{movie.id}", headers=headers)

    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == "Movie removed from cart successfully."

    # Verify item no longer exists
    result = await db_session.execute(select(CartItemModel).where(CartItemModel.id == cart_item.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_remove_movie_from_cart_cart_not_found(client, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    movie_id = 999
    response = await client.delete(f"/api/v1/carts/{movie_id}", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Cart not found"


@pytest.mark.asyncio
async def test_remove_movie_from_cart_movie_not_in_cart(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]

    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    movie_id = 999
    response = await client.delete(f"/api/v1/carts/{movie_id}", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found in your cart"


@pytest.mark.asyncio
async def test_get_user_cart_empty(client, db_session, seed_database, seed_users, jwt_manager):

    user = seed_users["user"]
    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()
    await db_session.refresh(cart)
    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/carts/users", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["movies"] == [], "Expected empty movie list for user with no cart"

@pytest.mark.asyncio
async def test_get_user_cart_with_one_movie(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    await db_session.refresh(cart)

    movie = await db_session.scalar(select(MovieModel).limit(1))
    cart_item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
    db_session.add(cart_item)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/carts/users", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert len(data["movies"]) == 1
    movie_data = data["movies"][0]
    assert movie_data["id"] == movie.id
    assert movie_data["name"] == movie.name
    assert movie_data["price"] == float(movie.price)

@pytest.mark.asyncio
async def test_get_user_cart_with_multiple_movies(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()

    movies = await db_session.execute(select(MovieModel).limit(3))
    movies = movies.scalars().all()

    for movie in movies:
        cart_item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
        db_session.add(cart_item)

    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/carts/users", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert len(data["movies"]) == len(movies)

    returned_ids = {m["id"] for m in data["movies"]}
    expected_ids = {m.id for m in movies}
    assert returned_ids == expected_ids

@pytest.mark.asyncio
async def test_get_all_carts_success(client, db_session, seed_database, seed_users, jwt_manager):
    """
    Test that admin can retrieve all carts with item counts and creation times.
    """
    admin = seed_users["admin"]
    user = seed_users["user"]

    user_cart = CartModel(user_id=user.id)
    admin_cart = CartModel(user_id=admin.id)
    db_session.add_all([user_cart, admin_cart])
    await db_session.flush()

    now = datetime.datetime.now(datetime.UTC)
    db_session.add_all([
        CartItemModel(cart_id=user_cart.id, movie_id=1, added_at=now - datetime.timedelta(days=1)),
        CartItemModel(cart_id=user_cart.id, movie_id=2, added_at=now),
    ])
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": UserGroupEnum.ADMIN})
    headers = {"Authorization": f"Bearer {token}"}

    # Act
    response = await client.get("/api/v1/carts/all", headers=headers)

    # Assert
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1

    user_cart_data = next((c for c in data if c["user_email"] == user.email), None)
    assert user_cart_data is not None
    assert user_cart_data["items_count"] == 2
    assert "created_at" in user_cart_data and user_cart_data["created_at"] is not None


@pytest.mark.asyncio
async def test_get_all_carts_empty(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    token = jwt_manager.create_access_token({"user_id": admin.id, "role": UserGroupEnum.ADMIN})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/carts/all", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_get_all_carts_forbidden_for_user(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id, "role": UserGroupEnum.USER})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/carts/all", headers=headers)

    assert response.status_code == 403, "Expected 403 Forbidden for regular users"

@pytest.mark.asyncio
async def test_get_cart_details_success(client, seed_database, db_session, seed_users, jwt_manager):
    user = seed_users["user"]

    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    await db_session.refresh(cart)

    movies = await db_session.scalars(select(MovieModel).options(selectinload(MovieModel.genres)).limit(2))
    movies = movies.all()

    for movie in movies:
        cart_item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
        db_session.add(cart_item)

    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/carts/details", headers=headers)

    assert response.status_code == 200
    data = response.json()

    assert "movies" in data
    assert "total_price" in data

    assert isinstance(data["movies"], list)
    assert len(data["movies"]) == 2

    first_movie = data["movies"][0]
    assert set(first_movie.keys()) == {"id", "name", "price", "genres", "release_year"}

    # total price should match sum of movie prices
    expected_total = sum(float(m.price) for m in movies)
    assert abs(data["total_price"] - expected_total) < 0.01


@pytest.mark.asyncio
async def test_get_cart_details_empty_cart(client,seed_database, db_session, seed_users, jwt_manager):
    user = seed_users["user"]
    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/carts/details", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Your cart is empty."


@pytest.mark.asyncio
async def test_get_cart_details_no_cart(client, seed_database, seed_users, db_session, jwt_manager):
    user = seed_users["user"]

    result = await db_session.execute(select(CartModel).where(CartModel.user_id == user.id))
    cart = result.scalar_one_or_none()
    if cart:
        await db_session.delete(cart)
        await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/carts/details", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Your cart is empty."

@pytest.mark.asyncio
async def test_clear_cart_success(client, seed_database, db_session, seed_users, jwt_manager):
    user = seed_users["user"]

    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    await db_session.refresh(cart)

    movies = await db_session.scalars(select(MovieModel).limit(2))
    for movie in movies:
        item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
        db_session.add(item)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete("/api/v1/carts", headers=headers)
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Your cart has been cleared successfully."

    result = await db_session.execute(select(CartItemModel).where(CartItemModel.cart_id == cart.id))
    remaining_items = result.scalars().all()
    assert remaining_items == []


@pytest.mark.asyncio
async def test_clear_cart_empty_cart(client, seed_database, db_session, seed_users, jwt_manager):
    user = seed_users["user"]

    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete("/api/v1/carts", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Your cart is already empty."


@pytest.mark.asyncio
async def test_clear_cart_no_cart(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]

    result = await db_session.execute(select(CartModel).where(CartModel.user_id == user.id))
    existing_cart = result.scalar_one_or_none()
    if existing_cart:
        await db_session.delete(existing_cart)
        await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete("/api/v1/carts", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Your cart is already empty."
