from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.prediction.domain.entities.despliegue_ota import DespliegueOta


class DespliegueOtaResponse(BaseModel):
    id_despliegue_ota: int
    id_version_modelo: int
    id_dispositivo_iot: int
    tipo_modelo: str
    modo_distribucion: str
    estado_despliegue: str
    hash_modelo_sha256: str
    resultado_validacion_hash: Optional[bool]
    id_version_modelo_anterior: Optional[int]
    rollback_ejecutado: bool
    intentos_descarga: int
    max_reintentos: int
    tamano_modelo_bytes: Optional[int]
    tamano_descargado_bytes: Optional[int]
    duracion_proceso_ms: Optional[int]
    ventana_inicio: Optional[datetime]
    ventana_fin: Optional[datetime]
    nivel_bateria_al_inicio: Optional[Decimal]
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]
    motivo_fallo: Optional[str]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, e: DespliegueOta) -> "DespliegueOtaResponse":
        return cls(
            id_despliegue_ota=e.id_despliegue_ota,
            id_version_modelo=e.id_version_modelo,
            id_dispositivo_iot=e.id_dispositivo_iot,
            tipo_modelo=e.tipo_modelo,
            modo_distribucion=e.modo_distribucion,
            estado_despliegue=e.estado_despliegue,
            hash_modelo_sha256=e.hash_modelo_sha256,
            resultado_validacion_hash=e.resultado_validacion_hash,
            id_version_modelo_anterior=e.id_version_modelo_anterior,
            rollback_ejecutado=e.rollback_ejecutado,
            intentos_descarga=e.intentos_descarga,
            max_reintentos=e.max_reintentos,
            tamano_modelo_bytes=e.tamano_modelo_bytes,
            tamano_descargado_bytes=e.tamano_descargado_bytes,
            duracion_proceso_ms=e.duracion_proceso_ms,
            ventana_inicio=e.ventana_inicio,
            ventana_fin=e.ventana_fin,
            nivel_bateria_al_inicio=e.nivel_bateria_al_inicio,
            fecha_inicio=e.fecha_inicio,
            fecha_fin=e.fecha_fin,
            motivo_fallo=e.motivo_fallo,
        )


class OtaStatusResponse(BaseModel):
    id_version_modelo: int
    despliegues: list[DespliegueOtaResponse]
    total: int


class DespliegueOtaListResponse(BaseModel):
    total: int
    items: list[DespliegueOtaResponse]
