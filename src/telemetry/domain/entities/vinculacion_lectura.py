# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: estados DB-13 y contexto historico |
# | 2026-10-25 | Arekkazu | USAB-M03 T-18 RF-61: nombres de activo, área, finca, variable y usuario (read-model) |
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.shared.errors import BusinessRuleError

# RF-61 Fase C1: el usuario resuelve una lectura AMBIGUA o SIN_VINCULAR (#494).
ESTADOS_VINCULACION = ('CONFIRMADA', 'AMBIGUA', 'SIN_VINCULAR', 'PENDIENTE_REVISION', 'SUPERADA')
_ESTADOS_RESOLUBLES = ('AMBIGUA', 'SIN_VINCULAR', 'PENDIENTE_REVISION')


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
    causa: Optional[str] = None
    contexto_activo: Optional[dict] = None
    # T-18 (read-model): la tabla de vinculaciones mostraba solo IDs (#115703, #854,
    # #391). Se llenan al leer; no se persisten.
    nombre_activo: Optional[str] = None
    especie_activo: Optional[str] = None
    nombre_infraestructura: Optional[str] = None
    nombre_finca: Optional[str] = None
    nombre_variable: Optional[str] = None
    nombre_sensor: Optional[str] = None
    valor_lectura: Optional[float] = None
    unidad_lectura: Optional[str] = None
    fecha_lectura: Optional[datetime] = None
    nombre_usuario: Optional[str] = None

    def resolver(self, id_activo_biologico: int, id_usuario: int) -> None:
        if self.fecha_fin_vinculacion is not None or self.estado_vinculacion not in _ESTADOS_RESOLUBLES:
            raise BusinessRuleError(
                code='VINCULACION_NO_AMBIGUA',
                message='Solo se pueden resolver vinculaciones abiertas AMBIGUA, SIN_VINCULAR o PENDIENTE_REVISION.',
            )
        self.id_activo_biologico = id_activo_biologico
        self.estado_vinculacion = 'CONFIRMADA'
        self.causa = None
        self.mecanismo_vinculacion = 'MANUAL'
        self.id_usuario = id_usuario
