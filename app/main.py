from fastapi import FastAPI

from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Proyecto Grado Maestría API",
        version="0.1.0",
    )
    app.include_router(api_router, prefix="/v1")
    return app


app = create_app()
