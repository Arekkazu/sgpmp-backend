# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..88: cálculo de valor razonable, reconocimiento y valoración por costo |
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: correctivo de variaciones con aprobación del Contador |
"""Entidades de valoración NIC 41."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class CalculoValor:
    """Cálculo de RF-84 (``calculos_valor_razonable``): la base de toda medición posterior."""

    id_activo_biologico: int
    id_precio_mercado: int
    id_periodo_contable: int
    magnitud: Decimal
    unidad_magnitud: str
    precio_unitario: Decimal
    valor_razonable_bruto: Decimal
    costo_transporte: Decimal
    costo_comisiones: Decimal
    costo_impuestos_transaccion: Decimal
    otros_costos_disposicion: Decimal
    valor_neto: Decimal
    metodo_costo: str
    json_metodo_costo: dict
    id_usuario: int
    estado: str = "CALCULADO"
    justificacion: Optional[str] = None
    id_parametro_costo_venta: Optional[int] = None
    id_evento_magnitud: Optional[int] = None
    tiene_valor_estimado: bool = False
    id_calculo_valor_razonable: Optional[int] = None
    fecha_calculo: Optional[datetime] = None

    def escalado(self, factor: Decimal, id_periodo_contable: int) -> "CalculoValor":
        """Base que queda tras una baja o cosecha parcial (``factor`` = fracción que permanece)."""
        from src.financial_valuation.domain.services.nic41 import q4

        costos = [q4(c * factor) for c in (self.costo_transporte, self.costo_comisiones,
                                            self.costo_impuestos_transaccion, self.otros_costos_disposicion)]
        bruto = q4(self.valor_razonable_bruto * factor)
        return CalculoValor(
            self.id_activo_biologico, self.id_precio_mercado, id_periodo_contable, q4(self.magnitud * factor),
            self.unidad_magnitud, self.precio_unitario, bruto, *costos, bruto - sum(costos), self.metodo_costo,
            self.json_metodo_costo, self.id_usuario, self.estado, self.justificacion, self.id_parametro_costo_venta,
            self.id_evento_magnitud, self.tiene_valor_estimado,
        )


@dataclass(frozen=True)
class Reconocimiento:
    id_reconocimiento_inicial: int
    id_activo_biologico: int
    estado: str
    clasificacion: str
    indicador_valoracion: str
    valor_razonable_neto_inicial: Decimal
    fecha_reconocimiento: datetime
    id_periodo_contable: int
    origen_financiero: Optional[str]
    costo_adquisicion: Optional[Decimal]
    id_precio_mercado: Optional[int]
    id_calculo_valor_razonable: Optional[int]
    id_valoracion_por_costo: Optional[int]
    es_apertura: bool
    cuenta_debito: Optional[str] = None
    cuenta_credito: Optional[str] = None


@dataclass
class ValoracionCosto:
    """Modelo de costo de NIC 41 ¶30 (``valoraciones_por_costos``)."""

    id_activo_biologico: int
    escenario_activacion: str
    costos_adquisicion: Decimal
    tasa_depreciacion: Decimal
    vida_util_meses: int
    fecha_adquisicion: date
    depreciacion_acumulada: Decimal
    deterioro_acumulado: Decimal
    valor_contable_por_costo: Decimal
    razon_sin_mercado: str
    id_usuario: int
    es_activa: bool = True
    justificacion: Optional[str] = None
    id_valoracion_por_costo: Optional[int] = None


@dataclass
class Medicion:
    id_activo_biologico: int
    id_calculo_actual: int
    id_calculo_anterior: int
    origen_medicion: str  # EVENTO | CIERRE_PERIODO
    valor_razonable_anterior: Decimal
    valor_razonable_actual: Decimal
    ganancia_perdida_transformacion: Decimal
    ganancia_perdida_precio_mercado: Decimal
    tiene_valor_estimado: bool
    id_periodo_contable: int
    id_evento: Optional[int] = None
    supuestos_aplicados: dict = field(default_factory=dict)
    id_medicion_posterior: Optional[int] = None

    @property
    def variacion_total(self) -> Decimal:
        return self.valor_razonable_actual - self.valor_razonable_anterior


@dataclass
class VariacionRegistro:
    """Un registro por componente distinto de cero (RF-86 paso 5)."""

    id_activo_biologico: int
    tipo: str
    variacion_transformacion: Decimal
    variacion_precio_mercado: Decimal
    valor_razonable_anterior: Decimal
    valor_razonable_nuevo: Decimal
    id_periodo_contable: int
    id_usuario: int
    tiene_estimacion: bool
    id_medicion_posterior: Optional[int] = None
    id_evento: Optional[int] = None
    id_precio_mercado: Optional[int] = None
    id_cierre: Optional[int] = None
    id_variacion_valor_razonable: Optional[int] = None
    id_variacion_corregida: Optional[int] = None  # RF-86 R5: el registro que este correctivo corrige

    @property
    def monto_variacion(self) -> Decimal:
        return self.variacion_transformacion + self.variacion_precio_mercado

    @property
    def es_correctivo(self) -> bool:
        return self.id_variacion_corregida is not None

    def correctivo(self, id_usuario: int) -> "VariacionRegistro":
        """RF-86 R5 / CA-13: registro con monto opuesto que referencia a este. El original no cambia.

        Ganancia ↔ pérdida del mismo componente; los valores de referencia se invierten (el correctivo
        devuelve el activo del valor nuevo al anterior)."""
        sentido, componente = self.tipo.split("_", 1)
        return VariacionRegistro(
            id_activo_biologico=self.id_activo_biologico,
            tipo=f"{'PERDIDA' if sentido == 'GANANCIA' else 'GANANCIA'}_{componente}",
            variacion_transformacion=-self.variacion_transformacion, variacion_precio_mercado=-self.variacion_precio_mercado,
            valor_razonable_anterior=self.valor_razonable_nuevo, valor_razonable_nuevo=self.valor_razonable_anterior,
            id_periodo_contable=self.id_periodo_contable, id_usuario=id_usuario, tiene_estimacion=self.tiene_estimacion,
            id_medicion_posterior=self.id_medicion_posterior, id_evento=self.id_evento,
            id_precio_mercado=self.id_precio_mercado, id_cierre=self.id_cierre,
            id_variacion_corregida=self.id_variacion_valor_razonable,
        )


@dataclass
class SolicitudCorrectivo:
    """Solicitud de correctivo de una variación (RF-86 CA-13): PENDIENTE hasta que otro Contador la resuelve."""

    id_solicitud_correctivo_variacion: int
    id_variacion_valor_razonable: int
    motivo: str
    estado: str  # PENDIENTE | APROBADA | RECHAZADA
    id_usuario_solicitante: int
    fecha_solicitud: datetime
    id_usuario_resolutor: Optional[int] = None
    fecha_resolucion: Optional[datetime] = None
    motivo_rechazo: Optional[str] = None
    id_variacion_correctiva: Optional[int] = None

    @property
    def esta_pendiente(self) -> bool:
        return self.estado == "PENDIENTE"
