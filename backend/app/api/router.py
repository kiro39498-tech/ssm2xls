from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.queries import router as queries_router
from app.api.v1.exports import router as exports_router
from app.api.v1.reports import router as reports_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(queries_router)
api_router.include_router(exports_router)
api_router.include_router(reports_router)

