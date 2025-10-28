from datetime import datetime
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import Request, Header
from config import get_settings, get_accounts_email_notificator
from config.settings import Settings
from database import get_db, OrderModel, PaymentModel, UserModel
from database.models.order_models import OrderStatusEnum, OrderItemModel
from database.models.payment_models import StatusEnum, PaymentItemModel
from decorators.custom_decorators import csrf_exempt
from notifications import EmailSenderInterface
from schemas.payments import CheckoutUrlResponse, PaymentHistoryItemSchema
from security.dependenices import require_authentication, require__admin

router = APIRouter(tags=["Payment"])


@csrf_exempt
@router.post("/create-checkout-session")
async def create_checkout_session(
        order_id: int,
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication),
        settings: Settings = Depends(get_settings),
) -> CheckoutUrlResponse:
    """
    Create a Stripe checkout session for a pending order.

    Args:
        order_id (int): ID of the order to pay for.
        db (AsyncSession): Database session.
        user_id (int): Authenticated user ID.
        settings (Settings): App settings containing Stripe API key and frontend URL.

    Returns:
        CheckoutUrlResponse: Stripe checkout URL for the client to complete payment.

    Raises:
        HTTPException 404: If the order does not exist or does not belong to the user.
        HTTPException 400: If the order is not pending (already processed).
    """
    stripe.api_key = settings.STRIPE_API_KEY
    stmt = (
        select(OrderModel)
        .options(
            selectinload(OrderModel.order_items)
            .selectinload(OrderItemModel.movie)
        )
        .where(OrderModel.id == order_id)
    )

    order = await db.execute(stmt)
    order = order.scalar_one_or_none()
    if not order or order.user_id != user_id:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Order already processed.")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": item.movie.name},
                    "unit_amount": int(float(item.price_at_order) * 100),
                },
                "quantity": 1,
            }
            for item in order.order_items
        ],
        mode="payment",
        success_url=f"{settings.FRONTEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/payment-cancel",
        payment_intent_data={
            "metadata": {
                "order_id": order_id,
                "user_id": user_id,
            }
        },
        metadata={
            "order_id": str(order_id),
            "user_id": str(user_id)
        }
    )

    return CheckoutUrlResponse(checkout_url=session.url)


@csrf_exempt
@router.post("/stripe/webhook", include_in_schema=False)
async def stripe_webhook(
        request: Request,
        db: AsyncSession = Depends(get_db),
        stripe_signature: str = Header(None, alias="Stripe-Signature"),
        settings=Depends(get_settings),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> dict:
    """
    Stripe webhook endpoint to handle payment events.

    - Updates order status to Paid when payment is successful.
    - Creates Payment and PaymentItem records.
    - Sends notification emails to users for success or failure.

    Args:
        request (Request): Incoming webhook request from Stripe.
        db (AsyncSession): Database session.
        stripe_signature (str): Signature from Stripe to verify webhook authenticity.
        settings (Settings): App settings containing Stripe webhook secret.
        email_sender (EmailSenderInterface): Email sender dependency.

    Returns:
        dict: {"status": "success"} for successful webhook processing, {"status": "fail"} for failed payments.

    Raises:
        HTTPException 400: If the webhook payload cannot be verified or parsed.
        HTTPException 404: If an order referenced in the webhook is not found.
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")
    email_subject = "Payment status update"
    if event["type"] == "charge.failed":
        payment_intent = event["data"]["object"]
        order_id = int(payment_intent["metadata"]["order_id"])
        user_id = int(payment_intent["metadata"]["user_id"])
        user = await db.get(UserModel, user_id)
        result = await db.execute(
            select(OrderModel)
            .options(
                selectinload(OrderModel.order_items)
                .selectinload(OrderItemModel.movie)
            )
            .where(OrderModel.id == order_id)
        )
        order = result.scalar_one_or_none()
        notification_text = (f"Your payment for {', '.join(map(str, order.order_items))} "
                             f"with total sum: {order.total_amount} was unsuccessful."
                             f" Please try again later or change payment method")
        await email_sender.send_notification_email(
            email=user.email,
            subject=email_subject,
            notification_text=notification_text,
            notification_title="Unsuccessful payment",
        )

        return {"status": "fail"}
    if event["type"] == "checkout.session.completed":
        print("test")
        session = event["data"]["object"]
        order_id = int(session["metadata"]["order_id"])
        external_payment_id = session["payment_intent"]

        result = await db.execute(select(OrderModel).where(OrderModel.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")

        order.status = OrderStatusEnum.PAID

        payment = PaymentModel(
            user_id=order.user_id,
            order_id=order.id,
            amount=order.total_amount,
            status=StatusEnum.SUCCESSFUL,
            external_payment_id=external_payment_id,
        )
        db.add(payment)
        await db.flush()

        result = await db.execute(
            select(OrderItemModel).where(OrderItemModel.order_id == order.id)
            .options(selectinload(OrderItemModel.movie))
        )
        order_items = result.scalars().all()
        for item in order_items:
            db.add(
                PaymentItemModel(
                    payment_id=payment.id,
                    order_item_id=item.id,
                    price_at_payment=item.price_at_order,
                )
            )

        await db.commit()
        user_id = int(session["metadata"]["user_id"])
        user = await db.get(UserModel, user_id)
        notification = (f"Your payment for sum {order.total_amount} "
                        f"has been successfully processed. "
                        f"{', '.join(map(str, order_items))} ")
        await email_sender.send_notification_email(
            email=user.email,
            subject=email_subject,
            notification_text=notification,
            notification_title="Payment status update",
        )
    return {"status": "success"}


@router.get("", response_model=List[PaymentHistoryItemSchema])
async def get_payment_history(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(require_authentication),
) -> List[PaymentHistoryItemSchema]:
    """
    Retrieve payment history for the authenticated user.

    Args:
        db (AsyncSession): Database session.
        user_id (int): Authenticated user ID.

    Returns:
        List[PaymentHistoryItemSchema]: List of payment records for the user, sorted by creation date descending.
    """
    result = await db.execute(
        select(PaymentModel)
        .where(PaymentModel.user_id == user_id)
        .order_by(PaymentModel.created_at.desc())
    )
    payments = result.scalars().all()

    return payments


@router.get("/all", response_model=List[PaymentHistoryItemSchema])
async def admin_get_payments(
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Payments created after this date"),
    end_date: Optional[datetime] = Query(None, description="Payments created before this date"),
    statuses: Optional[List[StatusEnum]] = Query(None, description="Filter by payment statuses"),
    _: int = Depends(require__admin)
) -> List[PaymentHistoryItemSchema]:
    """
    Retrieve all payments (admin only) with optional filters.

    Args:
        db (AsyncSession): Database session.
        user_id (Optional[int]): Filter by specific user ID.
        start_date (Optional[datetime]): Filter payments created after this date.
        end_date (Optional[datetime]): Filter payments created before this date.
        statuses (Optional[List[StatusEnum]]): Filter by payment statuses (SUCCESSFUL, CANCELED, REFUNDED).
        _ (int): Placeholder for admin authorization dependency.

    Returns:
        List[PaymentHistoryItemSchema]: List of payment records matching the filters.
    """
    query = select(PaymentModel).options(
        selectinload(PaymentModel.user)
    )

    if user_id is not None:
        query = query.where(PaymentModel.user_id == user_id)
    if start_date is not None:
        query = query.where(PaymentModel.created_at >= start_date)
    if end_date is not None:
        query = query.where(PaymentModel.created_at <= end_date)
    if statuses:
        query = query.where(PaymentModel.status.in_(statuses))

    result = await db.execute(query)
    payments = result.scalars().all()

    return payments
