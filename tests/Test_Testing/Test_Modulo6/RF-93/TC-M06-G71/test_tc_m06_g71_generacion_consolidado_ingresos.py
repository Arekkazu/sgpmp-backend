"""
TC-M06-G71 (RF-93 CA-1, Proceso 3a, CU-01/CU-02) - "Generación del estado
consolidado e integración de los componentes de INGRESOS."

Construido 2026-11-07 contra el código real de RF-93 (implementado
2026-11-04/05 por Arekkazu, `src/financial_valuation/`), que a la fecha de la
ficha NUNCA se había probado -- es la primera ronda, no una reverificación.

Código bajo prueba:
    src/financial_valuation/domain/services/consolidacion.py (estado_resultados, INGRESOS)
    src/financial_valuation/application/services/reportes.py (ConstructorEstadoResultados)
    src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py

ACTUALIZACIÓN 2026-11-16: CERRADO (INC-M06-364-G71, RF-45/RF-93, commit
2026-11-15, "la venta de un activo entra como ingreso en el estado de
resultados"). `consolidacion.py::INGRESOS` ahora tiene un sexto componente
real, `ingresos_venta_activos`: con valor en libros X y venta por Y, el
estado muestra Y en ingresos y X en gastos (`bajas_activos`), con neto Y−X.
CONFIRMADO EN VIVO contra TEST pendiente de un período con una venta nueva
posterior al despliegue del fix (los estados ya generados antes del fix
no se recalculan solos). Ver `tests/financial_valuation/
test_inc_m06_364_g71_ingreso_venta.py` (pytest del equipo que ya cubre el
caso con BD real) y las clases de abajo (reescritas contra el código real).

HALLAZGO PRINCIPAL (grave, HISTÓRICO -- ya no aplica, ver arriba): la ficha
pedía 4 componentes de ingreso -- transformación (RF-86), precio de mercado
(RF-86), cosecha (RF-85) y "resultados positivos por venta" (RF-45) -- con
la nota explícita "la parte positiva: una venta con pérdida no puede sumar
en ingresos". Antes del fix, `consolidacion.py::INGRESOS` solo definía 5
componentes y ninguno correspondía a una venta; una venta rentable se
asentaba íntegra por el valor en libros contra `bajas_activos` (GASTOS).

HALLAZGO SECUNDARIO (más preciso que "M08 no existe"): el ESQUEMA de BD
`modulo8` sí existe en `alembic/baseline/esquema_baseline.sql`, con una
tabla `modulo8.reportes_financieros` (FK a `modulo6.periodos_contables`,
columna `tipo_reporte` cuyo comentario da como ejemplo exactamente
`'ESTADO_RESULTADOS'`, con `ruta_archivo` y `sha256_archivo` de integridad)
-- es decir, la infraestructura de BD para "disponibilidad en M08" SÍ está
diseñada y provisionada. Pero NINGÚN archivo `.py` de `src/` menciona
`modulo8` ni escribe en esa tabla -- no existe código de aplicación que
conecte la generación de RF-93 con M08. Es una integración a medio
construir: el destino existe, el código que lo alimentaría no.

(a) Generación base del estado -- CONFIRMADO: `GenerarEstadoResultadosUseCase.generar()`
    sí construye un estado nuevo (vía `ConstructorEstadoResultados.guardar()`),
    calcula Total_Ingresos (suma de los 5 componentes de `INGRESOS`) y lo
    persiste con una versión incremental.
(b) Disponibilidad en M08 -- HALLAZGO: el esquema `modulo8` y su tabla
    `reportes_financieros` existen en BD, pero ningún código de `src/`
    escribe ahí -- la integración real no está construida (ver arriba).
(c)/(d)/(e)/(f) Los 4 componentes de ingreso -- HALLAZGO: solo 3 de los 4 que
    pide la ficha existen con una fuente real (transformación: VARIACION_VR_TB/GANANCIA;
    precio: VARIACION_VR_PM/GANANCIA; cosecha: PRODUCTO_AGRICOLA/UNICO). El cuarto
    (venta positiva de RF-45) NO EXISTE -- confirmado arriba.
(g) Total_Ingresos -- CONFIRMADO: es la suma literal de los 5 componentes de
    `INGRESOS` (propiedad `EstadoResultados.total_ingresos`).
(h) Separación transformación/precio en la presentación -- CONFIRMADO: el
    diccionario `componentes` que se persiste y se devuelve mantiene ambos
    valores por separado (no se suman antes de guardar).

Cómo se prueba: pytest de unidad sobre las funciones de dominio puras
(`estado_resultados`, `_COMPONENTE_LINEA`) y sobre
`GenerarEstadoResultadosUseCase`/`ConstructorEstadoResultados` con repos
mockeados (no hay BD real disponible en este entorno de pruebas). Confirmado
también que la ficha describe endpoints `/api/v1/m06/income-statements` que
NO EXISTEN -- el router real usa prefijo `/finanzas` con rutas
`POST /finanzas/periodos/{id}/estados-resultados` y
`GET /finanzas/estados-resultados/{id_estado}` (ver `m06_router.py`).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g71_generacion_consolidado_ingresos.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G71.html --self-contained-html
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.domain.services.consolidacion import (
    INGRESOS,
    CostoPeriodo,
    MovimientoResultado,
    estado_resultados,
)
from src.financial_valuation.domain.value_objects.nic41 import Sentido, TipoHecho

REPO_ROOT = Path(__file__).resolve().parents[5]


def _periodo(estado="CERRADO"):
    return Periodo(id_periodo_contable=93, numero_id_tributaria="900123456", tipo_cierre="MENSUAL",
                   fecha_inicio=__import__("datetime").date(2026, 10, 1),
                   fecha_fin=__import__("datetime").date(2026, 10, 31), estado=estado)


class TestSubCasoBDisponibilidadEnM08NoVerificable:
    def test_el_esquema_modulo8_y_su_tabla_de_reportes_si_existen_en_bd(self):
        ddl = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')
        assert 'CREATE SCHEMA modulo8' in ddl
        assert 'CREATE TABLE modulo8.reportes_financieros' in ddl

    def test_pero_ningun_codigo_de_src_escribe_en_modulo8_documentacion(self):
        """No es un defecto de RF-93: es una integracion con M08 que nunca se exigio en el
        alcance de este RF (el esquema esta provisionado para el futuro, documentacion
        aspiracional -- mismo patron que el repositorio centralizado de TC-M06-G94)."""
        archivos = [str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
                    if 'modulo8' in p.read_text(encoding='utf-8', errors='ignore').lower()]
        assert not archivos


class TestSubCasoCDEFLosCuatroComponentesDeIngresoDeLaFicha:
    def test_transformacion_biologica_ganancia_si_existe(self):
        er = estado_resultados([MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.GANANCIA.value, Decimal('100.00'))], [])
        assert er.componentes['ganancia_transformacion_biologica'] == Decimal('100.00')

    def test_precio_de_mercado_ganancia_si_existe(self):
        er = estado_resultados([MovimientoResultado(TipoHecho.VARIACION_VR_PM.value, Sentido.GANANCIA.value, Decimal('50.00'))], [])
        assert er.componentes['ganancia_precio_mercado'] == Decimal('50.00')

    def test_ingresos_por_cosecha_rf85_si_existe(self):
        er = estado_resultados([MovimientoResultado(TipoHecho.PRODUCTO_AGRICOLA.value, Sentido.UNICO.value, Decimal('30.00'))], [])
        assert er.componentes['ingresos_productos_agricolas'] == Decimal('30.00')

    def test_una_venta_rentable_ahora_si_produce_un_ingreso_corregido(self):
        """CERRADO (INC-M06-364-G71): una baja por venta con valor en libros 1000 vendida en
        1500 ahora reporta 1500 en ingresos_venta_activos y 1000 en bajas_activos (gastos) --
        el neto 500 es la utilidad real de la venta."""
        venta = MovimientoResultado(TipoHecho.BAJA_ACTIVO.value, Sentido.UNICO.value, Decimal('1000.00'),
                                    valor_venta=Decimal('1500.00'))
        er = estado_resultados([venta], [])
        assert er.componentes['ingresos_venta_activos'] == Decimal('1500.00')
        assert er.componentes['bajas_activos'] == Decimal('1000.00')
        assert er.resultado_neto == Decimal('500.00')

    def test_una_baja_sin_valor_de_venta_sigue_sin_generar_ingreso_confirmado_correcto(self):
        """Una baja por muerte/sacrificio sin valor_venta (p.ej. no hubo comprador) sigue sin
        generar ingreso -- solo las ventas con valor reportado lo generan."""
        sin_venta = MovimientoResultado(TipoHecho.BAJA_ACTIVO.value, Sentido.UNICO.value, Decimal('700.00'))
        er = estado_resultados([sin_venta], [])
        assert er.componentes['ingresos_venta_activos'] == 0
        assert er.componentes['bajas_activos'] == Decimal('700.00')

    def test_ahora_si_existe_un_componente_de_ingreso_de_venta_confirmado_correcto(self):
        nombres = " ".join(INGRESOS).lower()
        assert 'venta' in nombres


class TestSubCasoGTotalIngresosEsLaSumaDeLosComponentesReales:
    def test_total_ingresos_suma_los_seis_componentes_reales_documentacion(self):
        """No es un defecto: INGRESOS tiene 6 componentes reales (incluye
        ganancia_reconocimiento_inicial y ganancia_ajustes_periodos_anteriores, que la ficha
        original no mencionaba, y desde el fix tambien ingresos_venta_activos) -- documentacion
        de la forma real, no los 4 que describia la ficha."""
        assert len(INGRESOS) == 6
        assert 'ingresos_venta_activos' in INGRESOS

    def test_total_ingresos_es_la_suma_exacta_sin_redondeo_adicional(self):
        movimientos = [
            MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.GANANCIA.value, Decimal('123.45')),
            MovimientoResultado(TipoHecho.VARIACION_VR_PM.value, Sentido.GANANCIA.value, Decimal('67.89')),
            MovimientoResultado(TipoHecho.PRODUCTO_AGRICOLA.value, Sentido.UNICO.value, Decimal('10.01')),
        ]
        er = estado_resultados(movimientos, [])
        assert er.total_ingresos == Decimal('201.35')


class TestSubCasoAGeneracionBaseConfirmadaCorrecta:
    def test_generar_construye_un_estado_nuevo_con_version_incremental(self):
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo('CERRADO')
        periodos.ultima_ejecucion.return_value = {'activos_excluidos': []}
        reportes = MagicMock()
        reportes.movimientos.return_value = [
            {'tipo_hecho': 'VARIACION_VR_TB', 'sentido': 'GANANCIA', 'valor': '100.00', 'es_reverso': False},
        ]
        reportes.siguiente_version_estado.return_value = 3
        reportes.agregar_estado.return_value = 501
        reportes.hechos_sin_asiento.return_value = []  # PR #1121 (TC-M06-G74): conciliacion ya desplegada
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        auditoria = MagicMock()
        db = MagicMock()
        uc = GenerarEstadoResultadosUseCase(db=db, periodos=periodos, reportes=reportes, constructor=constructor,
                                            auditoria=auditoria)
        resultado = uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        assert resultado['version'] == 3
        assert resultado['id_estado'] == 501
        assert resultado['resultado_neto'] == Decimal('100.00')
        db.commit.assert_called_once()
        auditoria.registrar.assert_called_once()

    def test_generar_rechaza_periodo_no_cerrado(self):
        from src.shared.errors import BusinessRuleError
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo('ABIERTO')
        uc = GenerarEstadoResultadosUseCase(db=MagicMock(), periodos=periodos, reportes=MagicMock(),
                                            constructor=MagicMock(), auditoria=MagicMock())
        with pytest.raises(BusinessRuleError):
            uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)


class TestSubCasoHSeparacionTransformacionPrecioEnLaPresentacion:
    def test_transformacion_y_precio_se_mantienen_separados_no_se_suman(self):
        movimientos = [
            MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.GANANCIA.value, Decimal('40.00')),
            MovimientoResultado(TipoHecho.VARIACION_VR_PM.value, Sentido.GANANCIA.value, Decimal('25.00')),
        ]
        er = estado_resultados(movimientos, [])
        assert er.componentes['ganancia_transformacion_biologica'] == Decimal('40.00')
        assert er.componentes['ganancia_precio_mercado'] == Decimal('25.00')


class TestEndpointsRealesNoCoincidenConLaFichaDocumentacion:
    def test_el_router_real_usa_prefijo_finanzas_no_api_v1_m06(self):
        """No es un defecto: solo una diferencia de convencion de nombres de endpoint con la
        ficha original (que describia /api/v1/m06/income-statements)."""
        archivo = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'prefix="/finanzas"' in texto
