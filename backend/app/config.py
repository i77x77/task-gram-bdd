from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/taskgram.db"
    ingest_api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    default_columns: tuple[str, ...] = ("To Do", "In Progress", "Done")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
