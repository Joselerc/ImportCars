from typer.testing import CliRunner

from import_cars import cli
from import_cars.models import SearchResult


def test_compare_sends_the_same_filters_to_both_markets(monkeypatch) -> None:
    captured = {}

    class MobileStub:
        def search(self, *, query, limit):
            captured["mobile"] = (query, limit)
            return SearchResult(listings=[])

    class CochesStub:
        async def search(self, *, query, limit):
            captured["coches"] = (query, limit)
            return SearchResult(listings=[])

    monkeypatch.setattr(cli, "MobileDeHttpScraper", MobileStub)
    monkeypatch.setattr(cli, "CochesNetScraper", CochesStub)

    result = CliRunner().invoke(
        cli.app,
        [
            "compare",
            "--make",
            "BMW",
            "--model",
            "X5",
            "--min-year",
            "2019",
            "--max-year",
            "2021",
            "--limit",
            "7",
        ],
    )

    assert result.exit_code == 0, result.output
    mobile_filters, mobile_limit = captured["mobile"]
    coches_filters, coches_limit = captured["coches"]
    assert mobile_filters is coches_filters
    assert mobile_filters.make == "BMW"
    assert mobile_filters.model == "X5"
    assert mobile_filters.year_range.min_year == 2019
    assert mobile_filters.year_range.max_year == 2021
    assert mobile_limit == coches_limit == 7
