# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | RF-SSO02: UPDATE_USER de AgroFusion sobre la edición administrativa de perfil |
"""Caso de uso: actualización de un usuario pedida por AgroFusion (`UPDATE_USER`, RF-SSO02).

Reutiliza la edición administrativa de perfil (RF-05) con el usuario del token de canal como
quien edita: mismas reglas (formato de nombre y teléfono, no cambiar el propio rol, rol protegido)
y misma auditoría. AgroFusion no conoce la ``version`` del usuario en SGPMP, así que se toma la
vigente; los campos que no envía se conservan. El correo no se cambia por esta vía (es la llave
con la que AgroFusion identifica al usuario)."""
from __future__ import annotations

from typing import Optional

from pydantic import ValidationError as ErrorPydantic

from src.identity_access.application.use_cases.perfil.editar_perfil_use_case import EditarPerfilUseCase
from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.agrofusion_dto import AgroFusionUpdateUserDTO
from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilAdminDTO
from src.shared.errors import NotFoundError, ValidationError


class ActualizarUsuarioAgroFusionUseCase:
    def __init__(self, usuarios_repo: UsuarioRepository, roles_repo: RolRepository, editar_perfil: EditarPerfilUseCase):
        self.usuarios_repo = usuarios_repo
        self.roles_repo = roles_repo
        self.editar_perfil = editar_perfil

    def execute(self, email: str, dto: AgroFusionUpdateUserDTO, usuario_actual: UsuarioActual) -> Usuario:
        usuario = self.usuarios_repo.obtener_por_correo(Email(email))
        if usuario is None:
            raise NotFoundError(code="USUARIO_NO_ENCONTRADO", message="No existe un usuario del SGPMP con ese correo.")
        id_rol: Optional[int] = None
        if dto.rol_codigo:
            rol = self.roles_repo.obtener_por_nombre(dto.rol_codigo)
            if rol is None:
                raise ValidationError(code="ROL_NO_ENCONTRADO", field="rol_codigo",
                                      message=f"No existe el rol «{dto.rol_codigo}» en el SGPMP.")
            id_rol = rol.id_rol if rol.id_rol != usuario.id_rol else None
        try:
            cambios = EditarPerfilAdminDTO(
                nombre=dto.nombre or usuario.nombre, apellidos=dto.apellidos or usuario.apellidos,
                telefono=dto.telefono, direccion=dto.direccion, id_rol=id_rol, version=usuario.version)
        except ErrorPydantic as exc:
            error = exc.errors()[0]
            raise ValidationError(code="VAL_ENTRADA", field=str(error["loc"][-1]),
                                  message=str(error["msg"]).removeprefix("Value error, ")) from exc
        return self.editar_perfil.execute(usuario.id_usuario, cambios, usuario_actual)
