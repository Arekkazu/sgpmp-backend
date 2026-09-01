"""Pruebas unitarias de regresion para INC-M01-03-119 (RF-03)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import InternalError

from src.identity_access.application.use_cases.roles.eliminar_rol_use_case import (
    EliminarRolUseCase,
)
from src.identity_access.domain.entities.rol import Rol
from src.identity_access.infrastructure.repositories.rol_repository import (
    SqlAlchemyRolRepository,
)
from src.shared.errors import AuthorizationError, BusinessRuleError


def _use_case(rol: Rol, *, usuarios: int = 0):
    roles_repo = MagicMock()
    roles_repo.obtener_por_id.return_value = rol
    roles_repo.contar_usuarios.return_value = usuarios
    eventos_repo = MagicMock()
    db = MagicMock()
    use_case = EliminarRolUseCase(roles_repo, eventos_repo, db)
    actor = SimpleNamespace(id_usuario=99)
    return use_case, roles_repo, eventos_repo, db, actor


def test_elimina_rol_sin_usuarios_y_audita_en_la_misma_transaccion() -> None:
    rol = Rol(id_rol=10, nombre_rol="Auxiliar de Campo", es_protegido=False)
    use_case, roles_repo, eventos_repo, db, actor = _use_case(rol)

    use_case.execute(10, actor)

    roles_repo.eliminar.assert_called_once_with(rol)
    eventos_repo.registrar.assert_called_once_with(
        tipo_evento=13,
        exitoso=True,
        id_usuario=99,
        detalle={"id_rol": 10, "nombre_rol": "Auxiliar de Campo"},
    )
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


def test_fallo_al_eliminar_revierte_y_no_registra_exito() -> None:
    rol = Rol(id_rol=10, nombre_rol="Auxiliar de Campo", es_protegido=False)
    use_case, roles_repo, eventos_repo, db, actor = _use_case(rol)
    roles_repo.eliminar.side_effect = RuntimeError("fallo de persistencia")

    with pytest.raises(RuntimeError, match="fallo de persistencia"):
        use_case.execute(10, actor)

    eventos_repo.registrar.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once_with()


def test_rol_protegido_responde_403_sin_intentar_eliminar() -> None:
    rol = Rol(id_rol=1, nombre_rol="Administrador", es_protegido=True)
    use_case, roles_repo, eventos_repo, db, actor = _use_case(rol)

    with pytest.raises(AuthorizationError) as exc_info:
        use_case.execute(1, actor)

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "ROL_PROTEGIDO"
    roles_repo.contar_usuarios.assert_not_called()
    roles_repo.eliminar.assert_not_called()
    eventos_repo.registrar.assert_not_called()
    db.commit.assert_not_called()


def test_rol_con_usuarios_responde_422_y_conserva_el_rol() -> None:
    rol = Rol(id_rol=10, nombre_rol="Auxiliar de Campo", es_protegido=False)
    use_case, roles_repo, eventos_repo, db, actor = _use_case(rol, usuarios=2)

    with pytest.raises(BusinessRuleError) as exc_info:
        use_case.execute(10, actor)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "ROL_EN_USO"
    assert "existen 2 usuarios vinculados" in exc_info.value.message
    roles_repo.eliminar.assert_not_called()
    eventos_repo.registrar.assert_not_called()
    db.commit.assert_not_called()


class _ErrorTrigger(Exception):
    def __init__(self, pgcode: str, mensaje: str):
        super().__init__(mensaje)
        self.pgcode = pgcode


@pytest.mark.parametrize(
    ("pgcode", "mensaje", "error_esperado", "codigo"),
    [
        ("P0004", "PROTECTED_ROLE", AuthorizationError, "ROL_PROTEGIDO"),
        ("P0005", "ROLE_IN_USE", BusinessRuleError, "ROL_EN_USO"),
    ],
)
def test_repositorio_traduce_internal_error_de_triggers_concurrentes(
    pgcode,
    mensaje,
    error_esperado,
    codigo,
) -> None:
    db = MagicMock()
    db.get.return_value = MagicMock()
    db.flush.side_effect = InternalError(
        "DELETE FROM modulo1.roles",
        {},
        _ErrorTrigger(pgcode, mensaje),
    )
    repo = SqlAlchemyRolRepository(db)
    rol = Rol(id_rol=10, nombre_rol="Auxiliar de Campo", es_protegido=False)

    with pytest.raises(error_esperado) as exc_info:
        repo.eliminar(rol)

    assert exc_info.value.code == codigo
    db.delete.assert_called_once_with(db.get.return_value)
