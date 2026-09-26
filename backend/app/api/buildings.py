#Refactored!
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.api import (
    BuildingCreate,
    BuildingResponse,
    BuildingSummary,
    BuildingUpdate,
)
from app.services.building_service import BuildingService


router = APIRouter(
    prefix="/api/buildings",
    tags=["buildings"],
)


def list_buildings(db: Session = Depends(get_db)) -> list[BuildingSummary]:
    return BuildingService(db).list_buildings()


def create_building(
    payload: BuildingCreate,
    db: Session = Depends(get_db),
) -> BuildingResponse:
    return BuildingService(db).create_building(payload.layout)


def get_building(
    building_id: str,
    db: Session = Depends(get_db),
) -> BuildingResponse:
    return BuildingService(db).get_building(building_id)


def update_building(
    building_id: str,
    payload: BuildingUpdate,
    db: Session = Depends(get_db),
) -> BuildingResponse:
    return BuildingService(db).update_building(
        building_id,
        payload.layout,
    )


def delete_building(
    building_id: str,
    db: Session = Depends(get_db),
) -> None:
    BuildingService(db).delete_building(building_id)


# Register routes manually
router.add_api_route(
    "",
    list_buildings,
    methods=["GET"],
    response_model=list[BuildingSummary],
)

router.add_api_route(
    "",
    create_building,
    methods=["POST"],
    response_model=BuildingResponse,
    status_code=201,
)

router.add_api_route(
    "/{building_id}",
    get_building,
    methods=["GET"],
    response_model=BuildingResponse,
)

router.add_api_route(
    "/{building_id}",
    update_building,
    methods=["PUT"],
    response_model=BuildingResponse,
)

router.add_api_route(
    "/{building_id}",
    delete_building,
    methods=["DELETE"],
    status_code=204,
)
