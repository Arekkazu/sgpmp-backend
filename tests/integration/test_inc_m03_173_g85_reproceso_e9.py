# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-173-G85 RF-57 E9: el evento pendiente se reevalúa al configurar la regla |
"""INC-M03-173-G85 (#878, BUG-G85-01 parte 2): tras crear el umbral de la variable, el evento que
quedó PENDIENTE_EVALUACION se evalúa sin reenviarlo. Router real, worker real y PostgreSQL real.
"""
import pytest
from sqlalchemy import text

from src.telemetry.infrastructure.workers.postcommit_worker import reprocesar_pendientes_e9
from tests.integration.test_inc_m03_173_g85_e9_regla_sin_umbral import (  # noqa: F401
    _evento, _fila, _umbral, area, http, modelos,
)

pytestmark = pytest.mark.integration


def _operativas(db, hw):
    return db.execute(text("SELECT tipo_alerta::text FROM modulo3.alertas WHERE id_sensor=:s AND tipo_alerta <> 'TECNICA'"),
                      {"s": hw["sensor"]}).scalars().all()


def test_evento_pendiente_genera_su_alerta_cuando_se_configura_el_umbral(http, db_session, area):
    hw = area()
    tecnica = _evento(http, db_session, hw).json()["id_alerta"]
    assert _operativas(db_session, hw) == []

    # Sin umbral todavía: el worker no lo toca.
    reprocesar_pendientes_e9(db_session.connection(), identidad=True)
    assert _operativas(db_session, hw) == []
    assert _fila(db_session, tecnica)["metadato_evento"]["evento_pendiente"]["estado_evaluacion"] == "PENDIENTE_EVALUACION"

    _umbral(db_session, hw["especie"], "NH3")
    conexion = db_session.connection()
    conexion.execute(text("SET ROLE sgpmp_app"))  # rol de la API, sujeto a RLS
    try:
        resumen = reprocesar_pendientes_e9(conexion, identidad=True)
    finally:
        conexion.execute(text("RESET ROLE"))

    assert resumen["reevaluados"] >= 1
    assert _operativas(db_session, hw) == ["SINDROME_RESPIRATORIO"]
    metadato = _fila(db_session, tecnica)["metadato_evento"]
    assert metadato["evento_pendiente"]["estado_evaluacion"] == "EVALUADO"
    assert metadato["reevaluacion_e9"]["id_alerta_generada"] is not None
    assert db_session.execute(text("SELECT count(*) FROM modulo3.bitacora_auditoria_iot "
                                   "WHERE tipo_evento='EVENTO_PENDIENTE_REEVALUADO' AND entidad_afectada_id=:d"),
                              {"d": str(hw["device"])}).scalar_one() == 1

    # Idempotente: un segundo ciclo no vuelve a evaluar el mismo evento.
    reprocesar_pendientes_e9(db_session.connection(), identidad=True)
    assert _operativas(db_session, hw) == ["SINDROME_RESPIRATORIO"]
