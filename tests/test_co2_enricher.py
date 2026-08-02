from datetime import UTC, datetime

from import_cars.enrichment import Co2Enricher, co2_memory, load_co2_memory
from import_cars.models import NormalizedListing, Registration


def _listing(
    *,
    source: str = "mobile_de",
    version: str = "1.5 TSI Style",
    co2: int | None = None,
    co2_source: str | None = None,
    fuel: str = "Gasolina",
) -> NormalizedListing:
    return NormalizedListing(
        listing_id=f"{source}-{version}-{co2}",
        source=source,
        url=f"https://example.com/{source}/{version}",
        scraped_at=datetime.now(UTC),
        make="Volkswagen",
        model="Golf",
        version=version,
        first_registration=Registration(year=2021, month=5),
        fuel_type=fuel,
        power_kw=110,
        engine_displacement_cc=1498,
        transmission="Automático",
        co2_emissions_g_km=co2,
        co2_original_g_km=co2,
        co2_source_type=co2_source,
    )


def test_memory_learns_only_from_advertisement_data(tmp_path, monkeypatch) -> None:
    memory_path = tmp_path / "co2_memory.json"
    monkeypatch.setattr(co2_memory, "MEMORY_PATH", memory_path)
    observed = _listing(co2=132, co2_source="listing")
    user_value = _listing(source="manual", co2=999, co2_source="user")

    Co2Enricher().enrich([observed, user_value])

    memory = load_co2_memory()
    assert len(memory) == 1
    entry = next(iter(memory.values()))
    assert entry["co2_avg"] == 132
    assert entry["version"] == "1.5 TSI Style"


def test_memory_resolves_only_the_exact_make_model_version_and_year(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(co2_memory, "MEMORY_PATH", tmp_path / "co2_memory.json")
    Co2Enricher().enrich([_listing(co2=132, co2_source="listing")])
    exact = _listing(co2=None)
    other_version = _listing(version="2.0 TSI GTI", co2=None)

    Co2Enricher().enrich([exact, other_version])

    assert exact.co2_emissions_g_km == 132
    assert exact.co2_source_type == "memory"
    assert other_version.co2_emissions_g_km is None
    assert other_version.co2_source_type == "missing"


def test_pure_electric_without_co2_is_zero_but_not_written_to_memory(
    tmp_path, monkeypatch
) -> None:
    memory_path = tmp_path / "co2_memory.json"
    monkeypatch.setattr(co2_memory, "MEMORY_PATH", memory_path)
    electric = _listing(co2=None, fuel="Eléctrico")

    Co2Enricher().enrich([electric])

    assert electric.co2_emissions_g_km == 0
    assert electric.co2_source_type == "electric_zero"
    assert not memory_path.exists()
