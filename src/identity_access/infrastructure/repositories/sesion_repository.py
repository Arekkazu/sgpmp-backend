"""Implementación SQLAlchemy del puerto de dominio :class:`SesionRepository`.

Mapea entre las tablas ``sesiones`` / ``tokens`` y las entidades :class:`Sesion`
y :class:`Token`. Las operaciones de invalidación cierran la sesión y marcan el
token asociado como usado (blacklist).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.sesion import Sesion
from src.identity_access.domain.entities.token import Token
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.infrastructure.models.enums_models import EnumTokenTipo
from src.identity_access.infrastructure.models.sesiones_model import Sesiones
from src.identity_access.infrastructure.models.tokens_model import Tokens
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemySesionRepository(SesionRepository):
    """Adaptador SQLAlchemy para ``sesiones`` y ``tokens``."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _sesion_a_entidad(orm: Sesiones) -> Sesion:
        return Sesion(
            id_sesion=orm.id_sesion,
            id_token=orm.id_token,
            direccion_ip=orm.direccion_ip,
            agente_usuario=orm.agente_usuario,
            fecha_inicio=orm.fecha_inicio,
            fecha_finalizacion=orm.fecha_finalizacion,
            es_activa=orm.es_activa,
            id_cuenta_usuario=orm.id_cuenta_usuario,
            id_token_refresco=orm.id_token_refresco,
        )

    @staticmethod
    def _token_a_entidad(orm: Tokens) -> Token:
        return Token(
            id_token=orm.id_token,
            token_tipo=getattr(orm.token_tipo, "value", orm.token_tipo),
            fecha_expiracion=orm.fecha_expiracion,
            fecha_uso=orm.fecha_uso,
            fecha_creacion=orm.fecha_creacion,
            hash_valor=orm.hash_valor,
            id_sesion=orm.id_sesion,
        )

    def buscar_sesion_activa(self, id_cuenta_usuario: int) -> Optional[Sesion]:
        orm = (
            self.db.query(Sesiones)
            .filter(
                Sesiones.id_cuenta_usuario == id_cuenta_usuario,
                Sesiones.es_activa.is_(True),
            )
            .first()
        )
        return self._sesion_a_entidad(orm) if orm else None

    def buscar_sesion_por_token(self, id_token: int) -> Optional[Sesion]:
        orm = self.db.query(Sesiones).filter(Sesiones.id_token == id_token).first()
        return self._sesion_a_entidad(orm) if orm else None

    def buscar_sesion_por_id(self, id_sesion: int) -> Optional[Sesion]:
        orm = self.db.get(Sesiones, id_sesion)
        return self._sesion_a_entidad(orm) if orm else None

    def buscar_token_por_hash(self, hash_valor: str) -> Optional[Token]:
        # FOR UPDATE (bloqueante, sin NOWAIT/SKIP LOCKED): dos refrescos
        # concurrentes con el mismo refresh token (dos tabs, doble clic, un
        # bootstrap de sesión que compite con un login explícito) deben
        # serializarse, no leer ambos "no usado" antes de que el primero
        # rote el token — eso producía un falso positivo de reuso que mataba
        # la sesión que el primero acababa de emitir. El segundo espera al
        # primero y relee `fecha_uso` ya actualizado.
        orm = (
            self.db.query(Tokens)
            .filter(Tokens.hash_valor == hash_valor)
            .with_for_update()
            .first()
        )
        return self._token_a_entidad(orm) if orm else None

    def invalidar_sesion(self, sesion: Sesion) -> None:
        ahora = datetime.now(timezone.utc)
        orm = self.db.get(Sesiones, sesion.id_sesion)
        orm.es_activa = False
        orm.fecha_finalizacion = ahora
        token = self.db.get(Tokens, orm.id_token)
        if token is not None and token.fecha_uso is None:
            token.fecha_uso = ahora
        if orm.id_token_refresco is not None:
            token_refresco = self.db.get(Tokens, orm.id_token_refresco)
            if token_refresco is not None and token_refresco.fecha_uso is None:
                token_refresco.fecha_uso = ahora
        self.db.flush()

    def invalidar_todas_sesiones(self, id_cuenta_usuario: int) -> None:
        ahora = datetime.now(timezone.utc)
        sesiones = (
            self.db.query(Sesiones)
            .filter(
                Sesiones.id_cuenta_usuario == id_cuenta_usuario,
                Sesiones.es_activa.is_(True),
            )
            .all()
        )
        for orm in sesiones:
            orm.es_activa = False
            orm.fecha_finalizacion = ahora
            token = self.db.get(Tokens, orm.id_token)
            if token is not None and token.fecha_uso is None:
                token.fecha_uso = ahora
            if orm.id_token_refresco is not None:
                token_refresco = self.db.get(Tokens, orm.id_token_refresco)
                if token_refresco is not None and token_refresco.fecha_uso is None:
                    token_refresco.fecha_uso = ahora
        self.db.flush()

    def crear_token_acceso(self, fecha_expiracion: datetime) -> Token:
        orm = Tokens(token_tipo=EnumTokenTipo.ACCESO, fecha_expiracion=fecha_expiracion)
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._token_a_entidad(orm)
        except Exception as e:
            raise_from_db_error(e, conflict_messages={})

    def crear_token_refresco(self, fecha_expiracion: datetime, hash_valor: str) -> Token:
        orm = Tokens(token_tipo=EnumTokenTipo.REFRESCO, fecha_expiracion=fecha_expiracion, hash_valor=hash_valor)
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._token_a_entidad(orm)
        except Exception as e:
            raise_from_db_error(e, conflict_messages={})

    def vincular_token_a_sesion(self, id_token: int, id_sesion: int) -> None:
        orm = self.db.get(Tokens, id_token)
        orm.id_sesion = id_sesion
        self.db.flush()

    def rotar_tokens(
        self,
        sesion: Sesion,
        nuevo_id_token_acceso: int,
        nuevo_id_token_refresco: int,
        nueva_fecha_expiracion: datetime,
    ) -> Sesion:
        ahora = datetime.now(timezone.utc)
        orm = self.db.get(Sesiones, sesion.id_sesion)

        token_acceso_viejo = self.db.get(Tokens, orm.id_token)
        if token_acceso_viejo is not None and token_acceso_viejo.fecha_uso is None:
            token_acceso_viejo.fecha_uso = ahora
        if orm.id_token_refresco is not None:
            token_refresco_viejo = self.db.get(Tokens, orm.id_token_refresco)
            if token_refresco_viejo is not None and token_refresco_viejo.fecha_uso is None:
                token_refresco_viejo.fecha_uso = ahora

        orm.id_token = nuevo_id_token_acceso
        orm.id_token_refresco = nuevo_id_token_refresco
        orm.fecha_finalizacion = nueva_fecha_expiracion

        self.db.flush()
        self.db.refresh(orm)
        return self._sesion_a_entidad(orm)

    def crear_sesion(
        self,
        id_cuenta_usuario: int,
        id_token: int,
        direccion_ip: str,
        agente_usuario: str,
        fecha_expiracion: datetime,
        id_token_refresco: Optional[int] = None,
    ) -> Sesion:
        ahora = datetime.now(timezone.utc)
        orm = Sesiones(
            id_cuenta_usuario=id_cuenta_usuario,
            id_token=id_token,
            direccion_ip=direccion_ip,
            agente_usuario=agente_usuario,
            fecha_inicio=ahora,
            fecha_finalizacion=fecha_expiracion,
            es_activa=True,
            id_token_refresco=id_token_refresco,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._sesion_a_entidad(orm)
        except Exception as e:
            raise_from_db_error(e, conflict_messages={})
