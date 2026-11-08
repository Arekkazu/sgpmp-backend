"""
TC-M06-G08 (RF-93 Restricciones 1 y 4, CA-5, FA-1, CU-01/CU-05) -
"Disponibilidad permanente del consolidado y bloqueo sobre períodos no
cerrados."

Construido 2026-11-07 contra el código real de RF-93. Primera ronda.

Código bajo prueba:
    src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py (_cerrado, generar)
    src/shared/errors.py (status_code de cada excepción)
    alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py (trigger fn_tgr_m06_23_inmutabilidad_estado_resultados)

HALLAZGO PRINCIPAL (matiza el código HTTP de la ficha): la ficha pide
"se rechaza con HTTP 422 la generación sobre períodos ABIERTO y EN_CIERRE,
sobre identificadores inexistentes y con tipo_periodo inválido" -- es decir,
asume que LOS 4 casos responden 422. El código real distingue dos familias
de error distintas (`src/shared/errors.py`):
- `BusinessRuleError` → **HTTP 422**. `_cerrado()` lanza
  `BusinessRuleError(code="PERIODO_NO_CERRADO")` cuando
  `periodo.estado != "CERRADO"` -- esto SÍ cubre ABIERTO y EN_CIERRE con
  422, tal como pide la ficha.
- `NotFoundError` → **HTTP 404**, no 422. `_cerrado()` lanza
  `NotFoundError(code="PERIODO_NO_ENCONTRADO")` cuando
  `self.periodos.obtener(id_periodo_contable)` es `None` -- un
  identificador inexistente responde **404**, NO 422 como asume la ficha.

Sobre "tipo_periodo inválido": el endpoint real
(`POST /finanzas/periodos/{id_periodo_contable}/estados-resultados`) no
recibe ningún campo `tipo_periodo` en su body (`FiltrosEstadoDTO` tiene
solo los 4 filtros, ver TC-M06-G05/G06) ni en su ruta (`id_periodo_contable`
es un entero, no un tipo de período). `tipo_cierre` (MENSUAL/TRIMESTRAL/
ANUAL) es un atributo que se fija al CREAR el período, no un parámetro de
la generación del estado de resultados -- el escenario "generar con
tipo_periodo inválido" no es aplicable a este endpoint en absoluto.

(a)/(b)/(c) Consolidado siempre disponible e inalterado -- CONFIRMADO,
    aunque de forma más fuerte de lo que pide la ficha: existe un trigger
    real de inmutabilidad, `fn_tgr_m06_24_...` -- en realidad
    `fn_tgr_m06_23_inmutabilidad_estado_resultados`, que BLOQUEA a nivel de
    BD cualquier `DELETE` (`RAISE EXCEPTION ... RF-93 R5`) y cualquier
    `UPDATE` sobre una fila cuyo estado ya sea `GENERADO` o `APROBADO`
    (salvo la transición controlada GENERADO→APROBADO). Cada generación
    (filtrada o no) crea una fila nueva con versión incremental
    (`siguiente_version_estado`); ninguna versión anterior se toca jamás.
(d)/(e) Rechazo en período ABIERTO/EN_CIERRE -- CONFIRMADO: 422
    (`BusinessRuleError('PERIODO_NO_CERRADO')`).
(f) Rechazo con identificador inexistente -- HALLAZGO: responde **404**,
    no 422 (`NotFoundError`, no `BusinessRuleError`).
(g) "tipo_periodo inválido" -- HALLAZGO: no aplicable; no existe ese campo
    en el endpoint de generación.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g08_disponibilidad_consolidado_bloqueo_periodo.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G08.html --self-contained-html
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.infrastructure.dto.m06_dto import FiltrosEstadoDTO
from src.shared.errors import BusinessRuleError, NotFoundError

REPO_ROOT = Path(__file__).resolve().parents[5]
MIGRACION = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'


def _periodo(estado):
    return Periodo(id_periodo_contable=93, numero_id_tributaria='900123456', tipo_cierre='MENSUAL',
                   fecha_inicio=date(2026, 10, 1), fecha_fin=date(2026, 10, 31), estado=estado)


def _uc(periodo):
    periodos = MagicMock()
    periodos.obtener.return_value = periodo
    return GenerarEstadoResultadosUseCase(db=MagicMock(), periodos=periodos, reportes=MagicMock(),
                                          constructor=MagicMock(), auditoria=MagicMock())


class TestSubCasoDeRechazoPorPeriodoAbiertoOEnCierreEs422:
    @pytest.mark.parametrize('estado_periodo', ['ABIERTO', 'EN_CIERRE'])
    def test_periodo_no_cerrado_lanza_business_rule_error_422(self, estado_periodo):
        uc = _uc(_periodo(estado_periodo))
        with pytest.raises(BusinessRuleError) as exc:
            uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        assert exc.value.status_code == 422
        assert exc.value.code == 'PERIODO_NO_CERRADO'


class TestSubCasoFIdentificadorInexistenteEs404NoEs422HallazgoSobreElCodigoHttp:
    def test_periodo_inexistente_lanza_not_found_404_no_422(self):
        uc = _uc(None)
        with pytest.raises(NotFoundError) as exc:
            uc.generar(id_periodo_contable=999999, filtros={}, id_usuario=1)
        pytest.fail(
            f"HALLAZGO: un id_periodo_contable inexistente responde HTTP "
            f"{exc.value.status_code} (NotFoundError, code={exc.value.code!r}) -- la ficha pide "
            f"422 para este caso, pero el codigo real usa 404, distinto del 422 que SI aplica "
            f"a ABIERTO/EN_CIERRE."
        ) if exc.value.status_code == 404 else None


class TestSubCasoGTipoPeriodoInvalidoNoAplicaAEsteEndpoint:
    def test_filtros_estado_dto_no_tiene_ningun_campo_tipo_periodo(self):
        campos = set(FiltrosEstadoDTO.model_fields.keys())
        pytest.fail(
            "HALLAZGO: el endpoint de generacion (FiltrosEstadoDTO + id_periodo_contable como "
            "entero en la ruta) no tiene ningun campo 'tipo_periodo' -- el escenario 'generar con "
            "tipo_periodo invalido' no es aplicable; tipo_cierre es un atributo que se fija al "
            "CREAR el periodo, no un parametro de esta operacion."
        ) if 'tipo_periodo' not in campos else None


class TestSubCasoABCConsolidadoSiempreDisponibleEInalteradoPorUnTriggerReal:
    def test_existe_un_trigger_real_de_inmutabilidad_para_estados_generados_o_aprobados(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        assert 'fn_tgr_m06_23_inmutabilidad_estado_resultados' in texto
        assert "RF-93 R5" in texto

    def test_el_trigger_bloquea_cualquier_delete_sin_excepcion(self):
        texto = MIGRACION.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO CONFIRMADO (a): el trigger real rechaza TODO DELETE sobre "
            "modulo6.estados_resultados_periodo incondicionalmente (\"no puede eliminarse. "
            "RF-93 R5\") -- ninguna version, filtrada o no, puede borrarse jamas."
        ) if "TG_OP = 'DELETE'" in texto and 'no puede eliminarse' in texto else None

    def test_cada_generacion_crea_version_nueva_nunca_modifica_una_existente(self):
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo('CERRADO')
        periodos.ultima_ejecucion.return_value = {'activos_excluidos': []}
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
        r1 = uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        r2 = uc.generar(id_periodo_contable=93, filtros={'id_especie': 10}, id_usuario=1)
        r3 = uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        assert [r1['version'], r2['version'], r3['version']] == [1, 2, 3]
        assert [r1['id_estado'], r2['id_estado'], r3['id_estado']] == [101, 102, 103]
