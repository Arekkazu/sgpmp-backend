"""Issue #290 (SEG-M09-01) / RF-22: reasignar un sensor de área debe cerrar
(SUPERADA) sus asociaciones sensor→activo AMBIENTAL/POBLACIONAL vigentes en
M02 — dependen de que el sensor comparta área con el activo (RF-49 V6),
premisa que la reasignación rompe. DIRECTA no depende del área y no se toca.

Prueba de integración contra Postgres real: crea la cadena completa
(finca → 2 infraestructuras → dispositivo → sensor → sensor-área → activo →
asociación sensor-activo) y ejecuta `AsociarSensorAreaUseCase` con los
repositorios/adaptadores reales.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.models.activo_biologico_model import ActivoBiologicoModel
from src.biological_assets.infrastructure.models.asociacion_sensor_activo_model import AsociacionSensorActivoModel
from src.biological_assets.infrastructure.models.auditoria_asociacion_sensor_model import (
    AuditoriaAsociacionSensorModel,
)
from src.configuration.application.use_cases.sensores.asociar_sensor_area_use_case import AsociarSensorAreaUseCase
from src.configuration.infrastructure.adapters.asociacion_sensor_activo_m02_adapter import (
    AsociacionSensorActivoM02Adapter,
)
from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO
from src.configuration.infrastructure.models.dispositivo_iot_model import DispositivoIotModel
from src.configuration.infrastructure.models.sensor_area_model import SensorAreaModel
from src.configuration.infrastructure.models.sensor_model import SensorModel
from src.configuration.infrastructure.models.tipo_dispositivo_iot_model import (  # noqa: F401 — registra la tabla para la FK de DispositivoIotModel
    TipoDispositivoIotModel,
)
from src.configuration.infrastructure.repositories.auditoria_sensor_area_repository import (
    SqlAlchemyAuditoriaSensorAreaRepository,
)
from src.configuration.infrastructure.repositories.dispositivo_iot_repository import SqlAlchemyDispositivoIotRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import SqlAlchemyInfraestructuraRepository
from src.configuration.infrastructure.repositories.sensor_area_repository import SqlAlchemySensorAreaRepository
from src.configuration.infrastructure.repositories.sensor_repository import SqlAlchemySensorRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual

pytestmark = pytest.mark.integration

_ID_ESPECIE = 1  # Tilapia Roja — catálogo semilla
_ID_ESTADO_ACTIVO = 1  # ACTIVO — catálogo semilla


@pytest.fixture
def escenario(db_session: Session, crear_usuario_db):
    dueno = crear_usuario_db()
    id_usuario = dueno["id_usuario"]

    id_finca = db_session.execute(
        text(
            "INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, id_usuario, es_activo) "
            "VALUES ('Finca Reasignacion Sensor', '{}'::jsonb, 10, now(), now(), :id_usuario, true) "
            "RETURNING id_finca"
        ),
        {"id_usuario": id_usuario},
    ).scalar_one()

    id_area_1 = db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo) "
            "VALUES ('Area Origen Reasignacion', :id_finca, 100, true, 'Estanque') RETURNING id_infraestructura"
        ),
        {"id_finca": id_finca},
    ).scalar_one()
    id_area_2 = db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo) "
            "VALUES ('Area Destino Reasignacion', :id_finca, 100, true, 'Estanque') RETURNING id_infraestructura"
        ),
        {"id_finca": id_finca},
    ).scalar_one()

    dispositivo = DispositivoIotModel(
        serial=f"SEG-M09-01-{id_finca}",
        descripcion="Dispositivo de prueba SEG-M09-01",
        id_infraestructura=id_area_1,
        id_tipo_dispositivo=1,
        es_activo=True,
        fecha_creacion=datetime.now(timezone.utc),
    )
    db_session.add(dispositivo)
    db_session.flush()

    sensor = SensorModel(
        id_dispositivo_iot=dispositivo.id_dispositivo_iot,
        nombre="Sensor Reasignacion",
        categoria="TEMPERATURA",
        es_activo=True,
    )
    db_session.add(sensor)
    db_session.flush()

    db_session.add(SensorAreaModel(
        id_sensor=sensor.id_sensores,
        id_dispositivo_iot=dispositivo.id_dispositivo_iot,
        id_infraestructura=id_area_1,
        punto_instalacion="Punto original",
        tiene_estado=True,
        fecha_asociacion=datetime.now(timezone.utc),
        id_usuario=id_usuario,
    ))

    db_session.execute(text("SET app.usuario_id = :uid"), {"uid": str(id_usuario)})
    activo = ActivoBiologicoModel(
        id_especie=_ID_ESPECIE,
        identificador=f"SEG-M09-01-{id_finca}",
        id_infraestructura=id_area_1,
        tipo="INDIVIDUAL",
        fecha_inicio_ciclo=datetime.now(timezone.utc).date(),
        id_estado=_ID_ESTADO_ACTIVO,
        origen_financiero="nacimiento",
        id_usuario=id_usuario,
        fecha_creacion=datetime.now(timezone.utc),
    )
    db_session.add(activo)
    db_session.flush()

    db_session.commit()

    return {
        "id_usuario": id_usuario,
        "id_area_1": id_area_1,
        "id_area_2": id_area_2,
        "id_dispositivo": dispositivo.id_dispositivo_iot,
        "id_sensor": sensor.id_sensores,
        "id_activo": activo.id_activo_biologico,
    }


def _crear_asociacion_sensor_activo(db_session: Session, escenario: dict, tipo: str) -> int:
    asociacion = AsociacionSensorActivoModel(
        id_activo_biologico=escenario["id_activo"],
        tipo_activo="INDIVIDUAL",
        tipo=tipo,
        dispositivo_iot_id=escenario["id_dispositivo"],
        id_sensor=escenario["id_sensor"],
        id_infraestructura=escenario["id_area_1"],
        id_usuario=escenario["id_usuario"],
        fecha_inicio=datetime.now(timezone.utc),
        estado_asociacion="ACTIVA",
    )
    db_session.add(asociacion)
    db_session.commit()
    return asociacion.id_asociacion_activo_sensor


def _reasignar(db_session: Session, escenario: dict) -> None:
    use_case = AsociarSensorAreaUseCase(
        db=db_session,
        sensor_repo=SqlAlchemySensorRepository(db_session),
        sensor_area_repo=SqlAlchemySensorAreaRepository(db_session),
        infra_repo=SqlAlchemyInfraestructuraRepository(db_session),
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db_session),
        auditoria_repo=SqlAlchemyAuditoriaSensorAreaRepository(db_session),
        asociacion_sensor_activo_port=AsociacionSensorActivoM02Adapter(db_session),
    )
    usuario = UsuarioActual(id_usuario=escenario["id_usuario"], id_token=1, id_rol=1)
    dto = AsociarSensorAreaDTO(
        id_dispositivo_iot=escenario["id_dispositivo"],
        id_infraestructura=escenario["id_area_2"],
        punto_instalacion="Punto nuevo",
        confirmar=True,
    )
    use_case.execute(escenario["id_sensor"], dto, usuario)


def test_reasignar_area_supera_asociacion_ambiental(db_session: Session, escenario: dict) -> None:
    id_asociacion = _crear_asociacion_sensor_activo(db_session, escenario, "ambiental")

    _reasignar(db_session, escenario)

    fila = db_session.get(AsociacionSensorActivoModel, id_asociacion)
    assert fila.estado_asociacion == "SUPERADA"
    assert fila.fecha_fin is not None

    auditoria = (
        db_session.query(AuditoriaAsociacionSensorModel)
        .filter_by(id_asociacion_activo_sensor=id_asociacion)
        .all()
    )
    assert any(a.tipo_operacion == "UPDATE" for a in auditoria)


def test_reasignar_area_supera_asociacion_poblacional(db_session: Session, escenario: dict) -> None:
    id_asociacion = _crear_asociacion_sensor_activo(db_session, escenario, "poblacional")

    _reasignar(db_session, escenario)

    fila = db_session.get(AsociacionSensorActivoModel, id_asociacion)
    assert fila.estado_asociacion == "SUPERADA"
    assert fila.fecha_fin is not None


def test_reasignar_area_no_toca_asociacion_directa(db_session: Session, escenario: dict) -> None:
    id_asociacion = _crear_asociacion_sensor_activo(db_session, escenario, "directa")

    _reasignar(db_session, escenario)

    fila = db_session.get(AsociacionSensorActivoModel, id_asociacion)
    assert fila.estado_asociacion == "ACTIVA"
    assert fila.fecha_fin is None
