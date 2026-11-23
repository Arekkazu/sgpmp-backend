# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-15 | Arekkazu | INC-M06-364-G71 RF-45/RF-93: valor y referencia de la venta en la baja |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""DTO de entrada de ``POST /activos-biologicos/{id_activo}/eventos/baja`` (RF-45)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator, model_validator

from src.shared.base_dto import BaseDTO

_TIPOS_BAJA = {'muerte', 'venta', 'sacrificio', 'perdida', 'descarte_sanitario'}


class RegistrarEventoBajaDTO(BaseDTO):
    """Baja de un activo o de parte de un lote.

    ``tipo_baja``: ``muerte`` | ``venta`` | ``sacrificio`` | ``perdida`` |
    ``descarte_sanitario``. En lotes, ``cantidad_afectada`` omitida da de baja el lote
    completo; en individuales se ignora.
    """
    tipo_baja: str
    fecha_baja: date
    motivo_baja: str
    cantidad_afectada: Optional[int] = None  # solo LOTE baja parcial; None = baja total del lote
    # Solo en una venta (INC-M06-364-G71): lo recibido por la venta y su factura o remisión. El estado de resultados
    # lo muestra como ingreso por venta; la factura se registra en la contabilidad externa.
    valor_venta: Optional[Decimal] = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    referencia_venta: Optional[str] = Field(default=None, max_length=100)

    @field_validator('tipo_baja')
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        """Normaliza y valida el tipo de baja."""
        v = v.strip().lower()
        if v not in _TIPOS_BAJA:
            raise ValueError(f"El tipo de baja debe ser uno de: {', '.join(sorted(_TIPOS_BAJA))}.")
        return v

    @field_validator('motivo_baja')
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        """Exige un motivo de baja no vacío."""
        v = v.strip()
        if not v:
            raise ValueError('El motivo de baja no puede estar vacío.')
        return v

    @field_validator('referencia_venta')
    @classmethod
    def referencia_sin_espacios(cls, v: Optional[str]) -> Optional[str]:
        """Quita espacios de la referencia y la deja en ``None`` si queda vacía."""
        return (v or '').strip() or None

    @model_validator(mode='after')
    def venta_solo_en_ventas(self) -> 'RegistrarEventoBajaDTO':
        """Admite valor y referencia de venta solo en bajas por venta."""
        if self.tipo_baja != 'venta' and (self.valor_venta is not None or self.referencia_venta):
            raise ValueError('El valor y la referencia de la venta solo se registran en una baja por venta.')
        return self

    @field_validator('cantidad_afectada')
    @classmethod
    def cantidad_positiva(cls, v: Optional[int]) -> Optional[int]:
        """Exige una cantidad afectada positiva."""
        if v is not None and v <= 0:
            raise ValueError('La cantidad afectada debe ser un entero positivo.')
        return v
