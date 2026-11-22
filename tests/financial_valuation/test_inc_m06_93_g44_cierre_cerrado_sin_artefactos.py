# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-14 | destroyerban | INC-M06-93-G44 RF-87 FA-5: el período cerrado se rechaza antes de procesar eventos pendientes (sin artefactos nuevos) |
"""INC-M06-93-G44 / TC-M06-030 (sin BD): intentar cerrar un período CERRADO responde 409 con la fecha y quien lo
cerró, y no deja artefactos: no se procesan los eventos pendientes de M02 (mediciones y asientos) ni se toca el
período. El fake imita la RLS: un período CERRADO se lee pero no se bloquea (ver INC-M06-054B-G56)."""
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src.financial_valuation.application.use_cases.cierre.ejecutar_cierre_periodo_use_case import (
    EjecutarCierrePeriodoUseCase,
)
from src.shared.errors import ConflictError
from tests.financial_valuation.test_inc_m06_054b_g56_cierre_periodo_cerrado import _Periodos, _periodo


def _caso(periodo, ultima=None):
    uc = object.__new__(EjecutarCierrePeriodoUseCase)
    uc.db = Mock()
    uc.periodos = _Periodos([periodo], ultima)
    uc.procesador_eventos = Mock()
    return uc


@pytest.mark.parametrize("id_periodo", [7, 219])
def test_cerrar_un_periodo_cerrado_responde_409_sin_procesar_eventos(id_periodo):
    uc = _caso(_periodo(id_periodo, "CERRADO", datetime(2026, 11, 3, 15, tzinfo=timezone.utc)),
               {"nombre_usuario_ejecutor": "Juan Contador"})
    with pytest.raises(ConflictError) as error:
        uc.execute(id_periodo, 1)
    assert error.value.code == "PERIODO_CERRADO" and error.value.status_code == 409
    assert "ya fue cerrado el 03/11/2026 por Juan Contador" in error.value.message
    assert "no se reabren" in error.value.message
    uc.procesador_eventos.execute.assert_not_called()  # sin mediciones ni asientos nuevos
    assert uc.periodos.lecturas == [False]  # ni siquiera se intenta bloquear el período
    uc.db.commit.assert_not_called()


def test_un_periodo_abierto_sigue_procesando_los_eventos_antes_del_cierre():
    uc = _caso(_periodo(5, "ABIERTO"))
    uc._iniciar = Mock(side_effect=RuntimeError("se detiene aquí"))
    with pytest.raises(RuntimeError):
        uc.execute(5, 1)
    uc.procesador_eventos.execute.assert_called_once()
    uc._iniciar.assert_called_once()
