import secrets

from fastapi import APIRouter, Depends, FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.config.settings import xsettings
from src.core.exceptions import UnauthorizedAPIException

security = HTTPBasic()
_credentials_dep = Depends(security)


def require_docs_auth(credentials: HTTPBasicCredentials = _credentials_dep) -> None:
    """Gate Swagger/ReDoc/OpenAPI behind HTTP Basic auth from .env."""
    valid_user = secrets.compare_digest(credentials.username, xsettings.SWAGGER_USERNAME)
    valid_pass = secrets.compare_digest(credentials.password, xsettings.SWAGGER_PASSWORD)
    if not (valid_user and valid_pass):
        raise UnauthorizedAPIException("Invalid credentials")


def build_docs_router(app: FastAPI) -> APIRouter:
    """Swagger/ReDoc/OpenAPI routes, protected by require_docs_auth."""
    router = APIRouter(include_in_schema=False, dependencies=[Depends(require_docs_auth)])

    @router.get("/docs")
    async def swagger_docs():
        return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs")

    @router.get("/redoc")
    async def redoc_docs():
        return get_redoc_html(openapi_url="/openapi.json", title="API Docs")

    @router.get("/openapi.json")
    async def openapi_json():
        return app.openapi()

    return router
