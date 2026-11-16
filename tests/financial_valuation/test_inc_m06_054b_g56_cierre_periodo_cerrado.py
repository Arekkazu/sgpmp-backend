# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-14 | destroyerban | INC-M06-054B-G56 RF-91: cerrar de nuevo un período cerrado responde 409, no 404; mensaje sin fecha de cierre |
"""INC-M06-054B-G56 / INC-M06-054-G56 (sin BD).

La política de filas de ``periodos_contables`` no deja bloquear (``FOR UPDATE``) un período CERRADO, así que el
bloqueo no lo devuelve aunque exista. El fake reproduce eso: ``obtener(bloquear=True)`` devuelve ``None`` para un
CERRADO y la lectura sin bloqueo sí lo ve. Cerrar de nuevo debe responder 409 PERIODO_CERRADO (RF-87 FA-5,
RF-91 Restricción 4), también cuando el período no tiene fecha de cierre registrada.
"""
from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from src.financial_valuation.application.use_cases.cierre.ejecutar_cierre_periodo_use_case import (
    EjecutarCierrePeriodoUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.shared.errors import ConflictError, NotFoundError


class _Periodos:
    """Como la BD bajo la RLS de la app: un CERRADO se lee, pero no se bloquea."""

    def __init__(self, periodos, ultima=None):
        self.periodos = {p.id_periodo_contable: p for p in periodos}
        self.ultima = ultima
        self.lecturas = []

    def obtener(self, id_periodo, bloquear=False):
        self.lecturas.append(bloquear)
        periodo = self.periodos.get(id_periodo)
        if bloquear and periodo is not None and periodo.estado == "CERRADO":
            return None
        return periodo

    def ultima_ejecucion(self, _id):
        return self.ultima

    def ejecucion_en_proceso(self, _id):
        return None


def _periodo(id_periodo, estado, fecha_cierre=None):
    return Periodo(id_periodo, "900123456", "MENSUAL", date(2026, 10, 1), date(2026, 10, 31), estado, fecha_cierre)


def _caso(periodos, ultima=None):
    uc = object.__new__(EjecutarCierrePeriodoUseCase)
    uc.db = Mock()
    uc.periodos = _Periodos(periodos, ultima)
    return uc


def test_cerrado_con_fecha_responde_409_y_no_404():
    uc = _caso([_periodo(7, "CERRADO", datetime(2026, 11, 3, 15, tzinfo=timezone.utc))],
               {"nombre_usuario_ejecutor": "Ana Contadora"})
    with pytest.raises(ConflictError) as error:
        uc._iniciar(7, 1, False, False)
    assert error.value.code == "PERIODO_CERRADO"
    assert error.value.message.startswith("El período 2026-10 ya fue cerrado el 03/11/2026 por Ana Contadora.")
    assert "Los períodos cerrados no se reabren" in error.value.message
    uc.db.rollback.assert_called_once()


def test_cerrado_sin_fecha_toma_la_del_ultimo_cierre():
    uc = _caso([_periodo(2, "CERRADO")], {"fecha_fin": datetime(2026, 11, 2, 12, tzinfo=timezone.utc)})
    with pytest.raises(ConflictError) as error:
        uc._iniciar(2, 1, False, False)
    assert error.value.code == "PERIODO_CERRADO"
    assert "ya fue cerrado el 02/11/2026." in error.value.message


def test_cerrado_sin_ninguna_fecha_no_muestra_vacios():
    uc = _caso([_periodo(2, "CERRADO")])
    with pytest.raises(ConflictError) as error:
        uc._iniciar(2, 1, False, False)
    assert error.value.message.startswith("El período 2026-10 ya fue cerrado. Los períodos cerrados no se reabren")
    assert "None" not in error.value.message


def test_periodo_inexistente_sigue_respondiendo_404():
    uc = _caso([])
    with pytest.raises(NotFoundError) as error:
        uc._iniciar(99, 1, False, False)
    assert error.value.code == "PERIODO_NO_ENCONTRADO"


def test_periodo_abierto_se_toma_con_bloqueo_sin_lectura_extra():
    uc = _caso([_periodo(5, "ABIERTO")])
    assert uc._bloquear_periodo(5).estado == "ABIERTO"
    assert uc.periodos.lecturas == [True]


def test_cancelar_un_periodo_cerrado_responde_409_y_no_404():
    uc = _caso([_periodo(7, "CERRADO", datetime(2026, 11, 3, tzinfo=timezone.utc))])
    with pytest.raises(ConflictError) as error:
        uc.cancelar(7, 1)
    assert error.value.code == "CIERRE_NO_CANCELABLE"
