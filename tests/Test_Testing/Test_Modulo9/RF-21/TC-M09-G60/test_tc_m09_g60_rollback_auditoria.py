"""
TC-M09-G60 (RF-21, G60-02) - Rollback por fallo de auditoria al registrar
un dispositivo IoT.

Ficha: "Requiere inyeccion de fallo en la auditoria (no disponible en caja
negra en TEST). Verificar rollback en BD." / "Verificar en BD que SENSOR y
CAMARA hacen rollback completo."

Por que mocks (igual patron que TC-M09-G73/RF-23): no hay forma de inyectar
un fallo de BD controlado contra el backend real en TEST sin acceso a
logs/BD. Mismo patron ya establecido (`tests/configuration/test_rf23_alcance_finca.py`,
spies/fakes + monkeypatch de RBAC).

Nota sobre "SENSOR y CAMARA": leido el codigo completo de
`RegistrarDispositivoIotUseCase.execute()` -- la categoria del dispositivo
NO es una rama de codigo separada ahi; el flujo (guardar + auditar + commit,
con rollback ante cualquier excepcion) es EXACTAMENTE el mismo sin importar
`id_tipo_dispositivo`. De hecho "CAMARA" no existe como concepto en
`src/configuration` en absoluto (confirmado por busqueda exhaustiva --
0 referencias fuera de los documentos de QA); TC-M09-G130 ya documento esto
como "CAMARA no implementado". Por eso este test parametriza sobre DOS
`id_tipo_dispositivo` distintos (3 = SENSOR_AMBIENTAL del catalogo real, y
un segundo tipo arbitrario a modo de control) en vez de una categoria real
-- el resultado (rollback identico para ambos) es la prueba de que la
distincion SENSOR/CAMARA que pide la ficha es, a nivel de este mecanismo,
irrelevante: no hay bifurcacion de codigo que trate una categoria distinto
de la otra.

Fuente del flujo leido en codigo:
`registrar_dispositivo_iot_use_case.py::RegistrarDispositivoIotUseCase.execute()`
-- `try: guardar() ; auditoria_repo.registrar(...) ; db.commit() / except:
db.rollback(); raise`. `dispositivo_repo.guardar()` usa `db.flush()`, NO
`db.commit()` (confirmado en `dispositivo_iot_repository.py`), asi que un
fallo en el paso de auditoria SI alcanza a deshacer el `guardar()` anterior.

Como correrlo:
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-21/TC-M09-G60/test_tc_m09_g60_rollback_auditoria.py -v \
        --html=resultados/resultado_TC-M09-G60_reintento1.html --self-contained-html
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.dispositivos_iot.registrar_dispositivo_iot_use_case import (
    RegistrarDispositivoIotUseCase,
)
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import RegistrarDispositivoIotDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

USUARIO_ADMIN = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

_TIPOS_A_PROBAR = [
    pytest.param(3, id="SENSOR_AMBIENTAL(id=3,-catalogo-real)"),
    pytest.param(1, id="GENERICO(id=1,-control-'CAMARA'-no-existe-como-tipo)"),
]


class _FalloAuditoria(Exception):
    pass


class DbSpy:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class AreaRepoFake:
    def obtener_por_id(self, _id):
        return type("AreaFake", (), {"es_activo": True})()


class TipoRepoFake:
    def obtener_por_id(self, _id):
        return type("TipoFake", (), {})()


class DispositivoRepoGuardaYFalla:
    """Permite guardar() (flush, sin commit); nunca llega a actualizar."""

    def __init__(self) -> None:
        self.guardados = 0

    def obtener_por_serial(self, _serial):
        return None  # sin duplicado

    def guardar(self, dispositivo):
        self.guardados += 1
        dispositivo.id_dispositivo_iot = 999  # simula el id asignado por el flush
        return dispositivo


class AuditoriaRepoFalla:
    def __init__(self) -> None:
        self.intentos = 0

    def registrar(self, **_kwargs):
        self.intentos += 1
        raise _FalloAuditoria("Fallo simulado de BD al registrar la auditoria de alta de dispositivo")


class TestTCM09G60RollbackAuditoria:
    """TC-M09-G60 / G60-02: fallo de auditoria -> rollback completo, sin importar id_tipo_dispositivo."""

    @pytest.mark.parametrize("id_tipo_dispositivo", _TIPOS_A_PROBAR)
    def test_use_case_directo_rollback_completo(self, id_tipo_dispositivo):
        db = DbSpy()
        dispositivo_repo = DispositivoRepoGuardaYFalla()
        auditoria_repo = AuditoriaRepoFalla()
        use_case = RegistrarDispositivoIotUseCase(
            db=db,
            dispositivo_repo=dispositivo_repo,
            infra_repo=AreaRepoFake(),
            tipo_repo=TipoRepoFake(),
            auditoria_repo=auditoria_repo,
        )
        dto = RegistrarDispositivoIotDTO(
            serial=f"QA-G60-ROLLBACK-{id_tipo_dispositivo}",
            descripcion="QA rollback auditoria",
            id_infraestructura=3,
            id_tipo_dispositivo=id_tipo_dispositivo,
        )

        with pytest.raises(_FalloAuditoria):
            use_case.execute(dto, USUARIO_ADMIN)

        assert dispositivo_repo.guardados == 1, "guardar() debio intentarse antes del fallo de auditoria"
        assert auditoria_repo.intentos == 1
        assert db.rollbacks == 1, "RF-21 exige rollback completo ante fallo de auditoria"
        assert db.commits == 0, "no debio quedar ningun commit parcial (dispositivo huerfano)"

    @pytest.mark.parametrize("id_tipo_dispositivo", _TIPOS_A_PROBAR)
    def test_endpoint_responde_500_sin_dejar_dispositivo_persistido(
        self, id_tipo_dispositivo, monkeypatch: pytest.MonkeyPatch
    ):
        from src.configuration.infrastructure.routers import dispositivo_iot_router as modulo
        from src.shared import rbac

        db = DbSpy()
        dispositivo_repo = DispositivoRepoGuardaYFalla()
        auditoria_repo = AuditoriaRepoFalla()

        monkeypatch.setattr(rbac, "tiene_permiso", lambda *_args: True)
        monkeypatch.setattr(modulo, "SqlAlchemyDispositivoIotRepository", lambda _db: dispositivo_repo)
        monkeypatch.setattr(modulo, "SqlAlchemyInfraestructuraRepository", lambda _db: AreaRepoFake())
        monkeypatch.setattr(modulo, "SqlAlchemyTipoDispositivoIotRepository", lambda _db: TipoRepoFake())
        monkeypatch.setattr(modulo, "SqlAlchemyAuditoriaDispositivoIotRepository", lambda _db: auditoria_repo)

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(modulo.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: USUARIO_ADMIN

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/configuracion/dispositivos-iot",
                json={
                    "serial": f"QA-G60-ENDPOINT-{id_tipo_dispositivo}",
                    "descripcion": "QA rollback auditoria endpoint",
                    "id_infraestructura": 3,
                    "id_tipo_dispositivo": id_tipo_dispositivo,
                },
            )

        assert response.status_code == 500, (
            f"RF-21/G60 exige 500 ante fallo de auditoria; respondio "
            f"{response.status_code}. Cuerpo: {response.text}"
        )
        assert response.json().get("error_code") == "ERROR_INTERNO"
        assert db.rollbacks == 1
        assert db.commits == 0
