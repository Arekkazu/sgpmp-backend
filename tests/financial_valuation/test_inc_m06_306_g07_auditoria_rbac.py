# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-306-G07 RF-82: los rechazos 403 de M06 quedan en la auditoría financiera |
"""INC-M06-306-G07 / RNF-82-05: un rol no autorizado recibe 403 y el intento queda en RF-94."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.financial_valuation.application.use_cases.auditoria.consultar_auditoria_financiera_use_case import DESCRIPCIONES
from src.financial_valuation.infrastructure import rbac_auditoria
from src.financial_valuation.infrastructure.rbac_auditoria import require_permission_m06
from src.financial_valuation.infrastructure.routers import m06_router
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import AuthorizationError


class PermisosQueryFake:
    def __init__(self, concedido: bool) -> None:
        self.concedido = concedido

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return object() if self.concedido else None


class DbFake:
    def __init__(self, *, concedido: bool = False) -> None:
        self.concedido = concedido
        self.commits = 0
        self.rollbacks = 0

    def query(self, _modelo):
        return PermisosQueryFake(self.concedido)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class AuditoriaFake:
    eventos: list = []
    falla = False

    def __init__(self, _db) -> None:
        pass

    def registrar(self, evento) -> None:
        if AuditoriaFake.falla:
            raise RuntimeError("auditoría no disponible")
        AuditoriaFake.eventos.append(evento)


@pytest.fixture(autouse=True)
def auditoria(monkeypatch):
    AuditoriaFake.eventos, AuditoriaFake.falla = [], False
    monkeypatch.setattr(rbac_auditoria, "SqlAlchemyAuditoriaFinancieraRepository", AuditoriaFake)
    return AuditoriaFake


def _usuario(estado: int = Cuenta.ESTADO_ACTIVO) -> UsuarioActual:
    return UsuarioActual(id_usuario=41, id_token=1, id_rol=2, id_estado_cuenta=estado)


def _request() -> Request:
    ruta = "/finanzas/reconocimientos/{id_activo_biologico}/reversion"
    return Request({
        "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
        "path": "/finanzas/reconocimientos/187/reversion", "raw_path": b"", "query_string": b"", "headers": [],
        "client": ("qa", 50000), "server": ("testserver", 80),
        "path_params": {"id_activo_biologico": "187"}, "route": SimpleNamespace(path=ruta),
    })


def test_rechazo_403_queda_en_la_auditoria_financiera(auditoria) -> None:
    db = DbFake()
    with pytest.raises(AuthorizationError) as excinfo:
        require_permission_m06("reconocimiento_inicial", 3)(request=_request(), db=db, usuario_actual=_usuario())

    assert excinfo.value.code == "ACCESO_DENEGADO"
    assert db.commits == 1 and db.rollbacks == 0
    [evento] = auditoria.eventos
    assert evento.tipo_evento == "ACCESO_NO_AUTORIZADO"
    assert evento.severidad == "WARNING"
    assert evento.id_usuario == 41
    assert evento.id_activo_biologico is None and evento.id_periodo_contable is None  # FK: id de la URL sin validar
    assert evento.payload["id_activo_biologico"] == 187
    assert evento.payload["id_periodo_contable"] is None
    assert evento.payload["error_code"] == "ACCESO_DENEGADO"
    assert evento.payload["id_rol"] == 2
    assert evento.payload["recurso"] == "reconocimiento_inicial"
    assert evento.payload["id_accion"] == 3
    assert evento.payload["metodo_http"] == "POST"
    assert evento.payload["ruta"] == "/finanzas/reconocimientos/{id_activo_biologico}/reversion"


def test_permiso_concedido_no_registra_evento(auditoria) -> None:
    db = DbFake(concedido=True)
    assert require_permission_m06("reconocimiento_inicial", 3)(request=_request(), db=db, usuario_actual=_usuario()) is None
    assert auditoria.eventos == [] and db.commits == 0


def test_cuenta_no_activa_tambien_queda_auditada(auditoria) -> None:
    db = DbFake(concedido=True)
    with pytest.raises(AuthorizationError) as excinfo:
        require_permission_m06("reconocimiento_inicial", 3)(
            request=_request(), db=db, usuario_actual=_usuario(Cuenta.ESTADO_BLOQUEADO))
    assert excinfo.value.code == "CUENTA_NO_ACTIVA"
    assert auditoria.eventos[0].payload["error_code"] == "CUENTA_NO_ACTIVA"


def test_fallo_al_auditar_no_reemplaza_el_403(auditoria) -> None:
    auditoria.falla = True
    db = DbFake()
    with pytest.raises(AuthorizationError) as excinfo:
        require_permission_m06("reconocimiento_inicial", 3)(request=_request(), db=db, usuario_actual=_usuario())
    assert excinfo.value.code == "ACCESO_DENEGADO"
    assert db.commits == 0 and db.rollbacks == 1


@pytest.mark.parametrize("metodo, ruta, cuerpo, activo, periodo", [
    ("post", "/finanzas/reconocimientos/187/reversion", {"motivo": "x" * 30}, 187, None),
    ("post", "/finanzas/reconocimientos/180", {}, 180, None),
    ("post", "/finanzas/costos", {}, None, None),
    ("post", "/finanzas/periodos/9/cierre", {}, None, 9),
])
def test_contrato_http_403_y_evento_registrado(auditoria, metodo, ruta, cuerpo, activo, periodo) -> None:
    db = DbFake()
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(m06_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = _usuario

    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = getattr(client, metodo)(ruta, json=cuerpo)

    assert respuesta.status_code == 403
    [evento] = auditoria.eventos
    assert evento.tipo_evento == "ACCESO_NO_AUTORIZADO"
    assert evento.payload["id_activo_biologico"] == activo
    assert evento.payload["id_periodo_contable"] == periodo


def test_todas_las_rutas_m06_auditan_el_rechazo_rbac() -> None:
    rutas = [r for r in m06_router.router.routes if isinstance(r, APIRoute)]
    assert rutas
    for route in rutas:
        auditadas = [d for d in route.dependant.dependencies if getattr(d.call, "audita_rechazo_rbac_m06", False)]
        assert len(auditadas) == 1, (route.methods, route.path)


def test_el_tipo_tiene_descripcion_legible_y_se_puede_filtrar() -> None:
    assert DESCRIPCIONES["ACCESO_NO_AUTORIZADO"] == "Intento de operación sin permiso del rol"
