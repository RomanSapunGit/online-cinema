from fastapi import APIRouter, Depends
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from security.dependenices import require_authentication

router = APIRouter()


@router.get("/docs", include_in_schema=False)
async def custom_swagger_ui(_=Depends(require_authentication)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Docs")


@router.get("/redoc", include_in_schema=False)
async def custom_redoc_ui(_=Depends(require_authentication)):
    return get_redoc_html(openapi_url="/openapi.json", title="ReDoc")
