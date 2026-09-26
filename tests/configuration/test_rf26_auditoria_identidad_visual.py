"""RF-26 / TC-M09-169-G89 — consulta de auditoría de identidad visual."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.application.use_cases.personalizacion.consultar_auditoria_identidad_visual_use_case import (
    ConsultarAuditoriaIdentidadVisualUseCase,
)
from src.configuration.domain.entities.auditoria_identidad_visual import AuditoriaIdentidadVisual
from src.configuration.infrastructure.models.auditoria_identidad_visual_model import AuditoriaIdentidadVisualModel
from src.configuration.infrastructure.repositories.auditoria_identidad_visual_repository import (
    SqlAlchemyAuditoriaIdentidadVisualRepository,
)
from src.configuration.infrastructure.routers.identidad_visual_router import router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import NotFoundError


AHORA = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def _registro() -> AuditoriaIdentidadVisual:
    return AuditoriaIdentidadVisual(
        id_auditoria_visual=45,
        id_finca=6,
        id_usuario=50,
        usuario="Administrador QA",
        fecha_creacion=AHORA,
        tipo_operacion="UPDATE",
        valor_anterior={"id_finca": 6, "primary_color": "#C41E3A", "version": 9},
        valor_nuevo={"id_finca": 6, "primary_color": "#3A7BD5", "version": 10},
    )


class IdentidadRepoFake:
    def __init__(self, existe: bool = True) -> None:
        self.existe = existe

    def obtener_por_finca(self, id_finca: int):
        assert id_finca == 6
        return object() if self.existe else None


class AuditoriaRepoFake:
    def __init__(self, filas: list[AuditoriaIdentidadVisual]) -> None:
        self.filas = filas
        self.consultas: list[int] = []

    def listar_por_finca(self, id_finca: int) -> list[AuditoriaIdentidadVisual]:
        self.consultas.append(id_finca)
        return self.filas


def test_caso_de_uso_devuelve_historial_de_la_finca() -> None:
    auditoria = AuditoriaRepoFake([_registro()])
    caso = ConsultarAuditoriaIdentidadVisualUseCase(
        auditoria_repo=auditoria,
        identidad_repo=IdentidadRepoFake(),
    )

    assert caso.execute(6) == [_registro()]
    assert auditoria.consultas == [6]


def test_caso_de_uso_rechaza_finca_sin_identidad_visual() -> None:
    auditoria = AuditoriaRepoFake([])
    caso = ConsultarAuditoriaIdentidadVisualUseCase(
        auditoria_repo=auditoria,
        identidad_repo=IdentidadRepoFake(existe=False),
    )

    with pytest.raises(NotFoundError) as excinfo:
        caso.execute(6)

    assert excinfo.value.code == "IDENTIDAD_VISUAL_NO_ENCONTRADA"
    assert auditoria.consultas == []


class ResultadoFake:
    def __init__(self, filas) -> None:
        self.filas = filas

    def all(self):
        return self.filas


class SessionRepoFake:
    def __init__(self, filas) -> None:
        self.filas = filas
        self.sentencia = None

    def execute(self, sentencia):
        self.sentencia = sentencia
        return ResultadoFake(self.filas)


def test_repositorio_mapea_usuario_operacion_y_snapshot_canonico() -> None:
    orm = AuditoriaIdentidadVisualModel(
        id_auditoria_visual=45,
        id_usuario=50,
        fecha_creacion=AHORA,
        valor_anterior={"id_finca": 6, "version": 9},
        valor_nuevo={"id_finca": 6, "version": 10},
    )
    sesion = SessionRepoFake([(orm, "Administrador", "QA")])

    resultado = SqlAlchemyAuditoriaIdentidadVisualRepository(sesion).listar_por_finca(6)

    assert resultado[0].usuario == "Administrador QA"
    assert resultado[0].tipo_operacion == "UPDATE"
    assert resultado[0].id_finca == 6
    assert resultado[0].valor_anterior == {"id_finca": 6, "version": 9}
    assert resultado[0].valor_nuevo == {"id_finca": 6, "version": 10}
    assert "valor_nuevo" in str(sesion.sentencia)
    assert "ORDER BY" in str(sesion.sentencia)


def test_repositorio_deriva_create_cuando_no_hay_valor_anterior() -> None:
    orm = AuditoriaIdentidadVisualModel(
        id_auditoria_visual=46,
        id_usuario=50,
        fecha_creacion=AHORA,
        valor_anterior={},
        valor_nuevo={"id_finca": 6, "version": 1},
    )
    sesion = SessionRepoFake([(orm, "Administrador", None)])

    resultado = SqlAlchemyAuditoriaIdentidadVisualRepository(sesion).listar_por_finca(6)

    assert resultado[0].tipo_operacion == "CREATE"
    assert resultado[0].usuario == "Administrador"


class QueryPermisoFake:
    def __init__(self, permitido: bool) -> None:
        self.permitido = permitido

    def filter(self, *_criterios):
        return self

    def first(self):
        return object() if self.permitido else None


class DbEndpointFake:
    def __init__(self, permitido: bool) -> None:
        self.permitido = permitido

    def query(self, *_args):
        return QueryPermisoFake(self.permitido)


@pytest.mark.parametrize(
    ("permitido", "esperado"),
    [(True, 200), (False, 403)],
)
def test_endpoint_expone_historial_y_respeta_rbac(
    monkeypatch: pytest.MonkeyPatch,
    permitido: bool,
    esperado: int,
) -> None:
    import src.configuration.infrastructure.routers.identidad_visual_router as modulo

    class CasoFake:
        def __init__(self, **_kwargs) -> None:
            pass

        def execute(self, id_finca: int) -> list[AuditoriaIdentidadVisual]:
            assert id_finca == 6
            return [_registro()]

    monkeypatch.setattr(modulo, "ConsultarAuditoriaIdentidadVisualUseCase", CasoFake)

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    usuario = UsuarioActual(
        id_usuario=50,
        id_token=1,
        id_rol=1,
        id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
    )
    app.dependency_overrides[get_current_user] = lambda: usuario
    app.dependency_overrides[get_db] = lambda: DbEndpointFake(permitido)

    with TestClient(app, raise_server_exceptions=False) as cliente:
        respuesta = cliente.get("/configuracion/identidad-visual/6/auditoria")

    assert respuesta.status_code == esperado
    if esperado == 200:
        cuerpo = respuesta.json()
        assert cuerpo["total"] == 1
        assert cuerpo["items"][0]["usuario"] == "Administrador QA"
        assert cuerpo["items"][0]["tipo_operacion"] == "UPDATE"
        assert cuerpo["items"][0]["valor_anterior"]["version"] == 9
        assert cuerpo["items"][0]["valor_nuevo"]["version"] == 10
    else:
        assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"
