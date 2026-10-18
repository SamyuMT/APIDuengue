from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.router import api_router
from app.core.rutas import RAIZ


def create_app() -> FastAPI:
    load_dotenv(RAIZ / ".env")   # Llaves de los proveedores LLM
    app = FastAPI(
        title="Proyecto Grado Maestría API",
        version="0.1.0",
    )
    app.include_router(api_router, prefix="/v1")
    return app


app = create_app()
