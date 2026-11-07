# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: valida referencia y categoria escalar |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-27 | Leandro | INC-M03-131-G23 RF-53/54: recibir opcionalmente la secuencia original del Edge sin coerciones ni generacion. |
# | 2026-10-27 | Leandro | INC-M03-132-G30 RF-53/54/62: recibir evidencia opcional y estricta del reloj al capturar la lectura. |
# | 2026-10-30 | Arekkazu | INC-M03-136-G02 RF-53: verifica el checksum contra el contenido de la lectura |
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Optional

from pydantic import Field, StrictBool, field_validator, model_validator

from src.shared.base_dto import BaseDTO
from src.telemetry.domain.entities.telemetria import CategoriaTelemetria
from src.shared.fechas import FechaHoraUtc


def _canonico(valor):
    # Como JSON.stringify: 25.0 se escribe 25. ponytail: los floats en notación
    # científica (1e-7) difieren entre JS y Python; ampliar si el Edge los envía.
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, dict):
        return {k: _canonico(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_canonico(v) for v in valor]
    return valor


def checksum_lectura(datos: dict) -> str:
    """SHA-256 (hex) del JSON de la lectura sin ``checksum``: claves ordenadas, sin espacios, UTF-8."""
    contenido = {k: v for k, v in datos.items() if k != 'checksum'}
    texto = json.dumps(_canonico(contenido), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


class IngerirTelemetriaDTO(BaseDTO):
    device_id: int = Field(..., gt=0)
    sensor_id: int = Field(..., gt=0)
    tipo_variable: str = Field(..., min_length=2, max_length=40)
    valor: Decimal = Field(...)
    unidad: str = Field(..., min_length=1, max_length=20)
    timestamp_captura: FechaHoraUtc
    serial: str = Field(..., min_length=1, max_length=100)

    # Opcionales
    timestamp_envio: Optional[FechaHoraUtc] = None
    origen: str = Field(default='TIEMPO_REAL', max_length=20)
    frecuencia_muestreo: Optional[int] = Field(default=None, gt=0)
    valor_agregado: bool = False
    ventana_agregacion: Optional[int] = Field(default=None, gt=0)
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    estado_conectividad: Optional[bool] = None
    nivel_bateria: Optional[Decimal] = Field(default=None, ge=0, le=100)
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None
    checksum: Optional[str] = Field(
        default=None,
        description='SHA-256 (hex) del JSON de la lectura sin este campo, con claves ordenadas y sin espacios.',
    )
    buffer_sequence_id: Optional[int] = Field(
        default=None, strict=True, ge=0, le=2**63-1,
        description='Secuencia original del buffer Edge; se conserva como metadato de trazabilidad.',
    )
    reloj_sincronizado: Optional[StrictBool] = Field(
        default=None, description='Estado del reloj reportado al capturar; si falta se consulta el heartbeat.',
    )
    categoria_variable: Optional[str] = None
    id_variable: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode='before')
    @classmethod
    def verificar_checksum(cls, datos):
        # RF-53 Fase 1 (INC-M03-136-G02): si llega checksum, debe corresponder al contenido
        # recibido; si no, la lectura se rechaza como ERROR_ESTRUCTURA y no se guarda.
        if not isinstance(datos, dict) or datos.get('checksum') is None:
            return datos
        recibido = datos['checksum']
        try:
            esperado = checksum_lectura(datos)
        except (TypeError, ValueError):
            raise ValueError('checksum: el contenido de la lectura no se puede verificar.') from None
        if not isinstance(recibido, str) or recibido.strip().lower() != esperado:
            raise ValueError('checksum: no corresponde al contenido de la lectura (SHA-256 del JSON sin checksum, '
                             'claves ordenadas).')
        return datos

    @field_validator('categoria_variable')
    @classmethod
    def validar_categoria(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        categoria = v.upper()
        if categoria not in {item.value for item in CategoriaTelemetria}:
            raise ValueError('categoria_variable debe ser AMBIENTAL, ANIMAL o HIDRICA.')
        return categoria

    @field_validator('origen')
    @classmethod
    def validar_origen(cls, v: str) -> str:
        valores_validos = {'TIEMPO_REAL', 'BUFFER_LOCAL', 'EDGE_AGREGADO'}
        if v.upper() not in valores_validos:
            raise ValueError(f"origen debe ser uno de: {', '.join(valores_validos)}")
        return v.upper()

    @field_validator('tipo_variable')
    @classmethod
    def normalizar_tipo_variable(cls, v: str) -> str:
        return v.upper().strip()


class IngerirTelemetriaBatchDTO(BaseDTO):
    registros: list[IngerirTelemetriaDTO] = Field(..., min_length=1, max_length=500)
    idempotency_key: Optional[str] = None
