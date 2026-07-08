from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from src.shared.errors import BusinessRuleError


class TipoAlerta(str, Enum):
    ESTRES_TERMICO = "ESTRES_TERMICO"
    SINDROME_RESPIRATORIO = "SINDROME_RESPIRATORIO"
    RIESGO_HIDRICO = "RIESGO_HIDRICO"
    FIEBRE = "FIEBRE"
    INACTIVIDAD_ANORMAL = "INACTIVIDAD_ANORMAL"
    FALLO_AMBIENTAL = "FALLO_AMBIENTAL"
    PREDICCION_PATOLOGIA = "PREDICCION_PATOLOGIA"
    TORMENTA_DE_ALERTAS = "TORMENTA_DE_ALERTAS"


class EstadoAlerta(str, Enum):
    ACTIVA = "ACTIVA"
    EN_ATENCION = "EN_ATENCION"
    RESUELTA = "RESUELTA"
    DESCARTADA = "DESCARTADA"
    VENCIDA = "VENCIDA"
    PENDIENTE_SINCRONIZACION = "PENDIENTE_SINCRONIZACION"


class OrigenEventoAlerta(str, Enum):
    EDGE = "EDGE"
    BACKEND = "BACKEND"
    IA = "IA"


class ConflictoResolucion(str, Enum):
    SEVERIDAD_MAXIMA = "SEVERIDAD_MAXIMA"
    SEVERIDAD_COMPROMISO = "SEVERIDAD_COMPROMISO"
    IA_PREVALECE = "IA_PREVALECE"
    EDGE_PREVALECE = "EDGE_PREVALECE"


class SeveridadAlerta(str, Enum):
    LEVE = "LEVE"
    MODERADO = "MODERADO"
    CRITICO = "CRITICO"

    def __gt__(self, other: "SeveridadAlerta") -> bool:
        orden = {self.LEVE: 0, self.MODERADO: 1, self.CRITICO: 2}
        return orden[self] > orden[other]

    def __ge__(self, other: "SeveridadAlerta") -> bool:
        orden = {self.LEVE: 0, self.MODERADO: 1, self.CRITICO: 2}
        return orden[self] >= orden[other]


# SLA por severidad (en minutos)
_SLA_MINUTOS: dict[str, int] = {
    SeveridadAlerta.CRITICO: 5,
    SeveridadAlerta.MODERADO: 30,
    SeveridadAlerta.LEVE: 120,
}

# Transiciones de estado válidas
_TRANSICIONES_VALIDAS: dict[str, set[str]] = {
    EstadoAlerta.ACTIVA: {EstadoAlerta.EN_ATENCION, EstadoAlerta.DESCARTADA, EstadoAlerta.VENCIDA},
    EstadoAlerta.EN_ATENCION: {EstadoAlerta.RESUELTA, EstadoAlerta.VENCIDA},
    EstadoAlerta.RESUELTA: set(),
    EstadoAlerta.DESCARTADA: set(),
    EstadoAlerta.VENCIDA: {EstadoAlerta.EN_ATENCION},
    EstadoAlerta.PENDIENTE_SINCRONIZACION: {EstadoAlerta.ACTIVA},
}


@dataclass
class Alerta:
    tipo_alerta: str
    severidad: str
    estado_alerta: str
    origen_evento: str
    tipo_variable: str
    fecha_evento: datetime
    fecha_generacion: datetime
    reglas_activas: list[Any] = field(default_factory=list)

    id_alerta: Optional[int] = None
    id_evento_edge_computing: Optional[int] = None
    id_telemetria: Optional[int] = None
    id_paquete_inferencia: Optional[int] = None
    id_regla_alerta: Optional[int] = None
    id_sensor: Optional[int] = None
    id_dispositivo_ioit: Optional[int] = None
    id_activo_biologico: Optional[int] = None
    id_infraestructura: Optional[int] = None
    id_usuario_atencion: Optional[int] = None
    id_usuario_resolucion: Optional[int] = None
    referencia_alerta_original: Optional[int] = None

    valor: Optional[Decimal] = None
    unidad: Optional[str] = None
    contexto_activo_biologico: Optional[dict] = None
    metadato_evento: Optional[dict] = None
    accion_sugerida: Optional[str] = None
    motivo_descarte: Optional[str] = None
    diagnostico: Optional[str] = None

    tiene_inferencia_no_disponible: bool = False
    tiene_contexto_incompleto: bool = False
    tiene_generada_por_reevaluacion: bool = False

    conflicto_resolucion: Optional[str] = None
    severidad_edge_original: Optional[str] = None
    severidad_ia: Optional[str] = None

    frecuencia_evento: int = 1
    ultima_ocurrencia: Optional[datetime] = None

    fecha_registro: Optional[datetime] = None
    fecha_notificacion: Optional[datetime] = None
    fecha_atencion: Optional[datetime] = None
    fecha_resolucion: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None

    def calcular_fecha_vencimiento(self) -> datetime:
        minutos = _SLA_MINUTOS.get(self.severidad, 120)
        base = self.fecha_generacion
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        return base + timedelta(minutes=minutos)

    def es_transicion_valida(self, nuevo_estado: str) -> bool:
        return nuevo_estado in _TRANSICIONES_VALIDAS.get(self.estado_alerta, set())

    def transicionar(self, nuevo_estado: str, id_usuario: Optional[int], motivo: Optional[str]) -> None:
        if not self.es_transicion_valida(nuevo_estado):
            raise BusinessRuleError(
                code="TRANSICION_INVALIDA",
                message=f"No se puede pasar de {self.estado_alerta} a {nuevo_estado}.",
            )
        ahora = datetime.now(timezone.utc)
        if nuevo_estado == EstadoAlerta.EN_ATENCION:
            self.fecha_atencion = ahora
            self.id_usuario_atencion = id_usuario
        elif nuevo_estado == EstadoAlerta.RESUELTA:
            self.fecha_resolucion = ahora
            self.id_usuario_resolucion = id_usuario
        elif nuevo_estado == EstadoAlerta.DESCARTADA:
            self.motivo_descarte = motivo
            self.id_usuario_resolucion = id_usuario
        self.estado_alerta = nuevo_estado


@dataclass
class HistoricoEstadoAlerta:
    id_alerta: int
    estado_anterior: str
    estado_nuevo: str
    fecha_cambio: datetime
    id_historico_estado_alerta: Optional[int] = None
    id_usuario: Optional[int] = None
    motivo: Optional[str] = None


@dataclass
class ReglaAlerta:
    id_regla_alertas: int
    nombre: str
    tipo_sensor: str
    es_regla_compuesta: bool
    ventana_confirmacion_min: Decimal
    lectura_confirmacion_max: Decimal
    es_activa: bool
    version_regla: int
    fecha_creacion: datetime

    descripcion: Optional[str] = None
    categoria_variable: Optional[str] = None
    umbral_min: Optional[Decimal] = None
    umbral_max: Optional[Decimal] = None
    umbrales_severidad: Optional[dict] = None
    mensaje: Optional[str] = None
    tiene_ejecutar_edge: bool = False
    id_finca: Optional[int] = None
    id_especie: Optional[int] = None
    id_usuario: Optional[int] = None
    fecha_actualizacion: Optional[datetime] = None


@dataclass
class ResultadoGeneracionAlerta:
    es_duplicado: bool
    id_alerta: Optional[int] = None
    tipo_alerta: Optional[str] = None
    severidad: Optional[str] = None
    alerta_existente_id: Optional[int] = None
    motivo_descarte: Optional[str] = None
