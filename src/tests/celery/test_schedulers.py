import pytest
import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import select

from celery_apps.utils import delete_expired_activation_tokens
from database import ActivationTokenModel


@pytest.mark.asyncio
async def test_delete_expired_activation_tokens_removes_expired_tokens(db_session):
    expired_token = ActivationTokenModel(
        user_id=1,
        token="expired",
        expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
    )
    valid_token = ActivationTokenModel(
        user_id=2,
        token="valid",
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
    )

    db_session.add_all([expired_token, valid_token])
    await db_session.commit()

    await delete_expired_activation_tokens(db=db_session)

    tokens = (await db_session.execute(
        select(ActivationTokenModel)
    )).scalars().all()

    assert len(tokens) == 1
    assert tokens[0].token == "valid"


@pytest.mark.asyncio
async def test_delete_expired_activation_tokens_no_expired(db_session):
    valid_token = ActivationTokenModel(
        user_id=3,
        token="still_valid",
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2),
    )
    db_session.add(valid_token)
    await db_session.commit()

    await delete_expired_activation_tokens(db=db_session)

    tokens = (await db_session.execute(
        select(ActivationTokenModel)
    )).scalars().all()

    assert len(tokens) == 1
    assert tokens[0].token == "still_valid"


@pytest.mark.asyncio
async def test_delete_expired_activation_tokens_empty_db(db_session):
    await delete_expired_activation_tokens(db=db_session)

    tokens = (await db_session.execute(
        select(ActivationTokenModel)
    )).scalars().all()

    assert tokens == []


@pytest.mark.asyncio
async def test_delete_expired_activation_tokens_commits():
    mock_session = AsyncMock()
    mock_token = ActivationTokenModel(
        user_id=1,
        token="expired",
        expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_token]
    mock_session.execute.return_value = mock_result

    await delete_expired_activation_tokens(db=mock_session)

    mock_session.delete.assert_awaited_once_with(mock_token)
    mock_session.commit.assert_awaited_once()

