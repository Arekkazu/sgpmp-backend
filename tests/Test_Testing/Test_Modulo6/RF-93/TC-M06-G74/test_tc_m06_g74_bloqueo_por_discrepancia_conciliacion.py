"""
TC-M06-G74 (RF-93 FA-2, Restricción 2, Proceso 5, CU-04) - "Bloqueo por
discrepancia en la conciliación."

Construido 2026-11-07 contra el código real de RF-93. Primera ronda. Se
apoya directamente en la evidencia ya reunida en TC-M06-G71/G02/G03 --
léase junto a esos tres.

Código bajo prueba:
    src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py
    src/financial_valuation/application/services/reportes.py
    src/financial_valuation/infrastructure/routers/m06_router.py
    alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py (trigger)

HALLAZGO PRINCIPAL (ausencia total de funcionalidad): la ficha completa de
G04 da por hecho que existe un mecanismo de negocio capaz de DETECTAR una
discrepancia entre fuentes y, al detectarla, (1) SUSPENDER la generación,
(2) emitir una alerta crítica al Contador identificando componente y RF
fuente, y (3) registrar `ERROR_CONCILIACION` en RF-94. Ninguna de las tres
cosas existe:

1. No hay NADA que "detectar": como ya se confirmó en TC-M06-G73,
   `resultado_neto` se calcula SIEMPRE como `total_ingresos - total_gastos`
   de la MISMA estructura de componentes (`ConstructorEstadoResultados.
   calcular()`). No hay una segunda fuente independiente con la que
   comparar -- es una identidad algebraica, no una conciliación entre dos
   cálculos separados. Una "discrepancia" en el sentido de la ficha no
   puede existir en este diseño.
2. No existe ningún endpoint `POST /.../reconciliation-check` (la ficha lo
   asume en su columna de evidencia). El router real (`m06_router.py`) no
   tiene ninguna ruta con "reconciliation", "conciliacion" ni "discrepanc"
   en su definición.
3. No existe ningún endpoint `GET /.../alerts` genérico. Lo único parecido
   es `GET /finanzas/auditoria` (RF-94 real), que lista eventos de
   auditoría -- pero `ERROR_CONCILIACION` nunca se registra desde ningún
   caso de uso de Python (confirmado por grep exhaustivo en TC-M06-G73):
   la única aparición de ese nombre en todo `src/` es como ETIQUETA
   decorativa en el diccionario de nombres legibles de
   `consultar_auditoria_financiera_use_case.py` -- nunca se emite.
4. El único mecanismo real relacionado es el trigger de BD
   `fn_tgr_m06_24_consistencia_resultado_neto` (ver TC-M06-G73), que SÍ
   lanza una excepción con el texto `ERROR_CONCILIACION` -- pero es
   inalcanzable por la aplicación (la app nunca inserta valores
   inconsistentes), así que en la práctica NUNCA se dispara ante ningún
   escenario que el Contador pueda producir desde la API.

(a)-(f) Discrepancia en cada una de las 4 fuentes por separado, dos
    simultáneas, diferencia mínima representable -- TODOS HALLAZGO: no hay
    forma de inducir una "discrepancia" porque no hay dos cálculos
    independientes que puedan diferir. Cualquier intento de provocarla
    tendría que ser una escritura directa a BD que viole la identidad
    algebraica, no un escenario alcanzable por un caso de uso o endpoint
    real.

Cómo se prueba: pytest de unidad confirmando con evidencia directa de
código (grep + inspección de `generar()`/`guardar()`) que no existe ningún
camino de error de "discrepancia" entre el cálculo de ingresos y el de
gastos, y que `generar()` solo puede fallar por `PERIODO_NO_ENCONTRADO` o
`PERIODO_NO_CERRADO` -- nunca por una inconsistencia entre fuentes.

ACTUALIZACIÓN 2026-11-13 (respuesta de Análisis/Diseño): RESUELTO EN
DISEÑO. El mecanismo real de conciliación NO usa los endpoints
`/reconciliation-check` ni `/alerts` que esta ficha asumía -- la
verificación corre en la propia generación del estado: si una variación o
un producto agrícola del período no tiene asiento, `generar()` responde
`422 ESTADO_RESULTADOS_NO_CONCILIA` indicando qué falta, el cierre queda
pendiente con ese motivo, se registra `ERROR_CONCILIACION` en la bitácora
de RF-94 y se avisa al Contador. Llega con el PR #1121.

ACTUALIZACIÓN 2026-11-17: CERRADO -- el PR #1121 ya está mergeado y
desplegado (`ConciliacionError`/`ESTADO_RESULTADOS_NO_CONCILIA` en
`src/financial_valuation/application/services/reportes.py`,
líneas 128-149; invocado desde `generar()` en este mismo módulo). Confirmado
contra el código real: `_HECHO_FUENTE` identifica la fuente exacta
("la variación de valor razonable"/"el producto agrícola") y el activo
afectado en el mensaje; `_discrepancia()` registra `ERROR_CONCILIACION` vía
`auditoria.registrar(exc.evento(...))` y avisa al Contador vía
`notificador.a_contadores(...)`. Las clases de abajo quedan reescritas
contra ese código real -- los hallazgos (a)-(f) y 1-4 de arriba son
HISTÓRICOS (ya no aplican).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g74_bloqueo_por_discrepancia_conciliacion.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G74.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.financial_valuation.application.services.reportes import ConciliacionError, ConstructorEstadoResultados
from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.shared.errors import BusinessRuleError, NotFoundError

REPO_ROOT = Path(__file__).resolve().parents[5]
ROUTER = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'
USE_CASE = REPO_ROOT / 'src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py'
REPORTES = REPO_ROOT / 'src/financial_valuation/application/services/reportes.py'


def _periodo_cerrado():
    import datetime
    return Periodo(id_periodo_contable=93, numero_id_tributaria='900123456', tipo_cierre='MENSUAL',
                   fecha_inicio=datetime.date(2026, 10, 1), fecha_fin=datetime.date(2026, 10, 31), estado='CERRADO')


class TestSubCasoNoExisteNingunEndpointDeConciliacionNiDeAlertasConfirmadoPorDiseno:
    def test_no_existe_ningun_endpoint_de_reconciliation_check_o_conciliacion(self):
        """No es un defecto: el mecanismo real no usa un endpoint de conciliacion/alertas
        separado, usa 422 ESTADO_RESULTADOS_NO_CONCILIA directamente en generar()."""
        texto = ROUTER.read_text(encoding='utf-8').lower()
        archivos = [p for p in ('reconciliation', 'conciliacion', 'discrepanc') if p in texto]
        assert not archivos

    def test_no_existe_ningun_endpoint_generico_de_alerts(self):
        """No es un defecto: el mecanismo real es el aviso al Contador + ERROR_CONCILIACION en
        bitacora, no un endpoint '/alerts'."""
        texto = ROUTER.read_text(encoding='utf-8').lower()
        assert '"/alerts"' not in texto and "'/alerts'" not in texto


class TestSubCasoLaConciliacionCerradaConfirmadaCorrecta:
    def test_estado_resultados_no_concilia_existe_en_reportes_py(self):
        """No es un defecto: el codigo de conciliacion vive en reportes.py (ConciliacionError),
        no en generar_estado_resultados_use_case.py -- el grep original buscaba en el archivo
        equivocado. CERRADO 2026-11-17: confirmado desplegado."""
        texto = REPORTES.read_text(encoding='utf-8')
        assert 'code="ESTADO_RESULTADOS_NO_CONCILIA"' in texto

    def test_generar_bloquea_cuando_hay_hechos_sin_asiento_cerrado(self):
        """CERRADO: si reportes.hechos_sin_asiento() devuelve faltantes, guardar() lanza
        ConciliacionError y generar() la propaga -- ya NO es cierto que 'nunca se puede producir
        una excepcion de discrepancia desde la aplicacion'."""
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo_cerrado()
        periodos.ultima_ejecucion.return_value = {'activos_excluidos': []}
        reportes = MagicMock()
        reportes.hechos_sin_asiento.return_value = [
            {'fuente': 'variaciones_valor_razonable', 'identificador': 'BOV-001'},
        ]
        reportes.movimientos.return_value = []
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        auditoria = MagicMock()
        uc = GenerarEstadoResultadosUseCase(db=MagicMock(), periodos=periodos, reportes=reportes,
                                            constructor=constructor, auditoria=auditoria)
        with pytest.raises(ConciliacionError) as exc_info:
            uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        assert exc_info.value.code == 'ESTADO_RESULTADOS_NO_CONCILIA'
        assert 'la variación de valor razonable de BOV-001' in exc_info.value.message
        auditoria.registrar.assert_called_once()
        assert auditoria.registrar.call_args.args[0].tipo_evento == 'ERROR_CONCILIACION'

    def test_generar_no_bloquea_cuando_todos_los_hechos_tienen_asiento_cerrado(self):
        """Control positivo: sin faltantes, la generacion se completa normal (sin importar que
        tan dispares sean los montos entre componentes -- eso sigue siendo correcto, la
        conciliacion es sobre 'tiene asiento o no', no sobre comparar magnitudes)."""
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo_cerrado()
        periodos.ultima_ejecucion.return_value = {'activos_excluidos': []}
        reportes = MagicMock()
        reportes.hechos_sin_asiento.return_value = []
        reportes.movimientos.return_value = [
            {'tipo_hecho': 'VARIACION_VR_TB', 'sentido': 'GANANCIA', 'valor': '999999.99', 'es_reverso': False},
            {'tipo_hecho': 'PRODUCTO_AGRICOLA', 'sentido': 'UNICO', 'valor': '0.01', 'es_reverso': False},
        ]
        reportes.siguiente_version_estado.return_value = 1
        reportes.agregar_estado.return_value = 1
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        uc = GenerarEstadoResultadosUseCase(db=MagicMock(), periodos=periodos, reportes=reportes,
                                            constructor=constructor, auditoria=MagicMock())
        resultado = uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        assert resultado['resultado_neto'] == __import__('decimal').Decimal('1000000.00')


class TestSubCasoDElMecanismoDeAplicacionSiIdentificaFuenteConfirmadoCorrecto:
    def test_el_trigger_de_bd_es_barrera_secundaria_el_mecanismo_real_si_identifica_fuente(self):
        """No es un defecto: el trigger de BD (fn_tgr_m06_24_consistencia_resultado_neto) sigue
        sin identificar componente/RF por si solo, pero ya no es el unico mecanismo -- el real
        (ConciliacionError/_HECHO_FUENTE en reportes.py) SI identifica la fuente exacta y el
        activo afectado en el mensaje de 422. CERRADO 2026-11-17."""
        migracion = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'
        texto_migracion = migracion.read_text(encoding='utf-8', errors='ignore')
        assert 'fn_tgr_m06_24_consistencia_resultado_neto' in texto_migracion
        texto_reportes = REPORTES.read_text(encoding='utf-8')
        assert '_HECHO_FUENTE' in texto_reportes
