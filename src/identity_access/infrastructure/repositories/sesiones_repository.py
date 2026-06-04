from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado, EnumTokenTipo
from src.identity_access.infrastructure.models.eventos_model import Eventos
from src.identity_access.infrastructure.models.sesiones_model import Sesiones
from src.identity_access.infrastructure.models.tokens_model import Tokens
from src.shared.db_error_translator import raise_from_db_error


class SesionesSQLRepository(SesionesPort):

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
        evento = Eventos(
            tipo_evento=tipo_evento,
            fecha_evento=datetime.now(timezone.utc),
            modulo="MODULO1",
            resultado=resultado,
            detalle=detalle,
            id_usuario=id_usuario,
            categoria="AUTENTICACION",
            estado="PROCESADO",
            id_sesion=id_sesion,
        )
        self.db.add(evento)
        self.db.flush()
