# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-30 RF-57: trata VENCIDA como estado terminal  |
# | 2026-10-24 | Arekkazu | USAB-M03 M3-05/M3-06 RF-57: nombres de ubicación y autor del cambio (read-model) |
# | 2026-10-25 | Arekkazu | USAB-M03 T-18 RF-57: nombre del activo además de la ubicación (read-model) |
# | 2026-10-26 | Arekkazu | INC-M03-179-G57F RF-57: regla de umbral M09 con forma {id, nombre} |
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: tipo de alerta RIESGO_CONTAGIO |
# | 2026-10-28 | Arekkazu | BE-0/BE-3 RF-55: conducta de ReglaAlerta y regla Edge {id, nombre} en la alerta |
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from src.shared.errors import BusinessRuleError, ValidationError


class TipoAlerta(str, Enum):
    ESTRES_TERMICO = "ESTRES_TERMICO"
    SINDROME_RESPIRATORIO = "SINDROME_RESPIRATORIO"
    RIESGO_HIDRICO = "RIESGO_HIDRICO"
    FIEBRE = "FIEBRE"
    INACTIVIDAD_ANORMAL = "INACTIVIDAD_ANORMAL"
    FALLO_AMBIENTAL = "FALLO_AMBIENTAL"
    PREDICCION_PATOLOGIA = "PREDICCION_PATOLOGIA"
    TORMENTA_DE_ALERTAS = "TORMENTA_DE_ALERTAS"
    # RF-68 paso 8: riesgo de contagio Alto del lote (Modelo 4 de M04).
    RIESGO_CONTAGIO = "RIESGO_CONTAGIO"


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


#: RF-60: alertas técnicas de dispositivos IoT (batería, conectividad,
#: sobrecalentamiento). Comparten ``modulo3.alertas`` con las operativas.
TIPO_ALERTA_TECNICA = "TECNICA"


def regla_umbral(id_umbral, tipo_variable, estado_semaforo, version_umbral) -> dict:
    """RF-57 Restricción 4 / CA-15: la regla que disparó la alerta, con la forma {id, nombre}
    de las reglas de M03, para el umbral de M09 (RF-17) que evaluó la lectura."""
    return {
        'id': id_umbral,
        'nombre': f'UMBRAL_{tipo_variable}_{estado_semaforo}',
        'tipo': 'UMBRAL_AMBIENTAL',
        'id_umbral_ambiental': id_umbral,
        'version_umbral': version_umbral,
    }


def regla_edge(clasificacion_rf55: str, metadata_edge: Optional[dict], id_regla_alerta: Optional[int]) -> str | dict:
    """RF-55 BE-3: la regla que evaluó el Edge (``metadata_edge.regla_aplicada``), con la
    forma {id, nombre} de las demás; sin ella queda la clasificación, como antes."""
    metadata = metadata_edge or {}
    nombre = metadata.get('regla_aplicada')
    if not nombre:
        return clasificacion_rf55
    return {
        'id': id_regla_alerta,
        'nombre': str(nombre),
        'tipo': 'REGLA_EDGE',
        'clasificacion_rf55': clasificacion_rf55,
        'version_regla': metadata.get('version_regla'),
    }


class AmbitoAlerta(str, Enum):
    """Qué alertas atiende cada endpoint (RF-60, Restricción 5 — D-09).

    ``/iot/alertas`` (recurso 32, que el Productor tiene con R y U) solo ve y
    gestiona las operativas; ``/iot/alertas-tecnicas`` (recurso 36, Admin e
    Ingeniero) solo las técnicas. Una alerta fuera del ámbito del endpoint no
    existe para él (404), igual que una alerta de otra finca.
    """
    OPERATIVA = "OPERATIVA"
    TECNICA = "TECNICA"

    def admite(self, tipo_alerta: str) -> bool:
        return (tipo_alerta == TIPO_ALERTA_TECNICA) == (self is AmbitoAlerta.TECNICA)


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
    EstadoAlerta.VENCIDA: set(),
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

    # M3-06 (read-model): dónde ocurrió, para no mostrar solo IDs. Se llenan al leer.
    nombre_sensor: Optional[str] = None
    nombre_infraestructura: Optional[str] = None
    nombre_finca: Optional[str] = None
    # T-18: el detalle decía "Activo biológico #829".
    nombre_activo: Optional[str] = None

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
    # M3-05 (read-model): nombre de quien hizo el cambio.
    nombre_usuario: Optional[str] = None


@dataclass
class ReglaAlerta:
    nombre: str
    tipo_sensor: str
    es_regla_compuesta: bool
    ventana_confirmacion_min: Decimal
    lectura_confirmacion_max: Decimal
    es_activa: bool

    # Los asigna la BD: id y fecha al insertar; version_regla la sube
    # trg_aux_02_version_regla_alerta cuando cambia lo que recibe el Edge.
    id_regla_alertas: Optional[int] = None
    version_regla: int = 1
    fecha_creacion: Optional[datetime] = None

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

    @property
    def se_propaga_al_edge(self) -> bool:
        """Solo las compuestas marcadas para el Edge viajan con REGLA_COMPUESTA (DEV-08)."""
        return self.es_regla_compuesta and self.tiene_ejecutar_edge

    def validar(self) -> None:
        if self.umbral_min is None and self.umbral_max is None and not self.umbrales_severidad:
            raise ValidationError(
                code="REGLA_SIN_UMBRAL",
                message="La regla necesita umbral_min, umbral_max o umbrales_severidad.",
                field="umbral_min",
            )
        if self.umbral_min is not None and self.umbral_max is not None and self.umbral_min >= self.umbral_max:
            raise ValidationError(
                code="RANGO_UMBRAL_INVALIDO",
                message="umbral_min debe ser menor que umbral_max.",
                field="umbral_min",
            )
        if self.tiene_ejecutar_edge and not self.es_regla_compuesta:
            # Los umbrales simples llegan al Edge por RF-17 (origen "umbral"), no por esta tabla.
            raise ValidationError(
                code="REGLA_EDGE_NO_COMPUESTA",
                message="Solo una regla compuesta puede marcarse para ejecutarse en el Gateway Edge.",
                field="tiene_ejecutar_edge",
            )

    def actualizar(self, *, id_usuario: int, **campos: Any) -> None:
        if not self.es_activa:
            raise BusinessRuleError(
                code="REGLA_ALERTA_INACTIVA",
                message="No se puede editar una regla inactiva. Reactívela primero.",
            )
        for nombre, valor in campos.items():
            setattr(self, nombre, valor)
        self.id_usuario = id_usuario
        self.validar()

    def desactivar(self, id_usuario: int) -> None:
        if not self.es_activa:
            raise BusinessRuleError(code="REGLA_ALERTA_YA_INACTIVA", message="La regla ya está inactiva.")
        self.es_activa = False
        self.id_usuario = id_usuario

    def reactivar(self, id_usuario: int) -> None:
        if self.es_activa:
            raise BusinessRuleError(code="REGLA_ALERTA_YA_ACTIVA", message="La regla ya está activa.")
        self.es_activa = True
        self.id_usuario = id_usuario


@dataclass
class ResultadoGeneracionAlerta:
    es_duplicado: bool
    id_alerta: Optional[int] = None
    tipo_alerta: Optional[str] = None
    severidad: Optional[str] = None
    alerta_existente_id: Optional[int] = None
    motivo_descarte: Optional[str] = None
