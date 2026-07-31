from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Iterable, Optional

import httpx

try:
    from curl_cffi import requests as curl_requests  # type: ignore

    _HAS_CURL_CFFI = True
except Exception:  # ImportError u otros problemas de runtime
    curl_requests = None  # type: ignore
    _HAS_CURL_CFFI = False
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import ScraperSettings, get_settings

DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/ *;q=0.8",
    "accept-language": "es-ES,es;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "sec-ch-ua": '"Chromium";v="126", "Not.A/Brand";v="8", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "upgrade-insecure-requests": "1",
}


class HttpError(RuntimeError):
    """Signals an unrecoverable HTTP failure."""


class AsyncHttpClient:
    def __init__(
        self,
        *,
        settings: Optional[ScraperSettings] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._settings = settings or get_settings()
        headers = DEFAULT_HEADERS | {"user-agent": self._settings.user_agent}
        if extra_headers:
            headers |= extra_headers
        self._client = httpx.AsyncClient(
            http2=True,
            headers=headers,
            timeout=self._settings.request_timeout,
        )
        self._proxy_cycle: Iterable[Optional[str]]
        if self._settings.proxy_pool:
            self._proxy_cycle = self._infinite_cycle(
                str(p) for p in self._settings.proxy_pool
            )
        else:
            self._proxy_cycle = self._infinite_cycle([None])

    async def close(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        proxy = next(self._proxy_cycle)
        if proxy:
            kwargs.setdefault("proxies", proxy)
        retryer = AsyncRetrying(
            stop=stop_after_attempt(self._settings.max_retries),
            wait=wait_exponential(multiplier=0.5, min=1, max=10),
            retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        )
        async for attempt in retryer:
            with attempt:
                response = await self._client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
        raise HttpError(f"Failed after retries: {method} {url}")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def __aenter__(self) -> "AsyncHttpClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    @staticmethod
    def _infinite_cycle(items: Iterable[Optional[str]]) -> Iterable[Optional[str]]:
        pool = list(items)
        if not pool:
            pool = [None]
        while True:
            random.shuffle(pool)
            for item in pool:
                yield item


class StealthSession:
    """Cliente síncrono que usa curl_cffi si está disponible, con fallback a httpx.Client."""

    def __init__(
        self,
        *,
        settings: Optional[ScraperSettings] = None,
        impersonate: str = "chrome124",
    ) -> None:
        self._settings = settings or get_settings()
        headers = DEFAULT_HEADERS | {"user-agent": self._settings.user_agent}
        if _HAS_CURL_CFFI:
            self._session = curl_requests.Session()  # type: ignore[attr-defined]
            # Impersonación TLS solo cuando está disponible
            try:
                self._session.impersonate = impersonate  # type: ignore[attr-defined]
            except Exception:
                pass
            self._session.headers.update(headers)
            self._is_httpx = False
        else:
            # Fallback a httpx.Client con http2 habilitado
            self._session = httpx.Client(
                http2=True, headers=headers, timeout=self._settings.request_timeout
            )
            self._is_httpx = True

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        proxy = kwargs.pop("proxy", None)
        if proxy is None and self._settings.proxy_pool:
            proxy = random.choice([str(p) for p in self._settings.proxy_pool])
        if proxy:
            kwargs.setdefault("proxies", proxy)
        if self._is_httpx:
            response = self._session.request(method, url, **kwargs)
        else:
            response = self._session.request(
                method, url, timeout=self._settings.request_timeout, **kwargs
            )
        if getattr(response, "status_code", 200) >= 400:
            raise HttpError(f"{response.status_code} {method} {url}")
        return response

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs)


@asynccontextmanager
async def stealth_context(
    *, settings: Optional[ScraperSettings] = None, impersonate: str = "chrome124"
) -> AsyncIterator[StealthSession]:
    loop = asyncio.get_running_loop()
    session = StealthSession(settings=settings, impersonate=impersonate)
    try:
        yield session
    finally:
        await loop.run_in_executor(None, session._session.close)


__all__ = ["AsyncHttpClient", "StealthSession", "stealth_context", "HttpError"]
