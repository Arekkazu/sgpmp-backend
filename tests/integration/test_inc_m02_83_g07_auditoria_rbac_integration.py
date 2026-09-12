"""Integración PostgreSQL de INC-M02-83-G07 / TC-M02-249 en base aislada.

La sesión ``db_session`` usa un savepoint sobre una transacción exterior; aunque
el caso de uso confirme la auditoría, el fixture revierte todo al finalizar.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.biological_assets.infrastructure.models.bitacora_auditoria_m02_model import (
    BitacoraAuditoriaM02Model,
)
from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.identity_access.infrastructure.models.roles_model import Roles
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


def test_tc_m02_249_403_rbac_incrementa_bitacora_rf43(
    db_session: Session,
) -> None:
    # Precondición de QA: el rol Contador no tiene C sobre activos biológicos.
    # El ID se resuelve del catálogo real; los roles no se tratan como fijos.
    rol_contador = (
        db_session.query(Roles)
        .filter(Roles.nombre_rol.ilike('Contador'))
        .one()
    )
    permiso = (
        db_session.query(Permisos)
        .filter(
            Permisos.id_rol == rol_contador.id_rol,
            Permisos.id_recurso == 29,
            Permisos.id_accion == 1,
            Permisos.es_activo.is_(True),
        )
        .first()
    )
    assert permiso is None
    usuario_contador = (
        db_session.query(Usuarios)
        .filter(Usuarios.id_rol == rol_contador.id_rol)
        .first()
    )
    assert usuario_contador is not None

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_module.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id_usuario=usuario_contador.id_usuario,
        id_token=1,
        id_rol=rol_contador.id_rol,
        id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
    )

    filtro = (
        db_session.query(BitacoraAuditoriaM02Model)
        .filter(
            BitacoraAuditoriaM02Model.rf_origen == 'RF43',
            BitacoraAuditoriaM02Model.id_activo_biologico == 80,
            BitacoraAuditoriaM02Model.tipo_evento == 'ACCESO_NO_AUTORIZADO',
        )
    )
    conteo_antes = filtro.count()

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
    assert filtro.count() == conteo_antes + 1

    auditoria = (
        filtro.order_by(BitacoraAuditoriaM02Model.id_bitacora.desc()).first()
    )
    assert auditoria.resultado == 'RECHAZADO'
    assert auditoria.severidad_log == 'WARNING'
    assert auditoria.clasificacion_biologica == 'ACCESO_DATOS'
    assert auditoria.id_usuario_responsable == usuario_contador.id_usuario
    assert auditoria.detalle_tecnico['error_code'] == 'ACCESO_DENEGADO'
    assert auditoria.detalle_tecnico['id_recurso'] == 29
    assert auditoria.detalle_tecnico['id_accion'] == 1
