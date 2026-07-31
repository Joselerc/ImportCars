from __future__ import annotations
from typing import Optional
from .base import BootstrapStore, BootstrapTemplate
from ..config import ScraperSettings, get_settings

BOOTSTRAP_KEY = "mobile_de_websearch"


class MobileDeBootstrap:
    """
    Clase de bootstrap para mobile.de. Actualmente inactiva para este portal,
    ya que el scraper principal maneja la navegación directamente con Playwright.
    Podría reutilizarse en el futuro para cachear cookies si fuese necesario.
    """

    def __init__(self, *, settings: Optional[ScraperSettings] = None) -> None:
        self.settings = settings or get_settings()

    async def ensure(self, *, force: bool = False) -> BootstrapTemplate:
        # Devuelve una plantilla vacía para no interferir con el scraper.
        return BootstrapTemplate(
            url="", method="GET", headers={}, payload=None, query=None, cookies=[]
        )


__all__ = ["MobileDeBootstrap"]
