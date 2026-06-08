"""Implementación SQLAlchemy del puerto de dominio :class:`UsuarioRepository`.

Es el **único punto** donde se cruza la frontera entre el modelo ORM
(``Usuarios``) y la entidad de dominio (:class:`Usuario`). Traduce en ambos
sentidos: ORM → entidad al leer y entidad → ORM al escribir. El resto de la
aplicación trabaja siempre con la entidad pura.

Convive con el repositorio heredado ``usuarios_repository.py``
(``UsuariosSQLRepository``), que devuelve modelos ORM y todavía usan los demás
casos de uso. Este archivo es el patrón objetivo; aquel es el patrón a migrar.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyUsuarioRepository(UsuarioRepository):
    """Adaptador SQLAlchemy que mapea entre la tabla ``usuarios`` y la entidad."""

    def __init__(self, db: Session):
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────
    @staticmethod
    def _a_entidad(orm: Usuarios) -> Usuario:
        """Convierte una fila ORM en la entidad de dominio."""
        return Usuario(
            id_usuario=orm.id_usuario,
            correo=Email(orm.correo_electronico),
            contrasena=Contrasena.desde_hash(orm.contrasena_cifrada),
            nombre=orm.nombre,
            apellidos=orm.apellidos,
            fecha_nacimiento=orm.fecha_nacimiento,
            genero=getattr(orm.genero, "value", orm.genero),
            tipo_identificacion=orm.tipo_identificacion,
            numero_identificacion=orm.numero_identificacion,
            id_rol=orm.id_rol,
            telefono=orm.telefono,
            direccion=orm.direccion,
            version=orm.version,
            fecha_registro=orm.fecha_registro,
        )

    @staticmethod
    def _a_orm(usuario: Usuario) -> Usuarios:
        """Construye una fila ORM nueva a partir de la entidad (alta)."""
        return Usuarios(
            correo_electronico=str(usuario.correo),
            telefono=usuario.telefono,
            tipo_identificacion=usuario.tipo_identificacion,
            numero_identificacion=usuario.numero_identificacion,
            nombre=usuario.nombre,
            apellidos=usuario.apellidos,
            fecha_nacimiento=usuario.fecha_nacimiento,
            genero=EnumUsuarioGenero(usuario.genero),
            contrasena_cifrada=usuario.contrasena.hash,
            direccion=usuario.direccion,
            id_rol=usuario.id_rol,
        )

    # ── Operaciones del puerto ──────────────────────────────────────────────
    def obtener_por_id(self, id_usuario: int) -> Optional[Usuario]:
        orm = self.db.query(Usuarios).filter(Usuarios.id_usuario == id_usuario).first()
        return self._a_entidad(orm) if orm else None

    def obtener_por_correo(self, correo: Email) -> Optional[Usuario]:
        orm = (
            self.db.query(Usuarios)
            .filter(Usuarios.correo_electronico == str(correo))
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, usuario: Usuario) -> Usuario:
        # Esta referencia cubre el alta (id_usuario None → INSERT). La
        # actualización de un usuario existente se resolvería re-adjuntando la
        # fila ORM y copiando los campos modificados; queda fuera de este slice.
        orm = self._a_orm(usuario)
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as e:
            raise_from_db_error(e, conflict_messages={
                "uq_usuario_correo_electronico": "El correo electrónico ya está registrado",
                "uq_usuario_numero_identificacion": "El número de identificación ya está registrado",
            })
        return self._a_entidad(orm)
