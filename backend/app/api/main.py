from fastapi import APIRouter

from app.api.routes import (
    compounds,
    containers,
    instruments,
    login,
    measurements,
    private,
    results,
    samples,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(compounds.router)
api_router.include_router(instruments.router)
api_router.include_router(containers.router)
api_router.include_router(samples.router)
api_router.include_router(measurements.router)
api_router.include_router(results.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
