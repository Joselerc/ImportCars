"""Motor de cálculo fiscal para importación de vehículos DE -> ES.

Fuente única de verdad. Expone:
  - calcular(vehiculo, operacion, costes, precio_mercado_es) -> ResultadoFiscal
    Cálculo completo orientado al CLIENTE FINAL (producto público).
  - break_even_compraventa(...) -> dict
    Vista orientada al DEALER (opportunity finder), sin romper su contrato.

Las fórmulas implementan:
  - Depreciación por antigüedad (Anexo IV).
  - Minoración del art. 5 de la Orden de precios medios:
        BI_IEDMT = VM / (1 + IVA_hist + IEDMT_hist)
  - IEDMT por CO2 con recargo autonómico.
  - ITP = max(precio, valor_tablas_depreciado) x tipo_CCAA (solo particular).
  - IVA español para vehículos nuevos o adquisición intracomunitaria con ROI.
  - IVTM por potencia fiscal x coeficiente municipal, prorrateado.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from . import tablas as T
from .models import (
    CondicionFiscal,
    CostesConfig,
    LineaCoste,
    Operacion,
    Origen,
    ResultadoFiscal,
    TipoCarroceria,
    TipoVendedor,
    Vehiculo,
)

# --------------------------------------------------------------------------- #
#  Antigüedad y depreciación
# --------------------------------------------------------------------------- #

def antiguedad_anios(fecha_matriculacion: date, referencia: date | None = None) -> float:
    """Años transcurridos desde la 1ª matriculación (con fracción)."""
    ref = referencia or date.today()
    dias = (ref - fecha_matriculacion).days
    return max(dias / 365.25, 0.0)


def coeficiente_depreciacion(anios: float) -> float:
    """Devuelve el % del valor nuevo según el Anexo IV.

    Los tramos son 'más de N-1, hasta N años' -> se usa ceil sobre el límite
    superior inclusive. Ejemplo: 0.5 años -> tramo 'hasta 1' -> 100%.
    """
    for limite, pct in T.DEPRECIACION:
        if anios <= limite:
            return pct
    return T.DEPRECIACION_SUELO


def valor_mercado(vehiculo: Vehiculo, referencia: date | None = None,
                  uso_profesional: bool = False) -> float:
    """Valor de mercado = valor_tablas_nuevo x coef_depreciacion.

    `valor_tablas_nuevo` debe venir resuelto desde la base del BOE
    (data/import_cars.sqlite3). Si no se aporta, se usa el precio de compra
    como aproximación conservadora (y se deja un aviso en el resultado).
    """
    anios = antiguedad_anios(vehiculo.fecha_primera_matriculacion, referencia)
    coef = coeficiente_depreciacion(anios)
    base_nuevo = vehiculo.valor_tablas_nuevo
    if base_nuevo is None:
        # Fallback: sin tabla, el mejor proxy disponible es el precio pagado.
        base_nuevo = vehiculo.precio_compra / coef if coef > 0 else vehiculo.precio_compra
    vm = base_nuevo * coef
    if uso_profesional:
        vm *= T.REDUCCION_USO_PROFESIONAL
    return vm


# --------------------------------------------------------------------------- #
#  Condición fiscal nuevo / usado
# --------------------------------------------------------------------------- #

def condicion_fiscal(vehiculo: Vehiculo, referencia: date | None = None) -> CondicionFiscal:
    """Nuevo si < 6 meses desde 1ª matriculación O < 6.000 km."""
    ref = referencia or date.today()
    meses = (ref - vehiculo.fecha_primera_matriculacion).days / 30.4375
    if meses < 6:
        return CondicionFiscal.NUEVO
    if vehiculo.kilometros is not None and vehiculo.kilometros < 6000:
        return CondicionFiscal.NUEVO
    return CondicionFiscal.USADO


# --------------------------------------------------------------------------- #
#  IEDMT
# --------------------------------------------------------------------------- #

def tipo_iedmt_estatal(co2_gkm: float | None) -> float:
    """Tipo estatal del IEDMT según CO2. None -> tipo máximo."""
    if co2_gkm is None:
        return T.IEDMT_TIPO_MAXIMO
    if co2_gkm <= 120.0:
        return 0.0
    for co2_max, tipo in T.IEDMT_TRAMOS:
        if co2_gkm < co2_max:
            return tipo
    return T.IEDMT_TIPO_MAXIMO


def _iva_historico(fecha_matriculacion: date) -> float:
    iso = fecha_matriculacion.isoformat()
    for limite, tipo in T.IVA_HISTORICO:
        if iso < limite:
            return tipo
    return T.IVA_HISTORICO_ACTUAL


def base_imponible_iedmt(vehiculo: Vehiculo, vm: float) -> float:
    """Minoración del art. 5: BI = VM / (1 + IVA_hist + IEDMT_hist).

    El IEDMT histórico usado en el denominador es el que le habría correspondido
    al vehículo por sus emisiones (aproximación estándar del cálculo de la
    minoración para vehículos previamente matriculados en el extranjero).
    """
    iva_hist = _iva_historico(vehiculo.fecha_primera_matriculacion)
    iedmt_hist = tipo_iedmt_estatal(vehiculo.co2_gkm)
    return vm / (1.0 + iva_hist + iedmt_hist)


def calcular_iedmt(vehiculo: Vehiculo, operacion: Operacion, vm: float) -> tuple[float, float, float]:
    """Devuelve (base_imponible, tipo_efectivo, cuota) del IEDMT."""
    ccaa = T.normaliza_ccaa(operacion.comunidad_autonoma)
    recargo = T.RECARGO_IEDMT_CCAA.get(ccaa, 0.0)
    tipo = tipo_iedmt_estatal(vehiculo.co2_gkm) * (1.0 + recargo)
    base = base_imponible_iedmt(vehiculo, vm)
    return base, tipo, base * tipo


# --------------------------------------------------------------------------- #
#  ITP
# --------------------------------------------------------------------------- #

def calcular_itp(vehiculo: Vehiculo, operacion: Operacion, vm: float) -> tuple[float, float, float]:
    """ITP solo si se compra a particular. Base = max(precio, VM).

    Devuelve (base, tipo, cuota). Si no aplica, todo a 0.
    """
    if operacion.tipo_vendedor != TipoVendedor.PARTICULAR:
        return 0.0, 0.0, 0.0
    if operacion.traslado_residencia:
        return 0.0, 0.0, 0.0
    ccaa = T.normaliza_ccaa(operacion.comunidad_autonoma)
    tipo = T.ITP_POR_CCAA.get(ccaa, T.ITP_TIPO_DEFECTO)
    base = max(vehiculo.precio_compra, vm)
    return base, tipo, base * tipo


# --------------------------------------------------------------------------- #
#  IVA
# --------------------------------------------------------------------------- #

def calcular_iva(vehiculo: Vehiculo, operacion: Operacion,
                 condicion: CondicionFiscal) -> float:
    """IVA español que hay que ingresar en España.

    - Vehículo NUEVO: 21% siempre (modelo 309), venga de donde venga.
    - Usado + comprador EMPRESA_ROI + vendedor profesional con IVA: adquisición
      intracomunitaria; se autorepercute y se deduce -> efecto neto 0 (no es un
      coste). Devolvemos 0 como coste neto.
    - Usado + particular o margen: sin IVA español (paga ITP o va en el precio).
    """
    if operacion.traslado_residencia:
        return 0.0
    if condicion == CondicionFiscal.NUEVO:
        return T.IVA_ESPANA * vehiculo.precio_compra
    return 0.0


# --------------------------------------------------------------------------- #
#  IVTM
# --------------------------------------------------------------------------- #

def potencia_fiscal_cvf(vehiculo: Vehiculo) -> float:
    """Potencia fiscal en CVF.

    Si la ficha ya la trae (vehiculo.cvf), se usa. Si no, se estima con una
    aproximación a partir de la cilindrada (regla práctica; la CVF real depende
    de diámetro y carrera, no solo de la cilindrada, pero para un turismo esta
    aproximación es razonable y siempre es preferible el dato de la ficha).
    """
    if vehiculo.cvf is not None:
        return vehiculo.cvf
    # Aproximación: ~1 CVF por cada ~180 cc para turismos modernos.
    # Es una estimación; el valor correcto viene de la ficha técnica.
    return round(vehiculo.cilindrada_cc / 180.0, 2)


def tarifa_ivtm(cvf: float) -> float:
    for cvf_max, tarifa in T.IVTM_TRAMOS:
        if cvf < cvf_max:
            return tarifa
    return T.IVTM_TARIFA_MAXIMA


def calcular_ivtm_primer_anio(vehiculo: Vehiculo, operacion: Operacion,
                              referencia: date | None = None) -> float:
    """IVTM del primer año, prorrateado por trimestres desde la matriculación.

    El alta se produce al matricular; el primer año se prorratea por los
    trimestres naturales que restan (incluido el de alta).
    """
    ref = referencia or date.today()
    cvf = potencia_fiscal_cvf(vehiculo)
    base = tarifa_ivtm(cvf)
    municipio = operacion.municipio
    coef = T.IVTM_COEF_POR_MUNICIPIO.get(municipio, T.IVTM_COEF_MUNICIPAL_DEFECTO)
    cuota_anual = base * coef
    # Prorrateo por trimestres restantes (1..4).
    trimestre_alta = (ref.month - 1) // 3 + 1
    trimestres_restantes = 4 - trimestre_alta + 1
    return cuota_anual * trimestres_restantes / 4.0


# --------------------------------------------------------------------------- #
#  Cálculo completo — CLIENTE FINAL
# --------------------------------------------------------------------------- #


def estimar_coste_transporte(vehiculo: Vehiculo, costes: CostesConfig) -> float:
    """Resolve el transporte operativo por carrocería, sin tocar impuestos."""

    if costes.transporte is not None:
        return costes.transporte
    if vehiculo.carroceria in {TipoCarroceria.SUV, TipoCarroceria.MONOVOLUMEN}:
        return costes.transporte_suv_monovolumen
    if vehiculo.carroceria == TipoCarroceria.DEPORTIVO_GAMA_ALTA:
        return costes.transporte_deportivo_gama_alta
    return costes.transporte_turismo


def _nota_transporte(vehiculo: Vehiculo, costes: CostesConfig) -> str:
    if costes.transporte is not None:
        return "Importe de transporte configurado para esta operación"
    if vehiculo.carroceria in {TipoCarroceria.SUV, TipoCarroceria.MONOVOLUMEN}:
        return "Estimación para SUV o monovolumen"
    if vehiculo.carroceria == TipoCarroceria.DEPORTIVO_GAMA_ALTA:
        return "Estimación para deportivo o gama alta"
    if vehiculo.carroceria == TipoCarroceria.FAMILIAR:
        return "Estimación para vehículo familiar"
    if vehiculo.carroceria == TipoCarroceria.TURISMO:
        return "Estimación para turismo estándar"
    return "Estimación conservadora cuando la carrocería no está confirmada"

def calcular(vehiculo: Vehiculo,
             operacion: Operacion,
             costes: CostesConfig | None = None,
             precio_mercado_es: float | None = None,
             referencia: date | None = None,
             uso_profesional: bool = False) -> ResultadoFiscal:
    """Cálculo completo orientado al cliente final.

    Devuelve un ResultadoFiscal con el coste total puesto en España, el desglose
    en lenguaje claro, y (si se aporta precio_mercado_es) el ahorro vs. España.
    """
    costes = costes or CostesConfig()
    avisos: list[str] = []
    transporte = estimar_coste_transporte(vehiculo, costes)

    vm = valor_mercado(vehiculo, referencia, uso_profesional)
    if vehiculo.valor_tablas_nuevo is None:
        avisos.append(
            "Valor de tablas del BOE no aportado: se ha estimado a partir del "
            "precio de compra. El presupuesto formal usará el valor oficial."
        )

    condicion = condicion_fiscal(vehiculo, referencia)

    base_iedmt, tipo_iedmt, iedmt = calcular_iedmt(vehiculo, operacion, vm)
    base_itp, tipo_itp, itp = calcular_itp(vehiculo, operacion, vm)
    iva = calcular_iva(vehiculo, operacion, condicion)
    ivtm = calcular_ivtm_primer_anio(vehiculo, operacion, referencia)

    # Avisos de riesgo/confianza.
    if vehiculo.co2_gkm is None:
        avisos.append(
            "CO2 no acreditado: se aplica el tipo máximo de IEDMT (14,75%). "
            "Confirma el CoC antes de comprar; podría reducir el impuesto."
        )
    elif vehiculo.co2_confianza < 1.0:
        avisos.append(
            "CO2 inferido, no confirmado. Verifica el CoC: un cambio de tramo "
            "puede variar el IEDMT en cientos de euros."
        )
    _aviso_frontera_co2(vehiculo.co2_gkm, avisos)

    if operacion.traslado_residencia:
        avisos.append(
            "Traslado de residencia: posible exención de IEDMT/IVA/ITP "
            "(modelo 06). Requiere solicitud y cumplir requisitos."
        )

    # Costes extra-UE (aduana).
    otros = costes.coc + costes.traduccion_jurada
    if operacion.origen == Origen.EXTRA_UE:
        arancel = costes.arancel_pct * (vehiculo.precio_compra + transporte)
        iva_import = T.IVA_ESPANA * (vehiculo.precio_compra + transporte + arancel)
        otros += arancel + iva_import + costes.gestion_aduanera
        avisos.append(
            "Origen fuera de la UE: incluye arancel (10%), IVA de importación "
            "(21%) y gestión aduanera."
        )

    coste = (
        vehiculo.precio_compra
        + transporte
        + iedmt + itp + iva + ivtm
        + costes.itv_importacion + costes.tasa_dgt + costes.placas
        + costes.honorarios_gestion
        + otros
    )

    desglose = _construir_desglose(
        vehiculo, operacion, costes, transporte, iedmt, tipo_iedmt, itp, tipo_itp,
        iva, ivtm, otros,
    )

    resultado = ResultadoFiscal(
        base_iedmt=base_iedmt, tipo_iedmt=tipo_iedmt, iedmt=iedmt,
        base_itp=base_itp, tipo_itp=tipo_itp, itp=itp,
        iva=iva, ivtm_primer_anio=ivtm,
        transporte=transporte, itv=costes.itv_importacion,
        tasa_dgt=costes.tasa_dgt, placas=costes.placas,
        honorarios_gestion=costes.honorarios_gestion, otros_costes=otros,
        coste_cliente_final=coste, desglose_cliente=desglose,
        condicion_fiscal=condicion, version_tablas=T.VERSION_TABLAS,
        co2_confianza=vehiculo.co2_confianza, avisos=avisos,
    )

    if precio_mercado_es is not None:
        resultado.precio_mercado_es = precio_mercado_es
        resultado.ahorro_absoluto = precio_mercado_es - coste
        resultado.ahorro_pct = (
            (precio_mercado_es - coste) / precio_mercado_es * 100.0
            if precio_mercado_es > 0 else None
        )

    return resultado


def _aviso_frontera_co2(co2: float | None, avisos: list[str]) -> None:
    """Avisa si el CO2 está cerca de un salto de tramo del IEDMT."""
    if co2 is None:
        return
    for frontera in (120.0, 160.0, 200.0):
        if abs(co2 - frontera) <= 3.0:
            avisos.append(
                f"Emisiones ({co2:.0f} g/km) muy cerca del umbral de {frontera:.0f} "
                "g/km: una pequeña diferencia de versión puede cambiar el tramo "
                "de IEDMT. Confirma el CO2 exacto de la versión."
            )
            break


def _construir_desglose(vehiculo, operacion, costes, transporte, iedmt, tipo_iedmt,
                        itp, tipo_itp, iva, ivtm, otros) -> list[LineaCoste]:
    lineas = [
        LineaCoste("precio", "Precio del coche", vehiculo.precio_compra),
        LineaCoste(
            "transporte",
            "Transporte profesional a España",
            transporte,
            nota=_nota_transporte(vehiculo, costes),
        ),
        LineaCoste(
            "iedmt", "Impuesto de matriculación (IEDMT)", iedmt,
            nota=(f"{vehiculo.co2_gkm:.0f} g/km CO2 -> {tipo_iedmt*100:.2f}%"
                  if vehiculo.co2_gkm is not None
                  else "CO2 sin acreditar -> tipo máximo"),
        ),
    ]
    if itp > 0:
        lineas.append(LineaCoste(
            "itp", "Impuesto de transmisiones (ITP)", itp,
            nota=f"Compra a particular · {operacion.comunidad_autonoma} · {tipo_itp*100:.0f}%",
        ))
    if iva > 0:
        lineas.append(LineaCoste("iva", "IVA (vehículo nuevo)", iva, nota="21%"))
    lineas.append(LineaCoste(
        "admin", "ITV, tasas de la DGT y placas",
        costes.itv_importacion + costes.tasa_dgt + costes.placas,
    ))
    lineas.append(LineaCoste(
        "ivtm", "Impuesto de circulación (1er año, prorrateado)", ivtm,
    ))
    if otros > 0:
        lineas.append(LineaCoste("otros", "Otros costes (CoC, aduana, traducción)", otros))
    lineas.append(LineaCoste(
        "honorarios", "Honorarios de gestión", costes.honorarios_gestion,
        nota="Búsqueda, verificación, negociación, transporte y trámites",
    ))
    return lineas


# --------------------------------------------------------------------------- #
#  Vista DEALER — break-even (compatibilidad con el opportunity finder)
# --------------------------------------------------------------------------- #

def break_even_compraventa(vehiculo: Vehiculo,
                           operacion: Operacion,
                           costes: CostesConfig | None = None,
                           referencia: date | None = None) -> dict:
    """Coste de poner el coche a la venta en España (sin honorarios de gestión
    al cliente), para el buscador de oportunidades.

    Es el 'break-even': lo que le cuesta al dealer tener el coche listo para
    revender. NO incluye honorarios de intermediación (ese es el modo cliente).
    Devuelve un dict con los componentes, para que el opportunity finder calcule
    su margen como (precio_venta_es - break_even).
    """
    costes = costes or CostesConfig()
    # En modo dealer no hay honorarios de gestión al cliente.
    costes_dealer = replace(costes, honorarios_gestion=0.0)
    r = calcular(vehiculo, operacion, costes_dealer, referencia=referencia)
    return {
        "break_even": r.coste_cliente_final,   # sin honorarios => coste de reventa
        "precio_compra": vehiculo.precio_compra,
        "iedmt": r.iedmt,
        "itp": r.itp,
        "iva": r.iva,
        "ivtm": r.ivtm_primer_anio,
        "costes_fijos": r.itv + r.tasa_dgt + r.placas + r.transporte + r.otros_costes,
        "version_tablas": r.version_tablas,
    }
