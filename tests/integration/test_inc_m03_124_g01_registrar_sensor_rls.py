# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-25 | Arekkazu         | INC-M03-124-G01 RF-22: sensor nuevo bajo RLS  |
"""INC-M03-124-G01 (RF-22): registrar un sensor respondía 500.

`pol_sensores_select` usa `fn_sensores_del_usuario`, que relee `sensores` con
el snapshot de la sentencia: la fila recién insertada no pasa la política y
un INSERT ... RETURNING falla. La prueba corre como `sgpmp_app` (el rol de la
API); como superusuario pasaría en verde sin probar nada.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.sensor import Sensor
from src.configuration.infrastructure.repositories.sensor_repository import SqlAlchemySensorRepository

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("id_rol, rol", [(1, "Administrador"), (2, "Productor")])
def test_registrar_sensor_como_sgpmp_app(db_session: Session, crear_usuario_db, id_rol, rol) -> None:
    if db_session.execute(text("SELECT to_regrole('sgpmp_app')")).scalar() is None:
        pytest.skip("La base de pruebas no tiene el rol sgpmp_app.")
    if not db_session.execute(text("SELECT pg_has_role(current_user, 'sgpmp_app', 'MEMBER')")).scalar():
        pytest.skip("El usuario de TEST_DATABASE_URL no puede hacer SET ROLE sgpmp_app.")

    id_usuario = crear_usuario_db(id_rol=id_rol)["id_usuario"]
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
    id_dispositivo = db_session.execute(
        text(
            "INSERT INTO modulo9.dispositivos_iot (serial, descripcion, id_infraestructura, "
            "id_tipo_dispositivo, es_activo, fecha_creacion) "
            "VALUES (:s, 'Dispositivo INC-M03-124-G01', :a, 1, true, now()) RETURNING id_dispositivo_iot"
        ),
        {"s": f"INC-M03-124-{id_finca}", "a": id_area},
    ).scalar_one()

    db_session.execute(text("SET LOCAL ROLE sgpmp_app"))
    db_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true), set_config('app.current_role', :r, true)"),
        {"u": str(id_usuario), "r": rol},
    )
    assert db_session.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar() is False

    sensor = SqlAlchemySensorRepository(db_session).guardar(
        Sensor.crear(nombre="Sensor reproduccion", id_dispositivo_iot=id_dispositivo, categoria="TEMPERATURA")
    )

    assert sensor.id_sensores is not None
    assert sensor.categoria == "TEMPERATURA"
