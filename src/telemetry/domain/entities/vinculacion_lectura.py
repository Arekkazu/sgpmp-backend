from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.shared.errors import BusinessRuleError


@dataclass
class VinculacionLectura:
    id_vinculacion_lectura: Optional[int]
    id_telemetria: int
    modelo_manejo: str
    id_activo_biologico: Optional[int]
    id_infraestructura: int
    fecha_inicio_vinculacion: datetime
    fecha_fin_vinculacion: Optional[datetime]
    mecanismo_vinculacion: str
    estado_vinculacion: str
    id_usuario: Optional[int]
    motivo_correccion: Optional[str]
    id_vinculacion_reemplazada: Optional[int]
    fecha_creacion: datetime

    def resolver(self, id_activo_biologico: int, id_usuario: int) -> None:
        if self.estado_vinculacion != 'AMBIGUA':
            raise BusinessRuleError(
                code='VINCULACION_NO_AMBIGUA',
                message='Solo se pueden resolver vinculaciones en estado AMBIGUA.',
            )
        self.id_activo_biologico = id_activo_biologico
        self.estado_vinculacion = 'VINCULADA'
        self.mecanismo_vinculacion = 'MANUAL'
        self.id_usuario = id_usuario
