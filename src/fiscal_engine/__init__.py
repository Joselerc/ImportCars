"""fiscal_engine — motor de cálculo fiscal de importación DE -> ES.

Fuente única de verdad para impuestos y costes de importación de vehículos.
Dos superficies sobre el mismo cálculo:

    from fiscal_engine import calcular, break_even_compraventa
    from fiscal_engine import Vehiculo, Operacion, CostesConfig
    from fiscal_engine import Combustible, TipoVendedor, TipoComprador

- calcular(...)              -> ResultadoFiscal  (cliente final / producto público)
- break_even_compraventa(...) -> dict            (dealer / opportunity finder)
"""

from . import tablas
from .engine import (
    base_imponible_iedmt,
    break_even_compraventa,
    calcular,
    coeficiente_depreciacion,
    condicion_fiscal,
    es_nuevo_fiscal,
    estimar_coste_transporte,
    potencia_fiscal_cvf,
    tipo_iedmt_estatal,
    valor_mercado,
)
from .models import (
    Combustible,
    CondicionFiscal,
    CostesConfig,
    LineaCoste,
    Operacion,
    Origen,
    ResultadoFiscal,
    TipoCarroceria,
    TipoComprador,
    TipoVendedor,
    ValorIntermedio,
    Vehiculo,
)

__all__ = [
    "Combustible",
    "CondicionFiscal",
    "CostesConfig",
    "LineaCoste",
    "Operacion",
    "Origen",
    "ResultadoFiscal",
    "TipoCarroceria",
    "TipoComprador",
    "TipoVendedor",
    "ValorIntermedio",
    "Vehiculo",
    "base_imponible_iedmt",
    "break_even_compraventa",
    "calcular",
    "coeficiente_depreciacion",
    "condicion_fiscal",
    "es_nuevo_fiscal",
    "estimar_coste_transporte",
    "potencia_fiscal_cvf",
    "tablas",
    "tipo_iedmt_estatal",
    "valor_mercado",
]

__version__ = "1.0.0"
__tablas_fiscales__ = "2026 (Orden HAC/1501/2025)"
