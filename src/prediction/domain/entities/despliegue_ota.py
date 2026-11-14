from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DespliegueOta:
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
    # RF-70 v2.0 (RFC-009): despliegue granular por componente de un modelo POBLACIONAL.
    componente: Optional[str] = None
    # DEV-15 / DB-04: distribución y fase del rollout a la que pertenece, vencimiento
    # de la URL firmada que se le entregó y id del aviso ota/notify del broker.
    id_distribucion_ota: Optional[int] = None
    fase_rollout: Optional[str] = None
    fecha_expiracion_url: Optional[datetime] = None
    id_mensaje_notify: Optional[str] = None

    @property
    def esta_terminado(self) -> bool:
        return self.estado_despliegue in ESTADOS_TERMINALES

    def marcar_notificado(self, id_mensaje: str, fecha_expiracion_url: datetime) -> None:
        self.id_mensaje_notify = id_mensaje
        self.fecha_expiracion_url = fecha_expiracion_url
        self.motivo_fallo = None

    def marcar_aviso_fallido(self, motivo: str) -> None:
        """El broker no publicó ota/notify: sigue PENDIENTE para reintentar el aviso."""
        self.motivo_fallo = motivo

    def registrar_avance(
        self,
        *,
        tamano_descargado_bytes: Optional[int] = None,
        intentos_descarga: Optional[int] = None,
        nivel_bateria: Optional[Decimal] = None,
    ) -> None:
        self.estado_despliegue = ESTADO_EN_PROCESO
        if tamano_descargado_bytes is not None:
            self.tamano_descargado_bytes = tamano_descargado_bytes
        if intentos_descarga is not None:
            self.intentos_descarga = intentos_descarga
        if nivel_bateria is not None and self.nivel_bateria_al_inicio is None:
            self.nivel_bateria_al_inicio = nivel_bateria

    def posponer(self, motivo: str) -> None:
        """El nodo no puede instalar ahora (ventana, batería): vuelve a PENDIENTE."""
        self.estado_despliegue = ESTADO_PENDIENTE
        self.motivo_fallo = motivo

    def marcar_integridad_valida(self) -> None:
        self.estado_despliegue = ESTADO_EN_PROCESO
        self.resultado_validacion_hash = True

    def activar(self, ahora: datetime, duracion_proceso_ms: Optional[int]) -> None:
        self.estado_despliegue = ESTADO_EXITOSO
        self.fecha_fin = ahora
        self.motivo_fallo = None
        if duracion_proceso_ms is not None:
            self.duracion_proceso_ms = duracion_proceso_ms

    def fallar(self, ahora: datetime, motivo: str, *, rollback: bool, hash_invalido: bool = False) -> None:
        self.estado_despliegue = ESTADO_FALLIDO
        self.fecha_fin = ahora
        self.motivo_fallo = motivo
        self.rollback_ejecutado = self.rollback_ejecutado or rollback
        if hash_invalido:
            self.resultado_validacion_hash = False


ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_EN_PROCESO = "EN_PROCESO"
ESTADO_EXITOSO = "EXITOSO"
ESTADO_FALLIDO = "FALLIDO"
ESTADOS_TERMINALES = frozenset({ESTADO_EXITOSO, ESTADO_FALLIDO, "SIN_CAMBIOS"})
