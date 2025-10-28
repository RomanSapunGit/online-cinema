import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import ActivationTokenModel
from database.database_postgres import get_postgresql_db


async def delete_expired_activation_tokens(db: AsyncSession = Depends(get_postgresql_db)):
    tokens_db = await db.execute(
        select(ActivationTokenModel)
        .where(ActivationTokenModel.expires_at < datetime.datetime.now(
            datetime.timezone.utc
        )))
    tokens_db = tokens_db.scalars().all()
    if not tokens_db:
        return

    for token in tokens_db:
        await db.delete(token)

    await db.commit()
