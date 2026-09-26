from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.building import BuildingLayout, SimulationParameters, SimulationResults, SimulationFrame


class BuildingCreate(BaseModel):
    layout: BuildingLayout


class BuildingUpdate(BaseModel):
    layout: BuildingLayout


class BuildingSummary(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime


class BuildingResponse(BaseModel):
    id: str
    name: str
    layout: BuildingLayout
    created_at: datetime
    updated_at: datetime


class SimulationCreate(BaseModel):
    building_id: str
    parameters: SimulationParameters | None = None


class SimulationSummary(BaseModel):
    id: str
    building_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    results: SimulationResults | None = None
    error_message: str | None = None


class SimulationRunResponse(BaseModel):
    id: str
    building_id: str
    status: str
    parameters: SimulationParameters
    results: SimulationResults | None = None
    frames: list[SimulationFrame] = Field(default_factory=list)
    error_message: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "evacuation-simulation"
