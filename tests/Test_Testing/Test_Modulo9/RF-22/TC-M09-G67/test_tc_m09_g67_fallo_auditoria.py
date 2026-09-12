"""
TC-M09-G67 (TC-M09-129) - Rollback de la asociacion de sensores ante fallo
de auditoria.

RF relacionado: RF-22, CU-05 Gestionar Dispositivos IoT
Categoria: Integracion (RESILIENCIA / integridad transaccional)

Criterio de aceptacion (segun la ficha):
    "Verificar que la asociacion de sensores se revierta cuando falle el
    registro obligatorio de auditoria." Dato de prueba: asociacion valida
    con simulacion de fallo durante el registro de auditoria. Resultado
    esperado: la asociacion no debe permanecer activa despues del fallo
    (debe aplicarse rollback).

Por que local (mismo criterio que test_tc_m01_044_fallo_smtp.py y
test_tc_m09_g60_fallo_auditoria.py): no hace falta un fallo real de base
de datos para probar esto. El propio codigo de
AsociarSensorAreaUseCase.execute() (src/configuration/application/
use_cases/sensores/asociar_sensor_area_use_case.py), en el camino de
PRIMERA asociacion (sin asociacion activa previa), ya envuelve el guardado
de la nueva asociacion + el registro de auditoria en un unico bloque
try/except que hace rollback() y relanza la excepcion:

    try:
        asociacion_guardada = self.sensor_area_repo.guardar(nueva_asociacion)
        self.auditoria_repo.registrar(...)
        self.db.commit()
    except Exception:
        self.db.rollback()
        raise

NOTA importante (hallazgo de TC-M09-G64, RF-22): este try/except SOLO
protege la creacion de una asociacion nueva. El bloque de REASIGNACION
(cuando ya existe una asociacion activa en otra area y se confirma el
cambio: `asociacion_activa.terminar()` + `sensor_area_repo.actualizar()` +
`auditoria_repo.registrar(tipo_operacion="UPDATE")`, lineas 86-93) corre
FUERA de este try/except y por eso un fallo de auditoria ahi NO hace
rollback -- ese es justamente el defecto reproducido y documentado en
TC-M09-G64 (POST /configuracion/sensores/{id}/asociar con confirmar=true
responde 500 sin revertir). TC-M09-G67 prueba especificamente el camino
que SI esta bien protegido (primera asociacion, sin reasignacion previa),
tal como lo pide la ficha ("asociacion valida" simple, no una reasignacion).

Para esta prueba basta con simular el fallo del paso de auditoria
parcheando auditoria_repo.registrar en el punto donde lo usa el use case,
sin necesitar una base de datos real: como el repositorio solo hizo
flush() (no commit()) antes de fallar, el rollback() deshace exactamente
esa fila todavia no confirmada. Se verifica el mismo contrato en dos
niveles: (1) el use case en aislamiento, con dobles de prueba, y (2) el
endpoint completo via TestClient, confirmando que rollback() se invoca
sobre la sesion real que uso el request y que el commit() nunca llega a
ejecutarse.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m09_g67_fallo_auditoria.py -v \
        --html=Resultados/reporte-TC-M09-G67.html --self-contained-html
"""
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.sensores.asociar_sensor_area_use_case import (
    AsociarSensorAreaUseCase,
)
from src.configuration.domain.entities.sensor import Sensor
from src.configuration.domain.entities.sensor_area import SensorArea
from src.configuration.domain.value_objects.punto_instalacion import PuntoInstalacion
from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_SENSOR_PRUEBA = 777
ID_DISPOSITIVO_PRUEBA = 555
ID_INFRAESTRUCTURA_PRUEBA = 3
MENSAJE_FALLO_AUDITORIA = "Fallo simulado en el proceso de auditoria (TC-M09-G67)"


def _falla_auditoria_simulada() -> RuntimeError:
    """Excepcion generica: AsociarSensorAreaUseCase captura 'Exception' a
    secas en su bloque de rollback (camino de primera asociacion), no un
    tipo de error especifico de BD, asi que cualquier fallo del paso de
    auditoria debe activar el mismo camino de reversion."""
    return RuntimeError(MENSAJE_FALLO_AUDITORIA)


def _construir_use_case_con_dobles():
    """Dobles de prueba: sensor perteneciente al dispositivo indicado, area
    activa, y SIN asociacion activa previa (para llegar al camino de
    PRIMERA asociacion, el unico protegido por el try/except) -- llega
    exactamente al punto donde el use case guarda la asociacion (flush) y
    luego intenta auditar (paso que se hara fallar)."""
    sensor = Sensor.crear(
        nombre="Sensor de prueba TC-M09-G67",
        id_dispositivo_iot=ID_DISPOSITIVO_PRUEBA,
        categoria="TEMPERATURA",
    )
    sensor.id_sensores = ID_SENSOR_PRUEBA

    sensor_repo = MagicMock()
    sensor_repo.obtener_por_id.return_value = sensor

    area = MagicMock()
    area.es_activo = True

    infra_repo = MagicMock()
    infra_repo.obtener_por_id.return_value = area

    asociacion_guardada = SensorArea.crear(
        id_sensor=ID_SENSOR_PRUEBA,
        id_dispositivo_iot=ID_DISPOSITIVO_PRUEBA,
        id_infraestructura=ID_INFRAESTRUCTURA_PRUEBA,
        punto_instalacion=PuntoInstalacion("Punto de prueba - TC-M09-G67"),
        id_usuario=1,
    )
    asociacion_guardada.id_sensores_area_asociada = 999  # simula el ID asignado por el flush

    sensor_area_repo = MagicMock()
    sensor_area_repo.obtener_asociacion_activa.return_value = None  # sin asociacion previa
    sensor_area_repo.guardar.return_value = asociacion_guardada

    auditoria_repo = MagicMock()
    auditoria_repo.registrar.side_effect = _falla_auditoria_simulada()

    db = MagicMock()

    use_case = AsociarSensorAreaUseCase(
        db=db,
        sensor_repo=sensor_repo,
        sensor_area_repo=sensor_area_repo,
        infra_repo=infra_repo,
        auditoria_repo=auditoria_repo,
    )
    return use_case, sensor_area_repo, auditoria_repo, db


class TestTCM09G67FalloAuditoria:
    """Suite de pruebas para TC-M09-G67 / TC-M09-129."""

    def test_fallo_auditoria_debe_revertir_la_transaccion(self):
        """
        RF-22: si el registro obligatorio de auditoria falla luego de que la
        asociacion ya fue guardada (flush), el use case debe:
          1. Propagar la excepcion (no debe tragarsela ni responder como si
             la asociacion hubiera tenido exito).
          2. Ejecutar db.rollback() -- deshace el flush de la asociacion.
          3. NO ejecutar db.commit() bajo ninguna circunstancia.
        """
        use_case, sensor_area_repo, auditoria_repo, db = _construir_use_case_con_dobles()
        dto = AsociarSensorAreaDTO(
            id_dispositivo_iot=ID_DISPOSITIVO_PRUEBA,
            id_infraestructura=ID_INFRAESTRUCTURA_PRUEBA,
            punto_instalacion="Punto de prueba - TC-M09-G67",
        )
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

        excepcion_lanzada = None
        try:
            use_case.execute(ID_SENSOR_PRUEBA, dto, usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            "RF-22 exige que un fallo del proceso de auditoria se propague "
            "(no puede reportarse como asociacion exitosa); el use case no "
            "lanzo ninguna excepcion."
        )
        assert MENSAJE_FALLO_AUDITORIA in str(excepcion_lanzada)

        sensor_area_repo.guardar.assert_called_once()
        auditoria_repo.registrar.assert_called_once()

        db.rollback.assert_called_once()
        db.commit.assert_not_called()

    def test_endpoint_no_deja_la_asociacion_activa_cuando_falla_la_auditoria(self):
        """
        RF-22: POST /configuracion/sensores/{id}/asociar debe responder con
        un error (nunca 201) cuando el proceso de auditoria falla en el
        camino de primera asociacion, y la sesion de BD real que uso el
        request debe haber recibido rollback() -- la asociacion no debe
        quedar activa tras el fallo.
        """
        from src.configuration.infrastructure.repositories.auditoria_sensor_area_repository import (
            SqlAlchemyAuditoriaSensorAreaRepository,
        )
        from src.configuration.infrastructure.repositories.infraestructura_repository import (
            SqlAlchemyInfraestructuraRepository,
        )
        from src.configuration.infrastructure.repositories.sensor_area_repository import (
            SqlAlchemySensorAreaRepository,
        )
        from src.configuration.infrastructure.repositories.sensor_repository import (
            SqlAlchemySensorRepository,
        )
        from src.configuration.infrastructure.routers.sensor_router import router as sensor_router
        from src.identity_access.infrastructure.dependencies import get_current_user
        from src.shared.database import get_db
        from src.shared.error_handlers import register_error_handlers

        sensor = Sensor.crear(
            nombre="Sensor de prueba TC-M09-G67 (HTTP)",
            id_dispositivo_iot=ID_DISPOSITIVO_PRUEBA,
            categoria="TEMPERATURA",
        )
        sensor.id_sensores = ID_SENSOR_PRUEBA

        area = MagicMock()
        area.es_activo = True

        asociacion_guardada = SensorArea.crear(
            id_sensor=ID_SENSOR_PRUEBA,
            id_dispositivo_iot=ID_DISPOSITIVO_PRUEBA,
            id_infraestructura=ID_INFRAESTRUCTURA_PRUEBA,
            punto_instalacion=PuntoInstalacion("Punto de prueba HTTP - TC-M09-G67"),
            id_usuario=1,
        )
        asociacion_guardada.id_sensores_area_asociada = 998

        fake_db = MagicMock()

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(sensor_router)

        def _fake_db():
            yield fake_db

        def _fake_usuario_actual():
            return UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_current_user] = _fake_usuario_actual

        with (
            patch.object(SqlAlchemySensorRepository, "obtener_por_id", return_value=sensor),
            patch.object(SqlAlchemyInfraestructuraRepository, "obtener_por_id", return_value=area),
            patch.object(SqlAlchemySensorAreaRepository, "obtener_asociacion_activa", return_value=None),
            patch.object(SqlAlchemySensorAreaRepository, "guardar", return_value=asociacion_guardada),
            patch.object(
                SqlAlchemyAuditoriaSensorAreaRepository,
                "registrar",
                side_effect=_falla_auditoria_simulada(),
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                f"/configuracion/sensores/{ID_SENSOR_PRUEBA}/asociar",
                json={
                    "id_dispositivo_iot": ID_DISPOSITIVO_PRUEBA,
                    "id_infraestructura": ID_INFRAESTRUCTURA_PRUEBA,
                    "punto_instalacion": "Punto de prueba HTTP - TC-M09-G67",
                },
            )

        assert response.status_code != 201, (
            "RF-22 exige que un fallo del proceso de auditoria NO resulte "
            f"en una asociacion exitosa; el endpoint respondio 201. Cuerpo: {response.text}"
        )
        assert response.status_code >= 500, (
            "Se esperaba que el fallo interno de auditoria escalara como un "
            f"error de servidor; el endpoint respondio {response.status_code}. "
            f"Cuerpo: {response.text}"
        )

        fake_db.rollback.assert_called_once()
        fake_db.commit.assert_not_called()

        app.dependency_overrides.clear()
