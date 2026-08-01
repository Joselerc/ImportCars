"""Modelos canónicos de entrada y salida del motor fiscal.

Una sola fuente de verdad para todos los cálculos de importación DE -> ES.
Consumido por:
  - el buscador de oportunidades (modo interno: break-even / margen)
  - la calculadora pública (modo cliente final: coste total puesto en España)

Todos los importes en euros. Ningún valor se redondea hasta la presentación.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

# --------------------------------------------------------------------------- #
#  Enumeraciones de dominio
# --------------------------------------------------------------------------- #

class Combustible(str, Enum):
    GASOLINA = "gasolina"
    DIESEL = "diesel"
    ELECTRICO = "electrico"
    HIBRIDO = "hibrido"
    HIBRIDO_ENCHUFABLE = "phev"
    GLP = "glp"
    OTRO = "otro"


class TipoVendedor(str, Enum):
    """Cómo vende el vendedor alemán. Determina el régimen de IVA/ITP."""
    PARTICULAR = "particular"
    # Profesional que factura con IVA desglosado (Regelbesteuerung 19%).
    PROFESIONAL_IVA = "profesional_iva"
    # Profesional en régimen de margen §25a (sin IVA deducible en factura).
    PROFESIONAL_MARGEN = "profesional_margen"


class TipoComprador(str, Enum):
    """Quién compra en España. Determina qué circuito de IVA aplica."""
    PARTICULAR = "particular"
    # Empresa/autónomo con NIF-IVA intracomunitario (ROI).
    EMPRESA_ROI = "empresa_roi"


class CondicionFiscal(str, Enum):
    NUEVO = "nuevo"      # < 6 meses desde 1ª matriculación O < 6.000 km
    USADO = "usado"


class Origen(str, Enum):
    UE = "ue"
    EXTRA_UE = "extra_ue"


class TipoCarroceria(str, Enum):
    """Categorías operativas para estimar el transporte profesional."""

    TURISMO = "turismo"
    FAMILIAR = "familiar"
    SUV = "suv"
    MONOVOLUMEN = "monovolumen"
    DEPORTIVO_GAMA_ALTA = "deportivo_gama_alta"
    OTRO = "otro"


# --------------------------------------------------------------------------- #
#  Entrada
# --------------------------------------------------------------------------- #

@dataclass
class Vehiculo:
    """Datos del vehículo necesarios para el cálculo fiscal."""
    # Identificación (para valorar contra las tablas del BOE)
    marca: str
    modelo: str
    # Fecha de primera matriculación. OBLIGATORIA para calcular antigüedad,
    # depreciación, minoración y condición nuevo/usado.
    fecha_primera_matriculacion: date
    precio_compra: float                     # precio pactado en Alemania (€)
    combustible: Combustible
    cilindrada_cc: int                        # para potencia fiscal (CVF) e IVTM
    # Emisiones oficiales de CO2 en g/km (WLTP/NEDC según certifique el CoC).
    # None => no acreditado => tipo máximo de IEDMT (14,75%).
    co2_gkm: Optional[float] = None
    kilometros: Optional[int] = None
    potencia_kw: Optional[float] = None
    # Potencia fiscal en CVF si ya se conoce (casilla P.2.1 de la ficha ITV).
    # Si es None, se estima desde la cilindrada.
    cvf: Optional[float] = None
    # Valor de mercado del BOE si el llamador ya lo resolvió (evita otra consulta).
    # Si es None, el motor lo busca en las tablas por marca/modelo/año.
    valor_tablas_nuevo: Optional[float] = None
    # Confianza del dato de CO2: 1.0 original, <1 inferido. Solo informativo.
    co2_confianza: float = 1.0
    # Solo determina el tramo de transporte; nunca altera una fórmula fiscal.
    carroceria: Optional[TipoCarroceria] = None


@dataclass
class Operacion:
    """Cómo se compra y quién compra. Determina el régimen fiscal."""
    tipo_vendedor: TipoVendedor
    tipo_comprador: TipoComprador = TipoComprador.PARTICULAR
    origen: Origen = Origen.UE
    # Comunidad autónoma y municipio de residencia DEL COMPRADOR.
    comunidad_autonoma: str = "Madrid"
    municipio: str = "Madrid"
    # Traslado de residencia con el propio coche (exención art. 66 Ley 38/1992).
    traslado_residencia: bool = False


@dataclass
class CostesConfig:
    """Costes operativos parametrizables (no impuestos)."""
    honorarios_gestion: float = 900.0        # tarifa fija visible al cliente
    # Un valor explícito prevalece sobre los tramos (presupuesto cerrado/test).
    transporte: Optional[float] = None
    transporte_turismo: float = 950.0
    transporte_suv_monovolumen: float = 1100.0
    transporte_deportivo_gama_alta: float = 1200.0
    # Reservados para incorporar distancia sin cambiar el contrato del motor.
    transporte_origen: Optional[str] = None
    transporte_destino: Optional[str] = None
    itv_importacion: float = 140.0
    tasa_dgt: float = 99.77                   # tasa 1.1 matriculación turismo 2026
    placas: float = 35.0
    coc: float = 0.0                          # coste de CoC si el vendedor no lo tiene
    traduccion_jurada: float = 0.0            # 0 si contrato bilingüe
    # Extra-UE:
    arancel_pct: float = 0.10                 # 10% sobre (valor + transporte)
    gestion_aduanera: float = 200.0


# --------------------------------------------------------------------------- #
#  Salida
# --------------------------------------------------------------------------- #

@dataclass
class LineaCoste:
    """Una línea del desglose, con etiqueta legible y nota opcional."""
    clave: str
    etiqueta: str
    importe: float
    nota: str = ""


@dataclass
class ResultadoFiscal:
    """Resultado completo, válido para ambas superficies del producto.

    - La calculadora pública usa: coste_cliente_final, desglose_cliente, ahorro_*.
    - El opportunity finder usa: break_even, y puede leer cualquier componente.
    """
    # --- Componentes fiscales (siempre presentes) ---
    base_iedmt: float
    tipo_iedmt: float                         # tanto por uno ya con recargo autonómico
    iedmt: float
    base_itp: float
    tipo_itp: float
    itp: float
    iva: float                                # IVA español si aplica (nuevos / ROI)
    ivtm_primer_anio: float
    # --- Costes operativos ---
    transporte: float
    itv: float
    tasa_dgt: float
    placas: float
    honorarios_gestion: float
    otros_costes: float                       # CoC, traducción, aduana...
    # --- Totales orientados al CLIENTE (producto público) ---
    coste_cliente_final: float                # todo incluido, puesto en España
    desglose_cliente: list[LineaCoste] = field(default_factory=list)
    # --- Comparación con el mercado español (si se aporta) ---
    precio_mercado_es: Optional[float] = None
    ahorro_absoluto: Optional[float] = None
    ahorro_pct: Optional[float] = None
    # --- Metadatos / trazabilidad ---
    condicion_fiscal: CondicionFiscal = CondicionFiscal.USADO
    version_tablas: str = ""                  # p.ej. "Orden HAC/1501/2025"
    co2_confianza: float = 1.0
    avisos: list[str] = field(default_factory=list)

    def redondeado(self) -> dict:
        """Vista redondeada a céntimos para presentación/serialización."""
        def r(x):
            return None if x is None else round(x, 2)
        return {
            "coste_cliente_final": r(self.coste_cliente_final),
            "iedmt": r(self.iedmt),
            "itp": r(self.itp),
            "iva": r(self.iva),
            "ivtm_primer_anio": r(self.ivtm_primer_anio),
            "ahorro_absoluto": r(self.ahorro_absoluto),
            "ahorro_pct": r(self.ahorro_pct),
            "version_tablas": self.version_tablas,
            "avisos": list(self.avisos),
        }
