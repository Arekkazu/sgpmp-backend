from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.infrastructure.models.bitacora_auditoria_m02_model import BitacoraAuditoriaM02Model


def _calcular_hash(evento: EventoAuditoria, ts_registro: datetime) -> str:
    payload = {
        'rf_origen': evento.rf_origen,
        'tipo_evento': evento.tipo_evento,
        'clasificacion_biologica': evento.clasificacion_biologica,
        'id_activo_biologico': evento.id_activo_biologico,
        'timestamp_evento': evento.timestamp_evento.isoformat(),
        'timestamp_registro': ts_registro.isoformat(),
        'resultado': evento.resultado,
        'id_usuario_responsable': evento.id_usuario_responsable,
        'severidad_log': evento.severidad_log,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


class SqlAlchemyBitacoraAuditoriaRepository(BitacoraAuditoriaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(self, evento: EventoAuditoria) -> None:
        ts_registro = datetime.now(timezone.utc)
        hash_integridad = _calcular_hash(evento, ts_registro)
        orm = BitacoraAuditoriaM02Model(
            rf_origen=evento.rf_origen,
            tipo_evento=evento.tipo_evento,
            clasificacion_biologica=evento.clasificacion_biologica,
            id_activo_biologico=evento.id_activo_biologico,
            tipo_activo=evento.tipo_activo,
            timestamp_evento=evento.timestamp_evento,
            timestamp_registro=ts_registro,
            resultado=evento.resultado,
            descripcion=evento.descripcion,
            detalle_tecnico=evento.detalle_tecnico,
            id_usuario_responsable=evento.id_usuario_responsable,
            modulo_consumidor=evento.modulo_consumidor,
            severidad_log=evento.severidad_log,
            id_evento_correlacionado=evento.id_evento_correlacionado,
            hash_integridad=hash_integridad,
            registro_incompleto=evento.registro_incompleto,
        )
        self.db.add(orm)
        self.db.flush()

    def consultar(
        self,
        rf_origen: Optional[str],
        tipo_evento: Optional[str],
        id_activo_biologico: Optional[int],
        clasificacion_biologica: Optional[str],
        resultado: Optional[str],
        severidad_log: Optional[str],
        fecha_inicio: Optional[datetime],
        fecha_fin: Optional[datetime],
        pagina: int,
        page_size: int,
    ) -> tuple[list[EventoAuditoria], int]:
        q = self.db.query(BitacoraAuditoriaM02Model)

        if rf_origen is not None:
            q = q.filter(BitacoraAuditoriaM02Model.rf_origen == rf_origen)
        if tipo_evento is not None:
            q = q.filter(BitacoraAuditoriaM02Model.tipo_evento == tipo_evento)
        if id_activo_biologico is not None:
            q = q.filter(BitacoraAuditoriaM02Model.id_activo_biologico == id_activo_biologico)
        if clasificacion_biologica is not None:
            q = q.filter(BitacoraAuditoriaM02Model.clasificacion_biologica == clasificacion_biologica)
        if resultado is not None:
            q = q.filter(BitacoraAuditoriaM02Model.resultado == resultado)
        if severidad_log is not None:
            q = q.filter(BitacoraAuditoriaM02Model.severidad_log == severidad_log)
        if fecha_inicio is not None:
            q = q.filter(BitacoraAuditoriaM02Model.timestamp_evento >= fecha_inicio)
        if fecha_fin is not None:
            q = q.filter(BitacoraAuditoriaM02Model.timestamp_evento <= fecha_fin)

        total = q.count()
        registros_orm = (
            q.order_by(
                BitacoraAuditoriaM02Model.timestamp_evento.desc(),
                BitacoraAuditoriaM02Model.id_bitacora.desc(),
            )
            .offset((pagina - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [self._a_entidad(r) for r in registros_orm], total

    def _a_entidad(self, orm: BitacoraAuditoriaM02Model) -> EventoAuditoria:
        return EventoAuditoria(
            rf_origen=orm.rf_origen,
            tipo_evento=orm.tipo_evento,
            clasificacion_biologica=orm.clasificacion_biologica,
            timestamp_evento=orm.timestamp_evento,
            resultado=orm.resultado,
            severidad_log=orm.severidad_log,
            id_activo_biologico=orm.id_activo_biologico,
            tipo_activo=orm.tipo_activo,
            descripcion=orm.descripcion,
            detalle_tecnico=orm.detalle_tecnico,
            id_usuario_responsable=orm.id_usuario_responsable,
            modulo_consumidor=orm.modulo_consumidor,
            id_evento_correlacionado=orm.id_evento_correlacionado,
            id_bitacora=orm.id_bitacora,
            id_evento=orm.id_evento,
            timestamp_registro=orm.timestamp_registro,
            hash_integridad=orm.hash_integridad,
            registro_incompleto=orm.registro_incompleto,
        )
