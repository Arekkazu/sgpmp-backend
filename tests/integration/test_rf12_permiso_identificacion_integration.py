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
    MAX_CONSULTAS_DETALLE_POR_VENTANA,
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
from src.shared.errors import TooManyRequestsError

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



def test_extraccion_masiva_de_fichas_corta_con_429(
    db_session: Session,
    crear_usuario_db,
) -> None:
    """El umbral se cuenta sobre la auditoría real (eventos tipo 18) del actor."""
    objetivo = crear_usuario_db(id_rol=2, estado=2)
    actor = crear_usuario_db(id_rol=1, estado=2)
    use_case = ConsultarDetalleUsuarioUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db_session),
        permisos_repo=SqlAlchemyPermisoRepository(db_session),
        eventos_repo=SqlAlchemyEventoRepository(db_session),
        db=db_session,
    )
    quien_consulta = SimpleNamespace(id_usuario=actor["id_usuario"], id_rol=1)

    for _ in range(MAX_CONSULTAS_DETALLE_POR_VENTANA):
        use_case.execute(objetivo["id_usuario"], quien_consulta)

    with pytest.raises(TooManyRequestsError) as exc:
        use_case.execute(objetivo["id_usuario"], quien_consulta)
    assert exc.value.status_code == 429

    # El intento bloqueado deja alerta en auditoría, y como se registra FALLIDO
    # no realimenta su propia ventana.
    fallidos = db_session.execute(
        text(
            """
            SELECT count(*) FROM modulo1.eventos
            WHERE tipo_evento = 18
              AND id_usuario = :actor
              AND resultado = 'fallido'
              AND detalle->>'motivo' = 'PATRON_CONSULTA_INUSUAL'
            """
        ),
        {"actor": actor["id_usuario"]},
    ).scalar()
    assert fallidos == 1

    # Otro administrador no queda bloqueado por el ritmo de su colega.
    otro = crear_usuario_db(id_rol=1, estado=2)
    use_case.execute(
        objetivo["id_usuario"],
        SimpleNamespace(id_usuario=otro["id_usuario"], id_rol=1),
    )
