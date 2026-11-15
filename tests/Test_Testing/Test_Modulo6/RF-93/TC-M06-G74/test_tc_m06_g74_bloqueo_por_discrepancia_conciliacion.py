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
DISEÑO, PENDIENTE DE DESPLIEGUE A TEST (no es un hueco de diseño ni una
decisión abierta). El mecanismo real de conciliación NO usa los endpoints
`/reconciliation-check` ni `/alerts` que esta ficha asumía -- la
verificación corre en la propia generación del estado: si una variación o
un producto agrícola del período no tiene asiento, `generar()` responde
`422 ESTADO_RESULTADOS_NO_CONCILIA` indicando qué falta, el cierre queda
pendiente con ese motivo, se registra `ERROR_CONCILIACION` en la bitácora
de RF-94 y se avisa al Contador. Este mecanismo llega a TEST cuando se
mergee y despliegue el PR #1121 (el equipo de desarrollo avisará antes de
desplegar). Mientras ese PR no esté desplegado, el código real sigue sin
`ESTADO_RESULTADOS_NO_CONCILIA` (confirmado abajo) y este TC se mantiene en
rojo -- NO por ser un hallazgo nuevo, sino porque todavía no ha llegado a
este checkout/entorno. Re-verificar tras el despliegue del PR #1121.

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

from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.shared.errors import BusinessRuleError, NotFoundError

REPO_ROOT = Path(__file__).resolve().parents[5]
ROUTER = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'
USE_CASE = REPO_ROOT / 'src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py'


class TestSubCasoNoExisteNingunEndpointDeConciliacionNiDeAlertasPendienteDespliegue:
    def test_no_existe_ningun_endpoint_de_reconciliation_check_o_conciliacion(self):
        texto = ROUTER.read_text(encoding='utf-8').lower()
        archivos = [p for p in ('reconciliation', 'conciliacion', 'discrepanc') if p in texto]
        pytest.fail(
            f"PENDIENTE DE DESPLIEGUE (PR #1121, no es un hueco de diseno -- ver actualizacion "
            f"2026-11-13): el mecanismo real no usa estos endpoints, usa 422 "
            f"ESTADO_RESULTADOS_NO_CONCILIA en generar() (buscado en este checkout: 'reconciliation', "
            f"'conciliacion', 'discrepanc' -- encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None

    def test_no_existe_ningun_endpoint_generico_de_alerts(self):
        texto = ROUTER.read_text(encoding='utf-8').lower()
        pytest.fail(
            "PENDIENTE DE DESPLIEGUE (PR #1121, ver actualizacion 2026-11-13): el mecanismo real "
            "es el aviso al Contador + ERROR_CONCILIACION en bitacora, no un endpoint '/alerts' -- "
            "aun no aparece en este checkout."
        ) if '"/alerts"' not in texto and "'/alerts'" not in texto else None


class TestSubCasoLaGeneracionSoloPuedeFallarPorPeriodoPendienteDespliegue:
    def test_generar_solo_tiene_dos_posibles_errores_ninguno_de_discrepancia(self):
        """Lee la firma real de GenerarEstadoResultadosUseCase._cerrado() / generar(). PENDIENTE
        DE DESPLIEGUE (PR #1121, ver actualizacion 2026-11-13): en este checkout todavia no
        existe el codigo ESTADO_RESULTADOS_NO_CONCILIA que el equipo confirmo ya esta resuelto
        en diseno -- re-verificar tras el despliegue."""
        texto = USE_CASE.read_text(encoding='utf-8')
        codigos_error = [l.strip() for l in texto.splitlines() if 'code="' in l or "code='" in l]
        pytest.fail(
            f"PENDIENTE DE DESPLIEGUE: los codigos de error presentes en este checkout son "
            f"{codigos_error!r} -- 'ESTADO_RESULTADOS_NO_CONCILIA' aun no aparece, llega con el "
            f"PR #1121."
        ) if not any('CONCILIACION' in c for c in codigos_error) else None

    def test_generar_con_componentes_sintenticamente_separados_nunca_puede_discrepar(self):
        """Prueba directa: aunque se intente simular una fuente con datos 'contradictorios'
        (p.ej. ingresos de una especie y gastos de otra), el calculo siempre suma todo bajo
        la misma formula total_ingresos - total_gastos -- no hay una segunda ruta de calculo
        con la que comparar, asi que NUNCA se puede producir una excepcion de discrepancia
        desde la aplicacion, sin importar que tan contradictorios sean los datos de entrada."""
        periodos = MagicMock()
        periodos.obtener.return_value = Periodo(
            id_periodo_contable=93, numero_id_tributaria='900123456', tipo_cierre='MENSUAL',
            fecha_inicio=__import__('datetime').date(2026, 10, 1),
            fecha_fin=__import__('datetime').date(2026, 10, 31), estado='CERRADO',
        )
        periodos.ultima_ejecucion.return_value = {'activos_excluidos': []}
        reportes = MagicMock()
        # Datos deliberadamente "contradictorios" entre dos fuentes distintas (RF-86 vs RF-85):
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
        # No debe lanzar NINGUNA excepcion de conciliacion, sin importar que tan dispares sean
        # los montos entre fuentes.
        resultado = uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        pytest.fail(
            f"PENDIENTE DE DESPLIEGUE (PR #1121, ver actualizacion 2026-11-13): en este checkout, "
            f"con datos deliberadamente dispares entre dos RF fuente (999999.99 vs 0.01), la "
            f"generacion se completa sin ningun bloqueo -- resultado_neto={resultado['resultado_neto']}. "
            f"El mecanismo real de conciliacion ya fue confirmado por el equipo, llega con el "
            f"despliegue de ese PR; re-verificar entonces."
        )


class TestSubCasoDElMecanismoDeTriggerEsSecundarioAlDeAplicacionPendienteDespliegue:
    def test_el_trigger_de_bd_no_identifica_componente_ni_rf_fuente(self):
        """El trigger de BD (fn_tgr_m06_24_consistencia_resultado_neto) es una barrera de ultimo
        recurso, no el mecanismo principal -- el real (ESTADO_RESULTADOS_NO_CONCILIA, 422 con
        detalle de que falta) llega con el PR #1121 segun confirmo el equipo (actualizacion
        2026-11-13). El trigger en si mismo no identifica componente/RF, pero ya no es el unico
        mecanismo esperado."""
        migracion = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'
        texto = migracion.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "PENDIENTE DE DESPLIEGUE: el trigger de BD por si solo compara solo 2 numeros "
            "agregados y no identifica componente/RF -- pero el mecanismo real de la aplicacion "
            "(422 ESTADO_RESULTADOS_NO_CONCILIA con detalle) aun no esta en este checkout."
        ) if 'fn_tgr_m06_24_consistencia_resultado_neto' in texto else None
