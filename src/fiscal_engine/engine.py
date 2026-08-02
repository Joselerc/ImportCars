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
  - IVA español para vehículos fiscalmente nuevos, sobre su base neta.
  - Adquisición intracomunitaria ROI con efecto neto de IVA cero.
  - IVTM por potencia fiscal x coeficiente municipal, prorrateado.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, replace
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
    TipoComprador,
    TipoVendedor,
    ValorIntermedio,
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


@dataclass(frozen=True)
class _DetalleValorMercado:
    antiguedad_anios: float
    coeficiente_depreciacion: float
    valor_nuevo_aplicado: float
    valor_depreciado: float
    valor_boe_disponible: bool
    reduccion_uso_profesional: float


def _calcular_valor_mercado_detalle(
    vehiculo: Vehiculo,
    referencia: date | None = None,
    uso_profesional: bool = False,
) -> _DetalleValorMercado:
    """Resuelve una vez el valor de mercado y conserva sus términos."""

    anios = antiguedad_anios(vehiculo.fecha_primera_matriculacion, referencia)
    coef = coeficiente_depreciacion(anios)
    base_nuevo = vehiculo.valor_tablas_nuevo
    valor_boe_disponible = base_nuevo is not None
    if base_nuevo is None:
        base_nuevo = vehiculo.precio_compra / coef if coef > 0 else vehiculo.precio_compra
    reduccion = T.REDUCCION_USO_PROFESIONAL if uso_profesional else 1.0
    vm = base_nuevo * coef * reduccion
    return _DetalleValorMercado(
        antiguedad_anios=anios,
        coeficiente_depreciacion=coef,
        valor_nuevo_aplicado=base_nuevo,
        valor_depreciado=vm,
        valor_boe_disponible=valor_boe_disponible,
        reduccion_uso_profesional=reduccion,
    )


def valor_mercado(vehiculo: Vehiculo, referencia: date | None = None,
                  uso_profesional: bool = False) -> float:
    """Valor de mercado = valor_tablas_nuevo x coef_depreciacion.

    `valor_tablas_nuevo` debe venir resuelto desde la base del BOE
    (data/import_cars.sqlite3). Si no se aporta, se usa el precio de compra
    como aproximación conservadora (y se deja un aviso en el resultado).
    """
    return _calcular_valor_mercado_detalle(
        vehiculo, referencia, uso_profesional
    ).valor_depreciado


# --------------------------------------------------------------------------- #
#  Condición fiscal nuevo / usado
# --------------------------------------------------------------------------- #

def es_nuevo_fiscal(
    fecha_primera_matriculacion: date | None,
    kilometros: int | None,
    *,
    nuevo_sin_matricular: bool = False,
    referencia: date | None = None,
) -> bool:
    """Devuelve si el vehículo es nuevo a efectos de IVA español.

    Basta con que tenga menos de seis meses o menos de 6.000 km. Los coches
    anunciados expresamente como nuevos y todavía sin matricular también lo son.
    """
    if nuevo_sin_matricular:
        return True
    if fecha_primera_matriculacion is None:
        return False
    ref = referencia or date.today()
    registration = fecha_primera_matriculacion
    month_index = registration.month - 1 + 6
    cutoff_year = registration.year + month_index // 12
    cutoff_month = month_index % 12 + 1
    cutoff_day = min(registration.day, monthrange(cutoff_year, cutoff_month)[1])
    six_month_cutoff = date(cutoff_year, cutoff_month, cutoff_day)
    if ref < six_month_cutoff:
        return True
    return kilometros is not None and kilometros < 6000


def condicion_fiscal(vehiculo: Vehiculo, referencia: date | None = None) -> CondicionFiscal:
    """Nuevo si < 6 meses desde 1ª matriculación O < 6.000 km."""
    if es_nuevo_fiscal(
        vehiculo.fecha_primera_matriculacion,
        vehiculo.kilometros,
        nuevo_sin_matricular=vehiculo.nuevo_sin_matricular,
        referencia=referencia,
    ):
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

def calcular_itp(
    vehiculo: Vehiculo,
    operacion: Operacion,
    vm: float,
    condicion: CondicionFiscal | None = None,
) -> tuple[float, float, float]:
    """ITP solo si se compra a particular. Base = max(precio, VM).

    Devuelve (base, tipo, cuota). Si no aplica, todo a 0.
    """
    if operacion.tipo_vendedor != TipoVendedor.PARTICULAR:
        return 0.0, 0.0, 0.0
    if condicion == CondicionFiscal.NUEVO:
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

@dataclass(frozen=True)
class _DetalleIva:
    cuota: float
    caso: str
    motivo: str
    base: float
    origen_base: str
    precio_adquisicion: float


def _base_neta_profesional(vehiculo: Vehiculo) -> tuple[float, str]:
    if vehiculo.precio_neto is not None and vehiculo.precio_neto > 0:
        return vehiculo.precio_neto, "neto_anuncio"
    return vehiculo.precio_compra / (1.0 + T.IVA_ALEMANIA), "bruto_dividido_1_19"


def _calcular_iva_detalle(
    vehiculo: Vehiculo,
    operacion: Operacion,
    condicion: CondicionFiscal,
) -> _DetalleIva:
    if operacion.traslado_residencia:
        return _DetalleIva(
            0.0,
            "traslado_residencia",
            "Operación exenta por traslado de residencia, sujeta a requisitos.",
            0.0,
            "sin_iva",
            vehiculo.precio_compra,
        )

    if (
        operacion.tipo_comprador == TipoComprador.EMPRESA_ROI
        and operacion.tipo_vendedor == TipoVendedor.PROFESIONAL_IVA
    ):
        base, source = _base_neta_profesional(vehiculo)
        return _DetalleIva(
            0.0,
            "empresa_roi",
            "Adquisición intracomunitaria: autoliquida y deduce el IVA; efecto neto cero.",
            base,
            source,
            base,
        )

    if condicion == CondicionFiscal.USADO:
        cases = {
            TipoVendedor.PARTICULAR: (
                "usado_particular",
                "Vehículo usado comprado a particular: no lleva IVA español; puede aplicar ITP.",
            ),
            TipoVendedor.PROFESIONAL_IVA: (
                "usado_profesional_iva",
                "Vehículo usado con factura profesional: no lleva IVA español ni ITP.",
            ),
            TipoVendedor.PROFESIONAL_MARGEN: (
                "usado_profesional_margen",
                "Vehículo usado en régimen de margen: IVA no desglosado y sin IVA español adicional.",
            ),
        }
        case, reason = cases[operacion.tipo_vendedor]
        return _DetalleIva(
            0.0,
            case,
            reason,
            0.0,
            "sin_iva_espanol_usado",
            vehiculo.precio_compra,
        )

    if operacion.tipo_vendedor == TipoVendedor.PROFESIONAL_IVA:
        base, source = _base_neta_profesional(vehiculo)
    else:
        base, source = vehiculo.precio_compra, "precio_sin_iva_desglosable"
    return _DetalleIva(
        T.IVA_ESPANA * base,
        "nuevo_iva_espanol",
        "Vehículo fiscalmente nuevo: IVA español del 21% sobre el precio neto aplicable.",
        base,
        source,
        vehiculo.precio_compra,
    )


def calcular_iva(vehiculo: Vehiculo, operacion: Operacion,
                 condicion: CondicionFiscal) -> float:
    """IVA español que hay que ingresar en España.

    - Empresa ROI + profesional con IVA: autoliquida y deduce; coste neto cero.
    - Vehículo NUEVO: 21% sobre el neto anunciado, el bruto / 1,19 si procede,
      o el precio intacto cuando no existe IVA alemán desglosable.
    - Vehículo USADO: nunca añade IVA español.
    """
    return _calcular_iva_detalle(vehiculo, operacion, condicion).cuota


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
    return _calcular_ivtm_detalle(vehiculo, operacion, referencia).cuota


@dataclass(frozen=True)
class _DetalleIvtm:
    cvf: float
    cvf_estimado: bool
    tarifa_base: float
    coeficiente_municipal: float
    cuota_anual: float
    trimestre_alta: int
    trimestres_restantes: int
    cuota: float


def _calcular_ivtm_detalle(
    vehiculo: Vehiculo,
    operacion: Operacion,
    referencia: date | None = None,
) -> _DetalleIvtm:
    """Calcula una sola vez la cuota y todos sus términos auditables."""

    ref = referencia or date.today()
    cvf = potencia_fiscal_cvf(vehiculo)
    base = tarifa_ivtm(cvf)
    municipio = operacion.municipio
    coef = T.IVTM_COEF_POR_MUNICIPIO.get(municipio, T.IVTM_COEF_MUNICIPAL_DEFECTO)
    cuota_anual = base * coef
    # Prorrateo por trimestres restantes (1..4).
    trimestre_alta = (ref.month - 1) // 3 + 1
    trimestres_restantes = 4 - trimestre_alta + 1
    cuota = cuota_anual * trimestres_restantes / 4.0
    return _DetalleIvtm(
        cvf=cvf,
        cvf_estimado=vehiculo.cvf is None,
        tarifa_base=base,
        coeficiente_municipal=coef,
        cuota_anual=cuota_anual,
        trimestre_alta=trimestre_alta,
        trimestres_restantes=trimestres_restantes,
        cuota=cuota,
    )


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


@dataclass(frozen=True)
class _ContextoAuditoria:
    valor_mercado: _DetalleValorMercado
    iva_historico: float
    iedmt_historico: float
    tipo_iedmt_estatal: float
    recargo_iedmt_autonomico: float
    ivtm: _DetalleIvtm
    condicion_fiscal: CondicionFiscal


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

    detalle_vm = _calcular_valor_mercado_detalle(
        vehiculo, referencia, uso_profesional
    )
    vm = detalle_vm.valor_depreciado
    if vehiculo.valor_tablas_nuevo is None:
        avisos.append(
            "Valor de tablas del BOE no aportado: se ha estimado a partir del "
            "precio de compra. El presupuesto formal usará el valor oficial."
        )

    condicion = condicion_fiscal(vehiculo, referencia)

    base_iedmt, tipo_iedmt, iedmt = calcular_iedmt(vehiculo, operacion, vm)
    base_itp, tipo_itp, itp = calcular_itp(vehiculo, operacion, vm, condicion)
    detalle_iva = _calcular_iva_detalle(vehiculo, operacion, condicion)
    iva = detalle_iva.cuota
    detalle_ivtm = _calcular_ivtm_detalle(vehiculo, operacion, referencia)
    ivtm = detalle_ivtm.cuota
    ccaa = T.normaliza_ccaa(operacion.comunidad_autonoma)
    auditoria = _ContextoAuditoria(
        valor_mercado=detalle_vm,
        iva_historico=_iva_historico(vehiculo.fecha_primera_matriculacion),
        iedmt_historico=tipo_iedmt_estatal(vehiculo.co2_gkm),
        tipo_iedmt_estatal=tipo_iedmt_estatal(vehiculo.co2_gkm),
        recargo_iedmt_autonomico=T.RECARGO_IEDMT_CCAA.get(ccaa, 0.0),
        ivtm=detalle_ivtm,
        condicion_fiscal=condicion,
    )

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
        detalle_iva.precio_adquisicion
        + transporte
        + iedmt + itp + iva + ivtm
        + costes.itv_importacion + costes.tasa_dgt + costes.placas
        + costes.honorarios_gestion
        + otros
    )

    desglose = _construir_desglose(
        vehiculo, operacion, costes, transporte, base_iedmt, iedmt, tipo_iedmt,
        base_itp, itp, tipo_itp, detalle_iva, ivtm, otros, auditoria,
    )

    resultado = ResultadoFiscal(
        base_iedmt=base_iedmt, tipo_iedmt=tipo_iedmt, iedmt=iedmt,
        base_itp=base_itp, tipo_itp=tipo_itp, itp=itp,
        iva=iva,
        caso_iva=detalle_iva.caso,
        motivo_iva=detalle_iva.motivo,
        base_iva=detalle_iva.base,
        origen_base_iva=detalle_iva.origen_base,
        precio_adquisicion=detalle_iva.precio_adquisicion,
        ivtm_primer_anio=ivtm,
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


def _construir_desglose(
    vehiculo,
    operacion,
    costes,
    transporte,
    base_iedmt,
    iedmt,
    tipo_iedmt,
    base_itp,
    itp,
    tipo_itp,
    detalle_iva: _DetalleIva,
    ivtm,
    otros,
    auditoria: _ContextoAuditoria,
) -> list[LineaCoste]:
    vm = auditoria.valor_mercado
    iva = detalle_iva.cuota
    lineas = [
        LineaCoste(
            "precio",
            "Precio del coche",
            detalle_iva.precio_adquisicion,
            nota=(
                "Precio neto para comprador empresa ROI"
                if detalle_iva.precio_adquisicion != vehiculo.precio_compra
                else ""
            ),
            formula="Precio aplicable a la adquisición según el régimen del comprador",
            intermedios=[
                ValorIntermedio(
                    "precio_compra",
                    "Precio de compra",
                    detalle_iva.precio_adquisicion,
                    "EUR",
                )
            ],
        ),
        LineaCoste(
            "transporte",
            "Transporte profesional a España",
            transporte,
            nota=_nota_transporte(vehiculo, costes),
            formula="Tramo operativo según la carrocería declarada",
            intermedios=[
                ValorIntermedio(
                    "carroceria",
                    "Carrocería utilizada",
                    vehiculo.carroceria.value if vehiculo.carroceria else "no confirmada",
                ),
                ValorIntermedio("transporte", "Coste aplicado", transporte, "EUR"),
            ],
        ),
        LineaCoste(
            "iedmt", "Impuesto de matriculación (IEDMT)", iedmt,
            nota=(f"{vehiculo.co2_gkm:.0f} g/km CO2 -> {tipo_iedmt*100:.2f}%"
                  if vehiculo.co2_gkm is not None
                  else "CO2 sin acreditar -> tipo máximo"),
            formula=(
                "[valor BOE × coeficiente de depreciación] ÷ "
                "[1 + IVA histórico + IEDMT histórico] × tipo IEDMT aplicable"
            ),
            intermedios=[
                ValorIntermedio(
                    "boe_fila_id", "ID de la fila del BOE", vehiculo.boe_fila_id
                ),
                ValorIntermedio(
                    "boe_orden", "Orden del BOE", vehiculo.boe_orden or T.VERSION_TABLAS
                ),
                ValorIntermedio(
                    "boe_ejercicio", "Ejercicio de la tabla", vehiculo.boe_ejercicio
                ),
                ValorIntermedio(
                    "boe_modelo", "Modelo resuelto en el BOE", vehiculo.boe_modelo_resuelto
                ),
                ValorIntermedio(
                    "valor_tablas_nuevo",
                    "Valor oficial como nuevo",
                    vm.valor_nuevo_aplicado,
                    "EUR",
                    "Valor oficial" if vm.valor_boe_disponible else "Fallback desde el precio de compra",
                ),
                ValorIntermedio(
                    "antiguedad",
                    "Antigüedad en la fecha del cálculo",
                    vm.antiguedad_anios,
                    "años",
                ),
                ValorIntermedio(
                    "coeficiente_depreciacion",
                    "Coeficiente de depreciación",
                    vm.coeficiente_depreciacion * 100,
                    "%",
                ),
                ValorIntermedio(
                    "valor_tablas_depreciado",
                    "Valor de tablas depreciado",
                    vm.valor_depreciado,
                    "EUR",
                ),
                ValorIntermedio(
                    "iva_historico",
                    "IVA histórico del denominador",
                    auditoria.iva_historico * 100,
                    "%",
                ),
                ValorIntermedio(
                    "iedmt_historico",
                    "IEDMT histórico del denominador",
                    auditoria.iedmt_historico * 100,
                    "%",
                ),
                ValorIntermedio(
                    "denominador_minoracion",
                    "Denominador de minoración",
                    1 + auditoria.iva_historico + auditoria.iedmt_historico,
                ),
                ValorIntermedio(
                    "base_iedmt", "Base tras minoración", base_iedmt, "EUR"
                ),
                ValorIntermedio(
                    "tipo_iedmt_estatal",
                    "Tipo estatal por CO₂",
                    auditoria.tipo_iedmt_estatal * 100,
                    "%",
                ),
                ValorIntermedio(
                    "recargo_autonomico",
                    "Recargo autonómico sobre el tipo",
                    auditoria.recargo_iedmt_autonomico * 100,
                    "%",
                    operacion.comunidad_autonoma,
                ),
                ValorIntermedio(
                    "tipo_iedmt_aplicado", "Tipo efectivo aplicado", tipo_iedmt * 100, "%"
                ),
                ValorIntermedio("cuota_iedmt", "Cuota resultante", iedmt, "EUR"),
            ],
        ),
    ]
    if itp > 0:
        lineas.append(LineaCoste(
            "itp", "Impuesto de transmisiones (ITP)", itp,
            nota=f"Compra a particular · {operacion.comunidad_autonoma} · {tipo_itp*100:.0f}%",
            formula="máx.[precio de compra, valor de tablas depreciado] × tipo de la comunidad autónoma",
            intermedios=[
                ValorIntermedio("precio_compra", "Precio de compra", vehiculo.precio_compra, "EUR"),
                ValorIntermedio(
                    "valor_tablas_depreciado",
                    "Valor de tablas depreciado",
                    vm.valor_depreciado,
                    "EUR",
                ),
                ValorIntermedio(
                    "base_itp",
                    "Base seleccionada",
                    base_itp,
                    "EUR",
                    "El mayor de los dos valores",
                ),
                ValorIntermedio("tipo_itp", "Tipo de ITP", tipo_itp * 100, "%", operacion.comunidad_autonoma),
                ValorIntermedio("cuota_itp", "Cuota resultante", itp, "EUR"),
            ],
        ))
    if iva > 0:
        lineas.append(LineaCoste(
            "iva",
            "IVA (vehículo nuevo)",
            iva,
            nota="21%",
            formula="base neta aplicable × tipo de IVA español",
            intermedios=[
                ValorIntermedio(
                    "condicion_fiscal",
                    "Condición fiscal",
                    auditoria.condicion_fiscal.value,
                ),
                ValorIntermedio("base_iva", "Base del IVA", detalle_iva.base, "EUR"),
                ValorIntermedio(
                    "origen_base_iva",
                    "Origen de la base",
                    detalle_iva.origen_base,
                ),
                ValorIntermedio("tipo_iva", "Tipo de IVA", T.IVA_ESPANA * 100, "%"),
                ValorIntermedio("cuota_iva", "Cuota resultante", iva, "EUR"),
            ],
        ))
    lineas.append(LineaCoste(
        "admin", "ITV, tasas de la DGT y placas",
        costes.itv_importacion + costes.tasa_dgt + costes.placas,
        formula="ITV de importación + tasa de la DGT + placas",
        intermedios=[
            ValorIntermedio("itv", "ITV de importación", costes.itv_importacion, "EUR"),
            ValorIntermedio("tasa_dgt", "Tasa de la DGT", costes.tasa_dgt, "EUR"),
            ValorIntermedio("placas", "Placas", costes.placas, "EUR"),
        ],
    ))
    lineas.append(LineaCoste(
        "ivtm", "Impuesto de circulación (1er año, prorrateado)", ivtm,
        formula="tarifa base por CVF × coeficiente municipal × trimestres restantes ÷ 4",
        intermedios=[
            ValorIntermedio(
                "cvf",
                "Potencia fiscal utilizada",
                auditoria.ivtm.cvf,
                "CVF",
                "Estimada desde la cilindrada" if auditoria.ivtm.cvf_estimado else "Aportada por la ficha o la fila del BOE",
            ),
            ValorIntermedio("tarifa_base", "Tarifa base del tramo", auditoria.ivtm.tarifa_base, "EUR/año"),
            ValorIntermedio(
                "coeficiente_municipal",
                "Coeficiente municipal",
                auditoria.ivtm.coeficiente_municipal,
                "×",
                operacion.municipio,
            ),
            ValorIntermedio("cuota_anual", "Cuota anual", auditoria.ivtm.cuota_anual, "EUR"),
            ValorIntermedio("trimestre_alta", "Trimestre de alta", auditoria.ivtm.trimestre_alta),
            ValorIntermedio(
                "trimestres_restantes",
                "Trimestres incluidos",
                auditoria.ivtm.trimestres_restantes,
                "de 4",
            ),
            ValorIntermedio("cuota_ivtm", "Cuota prorrateada", ivtm, "EUR"),
        ],
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
        "precio_compra": r.precio_adquisicion,
        "iedmt": r.iedmt,
        "itp": r.itp,
        "iva": r.iva,
        "ivtm": r.ivtm_primer_anio,
        "costes_fijos": r.itv + r.tasa_dgt + r.placas + r.transporte + r.otros_costes,
        "version_tablas": r.version_tablas,
    }
