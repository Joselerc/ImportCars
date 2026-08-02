"""Official fiscal reference data loaders.

This package stores source data only. Tax calculations belong to the external
``fiscal_engine`` package.
"""

from import_cars.fiscal_data.boe import (
    DEFAULT_BOE_XML_URL,
    BoeDataset,
    BoeDepreciationBand,
    BoeGenericValueBand,
    BoeLoadSummary,
    BoeParseError,
    BoeVehicleValue,
    download_boe_xml,
    install_boe_dataset,
    load_boe_year,
    parse_boe_xml,
)
from import_cars.fiscal_data.resolver import (
    DEFAULT_DATABASE_PATH,
    BoeResolutionAudit,
    BoeValueCandidate,
    BoeValueResolution,
    resolver_diagnostico_valor_tablas,
    resolver_registro_valor_tablas,
    resolver_valor_tablas,
)

__all__ = [
    "DEFAULT_BOE_XML_URL",
    "DEFAULT_DATABASE_PATH",
    "BoeDataset",
    "BoeDepreciationBand",
    "BoeGenericValueBand",
    "BoeLoadSummary",
    "BoeParseError",
    "BoeResolutionAudit",
    "BoeValueCandidate",
    "BoeValueResolution",
    "BoeVehicleValue",
    "download_boe_xml",
    "install_boe_dataset",
    "load_boe_year",
    "parse_boe_xml",
    "resolver_diagnostico_valor_tablas",
    "resolver_registro_valor_tablas",
    "resolver_valor_tablas",
]
