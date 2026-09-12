"""INC-M02-83-G07 / RF-52: los rechazos RBAC 403 quedan auditados."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.biological_assets.infrastructure.rbac_auditoria import require_permission_m02
from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import AuthorizationError


class PermisosQueryFake:
    def __init__(self, permiso_concedido: bool) -> None:
        self.permiso_concedido = permiso_concedido

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return object() if self.permiso_concedido else None


class DbFake:
    def __init__(self, *, permiso_concedido: bool = False, falla_flush: bool = False) -> None:
        self.permiso_concedido = permiso_concedido
        self.falla_flush = falla_flush
        self.agregados: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, _modelo):
        return PermisosQueryFake(self.permiso_concedido)

    def add(self, entidad: object) -> None:
        self.agregados.append(entidad)

    def flush(self) -> None:
        if self.falla_flush:
            raise RuntimeError('auditoría no disponible')

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _usuario(*, estado: int = Cuenta.ESTADO_ACTIVO) -> UsuarioActual:
    return UsuarioActual(
        id_usuario=73,
        id_token=1,
        id_rol=5,
        id_estado_cuenta=estado,
    )


def _request(id_activo: int = 80) -> Request:
    return Request(
        {
            'type': 'http',
            'http_version': '1.1',
            'method': 'POST',
            'scheme': 'http',
            'path': f'/activos-biologicos/{id_activo}/eventos/productivo',
            'raw_path': b'',
            'query_string': b'',
            'headers': [],
            'client': ('qa', 50000),
            'server': ('testserver', 80),
            'path_params': {'id_activo': id_activo},
            'route': SimpleNamespace(
                path='/activos-biologicos/{id_activo}/eventos/productivo'
            ),
        }
    )


def test_dependencia_registra_acceso_no_autorizado_y_conserva_el_403() -> None:
    db = DbFake()
    dependencia = require_permission_m02(29, 1, rf_origen='RF43')

    with pytest.raises(AuthorizationError) as excinfo:
        dependencia(request=_request(), db=db, usuario_actual=_usuario())

    assert excinfo.value.code == 'ACCESO_DENEGADO'
    assert excinfo.value.status_code == 403
    assert db.commits == 1
    assert db.rollbacks == 0
    assert len(db.agregados) == 1

    auditoria = db.agregados[0]
    assert auditoria.rf_origen == 'RF43'
    assert auditoria.tipo_evento == 'ACCESO_NO_AUTORIZADO'
    assert auditoria.clasificacion_biologica == 'ACCESO_DATOS'
    assert auditoria.id_activo_biologico == 80
    assert auditoria.id_usuario_responsable == 73
    assert auditoria.resultado == 'RECHAZADO'
    assert auditoria.severidad_log == 'WARNING'
    assert auditoria.detalle_tecnico == {
        'error_code': 'ACCESO_DENEGADO',
        'causa': 'Acceso denegado. Su rol no tiene permisos para realizar esta operación.',
        'id_recurso': 29,
        'id_accion': 1,
        'metodo_http': 'POST',
        'ruta': '/activos-biologicos/{id_activo}/eventos/productivo',
    }
    assert len(auditoria.hash_integridad) == 64


def test_permiso_concedido_no_genera_evento_de_rechazo() -> None:
    db = DbFake(permiso_concedido=True)
    dependencia = require_permission_m02(29, 1, rf_origen='RF43')

    assert dependencia(request=_request(), db=db, usuario_actual=_usuario()) is None
    assert db.agregados == []
    assert db.commits == 0
    assert db.rollbacks == 0


def test_cuenta_no_activa_tambien_conserva_codigo_y_queda_auditada() -> None:
    db = DbFake(permiso_concedido=True)
    dependencia = require_permission_m02(29, 1, rf_origen='RF43')

    with pytest.raises(AuthorizationError) as excinfo:
        dependencia(
            request=_request(),
            db=db,
            usuario_actual=_usuario(estado=Cuenta.ESTADO_BLOQUEADO),
        )

    assert excinfo.value.code == 'CUENTA_NO_ACTIVA'
    assert db.agregados[0].detalle_tecnico['error_code'] == 'CUENTA_NO_ACTIVA'
    assert db.agregados[0].resultado == 'RECHAZADO'
    assert db.commits == 1


def test_fallo_de_auditoria_no_reemplaza_el_403_original() -> None:
    db = DbFake(falla_flush=True)
    dependencia = require_permission_m02(29, 1, rf_origen='RF43')

    with pytest.raises(AuthorizationError) as excinfo:
        dependencia(request=_request(), db=db, usuario_actual=_usuario())

    assert excinfo.value.code == 'ACCESO_DENEGADO'
    assert db.commits == 0
    assert db.rollbacks == 1


def test_contrato_http_tc_m02_249_retorna_403_y_persiste_auditoria() -> None:
    db = DbFake()
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_module.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = _usuario

    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = client.post(
            '/activos-biologicos/80/eventos/productivo',
            json={
                'tipo_producto': 'LECHE',
                'cantidad_producida': 12.5,
                'unidad_medida': 'litros',
                'fecha_evento': '2026-09-01',
            },
        )

    assert respuesta.status_code == 403
    assert respuesta.json()['error_code'] == 'ACCESO_DENEGADO'
    assert len(db.agregados) == 1
    assert db.agregados[0].tipo_evento == 'ACCESO_NO_AUTORIZADO'
    assert db.agregados[0].rf_origen == 'RF43'
    assert db.agregados[0].id_activo_biologico == 80


def test_todas_las_rutas_m02_protegidas_auditan_el_rf_que_las_origina() -> None:
    esperado = {
        ('POST', '/activos-biologicos'): 'RF33',
        ('GET', '/activos-biologicos'): 'RF33',
        ('GET', '/activos-biologicos/auditoria'): 'RF52',
        ('GET', '/activos-biologicos/{id_activo}'): 'RF35',
        ('PATCH', '/activos-biologicos/{id_activo}'): 'RF35',
        ('POST', '/activos-biologicos/{id_activo}/fases'): 'RF37',
        ('GET', '/activos-biologicos/{id_activo}/fases'): 'RF37',
        ('GET', '/activos-biologicos/{id_activo}/infraestructura'): 'RF34',
        ('GET', '/activos-biologicos/{id_activo}/eventos'): 'RF39',
        ('POST', '/activos-biologicos/{id_activo}/eventos/crecimiento'): 'RF40',
        ('POST', '/activos-biologicos/{id_activo}/eventos/baja'): 'RF45',
        ('POST', '/activos-biologicos/{id_activo}/eventos/sanitario'): 'RF41',
        ('PATCH', '/activos-biologicos/{id_activo}/estado'): 'RF44',
        ('POST', '/activos-biologicos/{id_activo}/cierre'): 'RF38',
        ('POST', '/activos-biologicos/{id_activo}/eventos/reproductivo'): 'RF42',
        ('POST', '/activos-biologicos/{id_activo}/eventos/productivo'): 'RF43',
        ('GET', '/activos-biologicos/{id_activo}/historial'): 'RF46',
        ('GET', '/activos-biologicos/{id_activo}/ficha-integral'): 'RF47',
        ('GET', '/activos-biologicos/{id_activo}/transferencias/disponibles'): 'RF48',
        ('POST', '/activos-biologicos/{id_activo}/transferencias'): 'RF48',
        ('POST', '/activos-biologicos/{id_activo}/sensores'): 'RF49',
        ('GET', '/activos-biologicos/{id_activo}/indicadores'): 'RF51',
        ('GET', '/activos-biologicos/{id_activo}/datos-consolidados'): 'RF50',
    }

    encontrado: dict[tuple[str, str], str] = {}
    for route in router_module.router.routes:
        if not isinstance(route, APIRoute):
            continue
        dependencias_auditadas = [
            dependencia.call
            for dependencia in route.dependant.dependencies
            if getattr(dependencia.call, 'audita_rechazo_rbac_m02', False)
        ]
        for metodo in route.methods:
            clave = (metodo, route.path)
            assert len(dependencias_auditadas) == 1, clave
            encontrado[clave] = dependencias_auditadas[0].rf_origen

    assert encontrado == esperado
