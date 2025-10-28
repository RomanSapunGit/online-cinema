from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings, get_accounts_email_notificator
from main import app
from database import get_db_contextmanager, reset_database, UserGroupEnum, UserGroupModel, UserModel
from notifications.email import EmailSender
from security.interfaces import JWTAuthManagerInterface
from security.token_manager import JWTAuthManager
from tests.utils import CSVDatabaseSeeder


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_db(request):
    if "e2e" in request.keywords:
        yield
    else:
        await reset_database()
        yield

@pytest_asyncio.fixture(scope="function")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        res = await async_client.get("/api/v1/users/csrf")
        cookie_token = res.cookies.get("fastapi-csrf-token")
        header_token = res.json().get("csrf_token")

        assert cookie_token and header_token, "CSRF cookie or header missing in test setup"

        async_client.headers.update({"X-CSRF-Token": header_token})
        async_client.cookies.set("fastapi-csrf-token", cookie_token)

        yield async_client

    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with get_db_contextmanager() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
async def jwt_manager() -> JWTAuthManagerInterface:
    settings = get_settings()
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )

@pytest_asyncio.fixture(scope="function")
async def seed_database(db_session):
    settings = get_settings()
    seeder = CSVDatabaseSeeder(csv_file_path=settings.PATH_TO_MOVIES_CSV, db_session=db_session)

    if not await seeder.is_db_populated():
        await seeder.seed()

    yield db_session

@pytest_asyncio.fixture(scope="function")
async def seed_user_groups(db_session: AsyncSession):
    groups = [{"name": group.value} for group in UserGroupEnum]
    await db_session.execute(insert(UserGroupModel).values(groups))
    await db_session.commit()
    yield db_session

@pytest_asyncio.fixture(scope="function")
async def seed_users(db_session: AsyncSession):

    group_names = [group.value for group in UserGroupEnum]
    existing_groups = await db_session.execute(select(UserGroupModel).where(UserGroupModel.name.in_(group_names)))
    existing_groups = existing_groups.scalars().all()

    assert len(existing_groups) == len(group_names), (
        f"Expected all user groups to exist ({group_names}), "
        f"but found only {[g.name for g in existing_groups]}"
    )

    group_map = {g.name: g for g in existing_groups}

    users = {
        "user": UserModel(
            email="test_user@example.com",
            _hashed_password="fake_hashed_password_user",
            is_active=True,
            group_id=group_map[UserGroupEnum.USER].id,
        ),
        "moderator": UserModel(
            email="test_moderator@example.com",
            _hashed_password="fake_hashed_password_moderator",
            is_active=True,
            group_id=group_map[UserGroupEnum.MODERATOR].id,
        ),
        "admin": UserModel(
            email="test_admin@example.com",
            _hashed_password="fake_hashed_password_admin",
            is_active=True,
            group_id=group_map[UserGroupEnum.ADMIN].id,
        ),
    }

    db_session.add_all(users.values())
    await db_session.commit()

    for u in users.values():
        await db_session.refresh(u)

    yield users

@pytest_asyncio.fixture
def mock_email_sender():
    mock_sender = AsyncMock()

    app.dependency_overrides[get_accounts_email_notificator] = lambda: mock_sender

    yield mock_sender

    app.dependency_overrides.clear()

@pytest_asyncio.fixture
def email_sender():
    sender = EmailSender.__new__(EmailSender)
    sender._email = "noreply@test.com"
    sender._settings = MagicMock(SENDGRID_API_KEY="fake_key")
    sender._env = MagicMock()
    sender._send_email = AsyncMock()
    sender._notification_template = "notification.html"
    sender._activation_email_template_name = "activate.html"
    sender._activation_complete_email_template_name = "activate_done.html"
    sender._password_email_template_name = "reset.html"
    sender._password_complete_email_template_name = "reset_done.html"
    return sender
