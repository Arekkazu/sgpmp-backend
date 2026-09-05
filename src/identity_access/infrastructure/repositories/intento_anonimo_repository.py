"""Implementación SQLAlchemy del puerto :class:`IntentoAnonimoRepository`."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.intento_anonimo_repository import (
    IntentoAnonimoRepository,
)
from src.identity_access.infrastructure.models.intentos_anonimos_ip_model import (
    IntentosAnonimosIp,
)


class SqlAlchemyIntentoAnonimoRepository(IntentoAnonimoRepository):
    """Adaptador SQLAlchemy para ``modulo1.intentos_anonimos_ip``."""

    def __init__(self, db: Session):
        self.db = db

    def registrar(self, tipo: str, ip: str) -> None:
        self.db.add(IntentosAnonimosIp(tipo=tipo, ip=ip))
        self.db.flush()

    def contar_por_ip(self, tipo: str, ip: str, desde: datetime) -> int:
        return (
            self.db.query(func.count(IntentosAnonimosIp.id_intento))
            .filter(
                IntentosAnonimosIp.tipo == tipo,
                IntentosAnonimosIp.ip == ip,
                IntentosAnonimosIp.fecha >= desde,
            )
            .scalar()
        )

    def obtener_fecha_mas_antigua_por_ip(
        self, tipo: str, ip: str, desde: datetime
    ) -> Optional[datetime]:
        return (
            self.db.query(func.min(IntentosAnonimosIp.fecha))
            .filter(
                IntentosAnonimosIp.tipo == tipo,
                IntentosAnonimosIp.ip == ip,
                IntentosAnonimosIp.fecha >= desde,
            )
            .scalar()
        )
