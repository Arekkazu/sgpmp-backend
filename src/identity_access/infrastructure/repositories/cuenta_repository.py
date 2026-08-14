"""Implementación SQLAlchemy del puerto de dominio :class:`CuentaRepository`.

Mapea entre la tabla ``cuentas_usuarios`` y la entidad :class:`Cuenta`, y
registra gestiones administrativas en ``gestiones_cuenta``. Las transiciones de
estado y los contadores de seguridad los decide la entidad; aquí solo se
persisten.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios
from src.identity_access.infrastructure.models.enums_models import EnumAccionCuenta
from src.identity_access.infrastructure.models.gestiones_cuenta_model import GestionesCuenta
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error



class SqlAlchemyCuentaRepository(CuentaRepository):
    """Adaptador SQLAlchemy para ``cuentas_usuarios`` y ``gestiones_cuenta``."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _a_entidad(orm: CuentasUsuarios) -> Cuenta:
        """Convierte una fila ORM ``CuentasUsuarios`` en la entidad :class:`Cuenta`."""
        return Cuenta(
            id_cuenta_usuario=orm.id_cuenta_usuario,
            id_usuario=orm.id_usuario,
            id_estado_cuenta=orm.id_estado_cuenta,
            tiene_correo_verificado=orm.tiene_correo_verificado,
            intentos_fallidos=orm.intentos_fallidos,
            fecha_verificacion=orm.fecha_verificacion,
            ultimo_acceso=orm.ultimo_acceso,
            bloqueado_hasta=orm.bloqueado_hasta,
            ultimo_intento_fallido=orm.ultimo_intento_fallido,
            token_activacion_actual=orm.token_activacion_actual,
            fecha_cambio_estado=orm.fecha_cambio_estado,
            motivo_ultimo_cambio=orm.motivo_ultimo_cambio,
        )

    @staticmethod
    def _aplicar_a_orm(cuenta: Cuenta, orm: CuentasUsuarios) -> None:
        """Copia el estado mutable de la entidad sobre la fila ORM gestionada."""
        orm.id_estado_cuenta = cuenta.id_estado_cuenta
        orm.tiene_correo_verificado = cuenta.tiene_correo_verificado
        orm.intentos_fallidos = cuenta.intentos_fallidos
        orm.fecha_verificacion = cuenta.fecha_verificacion
        orm.ultimo_acceso = cuenta.ultimo_acceso
        orm.bloqueado_hasta = cuenta.bloqueado_hasta
        orm.ultimo_intento_fallido = cuenta.ultimo_intento_fallido
        orm.token_activacion_actual = cuenta.token_activacion_actual
        orm.fecha_cambio_estado = cuenta.fecha_cambio_estado
        orm.motivo_ultimo_cambio = cuenta.motivo_ultimo_cambio

    def crear(self, id_usuario: int, token: str, id_estado_cuenta: Optional[int] = None) -> Cuenta:
        orm = CuentasUsuarios(
            id_usuario=id_usuario,
            id_estado_cuenta=id_estado_cuenta if id_estado_cuenta is not None else Cuenta.ESTADO_PENDIENTE,
            token_activacion_actual=token,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as e:
            raise_from_db_error(e, conflict_messages={
                "uq_usuario": "El usuario ya tiene una cuenta asociada",
            })

    def obtener_por_usuario(self, id_usuario: int) -> Optional[Cuenta]:
        orm = (
            self.db.query(CuentasUsuarios)
            .filter(CuentasUsuarios.id_usuario == id_usuario)
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def obtener_por_token(self, token: str) -> Optional[Cuenta]:
        orm = (
            self.db.query(CuentasUsuarios)
            .filter(CuentasUsuarios.token_activacion_actual == token)
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, cuenta: Cuenta) -> Cuenta:
        orm = self.db.get(CuentasUsuarios, cuenta.id_cuenta_usuario)
        self._aplicar_a_orm(cuenta, orm)
        self.db.flush()
        self.db.refresh(orm)
        return self._a_entidad(orm)

    def registrar_gestion(
        self,
        id_cuenta_usuario: int,
        accion: str,
        motivo: str,
        id_responsable: int,
    ) -> None:
        gestion = GestionesCuenta(
            id_cuenta_usuario=id_cuenta_usuario,
            accion_cuenta=EnumAccionCuenta(accion),
            motivo_accion=motivo,
            fecha_accion=datetime.now(timezone.utc),
            id_usuario_responsable=id_responsable,
        )
        self.db.add(gestion)
        self.db.flush()

    def contar_usuarios_activos_por_rol(self, id_rol: int) -> int:
        return (
            self.db.query(CuentasUsuarios)
            .join(Usuarios, Usuarios.id_usuario == CuentasUsuarios.id_usuario)
            .filter(
                Usuarios.id_rol == id_rol,
                CuentasUsuarios.id_estado_cuenta == Cuenta.ESTADO_ACTIVO,
            )
            .count()
        )
