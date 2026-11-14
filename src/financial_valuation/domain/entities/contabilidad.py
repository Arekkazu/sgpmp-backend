# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-86/87/109: período, configuración y línea de asiento |
# | 2026-11-11 | Arekkazu | USAB-M06 M6-03 RF-82/87: razón social del período y listas filtradas por el titular del período |
"""Entidades contables de M06: período, configuración, parámetros y líneas de asiento."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from src.financial_valuation.domain.value_objects.nic41 import EstadoPeriodo


@dataclass(frozen=True)
class Periodo:
    id_periodo_contable: int
    numero_id_tributaria: str
    tipo_cierre: str
    fecha_inicio: date
    fecha_fin: date
    estado: str
    fecha_cierre: Optional[datetime] = None
    # Razón social del titular (solo la trae el listado, para distinguir los períodos por algo más que el NIT).
    razon_social: Optional[str] = None

    @property
    def esta_abierto(self) -> bool:
        return self.estado == EstadoPeriodo.ABIERTO.value

    def contiene(self, dia: date) -> bool:
        return self.fecha_inicio <= dia <= self.fecha_fin


@dataclass(frozen=True)
class ConfiguracionContable:
    tipo_cierre: str
    pct_umbral_desviacion_precio: Decimal
    dias_alerta_vencimiento_precio: int
    fecha_inicio_operacion: date
    fecha_actualizacion: Optional[datetime] = None


@dataclass(frozen=True)
class ParametroEspecie:
    id_especie: int
    clasificacion: str
    categoria_precio: str
    vida_util_meses: Optional[int]


@dataclass(frozen=True)
class ParametroCostosVenta:
    id_parametro_costo_venta: int
    id_especie: int
    region: str
    pct_transporte: Decimal
    pct_comisiones: Decimal
    pct_impuestos: Decimal


@dataclass(frozen=True)
class AsignacionCuenta:
    id_asignacion_cuenta_contable: int
    tipo_hecho: str
    sentido: str
    id_especie: Optional[int]
    subtipo_costo: Optional[str]
    cuenta_debito: str
    cuenta_credito: str


@dataclass
class LineaAsiento:
    """Línea de asiento NIC 41 (RF-86 v2.0). ``cuenta_*`` vacías = PENDIENTE_CUENTA (FA-5)."""

    tipo_hecho: str
    sentido: str
    valor: Decimal
    fecha_hecho: date
    id_periodo_contable: int
    id_activo_biologico: int
    id_especie: int
    id_finca: int
    numero_id_tributaria: str
    tabla_origen: str
    id_origen: int
    tipo_evidencia: str
    subtipo_costo: Optional[str] = None
    es_estimacion: bool = False
    es_reverso: bool = False
    tipo_hecho_corregido: Optional[str] = None
    id_linea_corregida: Optional[int] = None
    cuenta_debito: Optional[str] = None
    cuenta_credito: Optional[str] = None
    justificacion: Optional[str] = None
    id_usuario: Optional[int] = None
    id_linea_asiento_nic41: Optional[int] = None
    estado: str = "PENDIENTE_CUENTA"
    extra: dict = field(default_factory=dict)

    def asignar_cuentas(self, asignacion: Optional[AsignacionCuenta]) -> None:
        """El reverso usa el par invertido (RF-86: nunca valores negativos)."""
        if asignacion is None:
            return
        debito, credito = asignacion.cuenta_debito, asignacion.cuenta_credito
        if self.es_reverso:
            debito, credito = credito, debito
        self.cuenta_debito, self.cuenta_credito, self.estado = debito, credito, "REGISTRADA"


@dataclass(frozen=True)
class EventoAuditoria:
    """Evento de RF-94. ``id_usuario`` nulo = actor SISTEMA (``id_sistema`` obligatorio)."""

    tipo_evento: str
    severidad: str
    payload: dict
    id_usuario: Optional[int] = None
    id_sistema: Optional[str] = None
    id_activo_biologico: Optional[int] = None
    id_periodo_contable: Optional[int] = None
    id_referencia: Optional[int] = None
    monto_afectado: Optional[Decimal] = None
    datos_anteriores: Optional[dict] = None
    metodo_anterior: Optional[str] = None
    metodo_nuevo: Optional[str] = None
