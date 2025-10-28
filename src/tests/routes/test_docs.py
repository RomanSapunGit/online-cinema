import pytest

@pytest.mark.asyncio
async def test_docs_access_authorized(client, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/docs", headers=headers)
    assert response.status_code == 200
    assert "SwaggerUI" in response.text

@pytest.mark.asyncio
async def test_docs_access_unauthorized(client):
    response = await client.get("/docs")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_redoc_access_authorized(client, seed_database, seed_users, jwt_manager):
    user = seed_users["user"]
    token = jwt_manager.create_access_token({"user_id": user.id, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/redoc", headers=headers)
    assert response.status_code == 200
    assert "ReDoc" in response.text

@pytest.mark.asyncio
async def test_redoc_access_unauthorized(client):
    response = await client.get("/redoc")
    assert response.status_code == 401
