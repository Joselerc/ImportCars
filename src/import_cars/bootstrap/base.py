from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from ..config import ScraperSettings, get_settings

CACHE_DIR = Path.home() / ".cache" / "import_cars"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BootstrapTemplate:
    url: str
    method: str
    headers: Dict[str, str]
    payload: Optional[Dict[str, Any]]
    query: Optional[Dict[str, Any]]
    cookies: List[Dict[str, Any]]

    def to_json(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "payload": self.payload,
            "query": self.query,
            "cookies": self.cookies,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "BootstrapTemplate":
        return cls(
            url=data["url"],
            method=data.get("method", "GET"),
            headers=data.get("headers", {}),
            payload=data.get("payload"),
            query=data.get("query"),
            cookies=data.get("cookies", []),
        )


class BootstrapStore(BaseModel):
    key: str
    template: BootstrapTemplate

    def save(self, *, settings: Optional[ScraperSettings] = None) -> Path:
        settings = settings or get_settings()
        path = CACHE_DIR / f"{self.key}.json"
        path.write_text(json.dumps(self.template.to_json(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(
        cls, key: str, *, settings: Optional[ScraperSettings] = None
    ) -> Optional["BootstrapStore"]:
        settings = settings or get_settings()
        path = CACHE_DIR / f"{key}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(key=key, template=BootstrapTemplate.from_json(data))


__all__ = ["BootstrapStore", "BootstrapTemplate", "CACHE_DIR"]
