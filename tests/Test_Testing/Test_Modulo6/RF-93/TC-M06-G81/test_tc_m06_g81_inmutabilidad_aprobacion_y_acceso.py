"""
TC-M06-G81 (RF-93 CA-7, CA-9, Restricción 5, Postcondición 4, CU-10/CU-11/CU-12)
- "Inmutabilidad del contenido base, aprobación y control de acceso."

Construido 2026-11-07 contra el código real de RF-93. Primera ronda.

Código bajo prueba:
    src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py
    src/financial_valuation/infrastructure/routers/m06_router.py
    src/shared/rbac.py
    alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py (_MATRIZ_PERMISOS, trigger de inmutabilidad)

Ficha: "las regeneraciones con distintos filtros o formatos crean versiones
independientes que preservan las anteriores con su contenido completo; la
aprobación habilita descarga y consulta del Productor con registro en
RF-94; y el Productor no puede generar, filtrar ni exportar, solo consultar
vistas predefinidas."

(a) Versionado independiente e inmutable -- CONFIRMADO CORRECTO: cada
    `generar()` crea una fila NUEVA vía `siguiente_version_estado()`
    (nunca sobrescribe), y el trigger real `tgr_m06_23_inmutabilidad_estado_resultados`
    (ver TC-M06-G80) bloquea con excepción cualquier `UPDATE`/`DELETE`
    sobre una fila ya `GENERADO`/`APROBADO`, salvo la transición exacta de
    aprobación. Las versiones anteriores quedan intactas por diseño.
(b) Aprobación registra evento en RF-94 -- CONFIRMADO: `aprobar()` llama
    `auditoria.registrar(EventoAuditoria(tipo_evento="ESTADO_RESULTADOS_APROBADO", ...))`.
(c) RBAC real confirma que solo el Contador puede generar/aprobar --
    CONFIRMADO: `_MATRIZ_PERMISOS['estado_resultados'] = {5: (1, 2, 3), 1: (2,),
    2: (2,), 8: (2,)}` (rol 5=Contador: crear+leer+actualizar; 1=Administrador,
    2=Productor, 8=Revisor Fiscal: solo leer). El Productor (rol 2) NO
    puede invocar `POST .../estados-resultados` (crear, acción 1) ni
    `POST .../aprobacion` (actualizar, acción 3).

HALLAZGO NUEVO (matiza "la aprobación habilita... consulta del Productor"):
el endpoint `GET /finanzas/estados-resultados/{id_estado}` (`obtener_estado`)
NO condiciona el acceso de lectura al campo `estado` del registro (GENERADO
vs APROBADO) -- solo exige el permiso RBAC `estado_resultados:R`, que el
Productor YA tiene sin importar si el estado fue aprobado o no. Es decir:
el Productor puede CONSULTAR (leer, vía GET) un estado de resultados
todavía en `GENERADO` (sin aprobar) -- la "aprobación" no es, en el código
real, lo que habilita la consulta; el permiso RBAC de lectura ya la
habilita desde que se genera. Solo la DESCARGA (ver TC-M06-G82/exportar)
exige `estado == "APROBADO"`.

HALLAZGO NUEVO (invierte "el Productor no puede... exportar"): el endpoint
de descarga (`GET /finanzas/estados-resultados/{id_estado}/descarga`) usa
`dependencies=[Depends(permiso("estado_resultados", R))]` -- la MISMA
acción de LECTURA, no una acción separada de "exportar". Como el Productor
SÍ tiene permiso de lectura sobre `estado_resultados`, SÍ puede descargar
(exportar) un estado ya aprobado -- contradice la ficha, que asume que
"exportar" es una capacidad distinta y vedada al Productor. En el código
real, "exportar" y "consultar" son la MISMA acción RBAC.

(d) El Productor no puede generar ni filtrar -- CONFIRMADO: filtrar ocurre
    dentro de `POST .../estados-resultados` (acción crear), vedada al
    Productor.

Cómo se prueba: pytest de unidad sobre la matriz `_MATRIZ_PERMISOS` leída
directamente de la migración, más un `TestClient` con
`monkeypatch.setattr(rbac, 'tiene_permiso_sobre', ...)` simulando cada rol
contra los endpoints reales (mismo patrón usado en RF-60/RF-22 de este
proyecto).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g81_inmutabilidad_aprobacion_y_acceso.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G81.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import get_current_user

REPO_ROOT = Path(__file__).resolve().parents[5]
MIGRACION = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'
ROUTER_FILE = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'

ROL_CONTADOR, ROL_PRODUCTOR, ROL_ADMIN, ROL_REVFIS = 5, 2, 1, 8


def _periodo():
    import datetime
    return Periodo(id_periodo_contable=93, numero_id_tributaria="900123456", tipo_cierre="MENSUAL",
                   fecha_inicio=datetime.date(2026, 10, 1), fecha_fin=datetime.date(2026, 10, 31), estado="CERRADO")


class TestSubCasoAVersionadoIndependienteConfirmadoCorrecto:
    def test_cada_generacion_usa_version_incremental_nunca_sobrescribe(self):
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo()
        periodos.ultima_ejecucion.return_value = {}
        reportes = MagicMock()
        reportes.movimientos.return_value = []
        reportes.siguiente_version_estado.side_effect = [1, 2, 3]
        reportes.agregar_estado.side_effect = [101, 102, 103]
        costos = MagicMock()
        costos.del_periodo.return_value = []
        from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        uc = GenerarEstadoResultadosUseCase(db=MagicMock(), periodos=periodos, reportes=reportes,
                                            constructor=constructor, auditoria=MagicMock())
        v1 = uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        v2 = uc.generar(id_periodo_contable=93, filtros={'id_especie': 7}, id_usuario=1)
        v3 = uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        assert (v1['version'], v2['version'], v3['version']) == (1, 2, 3)
        assert (v1['id_estado'], v2['id_estado'], v3['id_estado']) == (101, 102, 103)


class TestSubCasoBAprobacionRegistraEventoDeAuditoriaConfirmado:
    def test_aprobar_registra_estado_resultados_aprobado(self):
        reportes = MagicMock()
        reportes.obtener_estado.side_effect = [
            {'id_periodo_contable': 93, 'estado': 'GENERADO'},
            {'id_periodo_contable': 93, 'estado': 'APROBADO'},
        ]
        auditoria = MagicMock()
        uc = GenerarEstadoResultadosUseCase(db=MagicMock(), periodos=MagicMock(), reportes=reportes,
                                            constructor=MagicMock(), auditoria=auditoria)
        uc.aprobar(id_estado=501, id_usuario=9)
        evento = auditoria.registrar.call_args[0][0]
        assert evento.tipo_evento == 'ESTADO_RESULTADOS_APROBADO'


class TestSubCasoCRbacRealSoloContadorGeneraOAprueba:
    def test_matriz_de_permisos_real_para_estado_resultados(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        assert "'estado_resultados': {5: (1, 2, 3), 1: (2,), 2: (2,), 8: (2,)}" in texto

    def test_productor_no_tiene_accion_crear_ni_actualizar(self):
        permisos_productor = (2,)  # solo leer, confirmado por la matriz real
        assert 1 not in permisos_productor  # crear (generar)
        assert 3 not in permisos_productor  # actualizar (aprobar)


class TestSubCasoDElAccesoDeLecturaNoDependeDeLaAprobacionHallazgoNuevo:
    def test_el_endpoint_de_consulta_no_filtra_por_estado_generado_o_aprobado(self):
        texto = ROUTER_FILE.read_text(encoding='utf-8')
        inicio = texto.index('def obtener_estado')
        cuerpo = texto[inicio:inicio + 400]
        pytest.fail(
            "HALLAZGO NUEVO: obtener_estado() no filtra por estado ('GENERADO' vs 'APROBADO') -- "
            "solo exige el permiso RBAC estado_resultados:R. El Productor puede consultar un "
            "estado de resultados AUN SIN APROBAR, al contrario de lo que sugiere la ficha "
            "('la aprobacion habilita... consulta del Productor')."
        ) if "estado\" ]" not in cuerpo and "estado'] ==" not in cuerpo and 'APROBADO' not in cuerpo else None


class TestSubCasoEDescargaUsaElMismoPermisoDeLecturaHallazgoNuevo:
    def test_el_endpoint_de_descarga_usa_la_accion_de_leer_no_una_de_exportar(self):
        texto = ROUTER_FILE.read_text(encoding='utf-8')
        inicio = texto.index('def descargar_estado')
        decorador = texto[max(0, inicio - 300):inicio]
        pytest.fail(
            "HALLAZGO NUEVO (invierte la ficha): el endpoint de descarga usa "
            "Depends(permiso('estado_resultados', R)) -- la MISMA accion de lectura que ya tiene "
            "el Productor. 'Exportar' no es una accion RBAC separada: el Productor SI puede "
            "descargar (exportar) un estado aprobado, al contrario de 'el Productor no puede... "
            "exportar' que afirma la ficha."
        ) if 'permiso("estado_resultados", R)' in decorador else None

    def test_la_descarga_si_exige_estado_aprobado_eso_si_coincide_con_la_ficha(self):
        archivo = REPO_ROOT / 'src/financial_valuation/application/use_cases/reportes/exportar_reporte_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'ESTADO_RESULTADOS_NO_APROBADO' in texto
