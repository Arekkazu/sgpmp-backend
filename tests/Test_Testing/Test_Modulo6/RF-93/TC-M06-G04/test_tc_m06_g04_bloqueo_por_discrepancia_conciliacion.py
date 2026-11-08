"""
TC-M06-G04 (RF-93 FA-2, Restricción 2, Proceso 5, CU-04) - "Bloqueo por
discrepancia en la conciliación."

Construido 2026-11-07 contra el código real de RF-93. Primera ronda. Se
apoya directamente en la evidencia ya reunida en TC-M06-G01/G02/G03 --
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

1. No hay NADA que "detectar": como ya se confirmó en TC-M06-G03,
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
   caso de uso de Python (confirmado por grep exhaustivo en TC-M06-G03):
   la única aparición de ese nombre en todo `src/` es como ETIQUETA
   decorativa en el diccionario de nombres legibles de
   `consultar_auditoria_financiera_use_case.py` -- nunca se emite.
4. El único mecanismo real relacionado es el trigger de BD
   `fn_tgr_m06_24_consistencia_resultado_neto` (ver TC-M06-G03), que SÍ
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

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g04_bloqueo_por_discrepancia_conciliacion.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G04.html --self-contained-html
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


class TestSubCasoNoExisteNingunEndpointDeConciliacionNiDeAlertas:
    def test_no_existe_ningun_endpoint_de_reconciliation_check_o_conciliacion(self):
        texto = ROUTER.read_text(encoding='utf-8').lower()
        archivos = [p for p in ('reconciliation', 'conciliacion', 'discrepanc') if p in texto]
        pytest.fail(
            f"HALLAZGO: ninguna ruta del router real de M06 menciona reconciliacion/discrepancia "
            f"(buscado: 'reconciliation', 'conciliacion', 'discrepanc' -- encontrados: {archivos or 'ninguno'}). "
            f"La ficha asume un endpoint POST /.../reconciliation-check que no existe."
        ) if not archivos else None

    def test_no_existe_ningun_endpoint_generico_de_alerts(self):
        texto = ROUTER.read_text(encoding='utf-8').lower()
        pytest.fail(
            "HALLAZGO: no existe ningun endpoint '/alerts' en el router real -- el unico "
            "mecanismo de auditoria/alertas real es GET /finanzas/auditoria (RF-94), que no "
            "recibe nunca un evento ERROR_CONCILIACION (ver TC-M06-G03)."
        ) if '"/alerts"' not in texto and "'/alerts'" not in texto else None


class TestSubCasoLaGeneracionSoloPuedeFallarPorPeriodoNoLaFuente:
    def test_generar_solo_tiene_dos_posibles_errores_ninguno_de_discrepancia(self):
        """Lee la firma real de GenerarEstadoResultadosUseCase._cerrado() / generar(): las
        unicas excepciones de negocio posibles son PERIODO_NO_ENCONTRADO y
        PERIODO_NO_CERRADO. No existe ningun BusinessRuleError relacionado con
        discrepancia/conciliacion en todo el modulo."""
        texto = USE_CASE.read_text(encoding='utf-8')
        codigos_error = [l.strip() for l in texto.splitlines() if 'code="' in l or "code='" in l]
        pytest.fail(
            f"HALLAZGO: los unicos codigos de error que puede lanzar la generacion del estado son "
            f"{codigos_error!r} -- ninguno corresponde a una discrepancia de conciliacion. No "
            f"existe 'ERROR_CONCILIACION' como BusinessRuleError lanzable desde Python."
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
            f"HALLAZGO CONFIRMADO: con datos deliberadamente dispares entre dos RF fuente "
            f"(999999.99 vs 0.01), la generacion se completa sin ningun bloqueo ni alerta -- "
            f"resultado_neto={resultado['resultado_neto']}. No hay forma de que el sistema "
            f"detecte o rechace una 'discrepancia' porque no compara fuentes independientes."
        )


class TestSubCasoDElMecanismoRealEsUnTriggerDeBdNuncaUnaRegladeNegocio:
    def test_el_trigger_de_bd_no_identifica_componente_ni_rf_fuente(self):
        """La ficha exige que la alerta 'identifique el componente y el RF fuente'. El
        trigger real (fn_tgr_m06_24_consistencia_resultado_neto, ver TC-M06-G03) solo compara
        dos numeros agregados (resultado_neto vs total_ingresos-total_gastos) -- no tiene
        forma de saber CUAL componente o CUAL RF causo la diferencia, aunque llegara a
        dispararse."""
        migracion = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'
        texto = migracion.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO: el trigger de conciliacion real compara solo 2 numeros agregados "
            "(resultado_neto vs ingresos-gastos) -- no identifica ni el componente ni el RF "
            "fuente de ninguna diferencia, al contrario de lo que pide la ficha."
        ) if 'fn_tgr_m06_24_consistencia_resultado_neto' in texto else None
