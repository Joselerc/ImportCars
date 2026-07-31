"""
Script de prueba para validar la calculadora de importación

Prueba unitaria con los 3 casos:
- P = 5000€
- CO2 = 165 g/km → tasa IEDMT = 9.75%
- Transporte = 1100€
- Venta en España = 8500€

Resultados esperados:
- Caso 1 (Particular): breakEven=7401.5, beneficioNeto=867.8
- Caso 2 (EmpresaIVA): breakEven=7201.5, beneficioNeto=1025.8
- Caso 3 (EmpresaMargen): breakEven=7201.5, beneficioNeto=1025.8
"""

from src.import_cars.utils.import_calculator import ImportCalculator, TipoCompra


def test_caso_particular():
    """Caso 1: Compra a particular"""
    print("=" * 60)
    print("CASO 1: COMPRA A PARTICULAR")
    print("=" * 60)
    
    calc = ImportCalculator(
        transporte=1100,
        itv_tasa=160,
        traducciones=200,
        ivtm=224,
        placas=30
    )
    
    resultado = calc.analisis_completo(
        precio_alemania=5000,
        tipo_compra=TipoCompra.PARTICULAR,
        co2=165,
        precio_venta_espana=8500
    )
    
    print(f"\n📊 COSTES DE IMPORTACIÓN:")
    print(f"  Precio en Alemania: {resultado['precio_alemania']}€")
    print(f"  ITP (4%): {resultado['itp']}€")
    print(f"  IEDMT ({resultado['tasa_iedmt']}%): {resultado['iedmt']}€")
    print(f"  Costes base: {resultado['costes_base_total']}€")
    print(f"    - Transporte: {resultado['transporte']}€")
    print(f"    - ITV: {resultado['itv_tasa']}€")
    print(f"    - Traducciones: {resultado['traducciones']}€")
    print(f"    - IVTM: {resultado['ivtm']}€")
    print(f"    - Placas: {resultado['placas']}€")
    print(f"\n💰 COSTE TOTAL: {resultado['coste_total']}€")
    print(f"🎯 BREAK EVEN: {resultado['break_even']}€")
    
    print(f"\n📈 ANÁLISIS DE VENTA:")
    print(f"  Precio venta España: {resultado['precio_venta_espana']}€")
    print(f"  Margen bruto: {resultado['margen_bruto']}€")
    print(f"  IVA venta (21% sobre margen): {resultado['iva_venta']}€")
    print(f"  ✅ BENEFICIO NETO: {resultado['beneficio_neto']}€")
    print(f"  📊 Rentabilidad: {resultado['rentabilidad_porcentaje']}%")
    
    # Validación
    assert abs(resultado['coste_total'] - 7401.5) < 0.1, f"Error: esperado 7401.5, obtenido {resultado['coste_total']}"
    assert abs(resultado['beneficio_neto'] - 867.8) < 0.5, f"Error: esperado 867.8, obtenido {resultado['beneficio_neto']}"
    print("\n✅ VALIDACIÓN: OK")
    
def test_caso_empresa_iva():
    """Caso 2: Compra a empresa con IVA"""
    print("\n" + "=" * 60)
    print("CASO 2: COMPRA A EMPRESA (IVA ALEMÁN)")
    print("=" * 60)
    
    calc = ImportCalculator(
        transporte=1100,
        itv_tasa=160,
        traducciones=200,
        ivtm=224,
        placas=30
    )
    
    resultado = calc.analisis_completo(
        precio_alemania=5000,
        tipo_compra=TipoCompra.EMPRESA_IVA,
        co2=165,
        precio_venta_espana=8500
    )
    
    print(f"\n📊 COSTES DE IMPORTACIÓN:")
    print(f"  Precio en Alemania: {resultado['precio_alemania']}€")
    print(f"  ITP: {resultado['itp']}€ (no aplica)")
    print(f"  IEDMT ({resultado['tasa_iedmt']}%): {resultado['iedmt']}€")
    print(f"  Costes base: {resultado['costes_base_total']}€")
    print(f"\n💰 COSTE TOTAL: {resultado['coste_total']}€")
    print(f"🎯 BREAK EVEN: {resultado['break_even']}€")
    
    print(f"\n📈 ANÁLISIS DE VENTA:")
    print(f"  Precio venta España: {resultado['precio_venta_espana']}€")
    print(f"  Margen bruto: {resultado['margen_bruto']}€")
    print(f"  IVA venta (21% sobre margen): {resultado['iva_venta']}€")
    print(f"  ✅ BENEFICIO NETO: {resultado['beneficio_neto']}€")
    print(f"  📊 Rentabilidad: {resultado['rentabilidad_porcentaje']}%")
    
    # Validación
    assert abs(resultado['coste_total'] - 7201.5) < 0.1, f"Error: esperado 7201.5, obtenido {resultado['coste_total']}"
    assert abs(resultado['beneficio_neto'] - 1025.8) < 0.5, f"Error: esperado 1025.8, obtenido {resultado['beneficio_neto']}"
    print("\n✅ VALIDACIÓN: OK")
    
def test_caso_empresa_margen():
    """Caso 3: Compra a empresa con régimen de margen"""
    print("\n" + "=" * 60)
    print("CASO 3: COMPRA A EMPRESA (RÉGIMEN DE MARGEN §25a)")
    print("=" * 60)
    
    calc = ImportCalculator(
        transporte=1100,
        itv_tasa=160,
        traducciones=200,
        ivtm=224,
        placas=30
    )
    
    resultado = calc.analisis_completo(
        precio_alemania=5000,
        tipo_compra=TipoCompra.EMPRESA_MARGEN,
        co2=165,
        precio_venta_espana=8500
    )
    
    print(f"\n📊 COSTES DE IMPORTACIÓN:")
    print(f"  Precio en Alemania: {resultado['precio_alemania']}€")
    print(f"  ITP: {resultado['itp']}€ (no aplica)")
    print(f"  IEDMT ({resultado['tasa_iedmt']}%): {resultado['iedmt']}€")
    print(f"  Costes base: {resultado['costes_base_total']}€")
    print(f"\n💰 COSTE TOTAL: {resultado['coste_total']}€")
    print(f"🎯 BREAK EVEN: {resultado['break_even']}€")
    
    print(f"\n📈 ANÁLISIS DE VENTA:")
    print(f"  Precio venta España: {resultado['precio_venta_espana']}€")
    print(f"  Margen bruto: {resultado['margen_bruto']}€")
    print(f"  IVA venta (21% sobre margen): {resultado['iva_venta']}€")
    print(f"  ✅ BENEFICIO NETO: {resultado['beneficio_neto']}€")
    print(f"  📊 Rentabilidad: {resultado['rentabilidad_porcentaje']}%")
    
    # Validación
    assert abs(resultado['coste_total'] - 7201.5) < 0.1, f"Error: esperado 7201.5, obtenido {resultado['coste_total']}"
    assert abs(resultado['beneficio_neto'] - 1025.8) < 0.5, f"Error: esperado 1025.8, obtenido {resultado['beneficio_neto']}"
    print("\n✅ VALIDACIÓN: OK")
    
def comparar_casos():
    """Compara los 3 casos lado a lado"""
    print("\n" + "=" * 60)
    print("COMPARACIÓN DE LOS 3 CASOS")
    print("=" * 60)
    
    calc = ImportCalculator(
        transporte=1100,
        itv_tasa=160,
        traducciones=200,
        ivtm=224,
        placas=30
    )
    
    resultados = calc.comparar_casos(
        precio_alemania=5000,
        co2=165,
        precio_venta_espana=8500
    )
    
    print(f"\n{'Concepto':<30} {'Particular':<15} {'EmpresaIVA':<15} {'EmpresaMargen':<15}")
    print("-" * 75)
    print(f"{'Precio Alemania':<30} {resultados[TipoCompra.PARTICULAR]['precio_alemania']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['precio_alemania']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['precio_alemania']:<15.2f}")
    print(f"{'ITP':<30} {resultados[TipoCompra.PARTICULAR]['itp']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['itp']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['itp']:<15.2f}")
    print(f"{'IEDMT':<30} {resultados[TipoCompra.PARTICULAR]['iedmt']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['iedmt']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['iedmt']:<15.2f}")
    print(f"{'Costes base':<30} {resultados[TipoCompra.PARTICULAR]['costes_base_total']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['costes_base_total']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['costes_base_total']:<15.2f}")
    print("-" * 75)
    print(f"{'COSTE TOTAL':<30} {resultados[TipoCompra.PARTICULAR]['coste_total']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['coste_total']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['coste_total']:<15.2f}")
    print(f"{'BREAK EVEN':<30} {resultados[TipoCompra.PARTICULAR]['break_even']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['break_even']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['break_even']:<15.2f}")
    print("-" * 75)
    print(f"{'Margen bruto':<30} {resultados[TipoCompra.PARTICULAR]['margen_bruto']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['margen_bruto']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['margen_bruto']:<15.2f}")
    print(f"{'IVA venta':<30} {resultados[TipoCompra.PARTICULAR]['iva_venta']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['iva_venta']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['iva_venta']:<15.2f}")
    print(f"{'BENEFICIO NETO':<30} {resultados[TipoCompra.PARTICULAR]['beneficio_neto']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['beneficio_neto']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['beneficio_neto']:<15.2f}")
    print(f"{'Rentabilidad %':<30} {resultados[TipoCompra.PARTICULAR]['rentabilidad_porcentaje']:<15.2f} {resultados[TipoCompra.EMPRESA_IVA]['rentabilidad_porcentaje']:<15.2f} {resultados[TipoCompra.EMPRESA_MARGEN]['rentabilidad_porcentaje']:<15.2f}")
    
    print("\n🏆 MEJOR OPCIÓN:", max(resultados.items(), key=lambda x: x[1]['beneficio_neto'])[0].value)


if __name__ == "__main__":
    print("\n🚗 CALCULADORA DE IMPORTACIÓN DE VEHÍCULOS DE→ES")
    print("🧪 PRUEBAS UNITARIAS\n")
    
    # Ejecutar pruebas
    test_caso_particular()
    test_caso_empresa_iva()
    test_caso_empresa_margen()
    comparar_casos()
    
    print("\n" + "=" * 60)
    print("✅ TODAS LAS PRUEBAS PASARON CORRECTAMENTE")
    print("=" * 60)

