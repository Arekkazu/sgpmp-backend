# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | INC-M06-366-G31 RF-82/84/85: avisos de M06 en la bandeja del Contador |
"""INC-M06-366-G31 / TC-M06-G31 contra PostgreSQL real (SGPMP-FRONT-END-PWA#668).

- Los destinatarios del aviso se buscaban en una conexión aparte, que no ve la finca ni la asignación que el run
  del sandbox de QA aún no confirmó: el aviso se quedaba sin destinatarios.
- La valoración por costo (RF-82 CA-5), el bloqueo sin valor (RF-82 FA-3) y el costo de mantenimiento llevado a
  gasto (RF-84 paso 7) solo quedaban en la auditoría.
"""
from __future__ import annotations

from decimal import Decimal as D

import pytest
from sqlalchemy.orm import Session

from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import SolicitudCosto
from src.financial_valuation.infrastructure.adapters.notificacion_financiera_m01_adapter import (
    NotificacionFinancieraM01Adapter,
)
from src.shared.errors import AppError
from tests.integration.test_m06_flujo_nic41_integration import (  # noqa: F401 (fixtures)
    HOY,
    _activo,
    _configurar,
    _finca,
    _matriz,
    contador,
    m06,
)


def test_los_destinatarios_salen_de_la_transaccion_del_request(db_session, integration_engine, contador):
    uid = contador["id_usuario"]
    finca = _finca(db_session, uid)  # sin confirmar, como en el sandbox
    aparte = Session(integration_engine)
    try:
        assert NotificacionFinancieraM01Adapter(lambda: aparte)._contadores(aparte, finca) == []  # el error
        assert NotificacionFinancieraM01Adapter(lambda: aparte, db_session)._contadores(aparte, finca) == [uid]
    finally:
        aparte.close()


def test_valoracion_por_costo_bloqueo_y_mantenimiento_llegan_al_contador(db_session, m06, contador):
    uid, especie = contador["id_usuario"], 3  # sin precios: compra al costo, nacimiento sin valor
    finca = _finca(db_session, uid, nit="830095213", dv="0")
    _configurar(m06, uid, especie, vida=24)
    _matriz(m06, uid)
    avisos = m06.notificador.avisos

    comprado = _activo(db_session, finca, uid, especie=especie, origen="compra", costo=D("1200000"))
    assert m06.confirmar_reconocimiento().execute(comprado, uid)["indicador_valoracion"] == "VALORACION_POR_COSTO"
    assert any("se reconoció al costo" in a and "no hay precio de mercado" in a for a in avisos), avisos

    nacido = _activo(db_session, finca, uid, especie=especie, origen="nacimiento", costo=None)
    with pytest.raises(AppError) as bloqueo:
        m06.confirmar_reconocimiento().execute(nacido, uid)
    assert bloqueo.value.code == "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR"
    assert avisos[-1] == bloqueo.value.message and "Registre un precio de mercado" in avisos[-1]  # motivo y opciones

    m06.registrar_costo().execute(SolicitudCosto(subtipo_costo="MANO_OBRA", origen_costo="MANO_OBRA_PROPIA",
                                                 monto_costo=D("80000"), fecha_costo=HOY,
                                                 id_activo_biologico=comprado), uid)
    assert "se registró como gasto del período" in avisos[-1], avisos
