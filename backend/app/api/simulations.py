#Refactorred!!
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.api import SimulationCreate, SimulationRunResponse, SimulationSummary
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


def create_simulation(
    payload: SimulationCreate, db: Session = Depends(get_db)
) -> SimulationSummary:
    return SimulationService(db).create(payload.building_id, payload.parameters)


def get_simulation(
    simulation_id: str, db: Session = Depends(get_db)
) -> SimulationRunResponse:
    return SimulationService(db).get(simulation_id)


def run_simulation(
    simulation_id: str, db: Session = Depends(get_db)
) -> SimulationRunResponse:
    return SimulationService(db).run(simulation_id)


def reset_simulation(
    simulation_id: str, db: Session = Depends(get_db)
) -> SimulationSummary:
    return SimulationService(db).reset(simulation_id)


router.add_api_route(
    "",
    create_simulation,
    methods=["POST"],
    response_model=SimulationSummary,
    status_code=201,
)

router.add_api_route(
    "/{simulation_id}",
    get_simulation,
    methods=["GET"],
    response_model=SimulationRunResponse,
)

router.add_api_route(
    "/{simulation_id}/run",
    run_simulation,
    methods=["POST"],
    response_model=SimulationRunResponse,
)

router.add_api_route(
    "/{simulation_id}/reset",
    reset_simulation,
    methods=["POST"],
    response_model=SimulationSummary,
)
