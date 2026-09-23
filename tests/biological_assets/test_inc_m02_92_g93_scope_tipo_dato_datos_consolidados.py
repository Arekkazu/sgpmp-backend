"""INC-M02-92-G93 / issue #390 (TC-M02-155): RF-50 FA-04 exige evaluar un
scope por `tipo_dato` sobre GET /activos-biologicos/{id}/datos-consolidados,
además del permiso general (recurso 29/R) que ya cubre `require_permission_m02`.
Sin esto no existía forma de construir la precondición que exige TC-M02-155:
"credencial válida de módulo + scope general concedido + scope del tipo_dato
solicitado ausente".
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AuthorizationError


class DbFake:
    """Mismo doble mínimo que usa test_rf52_auditoria_rbac.py: suficiente para
    que `SqlAlchemyBitacoraAuditoriaRepository.registrar()` (add + flush) y
    `RegistrarAccesoNoAutorizadoUseCase.execute()` (commit/rollback) operen
    sin una sesión SQLAlchemy real."""

    def __init__(self) -> None:
        self.agregados: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, entidad: object) -> None:
        self.agregados.append(entidad)

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _usuario(id_rol: int = 12) -> UsuarioActual:
    return UsuarioActual(id_usuario=99, id_token=1, id_rol=id_rol, id_estado_cuenta=Cuenta.ESTADO_ACTIVO)


def _request(id_activo: int = 7) -> Request:
    return Request(
        {
            'type': 'http',
            'http_version': '1.1',
            'method': 'GET',
            'scheme': 'http',
            'path': f'/activos-biologicos/{id_activo}/datos-consolidados',
            'raw_path': b'',
            'query_string': b'tipo_dato=metricas',
            'headers': [],
            'client': ('qa', 50000),
            'server': ('testserver', 80),
            'path_params': {'id_activo': id_activo},
            'route': SimpleNamespace(path='/activos-biologicos/{id_activo}/datos-consolidados'),
        }
    )


def _tiene_permiso_fake(recursos_concedidos: set[int]):
    def _fake(_db, _id_rol, id_recurso, _id_accion):
        return id_recurso in recursos_concedidos
    return _fake


def test_scope_concedido_no_lanza(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        router_module, 'tiene_permiso',
        _tiene_permiso_fake({router_module._RECURSO_DATOS_METRICAS}),
    )
    db = DbFake()

    router_module._verificar_scope_tipo_dato(db, _usuario(), 'metricas', _request(), 7)

    assert db.agregados == []
    assert db.commits == 0


def test_scope_ausente_lanza_403_con_mensaje_literal_de_rf50(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router_module, 'tiene_permiso', _tiene_permiso_fake(set()))
    db = DbFake()

    with pytest.raises(AuthorizationError) as exc:
        router_module._verificar_scope_tipo_dato(db, _usuario(), 'metricas', _request(), 7)

    assert exc.value.code == 'SCOPE_TIPO_DATO_NO_AUTORIZADO'
    # Mensaje literal del flujo alterno #4 de RF-50: "Acceso denegado: El
    # módulo solicitante no tiene autorización para consumir datos de tipo
    # [TIPO_DATO]."
    assert exc.value.message == (
        'Acceso denegado: El módulo solicitante no tiene autorización '
        'para consumir datos de tipo metricas.'
    )


def test_scope_ausente_registra_rechazo_en_bitacora_rf52(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router_module, 'tiene_permiso', _tiene_permiso_fake(set()))
    db = DbFake()

    with pytest.raises(AuthorizationError):
        router_module._verificar_scope_tipo_dato(db, _usuario(), 'metricas', _request(), 7)

    assert db.commits == 1
    assert len(db.agregados) == 1


def test_todos_exige_los_4_scopes_estricto(monkeypatch: pytest.MonkeyPatch) -> None:
    # Concede eventos/fases/estado, falta metricas -- exactamente el fixture
    # que siembra la migración d944f4d8c215 para 'Integración M04', para que
    # QA pueda reejecutar TC-M02-155 tal cual sin fabricar nada.
    monkeypatch.setattr(
        router_module, 'tiene_permiso',
        _tiene_permiso_fake({
            router_module._RECURSO_DATOS_EVENTOS,
            router_module._RECURSO_DATOS_FASES,
            router_module._RECURSO_DATOS_ESTADO,
        }),
    )
    db = DbFake()

    with pytest.raises(AuthorizationError) as exc:
        router_module._verificar_scope_tipo_dato(db, _usuario(), 'todos', _request(), 7)

    assert exc.value.code == 'SCOPE_TIPO_DATO_NO_AUTORIZADO'
    assert 'metricas' in exc.value.message


def test_todos_concedido_cuando_los_4_scopes_estan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        router_module, 'tiene_permiso',
        _tiene_permiso_fake(set(router_module._SCOPES_TIPO_DATO.values())),
    )
    db = DbFake()

    router_module._verificar_scope_tipo_dato(db, _usuario(), 'todos', _request(), 7)

    assert db.agregados == []
