"""Building persistence and validation service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain.building import BuildingLayout
from app.models.building import BuildingRecord
from app.schemas.api import BuildingResponse, BuildingSummary
from app.services.seed import create_seed_layout


class BuildingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_buildings(self) -> list[BuildingSummary]:
        rows = self.db.query(BuildingRecord).order_by(BuildingRecord.created_at.asc()).all()
        # #region agent log
        try:
            import json, time
            with open("/Users/jackschultz/PycharmProjects/evacuation-simulation/.cursor/debug-8a2919.log", "a") as _f:
                _f.write(json.dumps({"sessionId": "8a2919", "hypothesisId": "A", "location": "building_service.py:list_buildings", "message": "list_buildings", "data": {"count": len(rows), "names": [r.name for r in rows], "ids": [r.id for r in rows]}, "timestamp": int(time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # #endregion
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
        # #region agent log
        try:
            import json, time
            with open("/Users/jackschultz/PycharmProjects/evacuation-simulation/.cursor/debug-8a2919.log", "a") as _f:
                _f.write(json.dumps({"sessionId": "8a2919", "hypothesisId": "B", "location": "building_service.py:create_building", "message": "create_building ok", "data": {"id": row.id, "name": row.name}, "timestamp": int(time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # #endregion
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
        existing = self.db.query(BuildingRecord).first()
        if existing:
            return None
        return self.create_building(create_seed_layout())

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
