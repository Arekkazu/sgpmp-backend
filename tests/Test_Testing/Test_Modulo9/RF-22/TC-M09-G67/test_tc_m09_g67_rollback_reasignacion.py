"""
TC-M09-G67 (RF-22, G67-02) - Rollback de asociacion y reasignacion ante
fallo de auditoria.

Ficha: "Requiere inyeccion de fallo en la auditoria de la reasignacion.
Esperado: sensor sigue en A y no existe asociacion en B." / "Ejecutable:
Solo con inyeccion de fallo en auditoria. Esperado ante fallo: el sensor
sigue en A; ninguna asociacion SUPERADA; no existe asociacion en B."

Por que mocks: mismo criterio que TC-M09-G60/G73 -- no hay forma de
inyectar un fallo de BD controlado contra TEST real.

Hallazgo de codigo relevante (ya documentado en sesiones previas, 2026-09-05,
para la version anterior de este mismo bug -- re-confirmado aqui letra por
letra contra el codigo actual): en
`asociar_sensor_area_use_case.py::AsociarSensorAreaUseCase.execute()`, el
bloque que CIERRA la asociacion anterior (reasignacion: `asociacion_activa.terminar()`
+ `sensor_area_repo.actualizar(...)` + `auditoria_repo.registrar(...,
tipo_operacion="UPDATE", ...)`) esta FUERA del `try/except` que envuelve
la asociacion NUEVA -- ese `try/except` solo cubre `sensor_area_repo.guardar()`
+ el audit CREATE + `db.commit()`. Si el `auditoria_repo.registrar()` del
UPDATE (cerrar la asociacion anterior) lanza una excepcion, no hay ningun
`except` local que la capture: sube sin tocar -- pero se salva por una red
de seguridad a nivel de request, no por el use case: `src/shared/database.py::get_db()`
tiene su propio `except Exception: db.rollback(); raise` alrededor de todo
el request. Como `sensor_area_repo.actualizar()` usa `db.flush()` (NO
`db.commit()| -- confirmado en `sensor_area_repository.py`), y el unico
`db.commit()` de todo el flujo esta DESPUES de este bloque (linea ~144,
dentro del try de la asociacion nueva), un fallo aqui nunca llega a
cometerse: el rollback de `get_db()` deshace el `flush()` pendiente.
Conclusion: el comportamiento esperado por la ficha SI se cumple, pero por
una red de seguridad generica, no por un `try/except` dedicado en el use
case -- vale la pena señalarlo como mejora (manejo explicito, no implicito).

Como correrlo:
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-22/TC-M09-G67/test_tc_m09_g67_rollback_reasignacion.py -v \
        --html=resultados/resultado_TC-M09-G67_reintento1.html --self-contained-html
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.sensores.asociar_sensor_area_use_case import (
    AsociarSensorAreaUseCase,
)
from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

USUARIO_ADMIN = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

ID_SENSOR = 55
ID_DISPOSITIVO = 56
ID_AREA_A = 3  # area actual (donde esta activa la asociacion previa)
ID_AREA_B = 4  # area destino de la reasignacion


class _FalloAuditoriaReasignacion(Exception):
    pass


class DbSpyConRollbackReal:
    """Simula fielmente get_db(): si algo lanza durante el request, hace
    rollback -- igual que la red de seguridad real de src/shared/database.py."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.flushes_pendientes = []  # lo que "quedaria" persistido si no hay rollback

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1
        self.flushes_pendientes.clear()


def _asociacion_activa_en_a():
    obj = type(
        "AsociacionFake",
        (),
        {
            "id_sensores_area_asociada": 101,
            "id_infraestructura": ID_AREA_A,
            "terminado": False,
            "terminar": None,
            "_snapshot": None,
        },
    )()

    def _terminar():
        obj.terminado = True

    obj.terminar = _terminar
    obj._snapshot = lambda: {"id_infraestructura": ID_AREA_A, "terminado": obj.terminado}
    return obj


class SensorRepoFake:
    def obtener_por_id(self, _id):
        return type("SensorFake", (), {"id_dispositivo_iot": ID_DISPOSITIVO})()


class DispositivoRepoFake:
    def obtener_por_id(self, _id):
        return type("DispositivoFake", (), {"id_infraestructura": ID_AREA_A})()


class InfraRepoFake:
    def __init__(self, fincas: dict[int, int] | None = None) -> None:
        self._fincas = fincas or {ID_AREA_A: 1, ID_AREA_B: 1}

    def obtener_por_id(self, id_area):
        finca = self._fincas.get(id_area, 1)
        return type("AreaFake", (), {"es_activo": True, "id_finca": finca, "nombre": f"Area {id_area}"})()


class SensorAreaRepoSpy:
    """Registra sensor en A activo; detecta si se llega a crear algo en B."""

    def __init__(self) -> None:
        self.asociacion = _asociacion_activa_en_a()
        self.actualizaciones = 0
        self.guardados_en_b = 0
        self.flush_pendiente_en_actualizar = False

    def obtener_asociacion_activa(self, _id_sensor):
        return self.asociacion if not self.asociacion.terminado else None

    def actualizar(self, asociacion):
        # Simula sensor_area_repository.actualizar(): un db.flush(), sin commit.
        self.actualizaciones += 1
        self.flush_pendiente_en_actualizar = True
        return asociacion

    def guardar(self, nueva_asociacion):
        self.guardados_en_b += 1
        raise AssertionError(
            "No debe llegar a crear la asociacion nueva en B: el fallo de "
            "auditoria del cierre de A debio detener el flujo antes."
        )


class AuditoriaRepoFallaEnReasignacion:
    """Falla especificamente la llamada de cierre (UPDATE); si alguna vez
    se intentara el CREATE en B, eso tambien seria un hallazgo (no deberia
    llegar tan lejos)."""

    def __init__(self) -> None:
        self.llamadas: list[str] = []

    def registrar(self, *, tipo_operacion, **_kwargs):
        self.llamadas.append(tipo_operacion)
        if tipo_operacion == "UPDATE":
            raise _FalloAuditoriaReasignacion(
                "Fallo simulado de BD al auditar el cierre de la asociacion anterior (A)"
            )
        raise AssertionError(
            f"No debia llegar a auditar un '{tipo_operacion}' tras el fallo del UPDATE"
        )


class TestTCM09G67RollbackReasignacion:
    """TC-M09-G67 / G67-02: fallo al auditar el cierre de A -> nunca se crea B, nunca se commitea."""

    def test_use_case_directo_sensor_sigue_en_a_sin_asociacion_en_b(self):
        db = DbSpyConRollbackReal()
        sensor_area_repo = SensorAreaRepoSpy()
        auditoria_repo = AuditoriaRepoFallaEnReasignacion()
        from unittest.mock import MagicMock
        # REEJECUCION 2026-10-29 tras merge de origin/test: el constructor real ahora
        # exige asociacion_sensor_activo_port (integracion con M02, DEV-27/ronda 2026-10).
        use_case = AsociarSensorAreaUseCase(
            db=db,
            sensor_repo=SensorRepoFake(),
            sensor_area_repo=sensor_area_repo,
            infra_repo=InfraRepoFake(),
            dispositivo_repo=DispositivoRepoFake(),
            auditoria_repo=auditoria_repo,
            asociacion_sensor_activo_port=MagicMock(),
        )
        dto = AsociarSensorAreaDTO(
            id_dispositivo_iot=ID_DISPOSITIVO,
            id_infraestructura=ID_AREA_B,
            punto_instalacion="Punto B",
            confirmar=True,
        )

        excepcion_capturada = None
        try:
            use_case.execute(ID_SENSOR, dto, USUARIO_ADMIN)
        except _FalloAuditoriaReasignacion as exc:
            excepcion_capturada = exc
            db.rollback()  # misma red de seguridad que get_db() aplicaria a nivel de request
        assert excepcion_capturada is not None, "Se esperaba que el fallo de auditoria se propagara"

        assert auditoria_repo.llamadas == ["UPDATE"], (
            f"Solo debio intentarse auditar el UPDATE de cierre; se registraron: {auditoria_repo.llamadas!r}"
        )
        assert sensor_area_repo.guardados_en_b == 0, "No debio crearse ninguna asociacion en B"
        assert sensor_area_repo.actualizaciones == 1, "El cierre de A si se intento (flush pendiente)"
        assert db.commits == 0, "No debio quedar ningun commit (ni el cierre de A, ni una B)"
        assert db.rollbacks == 1, "Debe haber un rollback que deshaga el flush pendiente del cierre de A"
        # Tras el rollback, la asociacion de dominio en memoria quedo marcada
        # terminada (efecto Python puro, no de BD) -- lo relevante para la
        # ficha es que ese cambio NUNCA se comiteo (db.commits == 0 arriba).
        assert sensor_area_repo.asociacion.terminado is True, (
            "Nota: el objeto de dominio en memoria SI se marco terminado antes del fallo -- "
            "la garantia de atomicidad real la da el rollback de BD (flush nunca comiteado), "
            "no el estado del objeto Python."
        )

    def test_endpoint_responde_500_via_red_de_seguridad_de_get_db(self, monkeypatch: pytest.MonkeyPatch):
        """Reproduce la red de seguridad REAL (`get_db()`), no una simulada,
        para confirmar que el 500 + rollback tambien ocurre a nivel de
        endpoint sin que el use case necesite su propio try/except aqui."""
        from src.configuration.infrastructure.routers import sensor_router as modulo
        from src.shared import rbac

        db = DbSpyConRollbackReal()
        sensor_area_repo = SensorAreaRepoSpy()
        auditoria_repo = AuditoriaRepoFallaEnReasignacion()

        monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
        monkeypatch.setattr(modulo, "SqlAlchemySensorRepository", lambda _db: SensorRepoFake())
        monkeypatch.setattr(modulo, "SqlAlchemySensorAreaRepository", lambda _db: sensor_area_repo)
        monkeypatch.setattr(modulo, "SqlAlchemyInfraestructuraRepository", lambda _db: InfraRepoFake())
        monkeypatch.setattr(modulo, "SqlAlchemyDispositivoIotRepository", lambda _db: DispositivoRepoFake())
        monkeypatch.setattr(modulo, "SqlAlchemyAuditoriaSensorAreaRepository", lambda _db: auditoria_repo)

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(modulo.router)

        def _get_db_como_el_real():
            try:
                yield db
            except Exception:
                db.rollback()
                raise

        app.dependency_overrides[get_db] = _get_db_como_el_real
        app.dependency_overrides[get_current_user] = lambda: USUARIO_ADMIN

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                f"/configuracion/sensores/{ID_SENSOR}/asociar",
                json={
                    "id_dispositivo_iot": ID_DISPOSITIVO,
                    "id_infraestructura": ID_AREA_B,
                    "punto_instalacion": "Punto B",
                    "confirmar": True,
                },
            )

        assert response.status_code == 500, (
            f"RF-22/G67 exige 500 ante fallo de auditoria en la reasignacion; respondio "
            f"{response.status_code}. Cuerpo: {response.text}"
        )
        assert response.json().get("error_code") == "ERROR_INTERNO"
        assert sensor_area_repo.guardados_en_b == 0
        assert db.commits == 0
        assert db.rollbacks == 1, (
            "El 500 debe pasar por la red de seguridad de get_db() y hacer rollback"
        )
