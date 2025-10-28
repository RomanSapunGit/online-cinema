from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, func
from sqlalchemy.orm import selectinload

from database import get_db, MovieModel, UserModel
from database.models.cart_models import CartModel, CartItemModel
from database.models.payment_models import PaymentModel, PaymentItemModel, StatusEnum
from database.models.order_models import OrderItemModel
from schemas import MessageResponseSchema
from schemas.carts import CartResponseSchema, MovieInCartSchema, AdminCartSchema, CartDetailSchema
from security.dependenices import require_authentication, require_moderator_or_admin

router = APIRouter(tags=["Cart"])

"""
Clear all items in the current user's cart.

- **Returns:** MessageResponseSchema with confirmation message.
- **Raises:** 404 if the cart is already empty.
"""


@router.delete("", status_code=200)
async def clear_cart(
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
):
    """
    Clear all items in the current user's cart.

    - **Returns:** MessageResponseSchema with confirmation message.
    - **Raises:** 404 if the cart is already empty.
    """
    result = await db.execute(
        select(CartModel).options(selectinload(CartModel.cart_items)).where(CartModel.user_id == user_id))
    cart = result.scalar_one_or_none()

    if not cart or not cart.cart_items:
        raise HTTPException(status_code=404, detail="Your cart is already empty.")

    for item in cart.cart_items:
        await db.delete(item)

    await db.commit()

    return MessageResponseSchema(message="Your cart has been cleared successfully.")


@router.post("/movies/{movie_id}", response_model=MessageResponseSchema)
async def add_movie_to_cart(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
):
    """
    Add a movie to the user's cart.

    - **Path parameter:** `movie_id` – ID of the movie to add.
    - **Returns:** MessageResponseSchema with confirmation.
    - **Raises:** 400 if movie is already in cart or already purchased.
    """
    stmt = (
        select(exists().where(
            PaymentModel.user_id == user_id,
            PaymentModel.status == StatusEnum.SUCCESSFUL,
            PaymentItemModel.payment_id == PaymentModel.id,
            OrderItemModel.id == PaymentItemModel.order_item_id,
            OrderItemModel.movie_id == movie_id
        ))
    )

    result = await db.execute(stmt)
    already_purchased = result.scalar()

    if already_purchased:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already purchased this movie. Repeat purchases are not allowed."
        )

    result = await db.execute(select(CartModel).where(CartModel.user_id == user_id))
    cart = result.scalar_one_or_none()

    if not cart:
        cart = CartModel(user_id=user_id)
        db.add(cart)
        await db.flush()
        await db.refresh(cart)

    result = await db.execute(
        select(CartItemModel).where(
            CartItemModel.cart_id == cart.id,
            CartItemModel.movie_id == movie_id
        )
    )
    existing_item = result.scalar_one_or_none()

    if existing_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already in cart."
        )

    new_item = CartItemModel(cart_id=cart.id, movie_id=movie_id)
    db.add(new_item)
    await db.commit()

    return MessageResponseSchema(message="Movie added to cart successfully.")


@router.delete("/{movie_id}", response_model=MessageResponseSchema)
async def remove_movie_from_cart(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
):
    """
    Remove a movie from the user's cart.

    - **Path parameter:** `movie_id` – ID of the movie to remove.
    - **Returns:** MessageResponseSchema with confirmation.
    - **Raises:** 404 if cart or movie not found.
    """
    result = await db.execute(select(CartModel).where(CartModel.user_id == user_id))
    cart = result.scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    result = await db.execute(
        select(CartItemModel).where(
            CartItemModel.cart_id == cart.id,
            CartItemModel.movie_id == movie_id
        )
    )
    cart_item = result.scalar_one_or_none()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Movie not found in your cart")

    await db.delete(cart_item)
    await db.commit()

    return MessageResponseSchema(message="Movie removed from cart successfully.")


@router.get("/users", response_model=CartResponseSchema)
async def get_user_cart(
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
):
    """
    Retrieve the current user's cart items.

    - **Returns:** CartResponseSchema including movies, genres, and prices.
    - **Raises:** 404 if cart is empty.
    """
    result = await db.execute(
        select(CartModel)
        .options(selectinload(CartModel.cart_items).selectinload(CartItemModel.movie).selectinload(MovieModel.genres))
        .where(CartModel.user_id == user_id)
    )
    cart = result.scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    movies = [
        MovieInCartSchema(
            id=item.movie.id,
            name=item.movie.name,
            price=float(item.movie.price),
            genres=[genre.name for genre in item.movie.genres],
            release_year=item.movie.year
        )
        for item in cart.cart_items
        if item.movie is not None
    ]
    return CartResponseSchema(movies=movies)


@router.get("/all", response_model=list[AdminCartSchema])
async def get_all_carts(
        db: AsyncSession = Depends(get_db),
        _: int = Depends(require_moderator_or_admin)
):
    """
    Retrieve all user carts (admin/moderator only).

    - **Returns:** List of AdminCartSchema containing user email, number of items, and creation date.
    """
    query = (
        select(
            CartModel.id,
            UserModel.email,
            func.count(CartItemModel.id).label("items_count"),
            func.min(CartItemModel.added_at).label("created_at"),
        )
        .join(UserModel, UserModel.id == CartModel.user_id)
        .join(CartItemModel, CartItemModel.cart_id == CartModel.id, isouter=True)
        .group_by(CartModel.id, UserModel.email)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        AdminCartSchema(
            id=row.id,
            user_email=row.email,
            items_count=row.items_count,
            created_at=row.created_at,
        )
        for row in rows
        if row.items_count != 0
    ]


@router.get("/details", response_model=CartDetailSchema)
async def get_cart_details(
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(require_authentication)
):
    """
    Retrieve detailed cart information.

    - **Returns:** CartDetailSchema including movies, genres, and total cart price.
    - **Raises:** 404 if cart is empty.
    """
    result = await db.execute(
        select(CartModel)
        .where(CartModel.user_id == user_id)
        .options(selectinload(CartModel.cart_items).selectinload(CartItemModel.movie).selectinload(MovieModel.genres))
    )
    cart = result.scalar_one_or_none()

    if not cart or not cart.cart_items:
        raise HTTPException(status_code=404, detail="Your cart is empty.")

    movies = [
        MovieInCartSchema(
            id=item.movie.id,
            name=item.movie.name,
            price=float(item.movie.price),
            genres=[genre.name for genre in item.movie.genres],
            release_year=item.movie.year,
        )
        for item in cart.cart_items
    ]
    total = sum(item.movie.price for item in cart.cart_items)

    return CartDetailSchema(movies=movies, total_price=float(total))
