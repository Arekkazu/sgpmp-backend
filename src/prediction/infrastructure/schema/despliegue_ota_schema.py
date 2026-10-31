# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU06 H-02 RF-70: nombre de la versión desplegada |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 T-18 RF-70: nombre del dispositivo en los despliegues |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.shared.tipo_modelo import paradigma_de


class DespliegueOtaResponse(BaseModel):
    id_despliegue_ota: int
    id_version_modelo: int
    # CU06 H-02: sin el nombre, la pantalla mostraba "v43" y no se sabía qué modelo se desplegó.
    nombre_version: Optional[str] = None
    id_dispositivo_iot: int
    # T-18: nombre del equipo (descripción o serial), no "#347".
    nombre_dispositivo: Optional[str] = None
    tipo_modelo: str
    paradigma: Optional[str] = None
    componente: Optional[str] = None
    modo_distribucion: str
    estado_despliegue: str
    hash_modelo_sha256: str
    resultado_validacion_hash: Optional[bool]
    id_version_modelo_anterior: Optional[int]
    nombre_version_anterior: Optional[str] = None
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
    # DEV-15 / DB-04
    id_distribucion_ota: Optional[int] = None
    fase_rollout: Optional[str] = None
    fecha_expiracion_url: Optional[datetime] = None
    id_mensaje_notify: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, e: DespliegueOta) -> "DespliegueOtaResponse":
        return cls(
            id_despliegue_ota=e.id_despliegue_ota,
            id_version_modelo=e.id_version_modelo,
            id_dispositivo_iot=e.id_dispositivo_iot,
            tipo_modelo=e.tipo_modelo,
            paradigma=paradigma_de(e.tipo_modelo),
            componente=e.componente,
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
            id_distribucion_ota=e.id_distribucion_ota,
            fase_rollout=e.fase_rollout,
            fecha_expiracion_url=e.fecha_expiracion_url,
            id_mensaje_notify=e.id_mensaje_notify,
        )


class OtaStatusResponse(BaseModel):
    id_version_modelo: int
    despliegues: list[DespliegueOtaResponse]
    total: int


class DespliegueOtaListResponse(BaseModel):
    total: int
    items: list[DespliegueOtaResponse]


class DistribucionOtaResponse(BaseModel):
    """Distribución OTA con su rollout y el estado de cada nodo (DEV-15)."""

    id_distribucion_ota: int
    id_version_modelo: int
    tipo_modelo: str
    componente: Optional[str] = None
    modo_distribucion: str
    ventana_inicio: Optional[datetime] = None
    ventana_fin: Optional[datetime] = None
    nivel_bateria_minimo: Optional[Decimal] = None
    tamano_fragmento_bytes: int
    max_reintentos_descarga: int
    porcentaje_parcial: int
    fase_rollout: str
    estado_distribucion: str
    id_usuario: int
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None
    despliegues: list[DespliegueOtaResponse]

    @classmethod
    def from_resultado(cls, resultado) -> "DistribucionOtaResponse":
        d = resultado.distribucion
        return cls(
            id_distribucion_ota=d.id_distribucion_ota,
            id_version_modelo=d.id_version_modelo,
            tipo_modelo=d.tipo_modelo,
            componente=d.componente,
            modo_distribucion=d.modo_distribucion,
            ventana_inicio=d.ventana_inicio,
            ventana_fin=d.ventana_fin,
            nivel_bateria_minimo=d.nivel_bateria_minimo,
            tamano_fragmento_bytes=d.tamano_fragmento_bytes,
            max_reintentos_descarga=d.max_reintentos_descarga,
            porcentaje_parcial=d.porcentaje_parcial,
            fase_rollout=d.fase_rollout,
            estado_distribucion=d.estado_distribucion,
            id_usuario=d.id_usuario,
            fecha_creacion=d.fecha_creacion,
            fecha_actualizacion=d.fecha_actualizacion,
            despliegues=[DespliegueOtaResponse.from_entity(e) for e in resultado.despliegues],
        )


class ReporteOtaResponse(BaseModel):
    """Respuesta al broker por cada reporte ``ota/<evento>`` reenviado."""

    id_despliegue_ota: int
    estado_despliegue: str
    evento_rf73: Optional[str] = None
    sin_cambios: bool = False
    fase_avanzada_a: Optional[str] = None
