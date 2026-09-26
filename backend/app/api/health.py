#Refactored!!
from fastapi import APIRouter

from app.schemas.api import HealthResponse

router = APIRouter(tags=["health"])


def health() -> HealthResponse:
    return HealthResponse()


router.add_api_route(
    "/api/health",
    health,
    methods=["GET"],
    response_model=HealthResponse,
)
