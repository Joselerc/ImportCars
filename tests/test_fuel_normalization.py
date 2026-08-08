from __future__ import annotations

import pytest

from import_cars.enrichment.signature import normalize_fuel_category


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gasolina, Indicado para E10", "gasoline"),
        ("gasoline", "gasoline"),
        ("Benzin, E10-geeignet", "gasoline"),
        ("Híbrido (gasolina/eléctrico)", "hybrid"),
        ("Híbrido (gasolina/eléctrico), Indicado para E10", "hybrid"),
        ("Híbrido (diésel/eléctrico)", "hybrid"),
        (
            "Híbrido (gasolina/eléctrico), Indicado para E10, Híbrido enchufable",
            "phev",
        ),
        ("Diesel", "diesel"),
        ("Eléctrico", "electric"),
        ("Autogás (LPG)", "lpg"),
        ("Gas natural (CNG)", "cng"),
        ("Hidrógeno", "hydrogen"),
        ("Combustible experimental", "other"),
        (None, "na"),
    ],
)
def test_noisy_marketplace_fuel_labels_are_classified_by_base_type(
    raw: str | None,
    expected: str,
) -> None:
    assert normalize_fuel_category(raw) == expected
