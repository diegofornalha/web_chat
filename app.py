from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from claude_mini_sdk.config import SERVER_CONFIG
from .routes import router

def create_app() -> FastAPI:
    app = FastAPI(
        title="Claude E2B API",
        description="API que executa Minimax/Claude em sandbox E2B isolado",
        version="2.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=SERVER_CONFIG["cors_origins"],
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Client-Project"],
        allow_credentials=True
    )

    app.include_router(router)

    return app

app = create_app()
