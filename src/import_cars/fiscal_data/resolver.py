"""Resolve official BOE vehicle values without implementing tax formulas."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, replace
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from ..persistence.paths import DEFAULT_FISCAL_DATABASE_PATH, fiscal_database_path

DEFAULT_DATABASE_PATH = DEFAULT_FISCAL_DATABASE_PATH
PRICE_SPREAD_HIGH_CONFIDENCE = 0.08
POWER_TOLERANCE_KW = 2.0
# Mejora futura: resolver primero por una tabla de equivalencias KBA (HSN/TSN)
# -> versión BOE. mobile.de publica ese código, pero el anexo fiscal no lo incluye.

_BRAND_ALIASES = {
    "VW": "VOLKSWAGEN",
    "MERCEDES BENZ": "MERCEDES",
    "MERCEDES-BENZ": "MERCEDES",
}

_FUEL_CODE_ALIASES = {
    "G": "G",
    "GASOLINA": "G",
    "GASOLINE": "G",
    "PETROL": "G",
    "D": "D",
    "DIESEL": "D",
    "E": "ELC",
    "ELC": "ELC",
    "ELECTRICO": "ELC",
    "ELECTRIC": "ELC",
    "HYBRID": "HYBRID",
    "HIBRIDO": "HYBRID",
    "HYBRID GASOLINE": "HYBRID",
    "HYBRID DIESEL": "HYBRID",
    "GYE": "HYBRID",
    "DYE": "HYBRID",
    "SYE": "HYBRID",
    "PHEV": "PHEV",
    "S": "GAS",
    "GLP": "GAS",
    "LPG": "GAS",
    "GNC": "GAS",
    "CNG": "GAS",
    "H": "H",
    "HYDROGEN": "H",
    "HIDROGENO": "H",
    "M": "FLEX_FUEL",
    "ETHANOL": "FLEX_FUEL",
    "ETANOL": "FLEX_FUEL",
}

_AUTOMATIC_MARKERS = {
    "aut",
    "automatic",
    "automatico",
    "cvt",
    "dct",
    "dsg",
    "eat6",
    "eat8",
    "edc",
    "etg5",
    "etg6",
    "multitronic",
    "powershift",
    "steptronic",
    "tiptronic",
}

_HYBRID_QUERY_MARKERS = {
    "hybrid",
    "hibrido",
    "hev",
    "mhev",
    "mild hybrid",
    "etsi",
}


@dataclass(frozen=True, slots=True)
class BoeValueCandidate:
    """One technically exact BOE row considered by the resolver."""

    row_id: int
    value_eur: float
    brand: str
    model_type: str
    commercial_start: int | None
    commercial_end: int | None
    displacement_cc: int | None
    cylinders: int | None
    fuel_code: str
    power_kw: int | None
    fiscal_hp: float | None
    power_cv: int
    order_code: str
    exercise: int
    text_score: float
    transmission_kind: str
    transmission_compatible: bool | None
    cylinders_compatible: bool | None
    selected: bool = False
    decision: str = ""


@dataclass(frozen=True, slots=True)
class BoeValueResolution:
    """The official row selected for one vehicle."""

    row_id: int
    value_eur: float
    brand: str
    model_type: str
    commercial_start: int | None
    commercial_end: int | None
    displacement_cc: int | None
    cylinders: int | None
    fuel_code: str
    power_kw: int | None
    fiscal_hp: float | None
    power_cv: int
    order_code: str
    exercise: int
    confidence: float
    confidence_label: str
    price_spread_pct: float
    candidate_count: int
    manually_selected: bool = False


@dataclass(frozen=True, slots=True)
class BoeResolutionAudit:
    """Complete, non-fiscal trace of how a BOE row was selected."""

    query: str
    normalized_brand: str
    year: int
    base_candidate_count: int
    technical_candidate_count: int
    transmission_candidate_count: int
    confidence_label: str
    price_spread_pct: float | None
    warning: str | None
    missing_technical_fields: tuple[str, ...]
    candidates: tuple[BoeValueCandidate, ...]
    resolution: BoeValueResolution | None


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = " ".join(re.findall(r"[a-z0-9]+", ascii_value.casefold()))
    return re.sub(r"\b(\d+)\s+([a-z])\b", r"\1\2", normalized)


def _database_path(database_path: str | Path | None) -> Path:
    if database_path is not None:
        return Path(database_path)
    return fiscal_database_path()


def _fuel_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize(value).upper()
    return _FUEL_CODE_ALIASES.get(normalized, normalized or None)


def _text_similarity(query: str, candidate: str) -> float:
    if query == candidate:
        return 1.5
    query_tokens = set(query.split())
    candidate_tokens = set(candidate.split())
    overlap = len(query_tokens & candidate_tokens)
    recall = overlap / len(query_tokens) if query_tokens else 0.0
    precision = overlap / len(candidate_tokens) if candidate_tokens else 0.0
    ratio = SequenceMatcher(None, query, candidate).ratio()
    score = 0.45 * ratio + 0.40 * recall + 0.15 * precision
    if candidate.startswith(query):
        score += 0.15
    elif query in candidate:
        score += 0.10
    return score


def _model_head(value: str) -> str:
    """Return the stable model token, treating BOE's E- prefix as decoration."""

    tokens = value.split()
    if not tokens:
        return ""
    if tokens[0] == "e" and len(tokens) > 1:
        return tokens[1]
    numeric = re.fullmatch(r"(\d+)[a-z]", tokens[0])
    return numeric.group(1) if numeric else tokens[0]


def _fuel_for_query(fuel_code: str | None, query: str) -> str | None:
    """Correct a combustion-only source label when the version says hybrid.

    mobile.de sometimes labels mild hybrids as plain petrol/diesel.  BOE rows
    correctly use GyE/DyE, both canonicalized as HYBRID.  The override is only
    allowed when the model/version text itself contains an explicit hybrid
    marker, so an ordinary combustion car never crosses fuel families.
    """

    canonical = _fuel_code(fuel_code)
    if canonical not in {"G", "D"}:
        return canonical
    query_tokens = set(query.split())
    if query_tokens & (_HYBRID_QUERY_MARKERS - {"mild hybrid"}) or "mild hybrid" in query:
        return "HYBRID"
    return canonical


def _boe_transmission(model_type: str) -> str:
    tokens = set(_normalize(model_type).split())
    if tokens & _AUTOMATIC_MARKERS or any(
        re.fullmatch(r"(?:[5-9]g|[5-9]gtronic)", token) for token in tokens
    ):
        return "automatic"
    if "manual" in tokens:
        return "manual"
    # En las tablas del BOE la variante base sin marca de cambio es la manual;
    # las automáticas se distinguen expresamente como Aut., EAT, DSG, etc.
    return "manual"


def _normalized_transmission(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _normalize(value)
    tokens = set(normalized.split())
    if (
        normalized in {"automatic", "automatico", "semi automatic", "semiautomatico"}
        or "automatik" in tokens
        or tokens & _AUTOMATIC_MARKERS
    ):
        return "automatic"
    if "manual" in tokens or "schaltgetriebe" in tokens:
        return "manual"
    return None


def _empty_audit(
    *,
    query: str,
    brand: str,
    year: int,
    warning: str,
    missing: tuple[str, ...] = (),
    base_candidate_count: int = 0,
) -> BoeResolutionAudit:
    return BoeResolutionAudit(
        query=query,
        normalized_brand=brand,
        year=year,
        base_candidate_count=base_candidate_count,
        technical_candidate_count=0,
        transmission_candidate_count=0,
        confidence_label="none",
        price_spread_pct=None,
        warning=warning,
        missing_technical_fields=missing,
        candidates=(),
        resolution=None,
    )


def resolver_diagnostico_valor_tablas(
    marca: str,
    modelo: str,
    fecha: date | int,
    *,
    displacement_cc: int | None = None,
    power_kw: float | None = None,
    fuel_code: str | None = None,
    cylinders: int | None = None,
    transmission: str | None = None,
    selected_row_id: int | None = None,
    database_path: str | Path | None = None,
) -> BoeResolutionAudit:
    """Resolve and expose the complete BOE candidate funnel.

    Make/model/year establish the search universe. Displacement, kW and fuel are
    mandatory exact filters for combustion vehicles. Cylinder count is only an
    optional preference. Text is used after the technical and transmission facts.
    """

    year = fecha if isinstance(fecha, int) else fecha.year
    normalized_brand = _normalize(marca).upper() if marca else ""
    normalized_brand = _BRAND_ALIASES.get(normalized_brand, normalized_brand)
    query = _normalize(modelo) if modelo else ""
    normalized_make_in_model = _normalize(marca) if marca else ""
    if query.startswith(f"{normalized_make_in_model} "):
        query = query[len(normalized_make_in_model) + 1 :]
    if not normalized_brand or not query:
        return _empty_audit(
            query=query,
            brand=normalized_brand,
            year=year,
            warning="Faltan marca o modelo para consultar las tablas del BOE.",
        )

    path = _database_path(database_path)
    if not path.is_file():
        return _empty_audit(
            query=query,
            brand=normalized_brand,
            year=year,
            warning="La base de datos oficial del BOE no está disponible.",
        )

    uri = f"{path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            """
            SELECT
                v.brand, v.model_type, v.commercial_start, v.commercial_end,
                v.displacement_cc, v.cylinders, v.fuel_code, v.power_kw,
                v.fiscal_hp, v.power_cv, v.value_eur, d.order_code,
                d.exercise, v.id
            FROM boe_valores AS v
            JOIN boe_dataset_versions AS d ON d.id = v.dataset_id
            WHERE UPPER(v.brand) = ?
              AND v.category = 'passenger_vehicle'
              AND d.exercise = (SELECT MAX(exercise) FROM boe_dataset_versions)
              AND (v.commercial_start IS NULL OR v.commercial_start <= ?)
              AND (v.commercial_end IS NULL OR v.commercial_end >= ?)
            """,
            (normalized_brand, year, year),
        ).fetchall()

    model_head = _model_head(query)
    base_rows = [
        row
        for row in rows
        if (candidate := _normalize(row[1]))
        and (
            _model_head(candidate) == model_head
            or (
                _fuel_code(row[6]) == "ELC"
                and _model_head(candidate) == model_head
            )
        )
    ]
    required = {
        "displacement_cc": displacement_cc,
        "power_kw": power_kw,
        "fuel_code": _fuel_for_query(fuel_code, query),
    }
    no_displacement = required["fuel_code"] in {"ELC", "H"}
    missing = tuple(
        key
        for key, value in required.items()
        if value is None and not (key == "displacement_cc" and no_displacement)
    )
    if missing:
        return _empty_audit(
            query=query,
            brand=normalized_brand,
            year=year,
            base_candidate_count=len(base_rows),
            missing=missing,
            warning=(
                "No se puede identificar una fila oficial sin cilindrada, potencia "
                "y combustible confirmados. La cilindrada no aplica al eléctrico puro."
            ),
        )

    technical_rows = [
        row
        for row in base_rows
        if (
            (no_displacement and row[4] in (None, 0))
            or (
                not no_displacement
                and displacement_cc is not None
                and row[4] == int(displacement_cc)
            )
        )
        and _fuel_code(row[6]) == required["fuel_code"]
        and row[7] is not None
        and abs(float(row[7]) - float(power_kw)) <= POWER_TOLERANCE_KW
    ]
    if not technical_rows:
        return _empty_audit(
            query=query,
            brand=normalized_brand,
            year=year,
            base_candidate_count=len(base_rows),
            warning=(
                "Ninguna fila del BOE coincide en cilindrada y combustible exactos, "
                f"potencia dentro de ±{POWER_TOLERANCE_KW:g} kW y periodo comercial."
            ),
        )

    requested_transmission = _normalized_transmission(transmission)
    candidates: list[BoeValueCandidate] = []
    for row in technical_rows:
        transmission_kind = _boe_transmission(row[1])
        compatible = (
            transmission_kind == requested_transmission
            if requested_transmission is not None and _fuel_code(row[6]) not in {"ELC", "H"}
            else None
        )
        cylinders_compatible = (
            row[5] == int(cylinders)
            if cylinders is not None and row[5] is not None
            else None
        )
        candidates.append(
            BoeValueCandidate(
                row_id=int(row[13]),
                value_eur=float(row[10]),
                brand=row[0],
                model_type=row[1],
                commercial_start=row[2],
                commercial_end=row[3],
                displacement_cc=row[4],
                cylinders=row[5],
                fuel_code=row[6],
                power_kw=row[7],
                fiscal_hp=float(row[8]) if row[8] is not None else None,
                power_cv=row[9],
                order_code=row[11],
                exercise=row[12],
                text_score=round(_text_similarity(query, _normalize(row[1])), 4),
                transmission_kind=transmission_kind,
                transmission_compatible=compatible,
                cylinders_compatible=cylinders_compatible,
            )
        )

    cylinder_matches = [
        candidate for candidate in candidates if candidate.cylinders_compatible is True
    ]
    cylinder_pool = cylinder_matches or candidates
    compatible_candidates = [
        candidate
        for candidate in cylinder_pool
        if candidate.transmission_compatible is not False
    ]
    transmission_conflict = requested_transmission is not None and not compatible_candidates
    selection_pool = compatible_candidates or cylinder_pool
    selection_pool.sort(key=lambda item: (item.text_score, item.value_eur), reverse=True)

    manually_selected = False
    selected = selection_pool[0]
    if selected_row_id is not None:
        override = next(
            (candidate for candidate in candidates if candidate.row_id == selected_row_id),
            None,
        )
        if override is not None:
            selected = override
            manually_selected = True

    values = [candidate.value_eur for candidate in selection_pool]
    spread = 0.0 if len(values) == 1 else (max(values) - min(values)) / min(values)
    if manually_selected:
        confidence_label = "manual"
    elif len(selection_pool) == 1 or (spread <= PRICE_SPREAD_HIGH_CONFIDENCE and not transmission_conflict):
        confidence_label = "high"
    else:
        confidence_label = "non_conclusive"

    warning = None
    if confidence_label == "non_conclusive":
        if transmission_conflict:
            warning = (
                "Hay filas técnicamente exactas, pero ninguna coincide con el cambio "
                "declarado. Se ha elegido la más parecida y requiere confirmación."
            )
        else:
            warning = (
                "La identificación BOE no es concluyente: varias versiones técnicamente "
                f"idénticas difieren un {spread * 100:.1f}% en valor oficial."
            )

    decorated: list[BoeValueCandidate] = []
    top_score_tied = sum(
        candidate.text_score == selected.text_score for candidate in selection_pool
    ) > 1
    for candidate in sorted(candidates, key=lambda item: (item.text_score, item.value_eur), reverse=True):
        if candidate.row_id == selected.row_id:
            if manually_selected:
                decision = "Seleccionada manualmente por el auditor."
            elif top_score_tied:
                decision = (
                    "Empate en similitud textual; elegida de forma conservadora por "
                    "tener el mayor valor oficial."
                )
            else:
                decision = (
                    "Elegida por mayor similitud textual tras los filtros técnicos y de cambio."
                )
            decorated.append(replace(candidate, selected=True, decision=decision))
        elif candidate.transmission_compatible is False:
            decorated.append(
                replace(
                    candidate,
                    decision=(
                        f"Descartada: el BOE parece {candidate.transmission_kind} y el "
                        f"anuncio declara {requested_transmission}."
                    ),
                )
            )
        elif cylinder_matches and candidate.cylinders_compatible is not True:
            decorated.append(
                replace(
                    candidate,
                    decision=(
                        "No elegida: el número de cilindros no coincide con el anuncio; "
                        "se usó solo como desempate opcional."
                    ),
                )
            )
        elif candidate.text_score == selected.text_score:
            decorated.append(
                replace(
                    candidate,
                    decision=(
                        "No elegida: empató en similitud textual y tiene menor valor oficial."
                    ),
                )
            )
        else:
            decorated.append(
                replace(
                    candidate,
                    decision="No elegida: menor similitud textual que la fila seleccionada.",
                )
            )

    resolution = BoeValueResolution(
        row_id=selected.row_id,
        value_eur=selected.value_eur,
        brand=selected.brand,
        model_type=selected.model_type,
        commercial_start=selected.commercial_start,
        commercial_end=selected.commercial_end,
        displacement_cc=selected.displacement_cc,
        cylinders=selected.cylinders,
        fuel_code=selected.fuel_code,
        power_kw=selected.power_kw,
        fiscal_hp=selected.fiscal_hp,
        power_cv=selected.power_cv,
        order_code=selected.order_code,
        exercise=selected.exercise,
        confidence=selected.text_score,
        confidence_label=confidence_label,
        price_spread_pct=round(spread * 100, 2),
        candidate_count=len(selection_pool),
        manually_selected=manually_selected,
    )
    return BoeResolutionAudit(
        query=query,
        normalized_brand=normalized_brand,
        year=year,
        base_candidate_count=len(base_rows),
        technical_candidate_count=len(candidates),
        transmission_candidate_count=len(compatible_candidates),
        confidence_label=confidence_label,
        price_spread_pct=round(spread * 100, 2),
        warning=warning,
        missing_technical_fields=(),
        candidates=tuple(decorated),
        resolution=resolution,
    )


def resolver_registro_valor_tablas(
    marca: str,
    modelo: str,
    fecha: date | int,
    *,
    displacement_cc: int | None = None,
    power_kw: float | None = None,
    fuel_code: str | None = None,
    cylinders: int | None = None,
    transmission: str | None = None,
    selected_row_id: int | None = None,
    database_path: str | Path | None = None,
) -> BoeValueResolution | None:
    """Return the most likely technically exact Annex I row, if one exists."""

    return resolver_diagnostico_valor_tablas(
        marca,
        modelo,
        fecha,
        displacement_cc=displacement_cc,
        power_kw=power_kw,
        fuel_code=fuel_code,
        cylinders=cylinders,
        transmission=transmission,
        selected_row_id=selected_row_id,
        database_path=database_path,
    ).resolution


def resolver_valor_tablas(
    marca: str,
    modelo: str,
    fecha: date | int,
    *,
    displacement_cc: int | None = None,
    power_kw: float | None = None,
    fuel_code: str | None = None,
    cylinders: int | None = None,
    transmission: str | None = None,
    database_path: str | Path | None = None,
) -> float | None:
    """Return the official new value for one technically exact BOE match."""

    resolution = resolver_registro_valor_tablas(
        marca,
        modelo,
        fecha,
        displacement_cc=displacement_cc,
        power_kw=power_kw,
        fuel_code=fuel_code,
        cylinders=cylinders,
        transmission=transmission,
        database_path=database_path,
    )
    return resolution.value_eur if resolution else None


__all__ = [
    "DEFAULT_DATABASE_PATH",
    "PRICE_SPREAD_HIGH_CONFIDENCE",
    "BoeResolutionAudit",
    "BoeValueCandidate",
    "BoeValueResolution",
    "resolver_diagnostico_valor_tablas",
    "resolver_registro_valor_tablas",
    "resolver_valor_tablas",
]
