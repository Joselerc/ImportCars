from __future__ import annotations

from functools import lru_cache

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraperSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMPORT_CARS_", env_file=".env")

    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
    )
    concurrency: int = 8
    request_timeout: float = 15.0
    max_retries: int = 4
    max_pages: int = 5
    page_pause_min: float = 0.5
    page_pause_max: float = 1.5
    proxy_pool: list[HttpUrl] = Field(default_factory=list)
    headless: bool = True
    playwright_channel: str = "chrome"
    playwright_slow_mo: int = 0
    log_level: str = "INFO"
    cookies_path: str | None = None
    mobile_de_base_url: str = "https://suchen.mobile.de"
    coches_net_base_url: str = "https://www.coches.net"


@lru_cache(maxsize=1)
def get_settings() -> ScraperSettings:
    return ScraperSettings()


__all__ = ["ScraperSettings", "get_settings"]
