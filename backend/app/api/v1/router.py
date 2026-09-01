"""Versioned API router."""

from fastapi import APIRouter

from app.api.v1 import admin, ai, auth, dictionaries, information, messages, sources, statistics

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(ai.router)
api_router.include_router(admin.router)
api_router.include_router(dictionaries.admin_router)
api_router.include_router(dictionaries.public_router)
api_router.include_router(sources.router)
api_router.include_router(messages.router)
api_router.include_router(information.router)

api_router.include_router(statistics.router)


