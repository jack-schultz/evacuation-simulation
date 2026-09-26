import uuid
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.api import (
    BuildingCreate,
    BuildingResponse,
    BuildingSummary,
    BuildingUpdate,
)
from app.services.building_service import BuildingService
from app.models.building import FloorPlanImageRecord, FloorPlanLibraryRecord

router = APIRouter(prefix="/api/buildings", tags=["buildings"])
MAX_FLOOR_PLAN_BYTES = 15 * 1024 * 1024


async def _read_floor_plan(request: Request) -> tuple[str, bytes]:
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
    return filename, image_data


@router.get("", response_model=list[BuildingSummary])
def list_buildings(db: Session = Depends(get_db)) -> list[BuildingSummary]:
    return BuildingService(db).list_buildings()


@router.post("", response_model=BuildingResponse, status_code=201)
def create_building(payload: BuildingCreate, db: Session = Depends(get_db)) -> BuildingResponse:
    return BuildingService(db).create_building(payload.layout)


@router.get("/{building_id}", response_model=BuildingResponse)
def get_building(building_id: str, db: Session = Depends(get_db)) -> BuildingResponse:
    return BuildingService(db).get_building(building_id)


@router.put("/{building_id}/floor-plan")
async def upload_floor_plan(
    building_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, object]:
    BuildingService(db)._get_or_404(building_id)
    filename, image_data = await _read_floor_plan(request)
    record = db.query(FloorPlanImageRecord).filter_by(building_id=building_id).first()
    if record:
        record.filename = filename
        record.image_data = image_data
    else:
        db.add(FloorPlanImageRecord(building_id=building_id, filename=filename, image_data=image_data))
    db.commit()
    return {"stored": True, "filename": filename}


@router.get("/{building_id}/floor-plans")
def list_floor_plans(building_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    BuildingService(db)._get_or_404(building_id)
    records = (
        db.query(FloorPlanLibraryRecord)
        .filter_by(building_id=building_id)
        .order_by(FloorPlanLibraryRecord.created_at.desc(), FloorPlanLibraryRecord.id.desc())
        .all()
    )
    images = [
        {"id": image.id, "filename": image.filename, "created_at": image.created_at.isoformat()}
        for image in records
    ]
    # Include a previously imported single-image floor plan in the new library.
    legacy = db.query(FloorPlanImageRecord).filter_by(building_id=building_id).first()
    if legacy:
        images.append({
            "id": f"legacy-{building_id}",
            "filename": legacy.filename,
            "created_at": legacy.created_at.isoformat(),
        })
    return sorted(images, key=lambda image: str(image["created_at"]), reverse=True)


@router.post("/{building_id}/floor-plans", status_code=201)
async def add_floor_plan(
    building_id: str, request: Request, db: Session = Depends(get_db)
) -> dict[str, object]:
    BuildingService(db)._get_or_404(building_id)
    filename, image_data = await _read_floor_plan(request)
    image = FloorPlanLibraryRecord(
        id=str(uuid.uuid4()), building_id=building_id, filename=filename, image_data=image_data
    )
    db.add(image)
    db.commit()
    return {"stored": True, "id": image.id, "filename": image.filename}


@router.get("/{building_id}/floor-plans/{image_id}")
def get_library_floor_plan(
    building_id: str, image_id: str, db: Session = Depends(get_db)
) -> Response:
    BuildingService(db)._get_or_404(building_id)
    if image_id == f"legacy-{building_id}":
        image = db.query(FloorPlanImageRecord).filter_by(building_id=building_id).first()
    else:
        image = db.query(FloorPlanLibraryRecord).filter_by(
            id=image_id, building_id=building_id
        ).first()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Floor plan not found")
    return Response(content=image.image_data, media_type="image/png")


@router.get("/{building_id}/floor-plan")
def get_floor_plan(building_id: str, db: Session = Depends(get_db)) -> Response:
    BuildingService(db)._get_or_404(building_id)
    record = db.query(FloorPlanImageRecord).filter_by(building_id=building_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No floor plan imported")
    return Response(content=record.image_data, media_type="image/png")


@router.put("/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: str, payload: BuildingUpdate, db: Session = Depends(get_db)
) -> BuildingResponse:
    return BuildingService(db).update_building(building_id, payload.layout)


@router.delete("/{building_id}", status_code=204)
def delete_building(building_id: str, db: Session = Depends(get_db)) -> None:
    BuildingService(db).delete_building(building_id)
