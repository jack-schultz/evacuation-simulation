from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import buildings, health, simulations
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.services.building_service import BuildingService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        BuildingService(db).ensure_seed()
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Evacuation Simulation API",
        description=(
            "API for building layout management and evacuation time estimation. "
            "Results are estimates only and are not safety certifications."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(buildings.router)
    app.include_router(simulations.router)
    return app


app = create_app()
