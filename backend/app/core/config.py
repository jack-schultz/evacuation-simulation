#Refactorred !
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/evacuation.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    sim_default_timestep_s: float = 0.25
    sim_default_max_time_s: float = 600.0
    sim_default_door_flow_per_s: float = 1.2
    sim_default_stairs_flow_per_s: float = 0.8
    sim_default_exit_flow_per_s: float = 1.5
    sim_default_corridor_density_per_m2: float = 2.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()


get_settings = lru_cache()(get_settings)
