# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-80: retención por tipo e intentos      |
"""Implementación SQLAlchemy del puerto :class:`AuditoriaSuministroPort` (RF-78/79, CU-05).

Usa ``flush()`` (nunca ``commit()``) y traduce errores de BD con
``raise_from_db_error``. ``hash_integridad`` lo calcula el trigger de BD
(``trg_audit_hash``); no se asigna aquí. ``clasificacion_registro``/
``retencion_aplicable`` salen del tipo de evento (RF-80 Fase 3) y
``fecha_emision`` es el ``timestamp_emision`` de M05 (RNF-08).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import clasificar_retencion
from src.supplies.infrastructure.models.auditoria_suministro_model import AuditoriaSuministroModel


class SqlAlchemyAuditoriaSuministroRepository(AuditoriaSuministroPort):
    """Adaptador SQLAlchemy para ``modulo5.auditorias_suministros`` (eventos RF-78/79)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(self, evento: EventoAuditoriaSuministro) -> None:
        clasificacion, retencion = clasificar_retencion(evento.tipo_operacion)
        orm = AuditoriaSuministroModel(
            entidad_afectada=evento.entidad_afectada,
            tipo_operacion=evento.tipo_operacion,
            id_usuario=evento.id_usuario,
            resultado=evento.resultado,
            id_activo_biologico=evento.id_activo_biologico,
            id_ciclo_productivo=evento.id_ciclo_productivo,
            id_gestion_fases=evento.id_gestion_fases,
            costo_afectado=evento.costo_afectado,
            origen_precio=evento.origen_precio,
            detalle_causa=evento.detalle_causa,
            numero_reintentos=evento.numero_reintentos,
            registro_incompleto=evento.registro_incompleto,
            fecha_intentos=evento.fecha_intentos or None,
            fecha_emision=evento.fecha_emision or datetime.now(timezone.utc),
            clasificacion_registro=clasificacion,
            retencion_aplicable=retencion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
