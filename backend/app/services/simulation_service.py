"""Simulation orchestration service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.building import BuildingLayout, SimulationParameters
from app.models.building import SimulationRecord
from app.schemas.api import SimulationRunResponse, SimulationSummary
from app.services.building_service import BuildingService
from app.simulation.engine import SimulationEngine


class SimulationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.buildings = BuildingService(db)
        self.engine = SimulationEngine()
        self.settings = get_settings()

    def create(self, building_id: str, parameters: SimulationParameters | None) -> SimulationSummary:
        layout = self.buildings.get_layout(building_id)
        params = parameters or self._default_params()
        self._validate_runnable(layout)

        row = SimulationRecord(
            id=str(uuid.uuid4()),
            building_id=building_id,
            status="ready",
            building_snapshot_json=layout.model_dump_json(),
            parameters_json=params.model_dump_json(),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return SimulationSummary(
            id=row.id,
            building_id=row.building_id,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def get(self, simulation_id: str) -> SimulationRunResponse:
        row = self._get_or_404(simulation_id)
        return self._to_run_response(row, include_frames=True)

    def get_summary(self, simulation_id: str) -> SimulationSummary:
        row = self._get_or_404(simulation_id)
        results = None
        if row.results_json:
            from app.domain.building import SimulationResults

            results = SimulationResults.model_validate_json(row.results_json)
        return SimulationSummary(
            id=row.id,
            building_id=row.building_id,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            results=results,
            error_message=row.error_message,
        )

    def run(self, simulation_id: str) -> SimulationRunResponse:
        row = self._get_or_404(simulation_id)
        layout = BuildingLayout.model_validate_json(row.building_snapshot_json)
        params = SimulationParameters.model_validate_json(row.parameters_json)

        try:
            self._validate_runnable(layout)
            output = self.engine.run(layout, params)
        except ValueError as exc:
            row.status = "error"
            row.error_message = str(exc)
            row.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        row.status = "completed"
        row.results_json = output.results.model_dump_json()
        row.frames_json = "[" + ",".join(f.model_dump_json() for f in output.frames) + "]"
        row.error_message = None
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return self._to_run_response(row, include_frames=True)

    def reset(self, simulation_id: str) -> SimulationSummary:
        row = self._get_or_404(simulation_id)
        row.status = "ready"
        row.results_json = None
        row.frames_json = None
        row.error_message = None
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return SimulationSummary(
            id=row.id,
            building_id=row.building_id,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _default_params(self) -> SimulationParameters:
        s = self.settings
        return SimulationParameters(
            timestep_s=s.sim_default_timestep_s,
            max_time_s=s.sim_default_max_time_s,
            door_flow_per_s=s.sim_default_door_flow_per_s,
            stairs_flow_per_s=s.sim_default_stairs_flow_per_s,
            exit_flow_per_s=s.sim_default_exit_flow_per_s,
            corridor_density_per_m2=s.sim_default_corridor_density_per_m2,
        )

    @staticmethod
    def _validate_runnable(layout: BuildingLayout) -> None:
        if not layout.exits:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Building must have at least one exit to run a simulation",
            )
        if not layout.occupant_groups:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Building must have at least one occupant group",
            )
        if not layout.spaces:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Building must have at least one space",
            )

    def _get_or_404(self, simulation_id: str) -> SimulationRecord:
        row = (
            self.db.query(SimulationRecord)
            .filter(SimulationRecord.id == simulation_id)
            .first()
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found"
            )
        return row

    @staticmethod
    def _to_run_response(row: SimulationRecord, include_frames: bool) -> SimulationRunResponse:
        from app.domain.building import SimulationFrame, SimulationResults

        params = SimulationParameters.model_validate_json(row.parameters_json)
        results = (
            SimulationResults.model_validate_json(row.results_json) if row.results_json else None
        )
        frames: list[SimulationFrame] = []
        if include_frames and row.frames_json:
            import json

            raw = json.loads(row.frames_json)
            frames = [SimulationFrame.model_validate(f) for f in raw]

        return SimulationRunResponse(
            id=row.id,
            building_id=row.building_id,
            status=row.status,
            parameters=params,
            results=results,
            frames=frames,
            error_message=row.error_message,
        )
