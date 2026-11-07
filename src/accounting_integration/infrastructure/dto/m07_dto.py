# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98/RF-101/RF-AE02: DTOs de administración de la integración |
"""DTOs de entrada de la administración de M07 (clientes, anexos y contratos)."""
from __future__ import annotations

import ipaddress
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO

Canal = Literal["IDENTIDAD_M2M", "CONSULTA_AAEF"]
Mapper = Literal["COMPRAS", "COMPROBANTE_NIC41"]


class CanalDTO(BaseDTO):
    canal: Canal
    limite_por_minuto: int = Field(60, ge=1, le=6000)


class _ConfiguracionClienteDTO(BaseDTO):
    canales: list[CanalDTO] = Field(min_length=1)
    ip_permitida: Optional[str] = Field(None, description="IP o red CIDR desde la que se acepta al cliente; vacío = cualquiera.")
    ttl_token_canal_minutos: int = Field(15, ge=5, le=60)

    @field_validator("ip_permitida")
    @classmethod
    def _ip(cls, valor: Optional[str]) -> Optional[str]:
        if not valor:
            return None
        try:
            return str(ipaddress.ip_network(valor, strict=False))
        except ValueError as exc:
            raise ValueError("Indique una IP o una red válida, por ejemplo 203.0.113.10 o 203.0.113.0/24.") from exc

    @field_validator("canales")
    @classmethod
    def _sin_repetidos(cls, canales: list[CanalDTO]) -> list[CanalDTO]:
        if len({c.canal for c in canales}) != len(canales):
            raise ValueError("Cada canal se indica una sola vez.")
        return canales

    def canales_dict(self) -> dict[str, int]:
        return {c.canal: c.limite_por_minuto for c in self.canales}


class RegistrarClienteDTO(_ConfiguracionClienteDTO):
    codigo: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,49}$", examples=["AGROFUSION"],
                        description="Identificador interno en mayúsculas; viaja en el token de canal.")
    nombre: str = Field(min_length=2, max_length=150, examples=["AgroFusion"])
    identificador_publico: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$",
                                       description="client_id que el cliente presenta al pedir el token.")
    fecha_vencimiento: date = Field(description="Último día de validez de la credencial.")
    client_secret: Optional[str] = Field(None, description=(
        "Secreto ya existente del cliente (16 a 72 caracteres). Si se omite, el sistema genera uno y lo muestra una vez."))


class EditarClienteDTO(_ConfiguracionClienteDTO):
    fecha_actualizacion: datetime = Field(description="La que devolvió la última consulta (control de concurrencia).")


class MotivoDTO(BaseDTO):
    motivo: Optional[str] = Field(None, max_length=500)


class RotarSecretoDTO(BaseDTO):
    motivo: str = Field(min_length=3, max_length=500)
    fecha_vencimiento: date
    client_secret: Optional[str] = None


class RegistrarAnexoDTO(BaseDTO):
    codigo_anexo: str = Field(min_length=3, max_length=40, examples=["AAEF-ANEXO-3.0"])
    version_anexo: str = Field(pattern=r"^\d{1,3}\.\d{1,3}$", examples=["3.0"])
    ruta_documento: str = Field(min_length=3, max_length=500, description="Dónde está el documento formal del anexo.")
    sha256_documento: str = Field(min_length=64, max_length=64, description="SHA-256 del documento formal.")


class AprobarAnexoDTO(BaseDTO):
    id_intercambio: str = Field(min_length=5, max_length=80, description="ExchangeId de la prueba en TEST.")
    ack_aceptado: bool = Field(description="SIGCON aceptó el 100 % de los documentos.")
    observaciones: Optional[str] = Field(None, max_length=1000)

    @field_validator("ack_aceptado")
    @classmethod
    def _ack(cls, valor: bool) -> bool:
        if not valor:
            raise ValueError("El anexo solo se aprueba si SIGCON aceptó todos los documentos de la prueba.")
        return valor


class RegistrarContratoDTO(BaseDTO):
    contrato_version: str = Field(pattern=r"^\d{1,3}\.\d{1,3}$", examples=["3.0"])
    tipo_cambio: Literal["MAJOR", "MINOR"]
    fecha_vigencia: date
    id_mapeo_anexo_aaef: int = Field(ge=1)
    mapeadores: list[Mapper] = Field(min_length=1)
    periodo_gracia_dias: Optional[int] = Field(None, ge=30, le=3650)
    descripcion: Optional[str] = Field(None, max_length=1000)


class DeprecarContratoDTO(BaseDTO):
    dias_gracia: int = Field(90, ge=30, le=3650)
