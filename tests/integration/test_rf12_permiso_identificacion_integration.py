"""Integración RF-12: migración RBAC y enmascaramiento de identificación."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.usuarios.consultar_detalle_usuario_use_case import (
    ConsultarDetalleUsuarioUseCase,
)
from src.identity_access.infrastructure.repositories.evento_repository import (
    SqlAlchemyEventoRepository,
)
from src.identity_access.infrastructure.repositories.permiso_repository import (
    SqlAlchemyPermisoRepository,
)
from src.identity_access.infrastructure.repositories.usuario_repository import (
    SqlAlchemyUsuarioRepository,
)

pytestmark = pytest.mark.integration

MIGRACION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "f2c84d91a6e7_rf12_permiso_identificacion_completa.py"
)


def _cargar_migracion():
    spec = importlib.util.spec_from_file_location("migracion_rf12_permiso", MIGRACION)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_migracion_concede_identificacion_completa_solo_al_administrador(
    db_session: Session,
    crear_usuario_db,
) -> None:
    migracion = _cargar_migracion()
    contexto = MigrationContext.configure(db_session.connection())

    # Ejecutarla dos veces verifica que el seed no duplica la combinación.
    with Operations.context(contexto):
        migracion.upgrade()
        migracion.upgrade()

    permisos = db_session.execute(
        text(
            """
            SELECT id_rol, id_recurso, id_accion, es_activo
            FROM modulo1.permisos
            WHERE id_recurso = 1 AND id_accion = 5
            ORDER BY id_rol
            """
        )
    ).mappings().all()
    assert permisos == [
        {
            "id_rol": 1,
            "id_recurso": 1,
            "id_accion": 5,
            "es_activo": True,
        }
    ]

    objetivo = crear_usuario_db(
        id_rol=2,
        estado=2,
        numero_identificacion="123456789012",
    )
    admin = crear_usuario_db(id_rol=1, estado=2)
    actor_sin_permiso = crear_usuario_db(id_rol=2, estado=2)
    use_case = ConsultarDetalleUsuarioUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db_session),
        permisos_repo=SqlAlchemyPermisoRepository(db_session),
        eventos_repo=SqlAlchemyEventoRepository(db_session),
        db=db_session,
    )

    completo = use_case.execute(
        objetivo["id_usuario"],
        SimpleNamespace(id_usuario=admin["id_usuario"], id_rol=1),
    )
    enmascarado = use_case.execute(
        objetivo["id_usuario"],
        SimpleNamespace(
            id_usuario=actor_sin_permiso["id_usuario"],
            id_rol=2,
        ),
    )

    assert completo["numero_identificacion"] == "123456789012"
    assert enmascarado["numero_identificacion"] == "1234********"

