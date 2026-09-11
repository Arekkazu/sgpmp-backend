from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.telemetry.domain.entities.evento_auditoria_iot import (
    ClasificacionRegistro,
    ComponenteOrigen,
    EntidadAfectadaTipo,
    EventoAuditoriaIot,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.models.bitacora_auditoria_iot_model import BitacoraAuditoriaIotModel


class SqlAlchemyBitacoraAuditoriaIotRepository(BitacoraAuditoriaIotRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(self, evento: EventoAuditoriaIot) -> EventoAuditoriaIot:
        try:
            orm = BitacoraAuditoriaIotModel(
                id_usuario=evento.id_usuario,
                nombre_usuario=evento.nombre_usuario,
                tipo_evento=evento.tipo_evento,
                modulo=evento.modulo,
                descripcion=evento.descripcion,
                resultado=evento.resultado.value if isinstance(evento.resultado, TipoResultado) else evento.resultado,
                direccion_ip=evento.direccion_ip,
                user_agent=evento.user_agent,
                id_sesion=evento.id_sesion,
                fecha_hora=evento.fecha_hora,
                accion_detallada=evento.accion_detallada,
                entidad_afectada_tipo=evento.entidad_afectada_tipo.value if isinstance(evento.entidad_afectada_tipo, EntidadAfectadaTipo) else evento.entidad_afectada_tipo,
                entidad_afectada_id=evento.entidad_afectada_id,
                severidad_log=evento.severidad_log.value if isinstance(evento.severidad_log, SeveridadLog) else evento.severidad_log,
                hash_integridad=evento.hash_integridad,
                clasificacion_registro=evento.clasificacion_registro.value if isinstance(evento.clasificacion_registro, ClasificacionRegistro) else evento.clasificacion_registro,
                retencion_aplicable=evento.retencion_aplicable,
                registro_incompleto=evento.registro_incompleto,
                componente_origen=evento.componente_origen.value if isinstance(evento.componente_origen, ComponenteOrigen) else evento.componente_origen,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception:
            # Auditoría es best-effort: no propaga error para no bloquear flujo principal
            return evento

    def obtener(self, id_evento: UUID) -> Optional[EventoAuditoriaIot]:
        orm = self.db.query(BitacoraAuditoriaIotModel).filter(
            BitacoraAuditoriaIotModel.id_evento == id_evento
        ).first()
        return self._a_entidad(orm) if orm else None

    def listar(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        tipo_evento: Optional[str] = None,
        severidad_log: Optional[str] = None,
        clasificacion_registro: Optional[str] = None,
        entidad_afectada_id: Optional[str] = None,
        resultado: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list[EventoAuditoriaIot], int]:
        q = self.db.query(BitacoraAuditoriaIotModel)
        if fecha_desde:
            q = q.filter(BitacoraAuditoriaIotModel.fecha_hora >= fecha_desde)
        if fecha_hasta:
            q = q.filter(BitacoraAuditoriaIotModel.fecha_hora <= fecha_hasta)
        if tipo_evento:
            q = q.filter(BitacoraAuditoriaIotModel.tipo_evento == tipo_evento)
        if severidad_log:
            q = q.filter(BitacoraAuditoriaIotModel.severidad_log == severidad_log)
        if clasificacion_registro:
            q = q.filter(BitacoraAuditoriaIotModel.clasificacion_registro == clasificacion_registro)
        if entidad_afectada_id:
            q = q.filter(BitacoraAuditoriaIotModel.entidad_afectada_id == entidad_afectada_id)
        if resultado:
            q = q.filter(BitacoraAuditoriaIotModel.resultado == resultado)
        total = q.count()
        items = q.order_by(BitacoraAuditoriaIotModel.fecha_hora.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina).all()
        return [self._a_entidad(o) for o in items], total

    def listar_todos_para_verificacion(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> list[EventoAuditoriaIot]:
        q = self.db.query(BitacoraAuditoriaIotModel)
        if fecha_desde:
            q = q.filter(BitacoraAuditoriaIotModel.fecha_hora >= fecha_desde)
        if fecha_hasta:
            q = q.filter(BitacoraAuditoriaIotModel.fecha_hora <= fecha_hasta)
        return [self._a_entidad(o) for o in q.order_by(BitacoraAuditoriaIotModel.fecha_hora).all()]

    @staticmethod
    def _a_entidad(orm: BitacoraAuditoriaIotModel) -> EventoAuditoriaIot:
        return EventoAuditoriaIot(
            id_evento=orm.id_evento,
            tipo_evento=orm.tipo_evento,
            fecha_hora=orm.fecha_hora,
            resultado=TipoResultado(orm.resultado),
            modulo=orm.modulo,
            id_usuario=orm.id_usuario,
            nombre_usuario=orm.nombre_usuario,
            descripcion=orm.descripcion,
            direccion_ip=orm.direccion_ip,
            user_agent=orm.user_agent,
            id_sesion=orm.id_sesion,
            accion_detallada=orm.accion_detallada,
            entidad_afectada_tipo=EntidadAfectadaTipo(orm.entidad_afectada_tipo) if orm.entidad_afectada_tipo else None,
            entidad_afectada_id=orm.entidad_afectada_id,
            severidad_log=SeveridadLog(orm.severidad_log),
            hash_integridad=orm.hash_integridad,
            clasificacion_registro=ClasificacionRegistro(orm.clasificacion_registro),
            retencion_aplicable=orm.retencion_aplicable,
            registro_incompleto=orm.registro_incompleto,
            componente_origen=ComponenteOrigen(orm.componente_origen) if orm.componente_origen else None,
            timestamp_registro=orm.timestamp_registro,
        )
