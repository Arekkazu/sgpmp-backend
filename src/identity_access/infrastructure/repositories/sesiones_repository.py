"""Implementación SQLAlchemy del port de sesiones y auditoría.

Gestiona tokens de acceso, sesiones activas y el registro de eventos con
hash de integridad SHA-256 para detectar manipulación del log.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func

from sqlalchemy.orm import Session

from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado, EnumTokenTipo
from src.identity_access.infrastructure.models.eventos_model import Eventos
from src.identity_access.infrastructure.models.sesiones_model import Sesiones
from src.identity_access.infrastructure.models.tokens_model import Tokens
from src.shared.db_error_translator import raise_from_db_error


class SesionesSQLRepository(SesionesPort):
    """Repositorio SQLAlchemy para `Sesiones`, `Tokens` y `Eventos`."""

    def __init__(self, db: Session):
        self.db = db

    def buscar_sesion_activa(self, id_cuenta_usuario: int) -> Optional[Sesiones]:
        return (
            self.db.query(Sesiones)
            .filter(
                Sesiones.id_cuenta_usuario == id_cuenta_usuario,
                Sesiones.es_activa.is_(True),
            )
            .first()
        )

    def buscar_sesion_por_token(self, id_token: int) -> Optional[Sesiones]:
        return (
            self.db.query(Sesiones)
            .filter(Sesiones.id_token == id_token)
            .first()
        )

    def invalidar_sesion(self, sesion: Sesiones) -> None:
        ahora = datetime.now(timezone.utc)
        sesion.es_activa = False
        sesion.fecha_finalizacion = ahora
        token = self.db.query(Tokens).filter(Tokens.id_token == sesion.id_token).first()
        if token is not None:
            token.fecha_uso = ahora
        self.db.flush()

    def crear_token_acceso(self, fecha_expiracion: datetime) -> Tokens:
        token = Tokens(
            token_tipo=EnumTokenTipo.ACCESO,
            fecha_expiracion=fecha_expiracion,
        )
        try:
            self.db.add(token)
            self.db.flush()
            self.db.refresh(token)
            return token
        except Exception as e:
            raise_from_db_error(e, conflict_messages={})

    def crear_sesion(
        self,
        id_cuenta_usuario: int,
        id_token: int,
        direccion_ip: str,
        agente_usuario: str,
        fecha_expiracion: datetime,
    ) -> Sesiones:
        ahora = datetime.now(timezone.utc)
        sesion = Sesiones(
            id_cuenta_usuario=id_cuenta_usuario,
            id_token=id_token,
            direccion_ip=direccion_ip,
            agente_usuario=agente_usuario,
            fecha_inicio=ahora,
            fecha_finalizacion=fecha_expiracion,
            es_activa=True,
        )
        try:
            self.db.add(sesion)
            self.db.flush()
            self.db.refresh(sesion)
            return sesion
        except Exception as e:
            raise_from_db_error(e, conflict_messages={})

    def registrar_evento(
        self,
        tipo_evento: int,
        resultado: EnumEventoResultado,
        id_usuario: int,
        detalle: dict,
        id_sesion: Optional[int] = None,
    ) -> None:
        # El hash SHA-256 cubre los campos clave del evento para detectar
        # modificaciones posteriores en la tabla de auditoría.
        fecha = datetime.now(timezone.utc)
        contenido_hash = json.dumps({
            "tipo_evento": tipo_evento,
            "fecha_evento": fecha.isoformat(),
            "id_usuario": id_usuario,
            "resultado": resultado.value,
            "modulo": "MODULO1",
            "detalle": detalle,
        }, sort_keys=True, default=str)
        hash_integridad = hashlib.sha256(contenido_hash.encode("utf-8")).hexdigest()

        evento = Eventos(
            tipo_evento=tipo_evento,
            fecha_evento=fecha,
            modulo="MODULO1",
            resultado=resultado,
            detalle=detalle,
            id_usuario=id_usuario,
            categoria="AUTENTICACION",
            estado="PROCESADO",
            id_sesion=id_sesion,
            hash_integridad=hash_integridad,
        )
        self.db.add(evento)
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
        for sesion in sesiones:
            sesion.es_activa = False
            sesion.fecha_finalizacion = ahora
            token = self.db.query(Tokens).filter(Tokens.id_token == sesion.id_token).first()
            if token is not None and token.fecha_uso is None:
                token.fecha_uso = ahora
        self.db.flush()

    def contar_solicitudes_recuperacion_por_ip(self, ip: str, desde: datetime) -> int:
        # .astext extrae el valor de texto de la columna JSONB sin comillas adicionales.
        return (
            self.db.query(func.count(Eventos.id_evento))
            .filter(
                Eventos.tipo_evento == 7,
                Eventos.fecha_evento >= desde,
                Eventos.detalle["ip"].astext == ip,
            )
            .scalar()
        )
