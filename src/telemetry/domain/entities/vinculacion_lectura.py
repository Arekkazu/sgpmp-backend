# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: estados DB-13 y contexto historico |
# | 2026-10-25 | Arekkazu | USAB-M03 T-18 RF-61: nombres de activo, área, finca, variable y usuario (read-model) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y método |
"""Entidad de dominio de la vinculación entre una lectura y un activo biológico (RF-61).

Una lectura puede quedar CONFIRMADA, AMBIGUA, SIN_VINCULAR, PENDIENTE_REVISION
o SUPERADA. La entidad permite resolver manualmente las abiertas y conserva el
contexto del activo para el read-model de la tabla de vinculaciones.
"""
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
    """Vínculo entre una lectura de telemetría y el activo/infraestructura al que pertenece.

    Los campos de nombre y valor de lectura se llenan al leer (read-model) y no
    se persisten. ``resolver`` solo aplica a vinculaciones abiertas.
    """

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
        """Confirma manualmente la vinculación y la asigna al activo indicado.

        Args:
            id_activo_biologico: Activo al que se asocia la lectura.
            id_usuario: Usuario que realiza la corrección.

        Raises:
            BusinessRuleError: Si la vinculación ya está cerrada o su estado no
                admite resolución manual.
        """
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
