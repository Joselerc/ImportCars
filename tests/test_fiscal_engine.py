"""Tests del motor fiscal. Casos exigidos en el plan de ejecución.

Cubre: Honda Civic 1.8 (2006), vehículo eléctrico, fronteras de CO2 119/121,
varias comunidades autónomas, régimen de vendedor, minoración, IVTM por CVF,
prorrateo, vehículo nuevo (IVA) y datos incompletos.
"""

from datetime import date

import pytest

from fiscal_engine import (
    Combustible,
    CondicionFiscal,
    Operacion,
    Origen,
    TipoComprador,
    TipoVendedor,
    Vehiculo,
    break_even_compraventa,
    calcular,
    coeficiente_depreciacion,
    condicion_fiscal,
    tipo_iedmt_estatal,
)

# Fecha de referencia fija para que los tests sean deterministas.
REF = date(2026, 7, 1)


# --------------------------------------------------------------------------- #
#  Depreciación
# --------------------------------------------------------------------------- #


def test_depreciacion_tramos():
    assert coeficiente_depreciacion(0.5) == 1.00
    assert coeficiente_depreciacion(1.5) == 0.84
    assert coeficiente_depreciacion(4.5) == 0.47
    assert coeficiente_depreciacion(11.5) == 0.13


def test_depreciacion_suelo_mas_de_12():
    assert coeficiente_depreciacion(13) == 0.10
    assert coeficiente_depreciacion(20) == 0.10
    assert coeficiente_depreciacion(30) == 0.10


# --------------------------------------------------------------------------- #
#  IEDMT por CO2 — tramos y fronteras
# --------------------------------------------------------------------------- #


def test_iedmt_tramos_co2():
    assert tipo_iedmt_estatal(0) == 0.0
    assert tipo_iedmt_estatal(120) == 0.0  # <= 120 incluido
    assert tipo_iedmt_estatal(121) == 0.0475
    assert tipo_iedmt_estatal(159) == 0.0475
    assert tipo_iedmt_estatal(160) == 0.0975
    assert tipo_iedmt_estatal(199) == 0.0975
    assert tipo_iedmt_estatal(200) == 0.1475
    assert tipo_iedmt_estatal(250) == 0.1475


def test_iedmt_co2_no_acreditado_tipo_maximo():
    assert tipo_iedmt_estatal(None) == 0.1475


def test_frontera_co2_119_vs_121_cambia_tramo():
    """La diferencia de 2 g/km cruza de 0% a 4,75%: debe notarse en la cuota."""
    base = {
        "marca": "VW",
        "modelo": "Golf",
        "fecha_primera_matriculacion": date(2020, 1, 1),
        "precio_compra": 20000,
        "combustible": Combustible.GASOLINA,
        "cilindrada_cc": 1500,
        "valor_tablas_nuevo": 30000,
    }
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Madrid")

    v119 = Vehiculo(co2_gkm=119, **base)
    v121 = Vehiculo(co2_gkm=121, **base)

    r119 = calcular(v119, op, referencia=REF)
    r121 = calcular(v121, op, referencia=REF)

    assert r119.iedmt == 0.0
    assert r121.iedmt > 0.0
    # El de 121 debe costar más en total, solo por el IEDMT.
    assert r121.coste_cliente_final > r119.coste_cliente_final


def test_frontera_genera_aviso():
    v = Vehiculo(
        marca="VW",
        modelo="Golf",
        fecha_primera_matriculacion=date(2020, 1, 1),
        precio_compra=20000,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1500,
        co2_gkm=121,
        valor_tablas_nuevo=30000,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR)
    r = calcular(v, op, referencia=REF)
    assert any("umbral" in a for a in r.avisos)


# --------------------------------------------------------------------------- #
#  Caso Honda Civic 1.8 (2006) — el caso de validación principal
# --------------------------------------------------------------------------- #


def test_honda_civic_2006():
    """>12 años => depreciación al 10%. Particular en Madrid.

    Verifica que la base del IEDMT usa la minoración con IVA histórico 16%
    (matriculado antes de 2010-07-01) y que se pagan ITP, IEDMT, tasas, etc.
    """
    v = Vehiculo(
        marca="Honda",
        modelo="Civic",
        fecha_primera_matriculacion=date(2006, 10, 1),
        precio_compra=1870,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1799,
        co2_gkm=152,  # tramo 4,75%
        kilometros=251000,
        valor_tablas_nuevo=20000,
    )
    op = Operacion(
        tipo_vendedor=TipoVendedor.PARTICULAR,
        comunidad_autonoma="Madrid",
        municipio="Madrid",
    )
    r = calcular(v, op, referencia=REF)

    # Usado (supera 6 meses y 6.000 km).
    assert r.condicion_fiscal == CondicionFiscal.USADO
    # Valor de mercado = 20.000 * 10% = 2.000.
    # Base IEDMT = 2000 / (1 + 0.16 + 0.0475) = 1655.94...
    assert r.base_iedmt == pytest.approx(2000 / (1 + 0.16 + 0.0475), rel=1e-6)
    # IEDMT = base * 4,75%.
    assert r.iedmt == pytest.approx(r.base_iedmt * 0.0475, rel=1e-6)
    # ITP en Madrid = max(1870, 2000) * 4% = 80.
    assert r.itp == pytest.approx(2000 * 0.04, rel=1e-6)
    # Tasa DGT presente.
    assert r.tasa_dgt == pytest.approx(99.77)
    # Honorarios por defecto visibles.
    assert r.honorarios_gestion == 900.0
    # Sin IVA (usado a particular).
    assert r.iva == 0.0
    # Coste final coherente (coche + impuestos + costes + honorarios).
    assert r.coste_cliente_final > v.precio_compra + 900


# --------------------------------------------------------------------------- #
#  Vehículo eléctrico — IEDMT 0%
# --------------------------------------------------------------------------- #


def test_electrico_iedmt_cero():
    v = Vehiculo(
        marca="Tesla",
        modelo="Model 3",
        fecha_primera_matriculacion=date(2022, 6, 1),
        precio_compra=28000,
        combustible=Combustible.ELECTRICO,
        cilindrada_cc=0,
        co2_gkm=0,
        kilometros=40000,
        valor_tablas_nuevo=45000,
        cvf=None,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Madrid")
    r = calcular(v, op, referencia=REF)
    assert r.iedmt == 0.0
    assert r.tipo_iedmt == 0.0
    # Aún así paga ITP (compra a particular), tasas e IVTM.
    assert r.itp > 0.0
    assert r.coste_cliente_final > v.precio_compra


# --------------------------------------------------------------------------- #
#  Recargo autonómico del IEDMT
# --------------------------------------------------------------------------- #


def test_recargo_autonomico_cataluna():
    """Cataluña aplica +15% sobre el tipo estatal del IEDMT."""
    base = {
        "marca": "Audi",
        "modelo": "A4",
        "fecha_primera_matriculacion": date(2019, 1, 1),
        "precio_compra": 25000,
        "combustible": Combustible.DIESEL,
        "cilindrada_cc": 1968,
        "co2_gkm": 140,
        "valor_tablas_nuevo": 45000,
    }
    v = Vehiculo(**base)
    r_madrid = calcular(
        v,
        Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Madrid"),
        referencia=REF,
    )
    r_cat = calcular(
        v,
        Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Cataluna"),
        referencia=REF,
    )
    assert r_cat.tipo_iedmt == pytest.approx(r_madrid.tipo_iedmt * 1.15, rel=1e-6)
    assert r_cat.iedmt > r_madrid.iedmt


def test_itp_varia_por_ccaa():
    """Galicia 3% vs Madrid 4% vs Cantabria 6%."""
    base = {
        "marca": "Seat",
        "modelo": "Leon",
        "fecha_primera_matriculacion": date(2018, 1, 1),
        "precio_compra": 12000,
        "combustible": Combustible.GASOLINA,
        "cilindrada_cc": 1498,
        "co2_gkm": 130,
        "valor_tablas_nuevo": 22000,
    }
    v = Vehiculo(**base)
    r_gal = calcular(
        v,
        Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Galicia"),
        referencia=REF,
    )
    r_mad = calcular(
        v,
        Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Madrid"),
        referencia=REF,
    )
    r_can = calcular(
        v,
        Operacion(
            tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Cantabria"
        ),
        referencia=REF,
    )
    assert r_gal.tipo_itp == 0.03
    assert r_mad.tipo_itp == 0.04
    assert r_can.tipo_itp == 0.06
    assert r_gal.itp < r_mad.itp < r_can.itp


# --------------------------------------------------------------------------- #
#  Régimen de vendedor: ITP solo a particular
# --------------------------------------------------------------------------- #


def test_profesional_no_paga_itp():
    base = {
        "marca": "BMW",
        "modelo": "320d",
        "fecha_primera_matriculacion": date(2019, 3, 1),
        "precio_compra": 22000,
        "combustible": Combustible.DIESEL,
        "cilindrada_cc": 1995,
        "co2_gkm": 125,
        "valor_tablas_nuevo": 42000,
    }
    v = Vehiculo(**base)
    r_part = calcular(
        v, Operacion(tipo_vendedor=TipoVendedor.PARTICULAR), referencia=REF
    )
    r_margen = calcular(
        v, Operacion(tipo_vendedor=TipoVendedor.PROFESIONAL_MARGEN), referencia=REF
    )
    r_iva = calcular(
        v, Operacion(tipo_vendedor=TipoVendedor.PROFESIONAL_IVA), referencia=REF
    )
    assert r_part.itp > 0.0
    assert r_margen.itp == 0.0
    assert r_iva.itp == 0.0


# --------------------------------------------------------------------------- #
#  Vehículo nuevo: IVA español
# --------------------------------------------------------------------------- #


def test_vehiculo_nuevo_por_meses_paga_iva():
    """< 6 meses desde 1ª matriculación => nuevo fiscal => 21% IVA."""
    v = Vehiculo(
        marca="VW",
        modelo="ID.3",
        fecha_primera_matriculacion=date(2026, 5, 1),  # 2 meses antes de REF
        precio_compra=35700,
        precio_neto=30000,
        iva_aleman_desglosable=True,
        combustible=Combustible.ELECTRICO,
        cilindrada_cc=0,
        co2_gkm=0,
        kilometros=3000,
        valor_tablas_nuevo=38000,
    )
    op = Operacion(
        tipo_vendedor=TipoVendedor.PROFESIONAL_IVA,
        tipo_comprador=TipoComprador.PARTICULAR,
    )
    r = calcular(v, op, referencia=REF)
    assert r.condicion_fiscal == CondicionFiscal.NUEVO
    assert r.iva == pytest.approx(0.21 * 30000, rel=1e-6)
    assert r.base_iva == 30000
    assert r.origen_base_iva == "neto_anuncio"


def test_vehiculo_nuevo_por_km():
    """< 6.000 km => nuevo fiscal aunque tenga más de 6 meses."""
    v = Vehiculo(
        marca="VW",
        modelo="Golf",
        fecha_primera_matriculacion=date(2025, 1, 1),
        precio_compra=25000,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1498,
        co2_gkm=130,
        kilometros=1200,
        valor_tablas_nuevo=32000,
    )
    assert condicion_fiscal(v, REF) == CondicionFiscal.NUEVO


def test_exactly_six_months_and_6000_km_is_used() -> None:
    vehicle = Vehiculo(
        marca="Volkswagen",
        modelo="Golf",
        fecha_primera_matriculacion=date(2026, 1, 1),
        precio_compra=25_000,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1498,
        kilometros=6_000,
    )

    assert condicion_fiscal(vehicle, date(2026, 6, 30)) == CondicionFiscal.NUEVO
    assert condicion_fiscal(vehicle, date(2026, 7, 1)) == CondicionFiscal.USADO


def _used_vat_vehicle() -> Vehiculo:
    return Vehiculo(
        marca="Volkswagen",
        modelo="Golf 1.5 TSI",
        fecha_primera_matriculacion=date(2017, 11, 1),
        precio_compra=15_990,
        precio_neto=13_436.97,
        iva_aleman_desglosable=True,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1498,
        co2_gkm=130,
        kilometros=109_800,
        valor_tablas_nuevo=30_000,
    )


def test_used_particular_never_pays_spanish_vat_regression() -> None:
    result = calcular(
        _used_vat_vehicle(),
        Operacion(tipo_vendedor=TipoVendedor.PARTICULAR),
        referencia=REF,
    )

    assert result.condicion_fiscal == CondicionFiscal.USADO
    assert result.iva == 0
    assert result.itp > 0
    assert result.caso_iva == "usado_particular"
    assert result.precio_adquisicion == 15_990
    assert result.coste_cliente_final == pytest.approx(19_043.37819085487)


def test_used_professional_with_itemized_vat_has_no_spanish_vat() -> None:
    result = calcular(
        _used_vat_vehicle(),
        Operacion(tipo_vendedor=TipoVendedor.PROFESIONAL_IVA),
        referencia=REF,
    )

    assert result.iva == 0
    assert result.itp == 0
    assert result.caso_iva == "usado_profesional_iva"
    assert result.precio_adquisicion == 15_990
    assert result.coste_cliente_final == pytest.approx(18_403.77819085487)


def test_used_margin_scheme_has_no_spanish_vat() -> None:
    vehicle = _used_vat_vehicle()
    vehicle.precio_neto = None
    vehicle.iva_aleman_desglosable = False

    result = calcular(
        vehicle,
        Operacion(tipo_vendedor=TipoVendedor.PROFESIONAL_MARGEN),
        referencia=REF,
    )

    assert result.iva == 0
    assert result.itp == 0
    assert result.caso_iva == "usado_profesional_margen"
    assert result.precio_adquisicion == 15_990
    assert result.coste_cliente_final == pytest.approx(18_403.77819085487)


def test_new_vehicle_uses_advertised_net_price_before_any_calculation() -> None:
    vehicle = Vehiculo(
        marca="Peugeot",
        modelo="E-5008 GT",
        fecha_primera_matriculacion=REF,
        precio_compra=54_550,
        precio_neto=45_840.34,
        iva_aleman_desglosable=True,
        nuevo_sin_matricular=True,
        combustible=Combustible.ELECTRICO,
        cilindrada_cc=0,
        co2_gkm=0,
        kilometros=16,
        valor_tablas_nuevo=41_100,
    )

    result = calcular(
        vehicle,
        Operacion(tipo_vendedor=TipoVendedor.PROFESIONAL_IVA),
        referencia=REF,
    )

    assert result.base_iva == 45_840.34
    assert result.origen_base_iva == "neto_anuncio"
    assert result.iva == pytest.approx(45_840.34 * 0.21)
    assert result.precio_adquisicion == 45_840.34
    price_line = next(line for line in result.desglose_cliente if line.clave == "precio")
    assert price_line.importe == 45_840.34
    assert "IVA español" in price_line.nota
    assert price_line.importe + result.iva == pytest.approx(45_840.34 * 1.21)
    assert result.coste_cliente_final == pytest.approx(
        sum(line.importe for line in result.desglose_cliente)
    )


def test_new_professional_gross_price_derives_net_by_dividing_1_19() -> None:
    vehicle = Vehiculo(
        marca="Volkswagen",
        modelo="ID.3",
        fecha_primera_matriculacion=REF,
        precio_compra=37_890,
        iva_aleman_desglosable=True,
        nuevo_sin_matricular=True,
        combustible=Combustible.ELECTRICO,
        cilindrada_cc=0,
        co2_gkm=0,
        kilometros=10,
        valor_tablas_nuevo=38_000,
    )

    result = calcular(
        vehicle,
        Operacion(tipo_vendedor=TipoVendedor.PROFESIONAL_IVA),
        referencia=REF,
    )

    assert result.base_iva == pytest.approx(37_890 / 1.19)
    assert result.origen_base_iva == "bruto_dividido_1_19"
    assert result.iva == pytest.approx((37_890 / 1.19) * 0.21)
    assert result.precio_adquisicion == pytest.approx(37_890 / 1.19)
    price_line = next(line for line in result.desglose_cliente if line.clave == "precio")
    assert price_line.importe == pytest.approx(37_890 / 1.19)
    assert price_line.importe + result.iva == pytest.approx((37_890 / 1.19) * 1.21)


@pytest.mark.parametrize(
    "seller_type",
    [TipoVendedor.PARTICULAR, TipoVendedor.PROFESIONAL_MARGEN],
)
def test_new_without_deductible_german_vat_uses_untouched_price(
    seller_type: TipoVendedor,
) -> None:
    vehicle = Vehiculo(
        marca="Volkswagen",
        modelo="ID.3",
        fecha_primera_matriculacion=REF,
        precio_compra=30_000,
        nuevo_sin_matricular=True,
        combustible=Combustible.ELECTRICO,
        cilindrada_cc=0,
        co2_gkm=0,
        kilometros=10,
        valor_tablas_nuevo=38_000,
    )

    result = calcular(
        vehicle,
        Operacion(tipo_vendedor=seller_type),
        referencia=REF,
    )

    assert result.base_iva == 30_000
    assert result.origen_base_iva == "precio_sin_iva_desglosable"
    assert result.iva == 6_300
    assert result.itp == 0
    assert result.precio_adquisicion == 30_000


def test_roi_company_uses_net_purchase_and_zero_net_vat_cost() -> None:
    vehicle = Vehiculo(
        marca="Peugeot",
        modelo="E-5008 GT",
        fecha_primera_matriculacion=REF,
        precio_compra=54_550,
        precio_neto=45_840.34,
        iva_aleman_desglosable=True,
        nuevo_sin_matricular=True,
        combustible=Combustible.ELECTRICO,
        cilindrada_cc=0,
        co2_gkm=0,
        kilometros=16,
        valor_tablas_nuevo=41_100,
    )

    result = calcular(
        vehicle,
        Operacion(
            tipo_vendedor=TipoVendedor.PROFESIONAL_IVA,
            tipo_comprador=TipoComprador.EMPRESA_ROI,
        ),
        referencia=REF,
    )

    assert result.caso_iva == "empresa_roi"
    assert result.iva == 0
    assert result.base_iva == 45_840.34
    assert result.precio_adquisicion == 45_840.34


def test_unregistered_vehicle_marked_new_is_new_without_registration_age() -> None:
    vehicle = _used_vat_vehicle()
    vehicle.nuevo_sin_matricular = True

    assert condicion_fiscal(vehicle, REF) == CondicionFiscal.NUEVO


# --------------------------------------------------------------------------- #
#  IVTM por CVF y prorrateo
# --------------------------------------------------------------------------- #


def test_ivtm_usa_cvf_de_ficha_si_existe():
    v = Vehiculo(
        marca="X",
        modelo="Y",
        fecha_primera_matriculacion=date(2018, 1, 1),
        precio_compra=10000,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1600,
        co2_gkm=140,
        cvf=12.5,
        valor_tablas_nuevo=20000,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, municipio="Madrid")
    # Prorrateo desde julio (REF): trimestre 3 => 2 trimestres restantes => mitad.
    r = calcular(v, op, referencia=REF)
    # CVF 12.5 => tramo 12-16 => 71.94 * coef 1.0. Prorrateado 2/4 = 35.97.
    assert r.ivtm_primer_anio == pytest.approx(71.94 * 0.5, rel=1e-6)


def test_ivtm_no_es_valor_fijo():
    """Regresión del bug: el IVTM no puede ser siempre 224 (peor caso)."""
    v = Vehiculo(
        marca="X",
        modelo="Y",
        fecha_primera_matriculacion=date(2018, 1, 1),
        precio_compra=10000,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1200,
        co2_gkm=120,
        cvf=9.0,
        valor_tablas_nuevo=18000,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, municipio="Madrid")
    r = calcular(v, op, referencia=date(2026, 1, 1))  # año completo
    # CVF 9 => tramo 8-12 => 34.08. Muy lejos de 224.
    assert r.ivtm_primer_anio == pytest.approx(34.08, rel=1e-6)


# --------------------------------------------------------------------------- #
#  Ahorro vs mercado español
# --------------------------------------------------------------------------- #


def test_ahorro_vs_mercado_es():
    v = Vehiculo(
        marca="VW",
        modelo="Golf GTI",
        fecha_primera_matriculacion=date(2020, 1, 1),
        precio_compra=24500,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1984,
        co2_gkm=148,
        kilometros=60000,
        valor_tablas_nuevo=38000,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Madrid")
    r = calcular(v, op, precio_mercado_es=30000, referencia=REF)
    assert r.precio_mercado_es == 30000
    assert r.ahorro_absoluto == pytest.approx(30000 - r.coste_cliente_final, rel=1e-9)
    assert r.ahorro_pct == pytest.approx(r.ahorro_absoluto / 30000 * 100, rel=1e-9)


# --------------------------------------------------------------------------- #
#  Datos incompletos
# --------------------------------------------------------------------------- #


def test_co2_none_aplica_maximo_y_avisa():
    v = Vehiculo(
        marca="X",
        modelo="Y",
        fecha_primera_matriculacion=date(2015, 1, 1),
        precio_compra=9000,
        combustible=Combustible.DIESEL,
        cilindrada_cc=1600,
        co2_gkm=None,
        valor_tablas_nuevo=25000,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR)
    r = calcular(v, op, referencia=REF)
    assert r.tipo_iedmt == pytest.approx(0.1475)
    assert any("CO2 no acreditado" in a for a in r.avisos)


def test_sin_valor_tablas_estima_y_avisa():
    v = Vehiculo(
        marca="X",
        modelo="Y",
        fecha_primera_matriculacion=date(2016, 1, 1),
        precio_compra=8000,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1400,
        co2_gkm=135,
    )  # sin valor_tablas_nuevo
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR)
    r = calcular(v, op, referencia=REF)
    assert any("Valor de tablas" in a for a in r.avisos)
    assert r.coste_cliente_final > 0


# --------------------------------------------------------------------------- #
#  Compatibilidad con el opportunity finder (break-even)
# --------------------------------------------------------------------------- #


def test_break_even_no_incluye_honorarios():
    v = Vehiculo(
        marca="BMW",
        modelo="320d",
        fecha_primera_matriculacion=date(2019, 1, 1),
        precio_compra=22000,
        combustible=Combustible.DIESEL,
        cilindrada_cc=1995,
        co2_gkm=125,
        valor_tablas_nuevo=42000,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, comunidad_autonoma="Madrid")
    be = break_even_compraventa(v, op, referencia=REF)
    r_cliente = calcular(v, op, referencia=REF)
    # El break-even (sin honorarios) es exactamente 900 menos que el coste cliente.
    assert be["break_even"] == pytest.approx(
        r_cliente.coste_cliente_final - 900, rel=1e-9
    )
    assert "iedmt" in be and "itp" in be and "version_tablas" in be


def test_traslado_residencia_exime():
    v = Vehiculo(
        marca="Audi",
        modelo="A3",
        fecha_primera_matriculacion=date(2021, 1, 1),
        precio_compra=20000,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1498,
        co2_gkm=130,
        valor_tablas_nuevo=32000,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, traslado_residencia=True)
    r = calcular(v, op, referencia=REF)
    assert r.itp == 0.0  # exención


def test_extra_ue_incluye_arancel_e_iva_importacion():
    v = Vehiculo(
        marca="Toyota",
        modelo="Land Cruiser",
        fecha_primera_matriculacion=date(2019, 1, 1),
        precio_compra=30000,
        combustible=Combustible.DIESEL,
        cilindrada_cc=2755,
        co2_gkm=220,
        valor_tablas_nuevo=60000,
    )
    op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, origen=Origen.EXTRA_UE)
    r_ue = calcular(
        v,
        Operacion(tipo_vendedor=TipoVendedor.PARTICULAR, origen=Origen.UE),
        referencia=REF,
    )
    r_extra = calcular(v, op, referencia=REF)
    # Extra-UE debe costar bastante más por arancel + IVA de importación.
    assert r_extra.coste_cliente_final > r_ue.coste_cliente_final
    assert any("fuera de la UE" in a for a in r_extra.avisos)
