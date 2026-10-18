from fastapi import APIRouter

from app.api.routes import documents, llm, tareas

api_router = APIRouter()
api_router.include_router(documents.router)
api_router.include_router(tareas.router)
api_router.include_router(llm.router)
