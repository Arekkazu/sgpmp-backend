"""RF-06: acción administrativa 'Desbloquear'.

Flujo alterno "Acción inconsistente con el estado actual": desbloquear una
cuenta ACTIVA o INACTIVA responde 400 con el mensaje literal del RF.
"""
from types import SimpleNamespace
from typing import Any

import pytest

from src.identity_access.application.use_cases.cuentas.gestionar_cuenta_use_case import (
    GestionarCuentaUseCase,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dto.gestion_cuenta_dto import GestionarCuentaDTO
from src.shared.errors import ConflictError, ValidationError


class _CuentasRepoFake:
    def __init__(self, cuenta: Cuenta) -> None:
        self.cuenta = cuenta
        self.gestiones: list[dict] = []

    def obtener_por_usuario(self, _id_usuario: int) -> Cuenta:
        return self.cuenta

    def contar_usuarios_activos_por_rol(self, _id_rol: int) -> int:
        return 5

    def guardar(self, cuenta: Cuenta) -> Cuenta:
        return cuenta

    def registrar_gestion(self, **datos: Any) -> None:
        self.gestiones.append(datos)


class _DbFake:
    commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass


def _desbloquear(estado_inicial: int) -> tuple[Cuenta, _CuentasRepoFake, _DbFake]:
    cuenta = Cuenta(id_cuenta_usuario=8, id_usuario=7, id_estado_cuenta=estado_inicial)
    repo = _CuentasRepoFake(cuenta)
    db = _DbFake()
    usuarios: Any = SimpleNamespace(obtener_por_id=lambda i: SimpleNamespace(id_usuario=i, id_rol=2))
    eventos: Any = SimpleNamespace(registrar=lambda **_k: None)
    sesiones: Any = SimpleNamespace(invalidar_todas_sesiones=lambda *_a: None)
    roles: Any = SimpleNamespace(obtener_por_id=lambda i: SimpleNamespace(id_rol=i, es_protegido=False))
    actual: Any = SimpleNamespace(id_usuario=99, id_rol=1)
    db_any: Any = db
    GestionarCuentaUseCase(
        usuarios_repo=usuarios,
        cuentas_repo=repo,  # type: ignore[arg-type]
        eventos_repo=eventos,
        sesiones_repo=sesiones,
        roles_repo=roles,
        db=db_any,
    ).execute(
        id_usuario=7,
        dto=GestionarCuentaDTO(accion_cuenta="desbloquear", motivo_accion="Revisión de soporte"),
        usuario_actual=actual,
    )
    return cuenta, repo, db


def test_desbloquear_una_cuenta_bloqueada_la_activa_y_queda_en_la_bitacora() -> None:
    cuenta, repo, db = _desbloquear(Cuenta.ESTADO_BLOQUEADO)

    assert cuenta.id_estado_cuenta == Cuenta.ESTADO_ACTIVO
    assert repo.gestiones[0]["accion"] == "desbloquear"
    assert db.commits == 1


@pytest.mark.parametrize(
    "estado, nombre",
    [(Cuenta.ESTADO_ACTIVO, "ACTIVO"), (Cuenta.ESTADO_INACTIVO, "INACTIVO")],
)
def test_desbloquear_una_cuenta_no_bloqueada_responde_400_con_el_mensaje_del_rf(estado, nombre) -> None:
    with pytest.raises(ValidationError) as exc:
        _desbloquear(estado)

    assert exc.value.status_code == 400
    assert exc.value.code == "ACCION_INCONSISTENTE_ESTADO"
    assert exc.value.message == (
        "Inconsistencia de estado. La acción 'Desbloquear' solo es aplicable a cuentas en estado "
        f"'BLOQUEADO'. El usuario actual ya se encuentra {nombre}."
    )


def test_desbloquear_una_cuenta_eliminada_mantiene_el_409_irreversible() -> None:
    with pytest.raises(ConflictError) as exc:
        _desbloquear(Cuenta.ESTADO_ELIMINADO)

    assert exc.value.status_code == 409
