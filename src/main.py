from fastapi import FastAPI, Depends
from fastapi_csrf_protect import CsrfProtect
from starlette.middleware.cors import CORSMiddleware

from config import get_settings
from config.dependencies import csrf_guard
from routes import users, movies, carts, orders, payments, docs

app = FastAPI(
    title="Cinema project",
    description="Cinema project with stripe integration and celery",
    dependencies=[Depends(csrf_guard)],
    docs_url=None,
    redoc_url=None
)

settings = get_settings()
origins = [
    settings.FRONTEND_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

secret_key: str = settings.SECRET_KEY


@CsrfProtect.load_config
def get_csrf_config():
    return settings


api_version_prefix = "/api/v1"
app.include_router(users.router, prefix=f"{api_version_prefix}/users")
app.include_router(movies.router, prefix=f"{api_version_prefix}/cinema")
app.include_router(carts.router, prefix=f"{api_version_prefix}/carts")
app.include_router(orders.router, prefix=f"{api_version_prefix}/orders")
app.include_router(payments.router, prefix=f"{api_version_prefix}/payments")
app.include_router(docs.router)
