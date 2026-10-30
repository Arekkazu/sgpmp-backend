# | Fecha      | Nombre   | Que se hizo                                                          |
# |------------|----------|----------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-226-G117 RF-59: alertas del sensor del periodo contra Postgres |
"""RF-59 Fase 4 (#861): con incluir_alertas, las alertas del sensor consultado en el periodo
aparecen aunque su lectura no esté entre las devueltas o no tengan lectura asociada."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from src.telemetry.domain.entities.monitoreo import FiltrosHistorial
from src.telemetry.infrastructure.repositories.historial_telemetria_repository import (
    SqlAlchemyHistorialTelemetriaRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def alertas(db_session):
    db = db_session
    db.execute(text("SET LOCAL session_replication_role = replica"))
    sensor, otro, infra, infra_ajena = 900001, 900002, 900011, 900012
    ids = {}
    for clave, id_sensor, id_infra, fecha, id_telemetria in (
        ("lectura_fuera", sensor, infra, "2026-05-12 10:00Z", 999999999),  # su lectura no está en el resultado
        ("sin_lectura", sensor, infra, "2026-05-12 11:00Z", None),
        ("otra_finca", sensor, infra_ajena, "2026-05-12 12:00Z", None),
        ("fuera_periodo", sensor, infra, "2026-06-12 11:00Z", None),
        ("otro_sensor", otro, infra, "2026-05-12 11:00Z", None),
    ):
        ids[clave] = db.execute(text(
            "INSERT INTO modulo3.alertas (tipo_alerta, severidad, origen_evento, fecha_evento, fecha_generacion, "
            "tipo_variable, id_sensor, id_telemetria, id_infraestructura) VALUES ('ESTRES_TERMICO', 'LEVE', 'EDGE', "
            ":f, :f, 'TEMPERATURA_AMBIENTAL', :s, :t, :i) RETURNING id_alerta"),
            {"f": fecha, "s": id_sensor, "t": id_telemetria, "i": id_infra}).scalar_one()
    finca = db.execute(text(
        "INSERT INTO modulo9.infraestructuras (id_infraestructura, id_finca, superficie, es_activo, nombre, tipo) "
        "OVERRIDING SYSTEM VALUE VALUES (:i, 900001, 1, true, 'A', 'AREA') RETURNING id_finca"), {"i": infra}).scalar_one()
    db.execute(text("SET LOCAL session_replication_role = origin"))
    return dict(ids, sensor=sensor, finca=finca)


def _ids(db, **filtros):
    repo = SqlAlchemyHistorialTelemetriaRepository(db)
    return {a.id_alerta for a in repo.alertas_correlacionadas(FiltrosHistorial(
        fecha_inicio=date(2026, 5, 11), fecha_fin=date(2026, 5, 13), incluir_alertas=True, **filtros))}


def test_alertas_del_sensor_en_el_periodo(db_session, alertas):
    a = alertas
    assert _ids(db_session, sensor_id=a["sensor"]) == {a["lectura_fuera"], a["sin_lectura"], a["otra_finca"]}


def test_respeta_el_alcance_de_fincas(db_session, alertas):
    a = alertas
    assert _ids(db_session, sensor_id=a["sensor"], ids_fincas_permitidas=[a["finca"]]) == {
        a["lectura_fuera"], a["sin_lectura"]}
