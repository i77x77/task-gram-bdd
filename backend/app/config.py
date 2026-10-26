from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/taskgram.db"
    ingest_api_key: str = ""
    turn_secret: str = ""  # общий секрет с coturn; пусто = только STUN
    turn_host: str = ""  # публичный IP/хост TURN-сервера
    turn_port: int = 3478
    app_password: str = ""  # пароль входа в веб-интерфейс; пусто = без пароля
    # Google-таблица с презентациями: ссылка на таблицу (доступ «у кого есть ссылка») или прямой CSV-экспорт. Пусто = выключено
    sheet_url: str = ""
    sheet_poll_seconds: int = 0  # 0 = только по кнопке «Синхронизировать»; >0 — ещё и автоопрос
    sheet_board: str = "Презентации"
    sheet_default_year: int = 2026  # если в таблице дата без года (16.11)
    sheet_column: str = "To Do"
    sheet_done_column: str = "Done"  # сюда уходят задачи из таблицы, когда дата выступления прошла
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    default_boards: tuple[str, ...] = ("ЕПУТС", "КИПАРИСС", "АИС ОМБУ", "Презентации")
    default_columns: tuple[str, ...] = ("To Do", "In Progress", "Done", "Backlog")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
