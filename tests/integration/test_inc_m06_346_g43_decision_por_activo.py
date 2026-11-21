# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | INC-M06-346-G43-03 RF-87 FA-2: decisión por activo sin precio (excluir o estimar) |
# | 2026-11-13 | Arekkazu | INC-M06-91-G43-03 RF-87: el estimado sale en la respuesta con su medición |
"""RF-87 FA-2 y CA-5: el Contador decide por cada activo sin precio si entra estimado con el último precio
conocido o se excluye al período siguiente. Ninguno pasa al costo (RF-88 v2.0, NIC 41 ¶31)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.integration.test_inc_m06_lote_2026_11_10 import ESPECIE, _codigo, _reconocido
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _activo,
    _pesaje,
    contador,
    m06,
)

pytestmark = pytest.mark.integration


def test_cada_activo_sin_precio_se_estima_o_se_excluye_por_separado(db_session, m06, contador):
    uid = contador["id_usuario"]
    finca, estimado, periodo = _reconocido(db_session, m06, uid)
    excluido = _activo(db_session, finca, uid, especie=ESPECIE, origen="compra", costo=3000000)
    _pesaje(db_session, excluido, "350", -timedelta(minutes=4))
    m06.confirmar_reconocimiento().execute(excluido, uid)
    db_session.execute(text("SET LOCAL session_replication_role = replica"))  # el precio vence: ambos sin precio
    db_session.execute(text("UPDATE modulo6.precios_mercado SET fecha_vencimiento = :d WHERE id_especie = :e"),
                       {"d": HOY - timedelta(days=1), "e": ESPECIE})
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    p = periodo.id_periodo_contable

    sin_precio = {a["id_activo_biologico"] for a in m06.cierre().prevalidar(periodo).activos_sin_precio}
    assert sin_precio == {estimado, excluido}

    # Estimar uno no basta: el otro se excluiría y eso exige autorización (el cierre queda en espera).
    assert _codigo(lambda: m06.cierre().execute(p, uid, activos_estimados=[estimado]))[0] == "EXCLUSION_REQUIERE_AUTORIZACION"

    # Solo se estima lo que la verificación previa muestra sin precio.
    assert _codigo(lambda: m06.cierre().execute(p, uid, activos_estimados=[999999]))[0] == "ACTIVO_ESTIMADO_NO_APLICA"

    cierre = m06.cierre().execute(p, uid, autorizar_exclusiones=True, activos_estimados=[estimado])
    assert cierre["estado"] == "CERRADO"
    assert [(a["id_activo_biologico"], a["motivo"]) for a in cierre["activos_excluidos"]] == [(excluido, "PENDIENTE_PRECIO")]
    # El estimado entró al cierre con su medición marcada como estimada (RF-83 v1.2), aunque no varíe.
    assert cierre["activos_procesados"] == 1
    assert [a["id_activo_biologico"] for a in cierre["activos_estimados"]] == [estimado]
