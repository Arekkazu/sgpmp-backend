# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | RF-SSO02: ubicar el usuario y el rol como los envía AgroFusion |
"""Ayudas compartidas por las operaciones de usuario que llama AgroFusion (RF-SSO02).

AgroFusion identifica al usuario por correo en ``GET_USER`` y por el id que SGPMP le devolvió en
``UPDATE_USER`` y ``CHANGE_USER_STATUS`` (reemplaza ``{user_id}`` en la ruta), y manda los roles como
la lista de ids que obtuvo de ``GET_ROLES``."""
from __future__ import annotations

from typing import Optional

from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.shared.errors import NotFoundError, ValidationError


def usuario_por_identificador(usuarios_repo: UsuarioRepository, identificador: str) -> Usuario:
    """Id numérico de SGPMP o correo; 404 si no existe."""
    usuario = (usuarios_repo.obtener_por_id(int(identificador)) if identificador.isdigit()
               else usuarios_repo.obtener_por_correo(Email(identificador)))
    if usuario is None:
        raise NotFoundError(code="USUARIO_NO_ENCONTRADO", message="No existe un usuario del SGPMP con ese identificador.")
    return usuario


def rol_solicitado(roles_repo: RolRepository, roles: Optional[list[int]], rol_codigo: Optional[str]) -> Optional[int]:
    """Primer id de ``roles`` (SGPMP asigna un rol por usuario) o el rol por nombre; ``None`` si no viene."""
    if roles:
        rol = roles_repo.obtener_por_id(roles[0])
    elif rol_codigo:
        rol = roles_repo.obtener_por_nombre(rol_codigo)
    else:
        return None
    if rol is None:
        raise ValidationError(code="ROL_NO_ENCONTRADO", field="roles", message="El rol indicado no existe en el SGPMP.")
    return rol.id_rol
