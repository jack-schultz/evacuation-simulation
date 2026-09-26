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

router = APIRouter(prefix="/api/buildings", tags=["buildings"])


@router.get("", response_model=list[BuildingSummary])
def list_buildings(db: Session = Depends(get_db)) -> list[BuildingSummary]:
    return BuildingService(db).list_buildings()


@router.post("", response_model=BuildingResponse, status_code=201)
def create_building(payload: BuildingCreate, db: Session = Depends(get_db)) -> BuildingResponse:
    return BuildingService(db).create_building(payload.layout)


@router.get("/{building_id}", response_model=BuildingResponse)
def get_building(building_id: str, db: Session = Depends(get_db)) -> BuildingResponse:
    return BuildingService(db).get_building(building_id)


@router.put("/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: str, payload: BuildingUpdate, db: Session = Depends(get_db)
) -> BuildingResponse:
    return BuildingService(db).update_building(building_id, payload.layout)


@router.delete("/{building_id}", status_code=204)
def delete_building(building_id: str, db: Session = Depends(get_db)) -> None:
    BuildingService(db).delete_building(building_id)
