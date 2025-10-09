from fastapi import FastAPI

from routers import users, movies

app = FastAPI(
    title="Cinema project",
    description="Cinema project with stripe integration and celery"
)

api_version_prefix = "/api/v1"
app.include_router(users.router, prefix=f"{api_version_prefix}/users")
app.include_router(movies.router, prefix=f"{api_version_prefix}/movies")
