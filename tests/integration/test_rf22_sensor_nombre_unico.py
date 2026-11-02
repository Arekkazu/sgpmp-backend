# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-01 | Arekkazu | RF-22/RF-53: nombre de sensor único y FOR UPDATE de RF53_AUDITORIA |
"""RF-22: el nombre del sensor identifica la lectura dentro de su dispositivo.

El broker busca el sensor por (dispositivo, nombre); un nombre repetido haría ambigua la
búsqueda. Además, RF53_AUDITORIA bloquea filas de `bitacora_ingest` con FOR UPDATE como
`sgpmp_app` (c9a8cc1ef814). Las pruebas corren como `sgpmp_app`: como superusuario
pasarían en verde sin probar nada.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.sensor import Sensor
from src.configuration.infrastructure.repositories.sensor_repository import SqlAlchemySensorRepository
from src.shared.errors import ConflictError

pytestmark = pytest.mark.integration


def _como_sgpmp_app(db_session: Session, id_usuario: int) -> None:
    if db_session.execute(text("SELECT to_regrole('sgpmp_app')")).scalar() is None:
        pytest.skip("La base de pruebas no tiene el rol sgpmp_app.")
    if not db_session.execute(text("SELECT pg_has_role(current_user, 'sgpmp_app', 'MEMBER')")).scalar():
        pytest.skip("El usuario de TEST_DATABASE_URL no puede hacer SET ROLE sgpmp_app.")
    db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
    db_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true), set_config('app.current_role', 'Administrador', true)"),
        {"u": str(id_usuario)},
    )


def _dispositivos(db_session: Session, id_usuario: int) -> tuple[int, int]:
    sufijo = "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:10])
    id_finca = db_session.execute(
        text(
            "INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo) "
            "VALUES (:n, '{}'::jsonb, 10, now(), now(), true) RETURNING id_finca"
        ),
        {"n": f"Finca Sensor {sufijo}"},
    ).scalar_one()
    db_session.execute(
        text("INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) VALUES (:u, :f)"),
        {"u": id_usuario, "f": id_finca},
    )
    id_area = db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo) "
            "VALUES (:n, :f, 100, true, 'Estanque') RETURNING id_infraestructura"
        ),
        {"n": f"Area Sensor {sufijo}", "f": id_finca},
    ).scalar_one()
    ids = [
        db_session.execute(
            text(
                "INSERT INTO modulo9.dispositivos_iot (serial, descripcion, id_infraestructura, "
                "id_tipo_dispositivo, es_activo, fecha_creacion) "
                "VALUES (:s, 'Dispositivo RF-22 nombre único', :a, 1, true, now()) RETURNING id_dispositivo_iot"
            ),
            {"s": f"RF22-{id_finca}-{i}", "a": id_area},
        ).scalar_one()
        for i in (1, 2)
    ]
    return ids[0], ids[1]


def test_nombre_de_sensor_unico_por_dispositivo(db_session: Session, crear_usuario_db) -> None:
    id_usuario = crear_usuario_db(id_rol=1)["id_usuario"]
    disp_a, disp_b = _dispositivos(db_session, id_usuario)
    _como_sgpmp_app(db_session, id_usuario)
    repo = SqlAlchemySensorRepository(db_session)

    repo.guardar(Sensor.crear(nombre="SEN-TEMP", id_dispositivo_iot=disp_a, categoria="TEMPERATURA"))
    # El mismo nombre en otro dispositivo es válido: la unicidad es por dispositivo.
    otro = repo.guardar(Sensor.crear(nombre="SEN-TEMP", id_dispositivo_iot=disp_b, categoria="TEMPERATURA"))
    assert otro.id_sensores is not None

    with pytest.raises(ConflictError) as exc:
        repo.guardar(Sensor.crear(nombre="SEN-TEMP", id_dispositivo_iot=disp_a, categoria="HUMEDAD"))
    assert exc.value.code == "RECURSO_DUPLICADO"
    assert exc.value.field == "nombre"


def test_sgpmp_app_puede_reclamar_bitacora_ingest(db_session: Session, crear_usuario_db) -> None:
    """RF53_AUDITORIA reclama con FOR UPDATE: sin el GRANT, 42501 en cada lectura."""
    id_usuario = crear_usuario_db(id_rol=1)["id_usuario"]
    _como_sgpmp_app(db_session, id_usuario)
    db_session.execute(
        text("SELECT id_dispositivo_iot FROM modulo3.bitacora_ingest WHERE id_bitacora_ingest = -1 FOR UPDATE SKIP LOCKED")
    ).all()
