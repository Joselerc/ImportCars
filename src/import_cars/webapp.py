from __future__ import annotations

import asyncio
import csv
import os
import secrets
import sys
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, model_validator

from .utils.import_calculator import TipoCompra, import_calculator

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(title="Import Cars Local")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
internal_security = HTTPBasic(auto_error=False)


def _require_internal_access(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(internal_security)],
) -> None:
    configured_username = os.getenv("IMPORT_CARS_INTERNAL_USERNAME")
    configured_password = os.getenv("IMPORT_CARS_INTERNAL_PASSWORD")

    if not configured_username or not configured_password:
        client_host = request.client.host if request.client else ""
        if client_host in {"127.0.0.1", "::1", "localhost", "testclient"}:
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configura las credenciales internas antes de publicar el dashboard.",
        )

    valid = (
        credentials is not None
        and secrets.compare_digest(
            credentials.username.encode("utf-8"),
            configured_username.encode("utf-8"),
        )
        and secrets.compare_digest(
            credentials.password.encode("utf-8"),
            configured_password.encode("utf-8"),
        )
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales internas no válidas.",
            headers={"WWW-Authenticate": "Basic"},
        )


class InMemoryRateLimiter:
    def __init__(self, *, requests: int, window_seconds: int) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def __call__(self, request: Request) -> None:
        client_host = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            events = self._events[client_host]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiadas solicitudes. Inténtalo de nuevo en unos minutos.",
                )
            events.append(now)


compare_rate_limit = InMemoryRateLimiter(requests=3, window_seconds=60)
calculator_rate_limit = InMemoryRateLimiter(requests=30, window_seconds=60)


class CompareRequest(BaseModel):
    mode: str = "simple"
    make: str | None = None
    model: str | None = None
    fuel_types: str | None = None
    transmissions: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_year: int | None = None
    max_year: int | None = None
    min_mileage: int | None = None
    max_mileage: int | None = None
    min_power: int | None = None
    max_power: int | None = None
    dealer_only: bool = False
    private_only: bool = False
    limit: int = 10
    de_make: str | None = None
    de_model: str | None = None
    de_min_price: float | None = None
    de_max_price: float | None = None
    de_min_year: int | None = None
    de_max_year: int | None = None
    de_min_mileage: int | None = None
    de_max_mileage: int | None = None
    de_min_power: int | None = None
    de_max_power: int | None = None
    de_fuel_types: str | None = None
    de_transmissions: str | None = None
    de_dealer_only: bool = False
    de_private_only: bool = False
    de_limit: int | None = None
    es_make: str | None = None
    es_model: str | None = None
    es_min_price: float | None = None
    es_max_price: float | None = None
    es_min_year: int | None = None
    es_max_year: int | None = None
    es_min_mileage: int | None = None
    es_max_mileage: int | None = None
    es_min_power: int | None = None
    es_max_power: int | None = None
    es_fuel_types: str | None = None
    es_transmissions: str | None = None
    es_dealer_only: bool = False
    es_private_only: bool = False
    es_limit: int | None = None

    @model_validator(mode="after")
    def validate_request(self):
        text_fields = (
            "make",
            "model",
            "fuel_types",
            "transmissions",
            "de_make",
            "de_model",
            "de_fuel_types",
            "de_transmissions",
            "es_make",
            "es_model",
            "es_fuel_types",
            "es_transmissions",
        )
        for field_name in text_fields:
            value = getattr(self, field_name)
            if value is not None:
                cleaned = value.strip()
                if not cleaned:
                    setattr(self, field_name, None)
                elif len(cleaned) > 100:
                    raise ValueError(f"{field_name} supera los 100 caracteres")
                else:
                    setattr(self, field_name, cleaned)

        numeric_fields = (
            "min_price",
            "max_price",
            "min_mileage",
            "max_mileage",
            "min_power",
            "max_power",
            "de_min_price",
            "de_max_price",
            "de_min_mileage",
            "de_max_mileage",
            "de_min_power",
            "de_max_power",
            "es_min_price",
            "es_max_price",
            "es_min_mileage",
            "es_max_mileage",
            "es_min_power",
            "es_max_power",
        )
        for field_name in numeric_fields:
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} no puede ser negativo")

        for field_name in (
            "min_year",
            "max_year",
            "de_min_year",
            "de_max_year",
            "es_min_year",
            "es_max_year",
        ):
            value = getattr(self, field_name)
            if value is not None and not 1900 <= value <= 2030:
                raise ValueError(f"{field_name} debe estar entre 1900 y 2030")

        for minimum, maximum in (
            ("min_price", "max_price"),
            ("min_year", "max_year"),
            ("min_mileage", "max_mileage"),
            ("min_power", "max_power"),
            ("de_min_price", "de_max_price"),
            ("de_min_year", "de_max_year"),
            ("de_min_mileage", "de_max_mileage"),
            ("de_min_power", "de_max_power"),
            ("es_min_price", "es_max_price"),
            ("es_min_year", "es_max_year"),
            ("es_min_mileage", "es_max_mileage"),
            ("es_min_power", "es_max_power"),
        ):
            low = getattr(self, minimum)
            high = getattr(self, maximum)
            if low is not None and high is not None and low > high:
                raise ValueError(f"{minimum} no puede ser mayor que {maximum}")

        for dealer, private in (
            ("dealer_only", "private_only"),
            ("de_dealer_only", "de_private_only"),
            ("es_dealer_only", "es_private_only"),
        ):
            if getattr(self, dealer) and getattr(self, private):
                raise ValueError(f"{dealer} y {private} son excluyentes")

        if not 1 <= self.limit <= 100:
            raise ValueError("limit debe estar entre 1 y 100")
        for field_name in ("de_limit", "es_limit"):
            value = getattr(self, field_name)
            if value is not None and not 1 <= value <= 100:
                raise ValueError(f"{field_name} debe estar entre 1 y 100")

        def normalized(value):
            return (
                " ".join(str(value).casefold().replace("-", " ").split())
                if value is not None
                else None
            )

        for field_name in (
            "make",
            "model",
            "min_year",
            "max_year",
            "min_mileage",
            "max_mileage",
            "min_power",
            "max_power",
            "fuel_types",
            "transmissions",
        ):
            de_value = getattr(self, f"de_{field_name}")
            es_value = getattr(self, f"es_{field_name}")
            common_value = getattr(self, field_name)
            resolved_de = de_value if de_value is not None else common_value
            resolved_es = es_value if es_value is not None else common_value
            if normalized(resolved_de) != normalized(resolved_es):
                raise ValueError(
                    f"{field_name} debe representar el mismo criterio en Alemania y España"
                )
        return self


class CalculatorRequest(BaseModel):
    purchase_price: float = Field(gt=0, le=5_000_000)
    sale_price: float | None = Field(None, gt=0, le=5_000_000)
    co2: int | None = Field(None, ge=0, le=1_000)
    seller_type: str = "EmpresaIVA"

    @model_validator(mode="after")
    def validate_seller_type(self):
        if self.seller_type not in {"Particular", "EmpresaIVA", "EmpresaMargen"}:
            raise ValueError("seller_type no reconocido")
        return self


FLOAT_FIELDS = {
    "price_eur",
    "break_even_particular",
    "break_even_empresa_iva",
    "break_even_empresa_margen",
    "es_market_avg",
    "es_market_median",
    "es_market_min",
    "best_break_even",
    "potential_margin_avg",
    "potential_margin_min",
    "opportunity_score",
    "co2_confidence",
}
INT_FIELDS = {
    "year",
    "mileage_km",
    "power_hp",
    "co2_g_km",
    "co2_original_g_km",
    "co2_inferred_g_km",
    "es_sample_size",
    "es_exact_sample_size",
    "es_near_sample_size",
    "es_broad_sample_size",
}


def _web_exports_dir() -> Path:
    # Los sistemas de archivos de las funciones serverless son efímeros. En
    # Vercel solo /tmp es escribible; en local preservamos la carpeta habitual.
    path = Path("/tmp/import_cars_exports") if os.getenv("VERCEL") else Path("exports")
    path.mkdir(exist_ok=True)
    return path


def _to_float(value: object) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    parsed = _to_float(value)
    return int(parsed) if parsed is not None else None


def _avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _co2_value(row: dict) -> int | None:
    return (
        _to_int(row.get("co2_g_km"))
        or _to_int(row.get("co2_original_g_km"))
        or _to_int(row.get("co2_inferred_g_km"))
    )


def _pick_tipo(row: dict) -> TipoCompra:
    scenarios = {
        TipoCompra.PARTICULAR: _to_float(row.get("break_even_particular")),
        TipoCompra.EMPRESA_IVA: _to_float(row.get("break_even_empresa_iva")),
        TipoCompra.EMPRESA_MARGEN: _to_float(row.get("break_even_empresa_margen")),
    }
    best_break_even = _to_float(row.get("best_break_even"))
    available = {tipo: value for tipo, value in scenarios.items() if value is not None}
    if best_break_even is not None and available:
        return min(
            available, key=lambda tipo: abs((available[tipo] or 0) - best_break_even)
        )
    if str(row.get("seller_type") or "").lower() == "private":
        return TipoCompra.PARTICULAR
    return TipoCompra.EMPRESA_IVA


def _cost_breakdown(row: dict) -> dict | None:
    price = _to_float(row.get("price_eur"))
    if price is None:
        return None
    tipo = _pick_tipo(row)
    breakdown = import_calculator.calcular_costes_importacion(
        price, tipo, _co2_value(row)
    )
    es_market_avg = _to_float(row.get("es_market_avg"))
    if es_market_avg is not None:
        breakdown.update(
            import_calculator.calcular_beneficio_venta(breakdown, es_market_avg)
        )
    return breakdown


def _normalize_row(row: dict[str, str]) -> dict:
    data = dict(row)
    for field in FLOAT_FIELDS:
        data[field] = _to_float(row.get(field))
    for field in INT_FIELDS:
        data[field] = _to_int(row.get(field))
    data["co2_display"] = _co2_value(data)
    data["display_title"] = data.get("title") or " ".join(
        filter(None, [data.get("make"), data.get("model"), data.get("variant_key")])
    )
    data["image_url"] = data.get("image_url") or ""
    data["cost_breakdown"] = (
        _cost_breakdown(data) if data.get("source") == "mobile_de" else None
    )
    return data


def _parse_csv(filepath: Path) -> dict:
    with filepath.open(encoding="utf-8-sig", newline="") as f:
        rows = [_normalize_row(row) for row in csv.DictReader(f)]

    mobile_rows = [row for row in rows if row.get("source") == "mobile_de"]
    coches_rows = [row for row in rows if row.get("source") == "coches_net"]
    opportunities = [
        row for row in mobile_rows if row.get("opportunity_score") is not None
    ]
    opportunities.sort(key=lambda row: row.get("opportunity_score") or 0, reverse=True)

    summary = {
        "de_count": len(mobile_rows),
        "es_count": len(coches_rows),
        "de_avg_price": _avg([row.get("price_eur") for row in mobile_rows]),
        "es_avg_price": _avg([row.get("price_eur") for row in coches_rows]),
        "avg_break_even": _avg([row.get("best_break_even") for row in opportunities]),
        "avg_margin": _avg([row.get("potential_margin_avg") for row in opportunities]),
        "best_margin": max(
            (row.get("potential_margin_avg") or float("-inf") for row in opportunities),
            default=None,
        ),
        "top_score": opportunities[0].get("opportunity_score")
        if opportunities
        else None,
        "positive_count": sum(
            1 for row in opportunities if (row.get("potential_margin_avg") or 0) > 0
        ),
        "exact_count": sum(
            1
            for row in opportunities
            if str(row.get("comparable_match_level") or "").lower() == "exact"
        ),
        "near_count": sum(
            1
            for row in opportunities
            if str(row.get("comparable_match_level") or "").lower() == "near"
        ),
        "broad_count": sum(
            1
            for row in opportunities
            if str(row.get("comparable_match_level") or "").lower() == "broad"
        ),
        "last_updated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    if summary["best_margin"] == float("-inf"):
        summary["best_margin"] = None

    return {
        "file": str(filepath),
        "export_url": f"/exports/{filepath.name}",
        "rows": rows,
        "opportunities": opportunities[:12],
        "summary": summary,
    }


def _append_option(command: list[str], flag: str, value: object) -> None:
    if value not in (None, ""):
        command.extend([flag, str(value)])


def _append_bool(command: list[str], flag: str, value: bool) -> None:
    if value:
        command.append(flag)


def _needs_advanced_mode(request: CompareRequest) -> bool:
    return (
        any(
            getattr(request, field)
            for field in (
                "min_price",
                "max_price",
                "min_year",
                "max_year",
                "min_mileage",
                "max_mileage",
                "min_power",
                "max_power",
                "dealer_only",
                "private_only",
                "de_make",
                "de_model",
                "de_min_price",
                "de_max_price",
                "de_min_year",
                "de_max_year",
                "de_min_mileage",
                "de_max_mileage",
                "de_min_power",
                "de_max_power",
                "de_fuel_types",
                "de_transmissions",
                "de_dealer_only",
                "de_private_only",
                "de_limit",
                "es_make",
                "es_model",
                "es_min_price",
                "es_max_price",
                "es_min_year",
                "es_max_year",
                "es_min_mileage",
                "es_max_mileage",
                "es_min_power",
                "es_max_power",
                "es_fuel_types",
                "es_transmissions",
                "es_dealer_only",
                "es_private_only",
                "es_limit",
            )
        )
        or request.mode == "advanced"
    )


def _has_search_seed(request: CompareRequest) -> bool:
    return any(
        value
        for value in (
            request.make,
            request.de_make,
            request.es_make,
        )
    )


def _build_command(request: CompareRequest, export_name: str) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "src.import_cars.cli",
        "comparar",
        "--limit",
        str(request.limit),
        "--export-filename",
        export_name,
    ]
    if not _needs_advanced_mode(request):
        _append_option(command, "--make", request.make)
        _append_option(command, "--model", request.model)
        _append_option(command, "--fuel-types", request.fuel_types)
        _append_option(command, "--transmissions", request.transmissions)
        return command

    de_payload = {
        "make": request.de_make or request.make,
        "model": request.de_model or request.model,
        "min_price": request.de_min_price
        if request.de_min_price is not None
        else request.min_price,
        "max_price": request.de_max_price
        if request.de_max_price is not None
        else request.max_price,
        "min_year": request.de_min_year
        if request.de_min_year is not None
        else request.min_year,
        "max_year": request.de_max_year
        if request.de_max_year is not None
        else request.max_year,
        "min_mileage": request.de_min_mileage
        if request.de_min_mileage is not None
        else request.min_mileage,
        "max_mileage": request.de_max_mileage
        if request.de_max_mileage is not None
        else request.max_mileage,
        "min_power": request.de_min_power
        if request.de_min_power is not None
        else request.min_power,
        "max_power": request.de_max_power
        if request.de_max_power is not None
        else request.max_power,
        "fuel_types": request.de_fuel_types or request.fuel_types,
        "transmissions": request.de_transmissions or request.transmissions,
        "dealer_only": request.de_dealer_only or request.dealer_only,
        "private_only": request.de_private_only or request.private_only,
        "limit": request.de_limit,
    }
    es_payload = {
        "make": request.es_make or request.make,
        "model": request.es_model or request.model,
        "min_price": request.es_min_price
        if request.es_min_price is not None
        else request.min_price,
        "max_price": request.es_max_price
        if request.es_max_price is not None
        else request.max_price,
        "min_year": request.es_min_year
        if request.es_min_year is not None
        else request.min_year,
        "max_year": request.es_max_year
        if request.es_max_year is not None
        else request.max_year,
        "min_mileage": request.es_min_mileage
        if request.es_min_mileage is not None
        else request.min_mileage,
        "max_mileage": request.es_max_mileage
        if request.es_max_mileage is not None
        else request.max_mileage,
        "min_power": request.es_min_power
        if request.es_min_power is not None
        else request.min_power,
        "max_power": request.es_max_power
        if request.es_max_power is not None
        else request.max_power,
        "fuel_types": request.es_fuel_types or request.fuel_types,
        "transmissions": request.es_transmissions or request.transmissions,
        "dealer_only": request.es_dealer_only or request.dealer_only,
        "private_only": request.es_private_only or request.private_only,
        "limit": request.es_limit,
    }

    for prefix, payload in (("de", de_payload), ("es", es_payload)):
        _append_option(command, f"--{prefix}-make", payload["make"])
        _append_option(command, f"--{prefix}-model", payload["model"])
        _append_option(command, f"--{prefix}-min-price", payload["min_price"])
        _append_option(command, f"--{prefix}-max-price", payload["max_price"])
        _append_option(command, f"--{prefix}-min-year", payload["min_year"])
        _append_option(command, f"--{prefix}-max-year", payload["max_year"])
        _append_option(command, f"--{prefix}-min-mileage", payload["min_mileage"])
        _append_option(command, f"--{prefix}-max-mileage", payload["max_mileage"])
        _append_option(command, f"--{prefix}-min-power", payload["min_power"])
        _append_option(command, f"--{prefix}-max-power", payload["max_power"])
        _append_option(command, f"--{prefix}-fuel-types", payload["fuel_types"])
        _append_option(command, f"--{prefix}-transmissions", payload["transmissions"])
        _append_option(command, f"--{prefix}-limit", payload["limit"])
        _append_bool(command, f"--{prefix}-dealer-only", bool(payload["dealer_only"]))
        _append_bool(command, f"--{prefix}-private-only", bool(payload["private_only"]))
    return command


def _report_entries(limit: int = 30) -> list[dict]:
    entries = []
    for path in sorted(
        _web_exports_dir().iterdir(),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        if not path.is_file():
            continue
        entries.append(
            {
                "name": path.name,
                "size_kb": round(path.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=UTC
                ).strftime("%Y-%m-%d %H:%M"),
                "url": f"/exports/{path.name}",
                "kind": path.suffix.lower().lstrip("."),
            }
        )
        if len(entries) >= limit:
            break
    return entries


def _page_context(
    request: Request, active_page: str, page_title: str, page_eyebrow: str
) -> dict:
    return {
        "request": request,
        "active_page": active_page,
        "page_title": page_title,
        "page_eyebrow": page_eyebrow,
        "reports": _report_entries(8),
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, _access: None = Depends(_require_internal_access)
):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _page_context(
            request,
            "dashboard",
            "Market Comparison Dashboard",
            "Germany [DE] -> Spain [ES] arbitrage analysis",
        ),
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check ligero para despliegues y monitorización."""
    return {"status": "ok"}


@app.get("/comparisons", response_class=HTMLResponse)
async def comparisons(
    request: Request, _access: None = Depends(_require_internal_access)
):
    return templates.TemplateResponse(
        request,
        "comparisons.html",
        _page_context(
            request,
            "comparisons",
            "Comparison Studio",
            "Cross-market comparison workspace",
        ),
    )


@app.get("/reports", response_class=HTMLResponse)
async def reports(request: Request, _access: None = Depends(_require_internal_access)):
    items = _report_entries()
    context = _page_context(
        request,
        "reports",
        "Saved Reports",
        "Recent exports and downloadable analysis files",
    )
    context.update(
        {
            "report_items": items,
            "report_count": len(items),
            "csv_count": sum(1 for item in items if item["kind"] == "csv"),
            "xlsx_count": sum(1 for item in items if item["kind"] == "xlsx"),
        }
    )
    return templates.TemplateResponse(request, "reports.html", context)


@app.get("/import-calculator", response_class=HTMLResponse)
async def calculator(
    request: Request, _access: None = Depends(_require_internal_access)
):
    context = _page_context(
        request, "calculator", "Import Calculator", "Germany to Spain cost simulator"
    )
    context["calculator_defaults"] = {
        "purchase_price": 29500,
        "sale_price": 43990,
        "co2": 179,
        "seller_type": "EmpresaIVA",
    }
    return templates.TemplateResponse(request, "import_calculator.html", context)


@app.get("/exports/{filename}")
async def export_file(
    filename: str,
    _access: None = Depends(_require_internal_access),
) -> FileResponse:
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    filepath = _web_exports_dir() / safe_name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(filepath)


@app.post("/api/compare")
async def compare(
    request: CompareRequest,
    _access: None = Depends(_require_internal_access),
    _rate_limit: None = Depends(compare_rate_limit),
) -> dict:
    if not _has_search_seed(request):
        raise HTTPException(
            status_code=400,
            detail="Introduce al menos una marca en Marca, Alemania o Espana antes de lanzar la comparacion.",
        )
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    export_path = _web_exports_dir() / f"web_compare_{timestamp}.csv"
    command = _build_command(request, export_path.name)
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(Path.cwd()),
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=stderr.decode("utf-8", errors="replace")
            or "Error ejecutando comparar",
        )
    if not export_path.exists():
        raise HTTPException(status_code=500, detail="No se genero el CSV esperado")
    return _parse_csv(export_path)


@app.post("/api/import-calculator")
async def import_calculator_api(
    request: CalculatorRequest,
    _access: None = Depends(_require_internal_access),
    _rate_limit: None = Depends(calculator_rate_limit),
) -> dict:
    seller_map = {
        "Particular": TipoCompra.PARTICULAR,
        "EmpresaIVA": TipoCompra.EMPRESA_IVA,
        "EmpresaMargen": TipoCompra.EMPRESA_MARGEN,
    }
    selected_tipo = seller_map.get(request.seller_type, TipoCompra.EMPRESA_IVA)
    selected = import_calculator.calcular_costes_importacion(
        request.purchase_price, selected_tipo, request.co2
    )
    selected_profit = (
        import_calculator.calcular_beneficio_venta(selected, request.sale_price)
        if request.sale_price is not None
        else None
    )

    scenarios = []
    for tipo in TipoCompra:
        costs = import_calculator.calcular_costes_importacion(
            request.purchase_price, tipo, request.co2
        )
        result = {"tipo": tipo.value, **costs}
        if request.sale_price is not None:
            result.update(
                import_calculator.calcular_beneficio_venta(costs, request.sale_price)
            )
        scenarios.append(result)

    best = min(scenarios, key=lambda item: item["break_even"]) if scenarios else None
    return {
        "selected": {
            **selected,
            **(selected_profit or {}),
            "tipo": selected_tipo.value,
        },
        "scenarios": scenarios,
        "best": best,
        "sale_price": request.sale_price,
    }


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
