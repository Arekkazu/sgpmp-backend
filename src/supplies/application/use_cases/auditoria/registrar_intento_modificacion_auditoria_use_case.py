# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: registrar intentos de alterar la bitácora sin modificar el evento solicitado. |
"""Audita el intento autenticado; no consulta ni modifica el registro objetivo."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort, EventoAuditoriaSuministro,
)

logger = logging.getLogger(__name__)
_OPERACIONES = {'PUT': ('UPDATE', 'actualización'), 'PATCH': ('UPDATE', 'actualización parcial'),
                'DELETE': ('DELETE', 'eliminación'), 'POST': ('INSERT', 'inserción')}


class RegistrarIntentoModificacionAuditoriaUseCase:
    def __init__(self, db: Session, auditoria_port: AuditoriaSuministroPort) -> None:
        self.db = db
        self.auditoria_port = auditoria_port

    def execute(self, *, id_usuario: int, id_registro_solicitado: int, metodo: str) -> None:
        operacion, accion = _OPERACIONES[metodo]
        evento = EventoAuditoriaSuministro(
            entidad_afectada='auditorias_suministros', tipo_operacion=operacion,
            id_usuario=id_usuario, resultado='RECHAZADO', numero_reintentos=0,
            detalle_causa=(f'Se rechazó una solicitud de {accion} del registro {id_registro_solicitado} '
                           'de la bitácora, que es de solo lectura.'),
        )
        try:
            self.auditoria_port.registrar(evento)
            self.db.commit()
        except Exception:
            # El intento nunca adquiere capacidad de modificación si falla la auditoría.
            logger.error('No se pudo auditar un intento de modificación: usuario=%s evento=%s',
                         id_usuario, evento.id_evento_m05)
            try:
                self.db.rollback()
            except Exception:
                logger.error('No se pudo revertir la auditoría del intento de modificación.')
