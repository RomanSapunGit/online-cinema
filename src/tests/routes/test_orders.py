import datetime
from decimal import Decimal

import pytest
from unittest.mock import AsyncMock
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import (
    CartModel, CartItemModel, MovieModel,
    OrderItemModel
)
from database.models.order_models import OrderStatusEnum, OrderModel
from database.models.payment_models import StatusEnum, PaymentModel


@pytest.mark.asyncio
async def test_create_order_empty_cart(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/v1/orders", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Your cart is empty."


@pytest.mark.asyncio
async def test_create_order_all_unavailable(client, db_session, seed_database, mock_email_sender, seed_users, jwt_manager):
    user = seed_users["user"]

    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    await db_session.refresh(cart)

    movie = await db_session.scalar(select(MovieModel).limit(1))
    movie.is_available = False
    db_session.add(movie)

    cart_item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
    db_session.add(cart_item)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/v1/orders", headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "No movies available to create an order."
    mock_email_sender.send_notification_email.assert_awaited_once()
    await db_session.refresh(cart)


@pytest.mark.asyncio
async def test_create_order_some_unavailable(client, db_session, seed_database, mock_email_sender, seed_users, jwt_manager):
    user = seed_users["user"]

    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    await db_session.refresh(cart)

    movie1 = await db_session.scalar(select(MovieModel).limit(1))
    movie1.is_available = False
    movie2 = await db_session.scalar(select(MovieModel).where(MovieModel.id != movie1.id).limit(1))

    db_session.add_all([movie1, movie2])
    await db_session.flush()

    db_session.add_all([
        CartItemModel(cart_id=cart.id, movie_id=movie1.id),
        CartItemModel(cart_id=cart.id, movie_id=movie2.id),
    ])
    await db_session.commit()
    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/v1/orders", headers=headers)

    assert response.status_code == 200
    order_id = response.json()["id"]

    result = await db_session.execute(select(OrderItemModel).where(OrderItemModel.order_id == order_id))
    order_items = result.scalars().all()
    assert len(order_items) == 1
    assert order_items[0].movie_id == movie2.id


@pytest.mark.asyncio
async def test_create_order_all_available(client, db_session, seed_database, mock_email_sender, seed_users, jwt_manager):
    user = seed_users["user"]

    cart = CartModel(user_id=user.id)
    db_session.add(cart)
    await db_session.flush()
    await db_session.refresh(cart)

    movies = await db_session.execute(select(MovieModel).limit(2))
    movies = movies.scalars().all()
    for movie in movies:
        movie.is_available = True
        db_session.add(movie)
        cart_item = CartItemModel(cart_id=cart.id, movie_id=movie.id)
        db_session.add(cart_item)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/v1/orders", headers=headers)

    assert response.status_code == 200
    order_id = response.json()["id"]

    result = await db_session.execute(select(OrderItemModel).options(selectinload(OrderItemModel.movie)).where(OrderItemModel.order_id == order_id))
    order_items = result.scalars().all()
    assert len(order_items) == len(movies)
    assert set([item.movie_id for item in order_items]) == set([m.id for m in movies])

@pytest.mark.asyncio
async def test_list_user_orders_no_orders(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/orders", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "No orders found for this user."


@pytest.mark.asyncio
async def test_list_user_orders_with_orders(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    movie = await db_session.scalar(select(MovieModel).limit(1))

    # Create order and order items
    order = OrderModel(user_id=user.id, status=OrderStatusEnum.PENDING, total_amount=Decimal(movie.price))
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)

    order_item = OrderItemModel(order_id=order.id, movie_id=movie.id, price_at_order=movie.price)
    db_session.add(order_item)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/orders", headers=headers)

    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 1

    returned_order = response_data[0]
    assert returned_order["id"] == order.id
    assert returned_order["status"] == order.status.value
    assert Decimal(returned_order["total_amount"]) == order.total_amount
    assert "movies" in returned_order
    assert len(returned_order["movies"]) == 1

    returned_movie = returned_order["movies"][0]
    assert returned_movie["id"] == movie.id
    assert returned_movie["name"] == movie.name
    assert Decimal(returned_movie["price"]) == Decimal(movie.price)


@pytest.mark.asyncio
async def test_cancel_order_not_found(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/orders/9999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found."


@pytest.mark.asyncio
async def test_cancel_order_already_canceled(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    order = OrderModel(user_id=user.id, status=OrderStatusEnum.CANCELED)
    db_session.add(order)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/orders/{order.id}", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Order has already been canceled."


@pytest.mark.asyncio
async def test_cancel_order_already_paid(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    order = OrderModel(user_id=user.id, status=OrderStatusEnum.PAID)
    db_session.add(order)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/orders/{order.id}", headers=headers)
    assert response.status_code == 400
    assert "already been paid" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_order_successful_payment_error(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    order = OrderModel(user_id=user.id, status=OrderStatusEnum.PENDING)
    db_session.add(order)
    await db_session.flush()

    payment = PaymentModel(status=StatusEnum.SUCCESSFUL, order_id=order.id, user_id=user.id, external_payment_id="123", amount=Decimal(100))
    db_session.add(payment)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/orders/{order.id}", headers=headers)
    assert response.status_code == 500
    assert "Inconsistent state" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_order_success(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    order = OrderModel(user_id=user.id, status=OrderStatusEnum.PENDING)
    db_session.add(order)
    await db_session.flush()

    payment1 = PaymentModel(status=StatusEnum.CANCELED, order_id=order.id, user_id=user.id, external_payment_id="123", amount=Decimal(100))
    payment2 = PaymentModel(status=StatusEnum.REFUNDED, order_id=order.id, user_id=user.id, external_payment_id="123", amount=Decimal(100))
    db_session.add_all([payment1, payment2])
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/orders/{order.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Order canceled successfully."

    await db_session.refresh(order)
    assert order.status == OrderStatusEnum.CANCELED
    await db_session.refresh(payment1)
    assert payment1.status == StatusEnum.CANCELED
    await db_session.refresh(payment2)
    assert payment2.status == StatusEnum.REFUNDED

@pytest.mark.asyncio
async def test_admin_get_orders_no_filters(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    movie = await db_session.scalar(select(MovieModel).limit(1))

    order = OrderModel(user_id=admin.id, status=OrderStatusEnum.PENDING, total_amount=Decimal(1200))
    db_session.add(order)
    await db_session.flush()
    order_item = OrderItemModel(order_id=order.id, movie_id=movie.id, price_at_order=movie.price)
    db_session.add(order_item)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/orders/all", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert any(o["id"] == order.id for o in data)
    assert "movies" in data[0]
    assert all("name" in m for m in data[0]["movies"])

@pytest.mark.asyncio
async def test_admin_get_orders_filter_by_user(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    user = seed_users["user"]
    movie = await db_session.scalar(select(MovieModel).limit(1))

    order_user = OrderModel(user_id=user.id, status=OrderStatusEnum.PENDING, total_amount=Decimal(movie.price))
    order_admin = OrderModel(user_id=admin.id, status=OrderStatusEnum.PAID, total_amount=Decimal(movie.price))
    db_session.add_all([order_user, order_admin])
    await db_session.flush()
    db_session.add_all([
        OrderItemModel(order_id=order_user.id, movie_id=movie.id, price_at_order=movie.price),
        OrderItemModel(order_id=order_admin.id, movie_id=movie.id, price_at_order=movie.price),
    ])
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(f"/api/v1/orders/all?user_id={user.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert all("movies" in o for o in data)
    assert all(o["status"] in [s.value for s in OrderStatusEnum] for o in data)
    assert all(o["user_id"] == order_user.id for o in data)

@pytest.mark.asyncio
async def test_admin_get_orders_filter_by_status(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    movies = await db_session.execute(select(MovieModel).limit(2))
    movies = movies.scalars().all()
    order_pending = OrderModel(user_id=admin.id, status=OrderStatusEnum.PENDING, total_amount=Decimal(movies[0].price))
    order_paid = OrderModel(user_id=admin.id, status=OrderStatusEnum.PAID, total_amount=Decimal(movies[1].price))
    db_session.add_all([order_pending, order_paid])
    await db_session.flush()
    db_session.add_all([
        OrderItemModel(order_id=order_pending.id, movie_id=movies[0].id, price_at_order=movies[0].price),
        OrderItemModel(order_id=order_paid.id, movie_id=movies[1].id, price_at_order=movies[1].price),
    ])
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/orders/all?statuses=Paid", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert all(o["status"] == "Paid" for o in data)
    assert all("movies" in o for o in data)

@pytest.mark.asyncio
async def test_admin_get_orders_filter_by_date_range(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    movie = await db_session.scalar(select(MovieModel).limit(1))
    now = datetime.datetime.now(datetime.UTC)

    total = Decimal(movie.price)

    order_old = OrderModel(user_id=admin.id, status=OrderStatusEnum.PENDING, created_at=now - datetime.timedelta(days=10), total_amount=total)
    order_recent = OrderModel(user_id=admin.id, status=OrderStatusEnum.PENDING, created_at=now - datetime.timedelta(days=1), total_amount=total)
    db_session.add_all([order_old, order_recent])
    await db_session.flush()
    db_session.add_all([
        OrderItemModel(order_id=order_old.id, movie_id=movie.id, price_at_order=movie.price),
        OrderItemModel(order_id=order_recent.id, movie_id=movie.id, price_at_order=movie.price)
    ])
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    start_date = (now - datetime.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")
    response = await client.get(f"/api/v1/orders/all?start_date={start_date}", headers=headers)
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert all(datetime.datetime.fromisoformat(o["created_at"]) >= datetime.datetime.fromisoformat(start_date) for o in data)

@pytest.mark.asyncio
async def test_admin_get_orders_combined_filters(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    user = seed_users["user"]
    movie = await db_session.scalar(select(MovieModel).limit(1))
    total = Decimal(1200)

    order1 = OrderModel(user_id=admin.id, status=OrderStatusEnum.PENDING, total_amount=total)
    order2 = OrderModel(user_id=admin.id, status=OrderStatusEnum.PAID, total_amount=total)
    order3 = OrderModel(user_id=user.id, status=OrderStatusEnum.PAID, total_amount=total)
    db_session.add_all([order1, order2, order3])
    await db_session.flush()
    db_session.add_all([
        OrderItemModel(order_id=order1.id, movie_id=movie.id, price_at_order=movie.price),
        OrderItemModel(order_id=order2.id, movie_id=movie.id, price_at_order=movie.price)
    ])
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(f"/api/v1/orders/all?user_id={admin.id}&statuses=Pending", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert all(o["status"] == "Pending" and o["user_id"] == admin.id for o in data)
