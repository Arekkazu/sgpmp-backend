"""Regresión de la separación RF-05 (perfil) y RF-06 (estado de cuenta)."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.identity_access.application.use_cases.cuentas.gestionar_cuenta_use_case import (
    GestionarCuentaUseCase,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dto.gestion_cuenta_dto import GestionarCuentaDTO
from src.identity_access.infrastructure.dto.perfil_dto import (
    EditarPerfilAdminDTO,
    EditarPerfilDTO,
)
from src.shared.errors import BusinessRuleError


ROOT = Path(__file__).resolve().parents[2]
ROUTER_PATH = ROOT / "src/identity_access/infrastructure/routers/usuarios_routers.py"
EDITAR_PATH = ROOT / "src/identity_access/application/use_cases/perfil/editar_perfil_use_case.py"
GESTIONAR_PATH = ROOT / "src/identity_access/application/use_cases/cuentas/gestionar_cuenta_use_case.py"
CUENTA_REPO_PATH = ROOT / "src/identity_access/infrastructure/repositories/cuenta_repository.py"


def _funcion(nombre: str) -> ast.FunctionDef:
    modulo = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))
    return next(
        nodo
        for nodo in modulo.body
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre
    )


def _decorador_patch(funcion: ast.FunctionDef) -> str:
    return next(
        ast.unparse(decorador)
        for decorador in funcion.decorator_list
        if isinstance(decorador, ast.Call)
        and isinstance(decorador.func, ast.Attribute)
        and decorador.func.attr == "patch"
    )


def test_router_separa_edicion_propia_y_administrativa_con_rbac() -> None:
    propio = _decorador_patch(_funcion("editar_perfil_propio"))
    administrativo = _decorador_patch(_funcion("editar_perfil_admin"))

    assert "'/me'" in propio
    assert "'/{id_usuario}'" in administrativo
    assert "require_permission(1, 3)" in administrativo


def test_router_gestionar_cuenta_conserva_permiso_rbac() -> None:
    fuente = ROUTER_PATH.read_text(encoding="utf-8")
    inicio = fuente.index("@router.post(\n    \"/{id_usuario}/gestionar\"")
    bloque = fuente[inicio:fuente.index("def gestionar_cuenta", inicio)]
    assert "require_permission(4, 3)" in bloque


def test_dtos_de_perfil_rechazan_campos_fuera_de_su_alcance() -> None:
    datos = {
        "nombre": "Ana",
        "apellidos": "Perez",
        "version": 1,
    }

    with pytest.raises(PydanticValidationError) as error_propio:
        EditarPerfilDTO(**datos, id_rol=2)

    assert any(
        error["loc"] == ("id_rol",)
        and error["type"] == "extra_forbidden"
        for error in error_propio.value.errors()
    )

    with pytest.raises(PydanticValidationError) as error_admin:
        EditarPerfilAdminDTO(**datos, id_estado_cuenta=3)

    assert any(
        error["loc"] == ("id_estado_cuenta",)
        and error["type"] == "extra_forbidden"
        for error in error_admin.value.errors()
    )


def test_estado_de_cuenta_solo_se_modifica_en_gestionar() -> None:
    editar = EDITAR_PATH.read_text(encoding="utf-8")
    gestionar = GESTIONAR_PATH.read_text(encoding="utf-8")

    assert "dto.id_estado_cuenta" not in editar
    assert ".cambiar_estado(" not in editar
    assert "TRANSICIONES_VALIDAS" not in editar
    assert ".cambiar_estado(" in gestionar
    assert "registrar_gestion(" in gestionar


def test_no_hay_id_de_administrador_fijo_en_los_flujos() -> None:
    for ruta in (EDITAR_PATH, GESTIONAR_PATH, CUENTA_REPO_PATH):
        fuente = ruta.read_text(encoding="utf-8")
        assert "ROL_ADMINISTRADOR" not in fuente
        assert "id_rol == 1" not in fuente


class _DbFake:
    def rollback(self) -> None:
        pass


class _UsuariosRepoFake:
    def obtener_por_id(self, id_usuario: int):
        return SimpleNamespace(id_usuario=id_usuario, id_rol=42, correo="admin@example.com")


class _CuentasRepoFake:
    def __init__(self) -> None:
        self.id_rol_contado = None

    def obtener_por_usuario(self, id_usuario: int) -> Cuenta:
        return Cuenta(
            id_cuenta_usuario=8,
            id_usuario=id_usuario,
            id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
        )

    def contar_usuarios_activos_por_rol(self, id_rol: int) -> int:
        self.id_rol_contado = id_rol
        return 1


class _RolesRepoFake:
    def __init__(self) -> None:
        self.id_rol_consultado = None

    def obtener_por_id(self, id_rol: int):
        self.id_rol_consultado = id_rol
        return SimpleNamespace(id_rol=id_rol, es_protegido=True)


def test_ultimo_usuario_activo_de_rol_protegido_usa_rol_real() -> None:
    cuentas = _CuentasRepoFake()
    roles = _RolesRepoFake()
    use_case = GestionarCuentaUseCase(
        usuarios_repo=_UsuariosRepoFake(),
        cuentas_repo=cuentas,
        eventos_repo=SimpleNamespace(),
        sesiones_repo=SimpleNamespace(),
        roles_repo=roles,
        db=_DbFake(),
    )

    with pytest.raises(BusinessRuleError) as error:
        use_case.execute(
            id_usuario=7,
            dto=GestionarCuentaDTO(
                accion_cuenta="inactivar",
                motivo_accion="Cambio administrativo justificado",
            ),
            # El rol del actor no se interpreta aquí: RBAC ya actuó en el router.
            usuario_actual=SimpleNamespace(id_usuario=99, id_rol=999),
        )

    assert error.value.code == "ULTIMO_ADMIN_PROTEGIDO"
    assert roles.id_rol_consultado == 42
    assert cuentas.id_rol_contado == 42
