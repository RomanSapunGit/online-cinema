import datetime

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from decimal import Decimal

from sqlalchemy import select

from database import OrderModel, OrderItemModel, MovieModel, OrderStatusEnum, PaymentModel
from database.models.payment_models import StatusEnum


@pytest.mark.asyncio
async def test_create_checkout_session_success(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]

    movie = await db_session.execute(select(MovieModel).where(MovieModel.id == 1))
    movie = movie.scalar_one_or_none()
    order = OrderModel(
        id=123,
        user_id=user.id,
        status=OrderStatusEnum.PENDING,
    )
    db_session.add(order)
    await db_session.flush()
    order_item = OrderItemModel(movie=movie, price_at_order=Decimal("10.00"), order=order)
    db_session.add(order_item)
    await db_session.commit()
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    with patch("stripe.checkout.Session.create") as mock_stripe:
        mock_stripe.return_value = MagicMock(url="https://checkout.stripe.com/test-session")

        response = await client.post(f"/api/v1/payments/create-checkout-session?order_id={order.id}", headers=headers)
        print(response.json())
        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert data["checkout_url"] == "https://checkout.stripe.com/test-session"


@pytest.mark.asyncio
async def test_create_checkout_session_order_not_found(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post("/api/v1/payments/create-checkout-session?order_id=999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found."


@pytest.mark.asyncio
async def test_create_checkout_session_order_already_processed(client, db_session, seed_database, seed_users,
                                                               jwt_manager):
    user = seed_users["user"]
    order = OrderModel(id=123, user_id=user.id, status=OrderStatusEnum.PAID, )

    db_session.add(order)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/payments/create-checkout-session?order_id={order.id}", headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Order already processed."


@pytest.mark.asyncio
async def test_stripe_webhook_charge_failed(client, db_session, seed_database, seed_users, mock_email_sender):
    user = seed_users["user"]

    order = OrderModel(user_id=user.id, total_amount=Decimal(100), status=OrderStatusEnum.PENDING)
    db_session.add(order)
    await db_session.flush()
    item = OrderItemModel(order_id=order.id, movie_id=1, price_at_order=Decimal(10))
    db_session.add(item)
    await db_session.commit()

    # Mock stripe event
    mock_event = {
        "type": "charge.failed",
        "data": {
            "object": {
                "metadata": {"order_id": str(order.id), "user_id": str(user.id)}
            }
        }
    }

    with patch("stripe.Webhook.construct_event", return_value=mock_event) as mock_event:
        payload = b"{}"
        headers = {"Stripe-Signature": "fake_sig"}

        response = await client.post(
            "/api/v1/payments/stripe/webhook",
            content=payload,
            headers=headers
        )

    assert response.status_code == 200
    assert response.json() == {"status": "fail"}
    mock_event.assert_called_once()


@pytest.mark.asyncio
async def test_stripe_webhook_checkout_session_completed(client, db_session, seed_database, seed_users, mock_email_sender):
    user = seed_users["user"]

    order = OrderModel(user_id=user.id, total_amount=Decimal(200), status=OrderStatusEnum.PENDING)
    db_session.add(order)
    await db_session.flush()
    item = OrderItemModel(order_id=order.id, movie_id=1, price_at_order=Decimal(20))
    db_session.add(item)
    await db_session.commit()

    mock_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"order_id": str(order.id), "user_id": str(user.id)},
                "payment_intent": "pi_12345"
            }
        }
    }

    with patch("stripe.Webhook.construct_event", return_value=mock_event) as mock_event:
        payload = b"{}"
        headers = {"Stripe-Signature": "fake_sig"}

        response = await client.post(
            "/api/v1/payments/stripe/webhook",
            content=payload,
            headers=headers
        )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    await db_session.refresh(order)
    updated_order = await db_session.scalar(select(OrderModel).where(OrderModel.id == order.id))
    assert updated_order.status == OrderStatusEnum.PAID

    payment = await db_session.scalar(select(PaymentModel).where(PaymentModel.order_id == order.id))
    assert payment.status == StatusEnum.SUCCESSFUL
    assert payment.external_payment_id == "pi_12345"

    mock_event.assert_called_once()

@pytest.mark.asyncio
async def test_get_payment_history_returns_only_user_payments(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    other_user = seed_users["moderator"]

    now = datetime.datetime.now(datetime.UTC)

    payments = [
        PaymentModel(user_id=user.id, order_id=1, amount=Decimal("10.00"), status=StatusEnum.SUCCESSFUL, created_at=now - datetime.timedelta(days=1)),
        PaymentModel(user_id=user.id, order_id=2, amount=Decimal("20.00"), status=StatusEnum.SUCCESSFUL, created_at=now),
        PaymentModel(user_id=other_user.id, order_id=3, amount=Decimal("99.99"), status=StatusEnum.SUCCESSFUL, created_at=now),
    ]
    db_session.add_all(payments)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/payments", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    assert data[0]["amount"] == "20.00"
    assert data[1]["amount"] == "10.00"

    assert all(p["amount"] != "99.99" for p in data)


@pytest.mark.asyncio
async def test_get_payment_history_returns_empty_list_for_new_user(client, seed_database, seed_users, jwt_manager):
    new_user = seed_users["user"]

    token = jwt_manager.create_access_token({"user_id": new_user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/payments", headers=headers)
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_admin_get_all_payments_no_filters(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    user = seed_users["user"]

    now = datetime.datetime.now(datetime.UTC)
    order = OrderModel(
        user_id=user.id,
        created_at=now - datetime.timedelta(days=1),
        status=OrderStatusEnum.PENDING,
        total_amount=Decimal(100),
    )
    db_session.add(order)
    await db_session.flush()
    payments = [
        PaymentModel(user_id=user.id, order_id=order.id, amount=Decimal("10.00"), status=StatusEnum.SUCCESSFUL, created_at=now - datetime.timedelta(days=2)),
        PaymentModel(user_id=user.id, order_id=order.id, amount=Decimal("15.00"), status=StatusEnum.CANCELED, created_at=now - datetime.timedelta(days=1)),
    ]
    db_session.add_all(payments)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/payments/all", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert all("id" in o and "amount" in o for o in data)


@pytest.mark.asyncio
async def test_admin_get_payments_filter_by_user_id(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    user1 = seed_users["user"]
    user2 = seed_users["moderator"]

    now = datetime.datetime.now(datetime.UTC)
    order = OrderModel(
        user_id=user1.id,
        created_at=now - datetime.timedelta(days=1),
        status=OrderStatusEnum.PENDING,
        total_amount=Decimal(100),
    )
    order1 = OrderModel(
        user_id=user2.id,
        created_at=now - datetime.timedelta(days=1),
        status=OrderStatusEnum.PENDING,
        total_amount=Decimal(100),
    )
    db_session.add_all((order, order1))
    await db_session.flush()
    db_session.add_all([
        PaymentModel(user_id=user1.id, order_id=order.id, amount=Decimal("10.00"), status=StatusEnum.SUCCESSFUL, created_at=now),
        PaymentModel(user_id=user2.id, order_id=order.id, amount=Decimal("99.00"), status=StatusEnum.SUCCESSFUL, created_at=now),
    ])
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(f"/api/v1/payments/all?user_id={user1.id}", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert Decimal(data[0]["amount"]) == Decimal("10.00")
    assert data[0]["status"] == StatusEnum.SUCCESSFUL


@pytest.mark.asyncio
async def test_admin_get_payments_filter_by_date_range(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    user = seed_users["user"]
    now = datetime.datetime.now(datetime.UTC)
    order = OrderModel(
        user_id=user.id,
        created_at=now - datetime.timedelta(days=1),
        status=OrderStatusEnum.PENDING,
        total_amount=Decimal(100),
    )
    db_session.add(order)
    await db_session.flush()

    payments = [
        PaymentModel(user_id=user.id, order_id=order.id, amount=Decimal("10.00"), status=StatusEnum.SUCCESSFUL, created_at=now - datetime.timedelta(days=10)),
        PaymentModel(user_id=user.id, order_id=order.id, amount=Decimal("20.00"), status=StatusEnum.SUCCESSFUL, created_at=now - datetime.timedelta(days=1)),
    ]
    db_session.add_all(payments)
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    start_date = (now - datetime.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")
    end_date = now.strftime("%Y-%m-%dT%H:%M:%S")

    response = await client.get(f"/api/v1/payments/all?start_date={start_date}&end_date={end_date}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert Decimal(data[0]["amount"]) == Decimal("20.00")


@pytest.mark.asyncio
async def test_admin_get_payments_filter_by_status(client, db_session, seed_database, seed_users, jwt_manager):
    admin = seed_users["admin"]
    user = seed_users["user"]

    now = datetime.datetime.now(datetime.UTC)
    order = OrderModel(
        user_id=user.id,
        created_at=now - datetime.timedelta(days=1),
        status=OrderStatusEnum.PENDING,
        total_amount=Decimal(100),
    )
    db_session.add(order)
    await db_session.flush()

    db_session.add_all([
        PaymentModel(user_id=user.id, order_id=order.id, amount=Decimal("10.00"), status=StatusEnum.SUCCESSFUL, created_at=now),
        PaymentModel(user_id=user.id, order_id=order.id, amount=Decimal("15.00"), status=StatusEnum.CANCELED, created_at=now),
    ])
    await db_session.commit()

    token = jwt_manager.create_access_token({"user_id": admin.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(f"/api/v1/payments/all?statuses=Canceled", headers=headers)
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == StatusEnum.CANCELED


@pytest.mark.asyncio
async def test_admin_get_payments_requires_admin(client, db_session, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/payments/all", headers=headers)
    assert response.status_code in (401, 403)
