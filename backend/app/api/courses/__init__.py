"""Courses API package: catalog, structure and completion funnel."""

from fastapi import APIRouter

from app.api.courses import catalog, funnel, structure

router = APIRouter()
router.include_router(catalog.router, prefix="/api/courses", tags=["courses"])
router.include_router(structure.router, prefix="/api/courses", tags=["courses"])
router.include_router(funnel.router, prefix="/api/courses", tags=["courses"])

__all__ = ["router"]
