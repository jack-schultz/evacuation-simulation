from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.api import SimulationCreate, SimulationRunResponse, SimulationSummary
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


@router.post("", response_model=SimulationSummary, status_code=201)
def create_simulation(
    payload: SimulationCreate, db: Session = Depends(get_db)
) -> SimulationSummary:
    return SimulationService(db).create(payload.building_id, payload.parameters)


@router.get("/{simulation_id}", response_model=SimulationRunResponse)
def get_simulation(simulation_id: str, db: Session = Depends(get_db)) -> SimulationRunResponse:
    return SimulationService(db).get(simulation_id)


@router.post("/{simulation_id}/run", response_model=SimulationRunResponse)
def run_simulation(simulation_id: str, db: Session = Depends(get_db)) -> SimulationRunResponse:
    return SimulationService(db).run(simulation_id)


@router.post("/{simulation_id}/reset", response_model=SimulationSummary)
def reset_simulation(simulation_id: str, db: Session = Depends(get_db)) -> SimulationSummary:
    return SimulationService(db).reset(simulation_id)
