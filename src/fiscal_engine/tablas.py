"""Tablas y constantes fiscales (año fiscal 2026).

Estas tablas son configurables y deben revisarse cada enero cuando se publica
la nueva Orden Ministerial de precios medios. La carga del valor de mercado del
vehículo (Anexo I) vive en la base SQLite que ya ingesta Cursor
(`data/import_cars.sqlite3`); aquí solo están los coeficientes y tipos.

Fuentes:
  - Depreciación: Anexo IV, Orden HAC/1501/2025.
  - IEDMT por CO2: art. 70 Ley 38/1992.
  - Recargos autonómicos IEDMT y tipos ITP: normativa autonómica vigente 2026.
  - Tarifas IVTM: art. 95 TRLRHL.
"""

from __future__ import annotations

VERSION_TABLAS = "Orden HAC/1501/2025"

# --------------------------------------------------------------------------- #
#  Depreciación por antigüedad (Anexo IV). % del valor nuevo.
#  Tramos: (limite_superior_anios_inclusive, porcentaje).
#  El último tramo (>12 años) es el suelo del 10%.
# --------------------------------------------------------------------------- #
DEPRECIACION = [
    (1, 1.00),
    (2, 0.84),
    (3, 0.67),
    (4, 0.56),
    (5, 0.47),
    (6, 0.39),
    (7, 0.34),
    (8, 0.28),
    (9, 0.24),
    (10, 0.19),
    (11, 0.17),
    (12, 0.13),
]
DEPRECIACION_SUELO = 0.10  # > 12 años

# Reducción adicional del art. 5 para uso profesional exclusivo >6 meses
# (autoescuela, alquiler sin conductor, taxi): valor de mercado al 70%.
REDUCCION_USO_PROFESIONAL = 0.70


# --------------------------------------------------------------------------- #
#  IEDMT por emisiones de CO2 (tipos estatales). Tanto por uno.
#  Tramos: (co2_max_exclusivo, tipo). CO2 no acreditado => tramo máximo.
# --------------------------------------------------------------------------- #
IEDMT_TRAMOS = [
    (120.0, 0.00),     # <= 120 g/km  -> 0%   (el <= se maneja en la función)
    (160.0, 0.0475),   # 121-159      -> 4,75%
    (200.0, 0.0975),   # 160-199      -> 9,75%
]
IEDMT_TIPO_MAXIMO = 0.1475  # >= 200 g/km o CO2 no acreditado


# --------------------------------------------------------------------------- #
#  Recargo autonómico del IEDMT (+15% sobre el tipo estatal) en las CCAA que
#  lo aplican. El resto: sin recargo (factor 1.0).
# --------------------------------------------------------------------------- #
RECARGO_IEDMT_CCAA = {
    "Andalucia": 0.15,
    "Asturias": 0.15,
    "Baleares": 0.15,
    "Cantabria": 0.15,
    "Cataluna": 0.15,
    "Murcia": 0.15,
    "Comunidad Valenciana": 0.15,
}


# --------------------------------------------------------------------------- #
#  IVA histórico según fecha de 1ª matriculación (para la minoración del IEDMT).
#  Tramos: (fecha_limite_ISO, tipo). El primero que cumpla fecha < limite gana.
# --------------------------------------------------------------------------- #
IVA_HISTORICO = [
    ("2010-07-01", 0.16),
    ("2012-09-01", 0.18),
]
IVA_HISTORICO_ACTUAL = 0.21  # desde 2012-09-01
IVA_ESPANA = 0.21
IVA_ALEMANIA = 0.19


# --------------------------------------------------------------------------- #
#  ITP: tipo general por CCAA (tanto por uno). Simplificado; las cuotas fijas
#  de algunas CCAA para coches antiguos se tratan como caso aparte donde
#  proceda. Verificar anualmente.
# --------------------------------------------------------------------------- #
ITP_POR_CCAA = {
    "Galicia": 0.03,
    "Madrid": 0.04,
    "Aragon": 0.04,
    "Asturias": 0.04,
    "Baleares": 0.04,
    "Murcia": 0.04,
    "Pais Vasco": 0.04,
    "La Rioja": 0.04,
    "Andalucia": 0.04,
    "Cataluna": 0.05,
    "Castilla y Leon": 0.05,
    "Cantabria": 0.06,
    "Castilla-La Mancha": 0.06,
    "Comunidad Valenciana": 0.06,
    "Extremadura": 0.06,
    "Navarra": 0.06,
    "Canarias": 0.065,  # IGIC entre particulares (no hay ITP)
}
ITP_TIPO_DEFECTO = 0.04


# --------------------------------------------------------------------------- #
#  IVTM: tarifas base estatales anuales (art. 95 TRLRHL). Cada ayuntamiento
#  aplica un coeficiente (1.0 - 2.0). Tramos por potencia fiscal (CVF).
#  Tramos: (cvf_max_exclusivo, tarifa_base_anual_eur).
# --------------------------------------------------------------------------- #
IVTM_TRAMOS = [
    (8.0, 12.62),
    (12.0, 34.08),
    (16.0, 71.94),
    (20.0, 89.61),
]
IVTM_TARIFA_MAXIMA = 112.00  # >= 20 CVF

# Coeficiente municipal por defecto (Madrid capital ~1.0 en el tramo relevante).
# Idealmente se lee de una tabla por municipio; aquí, valor conservador.
IVTM_COEF_MUNICIPAL_DEFECTO = 1.0
IVTM_COEF_POR_MUNICIPIO = {
    "Madrid": 1.0,
    "Leganes": 1.0,
    "Barcelona": 1.4,
    "Valencia": 1.3,
    "Sevilla": 1.3,
}


def normaliza_ccaa(nombre: str) -> str:
    """Normaliza el nombre de la CCAA quitando tildes y espacios sobrantes."""
    if not nombre:
        return ""
    tabla = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return nombre.strip().translate(tabla)
