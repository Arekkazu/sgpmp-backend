# | Fecha      | Nombre         | Que se hizo                                                          |
# |------------|----------------|----------------------------------------------------------------------|
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-296-G34-01 RF-86: aviso al Contador por medición suspendida  |
"""INC-M06-296-G34-01 (#984): cuando RF-83 no completa la medición, se avisa al Contador.

Se fuerza ``VALOR_NETO_NO_POSITIVO`` subiendo los costos de venta al 100 % después del
reconocimiento: el evento queda ``MEDICION_PENDIENTE``, no se crea ninguna línea, medición ni
variación, y el Contador recibe un aviso con causa, activo y evento (el que QA no encontraba)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from tests.integration.test_m06_flujo_nic41_integration import (
    HOY, _activo, _configurar, _escalar, _finca, _matriz, _pesaje, _precio, contador, m06,  # noqa: F401 (fixtures)
)

pytestmark = pytest.mark.integration


class _NotificadorConDetalle:
    def __init__(self) -> None:
        self.avisos: list[tuple[str, str, dict, int | None]] = []

    def a_contadores(self, tipo_evento, mensaje, detalle, id_finca=None) -> None:
        self.avisos.append((tipo_evento, mensaje, detalle, id_finca))


def test_medicion_suspendida_avisa_al_contador_sin_registros_parciales(db_session, m06, contador):
    uid = contador["id_usuario"]
    especie = 2
    finca = _finca(db_session, uid)
    _configurar(m06, uid, especie)
    _matriz(m06, uid)
    activo = _activo(db_session, finca, uid, especie=especie, origen="nacimiento", costo=None)
    _pesaje(db_session, activo, "400", -timedelta(minutes=5))
    _precio(m06, uid, especie, "8000", HOY - timedelta(days=10))
    m06.confirmar_reconocimiento().execute(activo, uid)
    m06.procesar_eventos().execute()  # el pesaje del reconocimiento no genera variación

    notificador = _NotificadorConDetalle()
    m06.__dict__["notificador"] = notificador
    m06.guardar_costos_venta().execute(especie, D("1"), D("0"), D("0"), uid)
    lineas_antes = len(m06.asientos.del_activo(activo))
    mediciones_antes = _escalar(db_session, "SELECT count(*) FROM modulo6.mediciones_posteriores "
                                            "WHERE id_activo_biologico = :a", a=activo)
    evento = _pesaje(db_session, activo, "420")

    assert m06.procesar_eventos().execute().get("MEDICION_PENDIENTE") == 1
    assert len(m06.asientos.del_activo(activo)) == lineas_antes
    assert _escalar(db_session, "SELECT count(*) FROM modulo6.mediciones_posteriores WHERE id_activo_biologico = :a",
                    a=activo) == mediciones_antes
    assert _escalar(db_session, "SELECT count(*) FROM modulo6.variaciones_valor_razonable "
                                "WHERE id_activo_biologico = :a", a=activo) == 0

    [(tipo, mensaje, detalle, id_finca)] = notificador.avisos
    assert tipo == "ALERTA_FINANCIERA_NIC41" and id_finca == finca
    assert detalle == {"causa": "RF_83_NO_COMPLETADO", "motivo": "VALOR_NETO_NO_POSITIVO",
                       "id_activo_biologico": activo, "id_evento": evento}
    assert "suspendido" in mensaje and "RF" not in mensaje and "None" not in mensaje
    # La auditoría existente se conserva.
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo6.auditorias_financieras WHERE tipo_evento = 'MEDICION_PENDIENTE' "
        "AND id_activo_biologico = :a"), {"a": activo}).scalar() >= 1
