"""
TC-M06-G03 (RF-93 CA-4, Restricción 2, RNF-93-02, CU-04) - "Ecuación de
conciliación y precisión decimal."

Construido 2026-11-07 contra el código real de RF-93. Primera ronda.

Código bajo prueba:
    src/financial_valuation/domain/services/consolidacion.py (EstadoResultados.resultado_neto)
    src/financial_valuation/domain/services/nic41.py (truncar2, q4)
    alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py (DDL + trigger fn_tgr_m06_24_consistencia_resultado_neto)

HALLAZGO PRINCIPAL: `EstadoResultados.resultado_neto` es una `@property`
que SIEMPRE devuelve `self.total_ingresos - self.total_gastos` -- ambos
derivados de la MISMA fuente (`self.componentes`). No hay dos cálculos
independientes que "concilien"; es una identidad algebraica garantizada por
construcción, no una validación que pueda fallar. "Los dos aportes de RF-45"
que la ficha espera verificar (uno a ingresos, uno a gastos) tampoco existen
como tales: RF-45 (bajas) solo tiene UN aporte real, a gastos
(`bajas_activos`, y solo para ventas -- ver TC-M06-G01/G02); el supuesto
aporte a ingresos no existe.

HALLAZGO SOBRE PRECISIÓN (matiza RNF-93-02): SÍ existe DECIMAL(18,4) --
pero solo en la tabla agregada `modulo6.estados_resultados_periodo`
(columnas `total_ingresos`, `total_gastos`, `resultado_neto`). Cada LÍNEA
individual (`modulo6.lineas_asiento_nic41.valor`) es `NUMERIC(18,2)`, y
`truncar2()` (Python) trunca cada línea a 2 decimales con `ROUND_DOWN`
ANTES de persistirla. Es decir: el "redondeo acumulado entre componentes"
que la ficha quiere probar con "1.000 componentes de 0,0001" es
estructuralmente IMPOSIBLE de producir por la vía real -- ninguna línea
puede tener más de 2 decimales de precisión; un valor de 0,0001 se trunca a
0,00 y ni siquiera se asienta (`if valor > 0`). Los "cuatro decimales en la
presentación" son, en la práctica, siempre terminados en par de ceros
(`X.YZ00`) para cualquier estado construido por el flujo real.

HALLAZGO SOBRE EL MECANISMO DE CONCILIACIÓN (relevante para TC-M06-G04): SÍ
existe un trigger real, `fn_tgr_m06_24_consistencia_resultado_neto()`
(migración `c4d81e6f2a95`), que lanza una EXCEPCIÓN DE POSTGRES
(`RAISE EXCEPTION '[TGR-M06-24] ERROR_CONCILIACION: ...'`) si
`abs(resultado_neto - (total_ingresos - total_gastos)) > 0.01` al
insertar/actualizar la fila. PERO como `ConstructorEstadoResultados.guardar()`
siempre calcula `resultado_neto` como `calculo["resultado_neto"]`
(exactamente `total_ingresos - total_gastos` de la MISMA estructura), el
trigger JAMÁS puede dispararse por la vía de la aplicación -- es una red de
seguridad contra una escritura directa a BD, no un mecanismo de negocio
alcanzable por ningún endpoint ni caso de uso real.

(a)/(b)/(c) Resultado positivo/negativo/cero -- CONFIRMADO: la resta
    algebraica simple produce cualquier signo correctamente.
(d) Los dos aportes de RF-45 -- HALLAZGO: solo existe uno (a gastos, y solo
    para ventas). Ver TC-M06-G01/G02.
(e) 1.000 componentes de 0,0001 sin redondeo acumulado -- HALLAZGO:
    imposible de producir por la vía real (líneas truncadas a 2 decimales);
    la función pura `estado_resultados()` sí suma exacto en Decimal (sin
    redondeo) si se le pasan valores de prueba directamente, pero eso no
    refleja ningún escenario alcanzable por la API real.
(f) Presentación con 4 decimales -- CONFIRMADO en el esquema
    (`NUMERIC(18,4)`), pero siempre con los últimos 2 dígitos en cero por
    el truncamiento de línea.
(g) Mecanismo de conciliación real -- HALLAZGO (ver arriba): existe como
    trigger de BD, inalcanzable por la aplicación, no como validación de
    negocio con alerta al Contador ni registro en RF-94.

Cómo se prueba: pytest de unidad sobre `EstadoResultados`/`truncar2`/`q4` +
inspección de la migración real para el DDL y el trigger (no requiere BD
viva: son hechos de esquema, no de datos).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m06_g03_ecuacion_conciliacion_precision_decimal.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G03.html --self-contained-html
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.financial_valuation.domain.services.consolidacion import MovimientoResultado, estado_resultados
from src.financial_valuation.domain.services.nic41 import truncar2
from src.financial_valuation.domain.value_objects.nic41 import Sentido, TipoHecho

REPO_ROOT = Path(__file__).resolve().parents[5]
MIGRACION = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'


class TestSubCasoABCResultadoPositivoNegativoCero:
    @pytest.mark.parametrize('valor_ingreso,valor_gasto,esperado', [
        (Decimal('100.00'), Decimal('40.00'), Decimal('60.00')),
        (Decimal('40.00'), Decimal('100.00'), Decimal('-60.00')),
        (Decimal('50.00'), Decimal('50.00'), Decimal('0.00')),
    ])
    def test_resultado_neto_con_cualquier_signo(self, valor_ingreso, valor_gasto, esperado):
        er = estado_resultados(
            [MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.GANANCIA.value, valor_ingreso)],
            [],
        ) if valor_gasto == 0 else estado_resultados(
            [MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.GANANCIA.value, valor_ingreso),
             MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.PERDIDA.value, valor_gasto)],
            [],
        )
        assert er.resultado_neto == esperado


class TestSubCasoDLosDosAportesDeRf45NoExistenComoTales:
    def test_rf45_solo_tiene_un_aporte_real_a_gastos(self):
        pytest.fail(
            "HALLAZGO: RF-45 (bajas) solo tiene UN aporte real al estado de resultados, a "
            "GASTOS (bajas_activos, via ventas/sacrificio) -- no existe el segundo aporte a "
            "INGRESOS que la ficha da por hecho (ver TC-M06-G01)."
        )


class TestSubCasoELineasTruncadasAUnSoloCentavoImposibilitanElEscenario:
    def test_truncar2_redondea_hacia_abajo_a_dos_decimales(self):
        assert truncar2(Decimal('0.0199')) == Decimal('0.01')

    def test_un_valor_de_0_0001_se_trunca_a_cero_y_no_se_asentaria(self):
        """HALLAZGO (e): el escenario de la ficha (1.000 componentes de 0,0001) es
        irreproducible via el flujo real: toda linea pasa por truncar2() antes de
        persistirse, y 0,0001 -> 0,00, que _baja()/los demas flujos descartan con
        'if valor > 0'."""
        valor_truncado = truncar2(Decimal('0.0001'))
        pytest.fail(
            f"HALLAZGO: 0.0001 se trunca a {valor_truncado} (no a 0.0001) -- ninguna linea real "
            f"puede tener esa magnitud; el escenario de 1.000 componentes de 0,0001 que pide la "
            f"ficha no es alcanzable por el flujo de registro real."
        ) if valor_truncado == Decimal('0.00') else None

    def test_la_funcion_pura_si_suma_exacto_sin_redondeo_si_se_la_alimenta_directo(self):
        """Esto confirma que el NUCLEO matematico (estado_resultados) no introduce error
        de redondeo -- pero el punto (e) de arriba es que la fuente real nunca le pasaria
        valores mas finos que 2 decimales en primer lugar."""
        mil_componentes = [MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.GANANCIA.value, Decimal('0.0001'))
                           for _ in range(1000)]
        er = estado_resultados(mil_componentes, [])
        assert er.componentes['ganancia_transformacion_biologica'] == Decimal('0.1000')


class TestSubCasoFPresentacionDecimal184EnLaTablaAgregada:
    def test_la_tabla_agregada_si_usa_numeric_18_4(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        assert "ADD COLUMN total_ingresos numeric(18,4)" in texto
        assert "ADD COLUMN total_gastos numeric(18,4)" in texto

    def test_pero_cada_linea_individual_es_numeric_18_2_no_18_4(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO: modulo6.lineas_asiento_nic41.valor es NUMERIC(18,2), no (18,4) -- la "
            "precision de 4 decimales solo existe en el agregado final, nunca en el dato fuente; "
            "en la practica el agregado siempre termina en dos ceros."
        ) if "valor numeric(18,2) NOT NULL" in texto else None


class TestSubCasoGElMecanismoDeConciliacionEsUnTriggerDeBdInalcanzable:
    def test_si_existe_un_trigger_real_de_conciliacion_en_la_migracion(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        assert "fn_tgr_m06_24_consistencia_resultado_neto" in texto
        assert "ERROR_CONCILIACION" in texto

    def test_el_trigger_es_inalcanzable_porque_la_app_siempre_calcula_consistente(self):
        """Ver generar_estado_resultados_use_case.py / reportes.py: resultado_neto SIEMPRE
        se guarda como calculo['resultado_neto'], que ya ES total_ingresos - total_gastos
        de la MISMA estructura -- nunca hay una via de la aplicacion que pueda insertar
        valores inconsistentes para disparar el trigger."""
        archivo = REPO_ROOT / 'src/financial_valuation/application/services/reportes.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (g): ConstructorEstadoResultados.guardar() pasa 'neto': "
            "calculo['resultado_neto'] (ya derivado de los mismos componentes) a agregar_estado() "
            "-- el trigger de BD que detecta ERROR_CONCILIACION nunca se dispara por esta via; "
            "solo protegeria contra un INSERT/UPDATE directo a la tabla, fuera del flujo de la API."
        ) if 'calculo["resultado_neto"]' in texto else None
