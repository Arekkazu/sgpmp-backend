"""Pruebas de INC-M01-127: el listado de roles no debe caer en N+1.

Antes, `ListarRolesUseCase` preguntaba los permisos de cada rol con una consulta
aparte (`listar_por_rol`), con lo que el endpoint crecía en latencia de forma
proporcional al número de roles. Ahora agrupa todos los permisos en una sola
consulta (`listar_por_roles`).
"""
from src.identity_access.application.use_cases.roles.listar_roles_use_case import (
    ListarRolesUseCase,
)
from src.identity_access.domain.entities.permiso import Permiso
from src.identity_access.domain.entities.rol import Rol


def _rol(id_rol: int, nombre: str) -> Rol:
    return Rol(id_rol=id_rol, nombre_rol=nombre, es_protegido=False)


def _permiso(id_permiso: int, id_rol: int) -> Permiso:
    return Permiso(
        id_permiso=id_permiso,
        id_rol=id_rol,
        id_recurso=1,
        id_accion=2,
        nombre=f"permiso_{id_permiso}",
        es_activo=True,
    )


class RolesRepoFake:
    def __init__(self, roles: list[Rol]) -> None:
        self.roles = roles

    def listar(self) -> list[Rol]:
        return self.roles


class PermisosRepoFake:
    def __init__(self, agrupados: dict[int, list[Permiso]]) -> None:
        self.agrupados = agrupados
        self.llamadas_por_roles = 0
        self.llamadas_por_rol = 0
        self.id_roles_recibidos: list[int] = []

    def listar_por_roles(self, id_roles: list[int]) -> dict[int, list[Permiso]]:
        self.llamadas_por_roles += 1
        self.id_roles_recibidos = id_roles
        return self.agrupados

    def listar_por_rol(self, id_rol: int) -> list[Permiso]:
        self.llamadas_por_rol += 1
        return self.agrupados.get(id_rol, [])


def test_el_listado_de_roles_agrupa_permisos_en_una_sola_consulta() -> None:
    roles = [_rol(1, "Administrador"), _rol(2, "Productor"), _rol(3, "Veterinario")]
    agrupados = {
        1: [_permiso(1, 1), _permiso(2, 1)],
        2: [_permiso(3, 2)],
        # rol 3 sin permisos: no debe figurar como clave.
    }
    repo = PermisosRepoFake(agrupados)
    caso = ListarRolesUseCase(roles_repo=RolesRepoFake(roles), permisos_repo=repo)

    resultado = caso.execute()

    assert repo.llamadas_por_roles == 1
    assert repo.llamadas_por_rol == 0
    assert repo.id_roles_recibidos == [1, 2, 3]
    assert resultado[0]["permisos"] == [_permiso(1, 1), _permiso(2, 1)]
    assert resultado[1]["permisos"] == [_permiso(3, 2)]
    assert resultado[2]["permisos"] == []


def test_sin_roles_no_se_consultan_permisos() -> None:
    repo = PermisosRepoFake({})
    caso = ListarRolesUseCase(roles_repo=RolesRepoFake([]), permisos_repo=repo)

    resultado = caso.execute()

    assert resultado == []
    assert repo.llamadas_por_roles == 1
    assert repo.id_roles_recibidos == []
