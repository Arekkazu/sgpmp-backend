# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-135-G01 RF-49: especies compatibles de un sensor desde M09 |
"""RF-49 (#849) contra Postgres: lo que configura M09 es lo que M02 valida al asociar."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from src.biological_assets.infrastructure.adapters.sensor_m09_adapter import SensorM09Adapter
from src.configuration.infrastructure.repositories.compatibilidad_sensor_especie_repository import (
    SqlAlchemyCompatibilidadSensorEspecieRepository,
)

pytestmark = pytest.mark.integration


def test_m02_ve_la_compatibilidad_configurada(db_session):
    db = db_session
    db.execute(text("SET LOCAL session_replication_role = replica"))
    sensor = db.execute(text("SELECT COALESCE(max(id_sensores), 0) + 1 FROM modulo9.sensores")).scalar_one()
    db.execute(text("INSERT INTO modulo9.sensores (id_sensores, nombre, id_dispositivo_iot, es_activo) "
                    "VALUES (:s, 'S', 1, true)"), {"s": sensor})
    especies = db.execute(text("SELECT id_especie FROM modulo9.especies ORDER BY id_especie LIMIT 2")).scalars().all()
    db.execute(text("SET LOCAL session_replication_role = origin"))
    if len(especies) < 2:
        pytest.skip("La base de pruebas necesita al menos dos especies.")
    compatible, otra = especies
    adaptador, repo = SensorM09Adapter(db), SqlAlchemyCompatibilidadSensorEspecieRepository(db)

    assert not adaptador.obtener_compatibilidad_especie(sensor, compatible).configurada
    repo.reemplazar(sensor, [compatible])
    assert repo.listar_especies(sensor) == [compatible]
    assert adaptador.obtener_compatibilidad_especie(sensor, compatible).es_compatible
    assert not adaptador.obtener_compatibilidad_especie(sensor, otra).es_compatible
    repo.reemplazar(sensor, [otra])
    assert repo.listar_especies(sensor) == [otra]
