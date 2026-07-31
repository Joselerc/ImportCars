"""
Calculadora de costes de importación de vehículos de Alemania a España (Comunidad de Madrid)

Implementa 3 casos de compra:
1. Particular: ITP (4%) + IEDMT
2. EmpresaIVA: IVA alemán incluido/no deducible + IEDMT
3. EmpresaMargen: Régimen de margen §25a UStG (Differenzbesteuerung) + IEDMT

Régimen de venta: REBU (IVA solo sobre el margen)
"""

from typing import Dict, Literal, Optional
from enum import Enum


class TipoCompra(str, Enum):
    """Tipo de vendedor en Alemania"""

    PARTICULAR = "Particular"
    EMPRESA_IVA = "EmpresaIVA"
    EMPRESA_MARGEN = "EmpresaMargen"


class ImportCalculator:
    """Calcula los costes de importación de Alemania a España (Madrid)"""

    # Constantes fiscales (Madrid)
    ITP_MADRID = 0.04  # 4% Impuesto de Transmisiones Patrimoniales
    IVA_VENTA = 0.21  # 21% IVA sobre el margen (régimen REBU)

    # Tramos IEDMT (Impuesto Especial sobre Determinados Medios de Transporte)
    # Según emisiones WLTP (g/km CO2)
    TRAMOS_IEDMT = [
        (120, 0.0),  # 0-120 g/km → 0%
        (159, 0.0475),  # 121-159 g/km → 4.75%
        (199, 0.0975),  # 160-199 g/km → 9.75%
        (float("inf"), 0.1475),  # ≥200 g/km → 14.75%
    ]

    # Costes base (Madrid)
    TRANSPORTE_DEFAULT = 1100  # €1000-1200
    ITV_TASA = 160  # Tasa ITV
    TRADUCCIONES = 200  # Traducción de documentos
    IVTM_MADRID = 224  # Impuesto vehículos tracción mecánica (≥20 CVF)
    PLACAS = 30  # Placas de matrícula

    def __init__(
        self,
        transporte: float = TRANSPORTE_DEFAULT,
        itv_tasa: float = ITV_TASA,
        traducciones: float = TRADUCCIONES,
        ivtm: float = IVTM_MADRID,
        placas: float = PLACAS,
    ):
        """
        Inicializa la calculadora con costes personalizables

        Args:
            transporte: Coste de transporte DE→ES (€)
            itv_tasa: Tasa de ITV (€)
            traducciones: Coste de traducción de documentos (€)
            ivtm: Impuesto vehículos tracción mecánica (€)
            placas: Coste de placas de matrícula (€)
        """
        self.transporte = transporte
        self.itv_tasa = itv_tasa
        self.traducciones = traducciones
        self.ivtm = ivtm
        self.placas = placas
        self.costes_base = transporte + itv_tasa + traducciones + ivtm + placas

    def rate_iedmt(self, co2: Optional[int]) -> float:
        """
        Calcula el tipo de IEDMT según emisiones CO2 WLTP

        Args:
            co2: Emisiones en g/km (None si no disponible)

        Returns:
            Tipo de IEDMT (0.0 a 0.1475)
        """
        # Si no hay datos de CO2, usar el peor caso
        if co2 is None:
            return self.TRAMOS_IEDMT[-1][1]

        for limite, tasa in self.TRAMOS_IEDMT:
            if co2 <= limite:
                return tasa
        return self.TRAMOS_IEDMT[-1][1]  # Por defecto, máximo

    def calcular_costes_importacion(
        self,
        precio_alemania: float,
        tipo_compra: TipoCompra,
        co2: Optional[int],
        cvf: int = 20,
    ) -> Dict[str, float]:
        """
        Calcula todos los costes de importación según el tipo de compra

        Args:
            precio_alemania: Precio del vehículo en Alemania (€)
            tipo_compra: Tipo de vendedor (Particular, EmpresaIVA, EmpresaMargen)
            co2: Emisiones WLTP (g/km)
            cvf: Caballos fiscales (para IVTM, por defecto ≥20)

        Returns:
            Dict con desglose completo de costes
        """
        P = precio_alemania
        t_iedmt = self.rate_iedmt(co2)

        # Impuestos de compra según el caso
        if tipo_compra == TipoCompra.PARTICULAR:
            itp = self.ITP_MADRID * P
            iedmt = t_iedmt * P
        elif tipo_compra == TipoCompra.EMPRESA_IVA:
            # IVA alemán incluido/no deducible
            itp = 0
            iedmt = t_iedmt * P
        elif tipo_compra == TipoCompra.EMPRESA_MARGEN:
            # §25a UStG (Differenzbesteuerung)
            itp = 0
            iedmt = t_iedmt * P
        else:
            raise ValueError(f"Tipo de compra inválido: {tipo_compra}")

        # Coste total
        coste_total = P + itp + iedmt + self.costes_base

        return {
            "precio_alemania": round(P, 2),
            "tipo_compra": tipo_compra.value,
            "co2_gkm": co2,
            "tasa_iedmt": round(t_iedmt * 100, 2),  # En %
            # Impuestos
            "itp": round(itp, 2),
            "iedmt": round(iedmt, 2),
            # Costes base
            "transporte": round(self.transporte, 2),
            "itv_tasa": round(self.itv_tasa, 2),
            "traducciones": round(self.traducciones, 2),
            "ivtm": round(self.ivtm, 2),
            "placas": round(self.placas, 2),
            "costes_base_total": round(self.costes_base, 2),
            # Total
            "coste_total": round(coste_total, 2),
            "break_even": round(coste_total, 2),  # Precio mínimo para no perder
        }

    def calcular_beneficio_venta(
        self, costes_importacion: Dict[str, float], precio_venta_espana: float
    ) -> Dict[str, float]:
        """
        Calcula el beneficio neto al vender en España (régimen REBU)

        En régimen REBU (Régimen Especial de Bienes Usados):
        - IVA solo sobre el margen (beneficio)
        - No se cobra IVA si no hay margen positivo

        Args:
            costes_importacion: Dict devuelto por calcular_costes_importacion()
            precio_venta_espana: Precio de venta propuesto en España (€)

        Returns:
            Dict con análisis de beneficio
        """
        coste_total = costes_importacion["coste_total"]
        S = precio_venta_espana

        # Margen bruto
        margen_bruto = S - coste_total

        # IVA sobre el margen (solo si hay beneficio)
        iva_venta = max(0, self.IVA_VENTA * margen_bruto)

        # Beneficio neto
        beneficio_neto = margen_bruto - iva_venta

        return {
            "precio_venta_espana": round(S, 2),
            "coste_total": round(coste_total, 2),
            "margen_bruto": round(margen_bruto, 2),
            "iva_venta": round(iva_venta, 2),
            "beneficio_neto": round(beneficio_neto, 2),
            "rentabilidad_porcentaje": round(
                (beneficio_neto / coste_total * 100) if coste_total > 0 else 0, 2
            ),
        }

    def analisis_completo(
        self,
        precio_alemania: float,
        tipo_compra: TipoCompra,
        co2: int,
        precio_venta_espana: float,
        cvf: int = 20,
    ) -> Dict[str, any]:
        """
        Análisis completo: costes + beneficio

        Args:
            precio_alemania: Precio del vehículo en Alemania (€)
            tipo_compra: Tipo de vendedor
            co2: Emisiones WLTP (g/km)
            precio_venta_espana: Precio de venta propuesto en España (€)
            cvf: Caballos fiscales

        Returns:
            Dict con análisis completo
        """
        costes = self.calcular_costes_importacion(
            precio_alemania, tipo_compra, co2, cvf
        )
        beneficio = self.calcular_beneficio_venta(costes, precio_venta_espana)

        return {**costes, **beneficio, "es_rentable": beneficio["beneficio_neto"] > 0}

    def comparar_casos(
        self,
        precio_alemania: float,
        co2: int,
        precio_venta_espana: float,
        cvf: int = 20,
    ) -> Dict[TipoCompra, Dict[str, any]]:
        """
        Compara los 3 casos de compra para el mismo vehículo

        Returns:
            Dict con análisis para cada tipo de compra
        """
        resultados = {}

        for tipo in TipoCompra:
            resultados[tipo] = self.analisis_completo(
                precio_alemania, tipo, co2, precio_venta_espana, cvf
            )

        return resultados


# Instancia global con valores por defecto
import_calculator = ImportCalculator()
