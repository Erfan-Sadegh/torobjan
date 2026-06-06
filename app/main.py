from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routes import admin, seller
from app.settings import settings


def create_app() -> FastAPI:
    settings.validate_for_runtime()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.database_url.startswith("sqlite"):
            Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(title="Torobjan", debug=settings.app_env == "local", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(seller.router)
    app.include_router(admin.router)

    @app.get("/health", response_class=PlainTextResponse)
    def health() -> str:
        return "ok"

    return app


app = create_app()
