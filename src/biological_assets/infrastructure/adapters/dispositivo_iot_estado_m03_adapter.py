from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.dispositivo_iot_estado_port import (
    DispositivoIotEstadoPort,
    EstadoDispositivoIot,
)


class DispositivoIotEstadoM03Adapter(DispositivoIotEstadoPort):
    """Consulta modulo3.estados_dispositivos_iot (UNIQUE por id_dispositivo_iot) para el heartbeat."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_estado(self, id_dispositivo_iot: int) -> Optional[EstadoDispositivoIot]:
        row = self.db.execute(
            text(
                'SELECT id_dispositivo_iot, fecha_ultimo_contacto '
                'FROM modulo3.estados_dispositivos_iot '
                'WHERE id_dispositivo_iot = :id_dispositivo_iot'
            ),
            {'id_dispositivo_iot': id_dispositivo_iot},
        ).fetchone()

        if row is None:
            return None

        return EstadoDispositivoIot(
            id_dispositivo_iot=row.id_dispositivo_iot,
            fecha_ultimo_contacto=row.fecha_ultimo_contacto,
        )
