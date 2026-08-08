"""Implementación SQLAlchemy del puerto de dominio :class:`UsuarioRepository`.

Es el **único punto** donde se cruza la frontera entre el modelo ORM
(``Usuarios``) y la entidad de dominio (:class:`Usuario`). Traduce en ambos
sentidos: ORM → entidad al leer y entidad → ORM al escribir. El resto de la
aplicación trabaja siempre con la entidad pura.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.exc import InternalError
from sqlalchemy.orm import Session, joinedload

from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.entities.usuario_detalle import UsuarioDetalle
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios
from src.identity_access.infrastructure.models.enums_models import EnumUsuarioGenero
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import ConflictError, PreconditionFailedError


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
            genero=EnumUsuarioGenero(usuario.genero) if usuario.genero is not None else None,
            contrasena_cifrada=usuario.contrasena.hash,
            direccion=usuario.direccion,
            id_rol=usuario.id_rol,
        )

    @staticmethod
    def _a_detalle(orm: Usuarios) -> UsuarioDetalle:
        """Construye la proyección de lectura desde el grafo ORM (usuario+rol+estado)."""
        return UsuarioDetalle(
            id_usuario=orm.id_usuario,
            nombre=orm.nombre,
            apellidos=orm.apellidos,
            correo_electronico=orm.correo_electronico,
            tipo_identificacion=orm.tipo_identificacion,
            numero_identificacion=orm.numero_identificacion,
            fecha_nacimiento=orm.fecha_nacimiento,
            fecha_registro=orm.fecha_registro,
            nombre_rol=orm.roles.nombre_rol,
            estado_cuenta=(
                orm.cuentas_usuarios.estados_cuentas.nombre if orm.cuentas_usuarios else None
            ),
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
        # Cubre el alta (id_usuario None → INSERT). La actualización de un
        # usuario existente se hace en :meth:`actualizar` (con optimistic lock).
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

    def cambiar_contrasena(self, usuario: Usuario) -> None:
        # Un trigger de DB eleva InternalError con "CONSTRAINT_VIOLATION" si la
        # contraseña ya fue usada recientemente; se traduce a ConflictError 409.
        orm = self.db.get(Usuarios, usuario.id_usuario)
        orm.contrasena_cifrada = usuario.contrasena.hash
        try:
            self.db.flush()
        except InternalError as e:
            self.db.rollback()
            if "CONSTRAINT_VIOLATION" in str(e.orig):
                raise ConflictError(
                    code="CONTRASENA_REUTILIZADA",
                    message=(
                        "Seguridad de credenciales: No se permite reutilizar la contraseña actual. "
                        "Por favor, defina una clave completamente nueva."
                    ),
                )
            raise
        except Exception as e:
            raise_from_db_error(e, conflict_messages={})

    def actualizar(self, usuario: Usuario, version_cliente: int) -> Usuario:
        orm = self.db.get(Usuarios, usuario.id_usuario)
        if orm.version != version_cliente:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message=(
                    "Conflicto de edición. Los datos del usuario han sido actualizados recientemente "
                    "por otro proceso. Por favor, recargue la página para obtener la información "
                    "más reciente antes de editar."
                ),
            )
        orm.nombre = usuario.nombre
        orm.apellidos = usuario.apellidos
        orm.correo_electronico = str(usuario.correo)
        orm.telefono = usuario.telefono
        orm.direccion = usuario.direccion
        orm.id_rol = usuario.id_rol
        orm.tipo_identificacion = usuario.tipo_identificacion
        orm.numero_identificacion = usuario.numero_identificacion
        orm.fecha_nacimiento = usuario.fecha_nacimiento
        orm.genero = EnumUsuarioGenero(usuario.genero) if usuario.genero is not None else None
        try:
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as e:
            raise_from_db_error(e, conflict_messages={
                "uq_usuario_correo_electronico": (
                    "Actualización denegada. La dirección ingresada ya se encuentra vinculada "
                    "a otra cuenta. El correo debe ser único."
                ),
                "uq_usuario_numero_identificacion": (
                    "Actualización denegada. El número de identificación ya se encuentra "
                    "vinculado a otra cuenta."
                ),
            })

    def obtener_detalle(self, id_usuario: int) -> Optional[UsuarioDetalle]:
        orm = (
            self.db.query(Usuarios)
            .options(
                joinedload(Usuarios.roles),
                joinedload(Usuarios.cuentas_usuarios).joinedload(CuentasUsuarios.estados_cuentas),
            )
            .filter(Usuarios.id_usuario == id_usuario)
            .first()
        )
        return self._a_detalle(orm) if orm else None

    def listar_detalle(
        self,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
        offset: int,
        limit: int,
    ) -> list[UsuarioDetalle]:
        query = self._query_detalle_con_filtros(nombre, correo, id_estado, id_rol)
        return [self._a_detalle(o) for o in query.offset(offset).limit(limit).all()]

    def contar(
        self,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
    ) -> int:
        return self._query_detalle_con_filtros(nombre, correo, id_estado, id_rol).count()

    def _query_detalle_con_filtros(self, nombre, correo, id_estado, id_rol):
        query = (
            self.db.query(Usuarios)
            .join(CuentasUsuarios, CuentasUsuarios.id_usuario == Usuarios.id_usuario)
            .options(
                joinedload(Usuarios.roles),
                joinedload(Usuarios.cuentas_usuarios).joinedload(CuentasUsuarios.estados_cuentas),
            )
        )
        if nombre:
            query = query.filter(
                or_(
                    Usuarios.nombre.ilike(f"%{nombre}%"),
                    Usuarios.apellidos.ilike(f"%{nombre}%"),
                )
            )
        if correo:
            query = query.filter(Usuarios.correo_electronico.ilike(f"%{correo}%"))
        if id_estado is not None:
            query = query.filter(CuentasUsuarios.id_estado_cuenta == id_estado)
        if id_rol is not None:
            query = query.filter(Usuarios.id_rol == id_rol)
        return query
