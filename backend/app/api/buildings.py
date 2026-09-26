from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from app.models.building import FloorPlanImageRecord

router = APIRouter(prefix="/api/buildings", tags=["buildings"])
MAX_FLOOR_PLAN_BYTES = 15 * 1024 * 1024

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
def create_building(
    payload: BuildingCreate,
    db: Session = Depends(get_db),
) -> BuildingResponse:
    return BuildingService(db).create_building(payload.layout)


def get_building(
    building_id: str,
    db: Session = Depends(get_db),
) -> BuildingResponse:
def get_building(
    building_id: str,
    db: Session = Depends(get_db),
) -> BuildingResponse:
    return BuildingService(db).get_building(building_id)


@router.put("/{building_id}/floor-plan")
async def upload_floor_plan(
    building_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, object]:
    BuildingService(db)._get_or_404(building_id)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "image/png":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Upload a PNG image")
    image_data = await request.body()
    if len(image_data) > MAX_FLOOR_PLAN_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="PNG must be 15 MB or smaller")
    if not image_data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File is not a valid PNG")

    filename = unquote(request.headers.get("x-filename", "floor-plan.png"))
    filename = filename.replace("\\", "/").split("/")[-1][:255] or "floor-plan.png"
    record = db.query(FloorPlanImageRecord).filter_by(building_id=building_id).first()
    if record:
        record.filename = filename
        record.image_data = image_data
    else:
        db.add(FloorPlanImageRecord(building_id=building_id, filename=filename, image_data=image_data))
    db.commit()
    return {"stored": True, "filename": filename}


@router.put("/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: str,
    payload: BuildingUpdate,
    db: Session = Depends(get_db),
    building_id: str,
    payload: BuildingUpdate,
    db: Session = Depends(get_db),
) -> BuildingResponse:
    return BuildingService(db).update_building(
        building_id,
        payload.layout,
    )
    return BuildingService(db).update_building(
        building_id,
        payload.layout,
    )


def delete_building(
    building_id: str,
    db: Session = Depends(get_db),
) -> None:
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
