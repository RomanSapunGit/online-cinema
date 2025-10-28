from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_accounts_email_notificator
from database import get_db, CartModel, OrderModel, PaymentModel, UserModel, CartItemModel
from database.models.order_models import OrderStatusEnum, OrderItemModel
from database.models.payment_models import StatusEnum
from notifications import EmailSenderInterface
from schemas import MessageResponseSchema
from schemas.orders import OrderResponseSchema, CreatedOrderResponseSchema
from security.dependenices import require_authentication, require__admin

router = APIRouter(tags=["Order"])


@router.post("", response_model=OrderResponseSchema)
async def create_order(
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> CreatedOrderResponseSchema:
    """
    Create a new order for the authenticated user using items from their cart.

    - Skips movies that are unavailable, already purchased, or pending in another order.
    - Sends email notification if some movies from the cart are unavailable.
    - Calculates total order amount based on available movies.

    Args:
        db (AsyncSession): Database session.
        user_id (int): ID of the authenticated user.
        email_sender (EmailSenderInterface): Email sender dependency.

    Returns:
        OrderResponseSchema: The created order with associated order items.

    Raises:
        HTTPException 400: If the cart is empty or no movies are available to create an order.
    """
    result = await db.execute(
        select(CartModel)
        .options(selectinload(CartModel.cart_items).selectinload(CartItemModel.movie))
        .where(CartModel.user_id == user_id)
    )
    cart = result.scalar_one_or_none()
    if not cart or not cart.cart_items:
        raise HTTPException(status_code=400, detail="Your cart is empty.")

    purchased_result = await db.execute(
        select(OrderItemModel.movie_id)
        .join(OrderItemModel.order)
        .join(PaymentModel, PaymentModel.id == OrderItemModel.order_id)
        .where(
            PaymentModel.user_id == user_id,
            PaymentModel.status == StatusEnum.SUCCESSFUL
        )
    )
    purchased_movie_ids = set(row[0] for row in purchased_result.all())

    pending_result = await db.execute(
        select(OrderItemModel.movie_id)
        .join(OrderItemModel.order)
        .where(
            OrderModel.user_id == user_id,
            OrderModel.status == OrderStatusEnum.PENDING
        )
    )
    pending_movie_ids = set(row[0] for row in pending_result.all())

    unavailable_movies = []
    available_cart_items = []

    for item in cart.cart_items:
        movie = item.movie

        if (
                not movie.is_available
                or movie.id in purchased_movie_ids
                or movie.id in pending_movie_ids
        ):
            unavailable_movies.append(movie.name)
            continue

        available_cart_items.append(item)

    if unavailable_movies:
        user = await db.get(UserModel, user_id)
        unavailable_movies_str = ", ".join(unavailable_movies)
        title = "Order update status"
        await email_sender.send_notification_email(
            email=user.email,
            subject=title,
            notification_text=f"Some movies from your cart are not available for purchase: {unavailable_movies_str}",
            notification_title=title,
        )

    if not available_cart_items:
        raise HTTPException(status_code=400, detail="No movies available to create an order.")

    total_amount = sum(float(item.movie.price) for item in available_cart_items)

    order = OrderModel(
        user_id=user_id,
        status=OrderStatusEnum.PENDING,
        total_amount=Decimal(total_amount),
    )
    db.add(order)
    await db.flush()

    for item in available_cart_items:
        db.add(OrderItemModel(
            order_id=order.id,
            movie_id=item.movie.id,
            price_at_order=item.movie.price
        ))

    await db.commit()
    result = await db.execute(
        select(OrderModel)
        .options(
            selectinload(OrderModel.order_items)
            .selectinload(OrderItemModel.movie)
        )
        .where(OrderModel.id == order.id)
    )
    order = result.scalar_one()
    return order


@router.get("", response_model=list[OrderResponseSchema])
async def list_user_orders(
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
) -> List[OrderResponseSchema]:
    """
    Retrieve all orders for the authenticated user, sorted by creation date descending.

    Args:
        db (AsyncSession): Database session.
        user_id (int): Authenticated user ID.

    Returns:
        list[OrderResponseSchema]: List of orders with their items and movie details.

    Raises:
        HTTPException 404: If no orders are found for the user.
    """
    result = await db.execute(
        select(OrderModel)
        .options(
            selectinload(OrderModel.order_items).selectinload(OrderItemModel.movie)
        )
        .where(OrderModel.user_id == user_id)
        .order_by(OrderModel.created_at.desc())
    )

    orders = result.scalars().unique().all()

    if not orders:
        raise HTTPException(status_code=404, detail="No orders found for this user.")

    return orders


@router.delete("/{order_id}", status_code=200)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(require_authentication),
) -> MessageResponseSchema:
    """
     Cancel an order if it has not been paid. Updates payment statuses to CANCELED if applicable.

     Args:
         order_id (int): ID of the order to cancel.
         db (AsyncSession): Database session.
         user_id (int): Authenticated user ID.

     Returns:
         MessageResponseSchema: Confirmation message indicating successful cancellation.

     Raises:
         HTTPException 404: If the order does not exist.
         HTTPException 400: If the order has already been canceled or paid.
         HTTPException 500: If a successful payment exists for a non-paid order (inconsistent state).
     """
    result = await db.execute(
        select(OrderModel)
        .where(OrderModel.id == order_id, OrderModel.user_id == user_id)
        .options(selectinload(OrderModel.payments))
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.status == OrderStatusEnum.CANCELED:
        raise HTTPException(status_code=400, detail="Order has already been canceled.")
    if order.status == OrderStatusEnum.PAID:
        raise HTTPException(
            status_code=400,
            detail="Order has already been paid and cannot be canceled. Please request a refund instead."
        )

    order.status = OrderStatusEnum.CANCELED

    for payment in getattr(order, "payments", []):
        if payment.status == StatusEnum.SUCCESSFUL:
            raise HTTPException(
                status_code=500,
                detail="Inconsistent state: a successful payment "
                       "exists for this non-paid order. Please contact "
                       "support."
            )
        if payment.status != StatusEnum.REFUNDED:
            payment.status = StatusEnum.CANCELED

    await db.commit()
    return MessageResponseSchema(message="Order canceled successfully.")


@router.get("/all", response_model=List[OrderResponseSchema])
async def admin_get_orders(
        db: AsyncSession = Depends(get_db),
        user_id: Optional[int] = Query(None, description="Filter by user ID"),
        start_date: Optional[datetime] = Query(None, description="Filter orders created after this date"),
        end_date: Optional[datetime] = Query(None, description="Filter orders created before this date"),
        statuses: Optional[List[OrderStatusEnum]] = Query(None, description="Filter by order statuses"),
        _: int = Depends(require__admin)
) -> List[OrderResponseSchema]:
    """
    Retrieve orders for all users (admin only), with optional filtering.

    Args:
        db (AsyncSession): Database session.
        user_id (Optional[int]): Filter orders by specific user ID.
        start_date (Optional[datetime]): Filter orders created after this date.
        end_date (Optional[datetime]): Filter orders created before this date.
        statuses (Optional[List[OrderStatusEnum]]): Filter by specific order statuses.
        _ (int): Placeholder for admin authorization dependency.

    Returns:
        List[OrderResponseSchema]: List of orders matching the filters, including items, movies, and user info.
    """
    query = select(OrderModel).options(
        selectinload(OrderModel.order_items).selectinload(OrderItemModel.movie),
        selectinload(OrderModel.user)
    )

    if user_id is not None:
        query = query.where(OrderModel.user_id == user_id)

    if start_date is not None:
        query = query.where(OrderModel.created_at >= start_date)

    if end_date is not None:
        query = query.where(OrderModel.created_at <= end_date)

    if statuses:
        query = query.where(OrderModel.status.in_(statuses))

    result = await db.execute(query)
    orders = result.scalars().all()

    return orders
