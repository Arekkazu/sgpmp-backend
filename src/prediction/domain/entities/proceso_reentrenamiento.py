# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: proceso de reentrenamiento por animal con fases, latido y resultado |
"""Proceso de reentrenamiento del modelo individual de un animal (RF-71, AJF-14).

Ciclo: PENDIENTE (lo solicita un usuario) → EN_CURSO (lo toma el motor de IA) →
COMPLETADO (registró la versión por RF-69) | FALLIDO (el pipeline abortó o la versión no
era registrable) | INTERRUMPIDO (el motor dejó de dar latido) | CANCELADO.

Las 7 fases son las que ve la pantalla; cada una corresponde a un tramo de
``entrenar_modelo_individual`` de ET-02 v5 (ver anotaciones/modulo_4/ajf14_reentrenador.md).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from src.shared.errors import FlowError, ValidationError

FASES: tuple[str, ...] = (
    "ACTIVACION", "DATASET", "PREPROCESAMIENTO", "ENTRENAMIENTO", "METRICAS", "ENTREGA", "CIERRE",
)
ESTADOS_ABIERTOS = frozenset({"PENDIENTE", "EN_CURSO"})
ESTADOS_FINALES = frozenset({"COMPLETADO", "FALLIDO", "INTERRUMPIDO", "CANCELADO"})
DISPARADORES = frozenset({"MANUAL", "PROGRAMADO", "DEGRADACION"})

#: BE-5: sin latido por más de esto, un proceso EN_CURSO se da por interrumpido.
LATIDO_MAXIMO = timedelta(minutes=15)


@dataclass(frozen=True)
class DatosAnimalReentrenamiento:
    """Lo que hace falta saber del animal antes de abrir un proceso."""
    tipo_modelo: Optional[str]
    horas_de_lecturas: float
    id_version_vigente: Optional[int]


@dataclass(eq=False)
class ProcesoReentrenamiento:
    tipo_modelo: str
    id_activo_biologico: int
    id_proceso_reentrenamiento: Optional[uuid.UUID] = None
    disparador: str = "MANUAL"
    modo_generacion: str = "REENTRENAMIENTO"
    estado: str = "PENDIENTE"
    fase_actual: int = 0
    porcentaje_progreso: int = 0
    fases: list[dict] = field(default_factory=list)
    porcentaje_cpu: Optional[Decimal] = None
    memoria_ram_mb: Optional[int] = None
    codigo_error: Optional[str] = None
    motivos: Optional[list] = None
    id_version_modelo_referencia: Optional[int] = None
    id_version_modelo_resultante: Optional[int] = None
    id_usuario_solicitante: Optional[int] = None
    fecha_solicitud: Optional[datetime] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    fecha_ultimo_latido: Optional[datetime] = None
    #: Solo lectura (para mostrar): código del animal y nombre de la versión resultante.
    identificador_activo: Optional[str] = None
    nombre_version_resultante: Optional[str] = None

    @classmethod
    def solicitar(cls, *, tipo_modelo: str, id_activo_biologico: int, id_usuario: Optional[int],
                  ahora: datetime, disparador: str = "MANUAL") -> "ProcesoReentrenamiento":
        if disparador not in DISPARADORES:
            raise ValidationError("DISPARADOR_INVALIDO", f"disparador debe ser uno de {sorted(DISPARADORES)}.", field="disparador")
        return cls(tipo_modelo=tipo_modelo, id_activo_biologico=id_activo_biologico, disparador=disparador,
                   id_usuario_solicitante=id_usuario, fecha_solicitud=ahora)

    @property
    def abierto(self) -> bool:
        return self.estado in ESTADOS_ABIERTOS

    def iniciar(self, ahora: datetime, id_version_referencia: Optional[int]) -> None:
        if self.estado != "PENDIENTE":
            raise FlowError("PROCESO_NO_PENDIENTE", "Solo se puede iniciar un proceso pendiente.")
        self.estado = "EN_CURSO"
        self.fecha_inicio = ahora
        self.fecha_ultimo_latido = ahora
        self.id_version_modelo_referencia = id_version_referencia
        self._abrir_fase(1, ahora)

    def reportar(self, *, ahora: datetime, fase: Optional[int] = None, progreso: Optional[int] = None,
                 cpu: Optional[Decimal] = None, ram_mb: Optional[int] = None) -> None:
        """Latido del motor: fase en curso, progreso y recursos. La fase nunca retrocede."""
        if self.estado != "EN_CURSO":
            raise FlowError("PROCESO_NO_EN_CURSO", "El proceso no está en curso.")
        if fase is not None:
            if not 1 <= fase <= len(FASES):
                raise ValidationError("FASE_INVALIDA", f"fase debe estar entre 1 y {len(FASES)}.", field="fase")
            if fase < self.fase_actual:
                raise FlowError("FASE_RETROCEDE", "La fase de un proceso no retrocede.")
            if fase > self.fase_actual:
                self._abrir_fase(fase, ahora)
        if progreso is not None:
            if not 0 <= progreso <= 100:
                raise ValidationError("PROGRESO_INVALIDO", "progreso debe estar entre 0 y 100.", field="progreso")
            self.porcentaje_progreso = max(self.porcentaje_progreso, progreso)
        if cpu is not None:
            if not Decimal(0) <= cpu <= Decimal(100):
                raise ValidationError("CPU_INVALIDA", "cpu debe estar entre 0 y 100.", field="cpu")
            self.porcentaje_cpu = cpu
        if ram_mb is not None:
            if ram_mb < 0:
                raise ValidationError("RAM_INVALIDA", "ram_mb no puede ser negativa.", field="ram_mb")
            self.memoria_ram_mb = ram_mb
        self.fecha_ultimo_latido = ahora

    def completar(self, *, ahora: datetime, id_version_modelo: int) -> None:
        if self.estado != "EN_CURSO":
            raise FlowError("PROCESO_NO_EN_CURSO", "Solo se completa un proceso en curso.")
        self._abrir_fase(len(FASES), ahora)
        self._cerrar(ahora, "COMPLETADO", resultado_fase="OK")
        self.id_version_modelo_resultante = id_version_modelo
        self.porcentaje_progreso = 100

    def fallar(self, *, ahora: datetime, codigo_error: str, motivos: Optional[list] = None) -> None:
        if self.estado not in ESTADOS_ABIERTOS:
            raise FlowError("PROCESO_CERRADO", "El proceso ya terminó.")
        if not codigo_error or not codigo_error.strip():
            raise ValidationError("CODIGO_ERROR_REQUERIDO", "Un proceso fallido necesita su código de error.", field="codigo_error")
        self.codigo_error = codigo_error.strip()[:60]
        self.motivos = motivos
        self._cerrar(ahora, "FALLIDO", resultado_fase="FALLIDA")

    def interrumpir(self, ahora: datetime) -> None:
        if self.estado != "EN_CURSO":
            raise FlowError("PROCESO_NO_EN_CURSO", "Solo se interrumpe un proceso en curso.")
        self._cerrar(ahora, "INTERRUMPIDO", resultado_fase="INTERRUMPIDA")

    def sin_latido(self, ahora: datetime, maximo: timedelta = LATIDO_MAXIMO) -> bool:
        referencia = self.fecha_ultimo_latido or self.fecha_inicio
        return self.estado == "EN_CURSO" and referencia is not None and ahora - referencia > maximo

    # ── internos ──────────────────────────────────────────────────────
    def _abrir_fase(self, fase: int, ahora: datetime) -> None:
        for f in self.fases:
            if f.get("fecha_fin") is None:
                f["fecha_fin"] = ahora.isoformat()
                f["resultado"] = "OK"
        for n in range(self.fase_actual + 1, fase + 1):
            self.fases.append({"fase": n, "nombre": FASES[n - 1], "fecha_inicio": ahora.isoformat(),
                               "fecha_fin": None if n == fase else ahora.isoformat(),
                               "resultado": None if n == fase else "OK"})
        self.fase_actual = max(self.fase_actual, fase)

    def _cerrar(self, ahora: datetime, estado: str, *, resultado_fase: str) -> None:
        for f in self.fases:
            if f.get("fecha_fin") is None:
                f["fecha_fin"] = ahora.isoformat()
                f["resultado"] = resultado_fase
        self.estado = estado
        self.fecha_fin = ahora
        self.fecha_ultimo_latido = ahora
