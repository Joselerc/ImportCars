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

__all__ = [
    "DEFAULT_BOE_XML_URL",
    "BoeDataset",
    "BoeDepreciationBand",
    "BoeGenericValueBand",
    "BoeLoadSummary",
    "BoeParseError",
    "BoeVehicleValue",
    "download_boe_xml",
    "install_boe_dataset",
    "load_boe_year",
    "parse_boe_xml",
]
