"""Building persistence and validation service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain.building import BuildingLayout
from app.models.building import BuildingRecord, FloorPlanLibraryRecord
from app.schemas.api import BuildingResponse, BuildingSummary
from app.services.seed import iter_default_maps


class BuildingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_buildings(self) -> list[BuildingSummary]:
        rows = self.db.query(BuildingRecord).order_by(BuildingRecord.created_at.asc()).all()
        return [
            BuildingSummary(
                id=r.id,
                name=r.name,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    def get_building(self, building_id: str) -> BuildingResponse:
        row = self._get_or_404(building_id)
        return self._to_response(row)

    def create_building(self, layout: BuildingLayout) -> BuildingResponse:
        self._validate_for_persistence(layout)
        row = BuildingRecord(
            id=str(uuid.uuid4()),
            name=layout.name,
            layout_json=layout.model_dump_json(),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_response(row)

    def update_building(self, building_id: str, layout: BuildingLayout) -> BuildingResponse:
        self._validate_for_persistence(layout)
        row = self._get_or_404(building_id)
        row.name = layout.name
        row.layout_json = layout.model_dump_json()
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return self._to_response(row)

    def delete_building(self, building_id: str) -> None:
        row = self._get_or_404(building_id)
        self.db.delete(row)
        self.db.commit()

    def ensure_seed(self) -> BuildingResponse | None:
        """Import every *.json map from app/maps/ when its name is not already present."""
        created: BuildingResponse | None = None
        existing_names = {
            row.name for row in self.db.query(BuildingRecord.name).all()
        }
        for path, layout in iter_default_maps():
            if layout.name in existing_names:
                building = (
                    self.db.query(BuildingRecord)
                    .filter(BuildingRecord.name == layout.name)
                    .first()
                )
            else:
                created = self.create_building(layout)
                existing_names.add(layout.name)
                building = self.db.query(BuildingRecord).filter(
                    BuildingRecord.id == created.id
                ).first()

            # A same-named PNG beside a built-in map is seeded into its library.
            image_path = path.with_suffix(".png")
            if building is not None and image_path.is_file():
                image_data = image_path.read_bytes()
                image = (
                    self.db.query(FloorPlanLibraryRecord)
                    .filter_by(building_id=building.id, filename=image_path.name)
                    .first()
                )
                if image is None:
                    self.db.add(
                        FloorPlanLibraryRecord(
                            id=str(uuid.uuid4()),
                            building_id=building.id,
                            filename=image_path.name,
                            image_data=image_data,
                        )
                    )
                    self.db.commit()
                elif image.image_data != image_data:
                    image.image_data = image_data
                    self.db.commit()

        # Drop superseded twin-tower seed if the 20 m map was just imported.
        if "Twin Towers 20m" in existing_names:
            legacy_twin = (
                self.db.query(BuildingRecord)
                .filter(BuildingRecord.name == "Twin Towers 30m")
                .first()
            )
            if legacy_twin is not None:
                self.db.delete(legacy_twin)
                self.db.commit()
        return created

    def get_layout(self, building_id: str) -> BuildingLayout:
        row = self._get_or_404(building_id)
        return BuildingLayout.model_validate_json(row.layout_json)

    def _get_or_404(self, building_id: str) -> BuildingRecord:
        row = self.db.query(BuildingRecord).filter(BuildingRecord.id == building_id).first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
        return row

    @staticmethod
    def _validate_for_persistence(layout: BuildingLayout) -> None:
        # Soft validation for save: allow incomplete buildings while editing,
        # but reject clearly broken geometry references (already in Pydantic).
        if layout.width <= 0 or layout.height <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Building dimensions must be positive",
            )

    @staticmethod
    def _to_response(row: BuildingRecord) -> BuildingResponse:
        layout = BuildingLayout.model_validate_json(row.layout_json)
        return BuildingResponse(
            id=row.id,
            name=row.name,
            layout=layout,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
