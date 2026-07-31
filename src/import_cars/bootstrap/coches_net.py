from __future__ import annotations

import asyncio
from urllib.parse import parse_qsl, urlparse
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright

from ..config import ScraperSettings, get_settings
from .base import BootstrapStore, BootstrapTemplate

BOOTSTRAP_KEY = "coches_net_search"
SEARCH_URL = "https://www.coches.net/segunda-mano/"


class CochesNetBootstrap:
    def __init__(self, *, settings: Optional[ScraperSettings] = None) -> None:
        self.settings = settings or get_settings()
        self._lock = asyncio.Lock()

    async def ensure(self, *, force: bool = False) -> BootstrapTemplate:
        async with self._lock:
            if not force:
                store = BootstrapStore.load(BOOTSTRAP_KEY, settings=self.settings)
                if store:
                    return store.template
            template = await self._create_template()
            BootstrapStore(key=BOOTSTRAP_KEY, template=template).save(
                settings=self.settings
            )
            return template

    async def _create_template(self) -> BootstrapTemplate:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.settings.headless,
                channel=self.settings.playwright_channel,
                slow_mo=self.settings.playwright_slow_mo or None,
            )
            context = await browser.new_context(
                locale="es-ES",
                user_agent=self.settings.user_agent,
                viewport={"width": 1280, "height": 1024},
            )
            page = await context.new_page()
            captured: Dict[str, Any] = {}

            async def handle_request(request):
                url = request.url
                if "api" not in url:
                    return
                parsed = urlparse(url)
                if "search" not in parsed.path:
                    return
                if request.method.upper() not in {"GET", "POST"}:
                    return
                captured["url"] = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                captured["method"] = request.method
                captured["headers"] = dict(request.headers)
                if request.method.upper() == "POST":
                    try:
                        captured["payload"] = await request.post_data_json()
                    except Exception:
                        captured["payload"] = request.post_data
                    captured["query"] = dict(parse_qsl(parsed.query))
                else:
                    captured["payload"] = None
                    captured["query"] = dict(parse_qsl(parsed.query))

            page.on("request", handle_request)
            await page.goto(SEARCH_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            if not captured:
                raise RuntimeError(
                    "No se interceptó la petición principal de búsqueda en coches.net"
                )

            cookies = await context.cookies()
            await context.close()
            await browser.close()

            return BootstrapTemplate(
                url=captured["url"],
                method=captured.get("method", "GET"),
                headers=captured.get("headers", {}),
                payload=captured.get("payload"),
                query=captured.get("query"),
                cookies=cookies,
            )


__all__ = ["CochesNetBootstrap", "BOOTSTRAP_KEY", "SEARCH_URL"]
