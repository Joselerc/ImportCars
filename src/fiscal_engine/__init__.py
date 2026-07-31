"""fiscal_engine — motor de cálculo fiscal de importación DE -> ES.

Fuente única de verdad para impuestos y costes de importación de vehículos.
Dos superficies sobre el mismo cálculo:

    from fiscal_engine import calcular, break_even_compraventa
    from fiscal_engine import Vehiculo, Operacion, CostesConfig
    from fiscal_engine import Combustible, TipoVendedor, TipoComprador

- calcular(...)              -> ResultadoFiscal  (cliente final / producto público)
- break_even_compraventa(...) -> dict            (dealer / opportunity finder)
"""

from .models import (
    Vehiculo,
    Operacion,
    CostesConfig,
    ResultadoFiscal,
    LineaCoste,
    Combustible,
    TipoVendedor,
    TipoComprador,
    CondicionFiscal,
    Origen,
)
from .engine import (
    calcular,
    break_even_compraventa,
    valor_mercado,
    coeficiente_depreciacion,
    tipo_iedmt_estatal,
    base_imponible_iedmt,
    condicion_fiscal,
    potencia_fiscal_cvf,
)
from . import tablas

__all__ = [
    "calcular",
    "break_even_compraventa",
    "valor_mercado",
    "coeficiente_depreciacion",
    "tipo_iedmt_estatal",
    "base_imponible_iedmt",
    "condicion_fiscal",
    "potencia_fiscal_cvf",
    "Vehiculo",
    "Operacion",
    "CostesConfig",
    "ResultadoFiscal",
    "LineaCoste",
    "Combustible",
    "TipoVendedor",
    "TipoComprador",
    "CondicionFiscal",
    "Origen",
    "tablas",
]

__version__ = "1.0.0"
__tablas_fiscales__ = "2026 (Orden HAC/1501/2025)"
