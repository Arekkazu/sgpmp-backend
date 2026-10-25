# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: expone marca externa sin editar evidencia |
# | 2026-10-25 | Arekkazu | INC-M03-137-G179 RF-63 E8: sin componente identificable se clasifica NIC41 |
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class TipoResultado(str, Enum):
    EXITOSO = 'EXITOSO'
    FALLIDO = 'FALLIDO'
    PARCIAL = 'PARCIAL'
    RECHAZADO = 'RECHAZADO'
    ADVERTENCIA = 'ADVERTENCIA'


class EntidadAfectadaTipo(str, Enum):
    LECTURA = 'LECTURA'
    HEARTBEAT = 'HEARTBEAT'
    DISPOSITIVO = 'DISPOSITIVO'
    ALERTA = 'ALERTA'
    VINCULACION = 'VINCULACION'
    BUFFER = 'BUFFER'
    PAQUETE_IA = 'PAQUETE_IA'
    CALIDAD_DATO = 'CALIDAD_DATO'
    UMBRAL = 'UMBRAL'  # umbral ambiental de RF-17 (INC-M09-70-G29)


class SeveridadLog(str, Enum):
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


class ClasificacionRegistro(str, Enum):
    NIC41 = 'NIC41'
    TECNICO = 'TECNICO'


class ComponenteOrigen(str, Enum):
    RF17 = 'RF17'  # propagación de umbrales ambientales al Nodo Edge (INC-M09-70-G29)
    RF20 = 'RF20'  # propagación del tipo_modelo_asignado de un área al Gateway Edge (DEV-10)
    RF23 = 'RF23'  # credencial MQTT y Gateway Edge de los dispositivos (TC-M09-250/251)
    RF53 = 'RF53'
    RF54 = 'RF54'
    RF55 = 'RF55'
    RF56 = 'RF56'
    RF57 = 'RF57'
    RF58 = 'RF58'
    RF59 = 'RF59'
    RF60 = 'RF60'
    RF61 = 'RF61'
    RF62 = 'RF62'


# Componentes cuya clasificación es NIC41 (retención 5 años)
_COMPONENTES_NIC41 = {ComponenteOrigen.RF53, ComponenteOrigen.RF56, ComponenteOrigen.RF61, ComponenteOrigen.RF62}


def clasificar_componente(componente: Optional[ComponenteOrigen]) -> tuple[ClasificacionRegistro, int]:
    """Retorna (clasificacion, retencion_anios).

    RF-63 E8: si no se puede saber qué RF lo emitió la clasificación es ambigua, y
    lo ambiguo va como NIC41 con la retención más larga.
    """
    if componente is None or componente in _COMPONENTES_NIC41:
        return ClasificacionRegistro.NIC41, 5
    return ClasificacionRegistro.TECNICO, 1


@dataclass
class EventoAuditoriaIot:
    # RF-10 base
    id_evento: Optional[UUID]
    tipo_evento: str
    fecha_hora: datetime
    resultado: TipoResultado
    modulo: str = 'M03'
    id_usuario: Optional[int] = None
    nombre_usuario: Optional[str] = None
    descripcion: Optional[str] = None
    direccion_ip: Optional[str] = None
    user_agent: Optional[str] = None
    id_sesion: Optional[UUID] = None
    # RF-63 IoT extension
    accion_detallada: Optional[dict] = None
    entidad_afectada_tipo: Optional[EntidadAfectadaTipo] = None
    entidad_afectada_id: Optional[str] = None
    severidad_log: SeveridadLog = SeveridadLog.INFO
    hash_integridad: str = ''
    clasificacion_registro: ClasificacionRegistro = ClasificacionRegistro.TECNICO
    retencion_aplicable: int = 1
    registro_incompleto: bool = False
    componente_origen: Optional[ComponenteOrigen] = None
    timestamp_registro: Optional[datetime] = None
    integridad_comprometida: bool = False  # Proyección externa; no forma parte del hash.
