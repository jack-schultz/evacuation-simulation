"""End-to-end API test: building -> occupants -> simulation -> results."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import create_app
from app.services.seed import create_seed_layout


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    # Seed via API create instead of lifespan DB
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_building_crud_and_simulation_e2e(client: TestClient):
    layout = create_seed_layout()
    # Smaller for faster test
    layout.occupant_groups[0].count = 10
    layout.occupant_groups[1].count = 8

    create = client.post("/api/buildings", json={"layout": layout.model_dump(mode="json")})
    assert create.status_code == 201
    building = create.json()
    building_id = building["id"]
    assert building["layout"]["exits"]
    assert building["layout"]["occupant_groups"]

    listed = client.get("/api/buildings")
    assert listed.status_code == 200
    assert any(b["id"] == building_id for b in listed.json())

    sim = client.post(
        "/api/simulations",
        json={
            "building_id": building_id,
            "parameters": {
                "timestep_s": 0.25,
                "max_time_s": 300,
                "frame_interval_s": 1.0,
                "door_flow_per_s": 0.8,
                "exit_flow_per_s": 1.0,
            },
        },
    )
    assert sim.status_code == 201
    sim_id = sim.json()["id"]
    assert sim.json()["status"] == "ready"

    run = client.post(f"/api/simulations/{sim_id}/run")
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    results = body["results"]
    assert results["total_occupants"] == 18
    assert results["evacuated_count"] == 18
    assert results["remaining_count"] == 0
    assert results["total_evacuation_time_s"] is not None
    assert results["total_evacuation_time_s"] > 0
    assert results["average_evacuation_time_s"] > 0
    assert len(body["frames"]) > 1
    assert body["frames"][0]["t"] == 0

    reset = client.post(f"/api/simulations/{sim_id}/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "ready"

    updated_layout = layout.model_copy(deep=True)
    updated_layout.name = "Updated Example"
    upd = client.put(
        f"/api/buildings/{building_id}",
        json={"layout": updated_layout.model_dump(mode="json")},
    )
    assert upd.status_code == 200
    assert upd.json()["name"] == "Updated Example"

    deleted = client.delete(f"/api/buildings/{building_id}")
    assert deleted.status_code == 204
