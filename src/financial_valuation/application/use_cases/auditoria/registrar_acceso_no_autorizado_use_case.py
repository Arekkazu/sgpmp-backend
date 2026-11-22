# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-306-G07 RF-82: el 403 RBAC de M06 queda en la auditoría financiera |
"""RNF-82-05: el intento de un rol no autorizado se rechaza y queda en RF-94 (``ACCESO_NO_AUTORIZADO``).

Se confirma en su propia transacción porque la operación pedida no se ejecuta. Un fallo al
escribir el evento se revierte y va al log técnico, pero no reemplaza el ``403`` original.

Los ids que trae la URL van en el payload y no en las columnas con FK: los envía alguien sin
permiso y pueden no existir, lo que haría fallar el INSERT y perder justo el evento que se busca."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository

logger = logging.getLogger(__name__)


class RegistrarAccesoNoAutorizadoUseCase:
    def __init__(self, db: Session, auditoria: AuditoriaFinancieraRepository) -> None:
        self.db = db
        self.auditoria = auditoria

    def execute(self, *, id_usuario: int, id_rol: int, recurso: str, id_accion: int, error_code: str,
                metodo_http: str, ruta: str, id_activo_biologico: Optional[int] = None,
                id_periodo_contable: Optional[int] = None) -> bool:
        evento = EventoAuditoria(
            tipo_evento="ACCESO_NO_AUTORIZADO", severidad="WARNING", id_usuario=id_usuario,
            payload={"descripcion": "Solicitud rechazada: el rol del usuario no tiene permiso para esta operación.",
                     "error_code": error_code, "id_rol": id_rol, "recurso": recurso, "id_accion": id_accion,
                     "metodo_http": metodo_http, "ruta": ruta, "id_activo_biologico": id_activo_biologico,
                     "id_periodo_contable": id_periodo_contable},
        )
        try:
            self.auditoria.registrar(evento)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            logger.exception("No se pudo registrar ACCESO_NO_AUTORIZADO en M06 para el usuario %s.", id_usuario)
            return False
