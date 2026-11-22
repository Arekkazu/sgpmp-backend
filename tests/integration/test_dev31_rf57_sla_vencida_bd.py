# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-31 RF-57: una alerta CRITICO sin atender 5 min queda VENCIDA, con histórico y bitácora |
"""DEV-31 (RF-57 E10, CA-12) contra los triggers reales de ``modulo3.alertas``."""
from datetime import datetime, timezone
import importlib
import pkgutil

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + "."):
            importlib.import_module(item.name)


def _alerta(db, severidad, minutos_atras, tipo="ESTRES_TERMICO", estado="ACTIVA"):
    return db.execute(text("""
        INSERT INTO modulo3.alertas (tipo_alerta, severidad, estado_alerta, origen_evento, fecha_evento,
                                     fecha_generacion, tipo_variable)
        VALUES (CAST(:t AS modulo3.enum_tipo_alerta), CAST(:s AS modulo3.enum_buffer_nivel_severidad),
                CAST(:e AS modulo3.enum_estado_alerta), 'EDGE', now(), now() - make_interval(mins => :m), 'TEMPERATURA')
        RETURNING id_alerta
    """), {"t": tipo, "s": severidad, "e": estado, "m": minutos_atras}).scalar_one()


def test_vence_las_activas_con_sla_cumplido(db_session):
    from src.telemetry.application.use_cases.alertas.vencer_alertas_sla_use_case import VencerAlertasSlaUseCase
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
    from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
        SqlAlchemyBitacoraAuditoriaIotRepository,
    )

    critica = _alerta(db_session, "CRITICO", 6)
    moderada_a_tiempo = _alerta(db_session, "MODERADO", 6)
    tecnica = _alerta(db_session, "CRITICO", 6, tipo="TECNICA")
    db_session.commit()

    n = VencerAlertasSlaUseCase(
        db_session, SqlAlchemyAlertaRepository(db_session), SqlAlchemyBitacoraAuditoriaIotRepository(db_session),
    ).execute(datetime.now(timezone.utc))

    estados = dict(db_session.execute(text(
        "SELECT id_alerta, estado_alerta::text FROM modulo3.alertas WHERE id_alerta IN (:a, :b, :c)"
    ), {"a": critica, "b": moderada_a_tiempo, "c": tecnica}).all())
    assert n >= 1
    assert estados == {critica: "VENCIDA", moderada_a_tiempo: "ACTIVA", tecnica: "ACTIVA"}
    motivo = db_session.execute(text(
        "SELECT motivo FROM modulo3.historico_estados_alertas WHERE id_alerta = :a AND estado_nuevo = 'VENCIDA'"
    ), {"a": critica}).scalar_one()
    assert motivo == "SLA vencido sin atención"
    tipos = {r[0] for r in db_session.execute(text(
        "SELECT tipo_evento FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = :a"
    ), {"a": str(critica)})}
    assert tipos == {"SLA_ALERTA_INCUMPLIDO", "ESCALAMIENTO_ALERTA_SLA"}
