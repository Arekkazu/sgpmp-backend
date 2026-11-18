# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: nivel y ciclo de vida NUEVA → LEÍDA → ATENDIDA/DESCARTADA |
"""Entidad de dominio para una notificación interna de usuario (RF-14, RF-105)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.identity_access.domain.value_objects.nivel_notificacion import (
    ATENDIDA,
    CRITICA,
    DESCARTADA,
    INFORMATIVA,
    LEIDA,
    NUEVA,
)
from src.shared.errors import BusinessRuleError, FlowError, ValidationError

# RF-105 restricción 1: la acción que cierra una alerta crítica dice qué se hizo.
_ACCION_MIN_CARACTERES = 20
_ACCION_MIN_DISTINTOS = 5


def _accion_informativa(texto: str) -> bool:
    """20+ caracteres y no solo espacios ni un puñado de caracteres repetidos ("aaaa…", "ok ok…")."""
    limpio = texto.strip()
    distintos = {c.lower() for c in limpio if c.isalnum()}
    return len(limpio) >= _ACCION_MIN_CARACTERES and len(distintos) >= _ACCION_MIN_DISTINTOS


@dataclass(eq=False)
class Notificacion:
    """Notificación persistida en la bandeja interna de un usuario."""

    id_notificacion: int
    id_evento: int
    tipo_evento: int
    id_usuario: int
    mensaje: str
    fecha_envio: datetime
    es_leido: bool
    estado_envio: str
    nivel: str = INFORMATIVA
    estado: str = NUEVA
    modulo: Optional[str] = None
    accion_documentada: Optional[str] = None
    fecha_lectura: Optional[datetime] = None
    fecha_atencion: Optional[datetime] = None
    fecha_descarte: Optional[datetime] = None
    ocurrencias: int = 1
    fecha_ultima_ocurrencia: Optional[datetime] = None
    contexto: dict[str, Any] = field(default_factory=dict)

    @property
    def url(self) -> Optional[str]:
        """Pantalla del front a la que lleva la notificación (relativa a la base)."""
        return self.contexto.get("url")

    @property
    def puede_descartarse(self) -> bool:
        return self.nivel != CRITICA and self.estado in (NUEVA, LEIDA)

    @property
    def puede_atenderse(self) -> bool:
        return self.estado in (NUEVA, LEIDA)

    def marcar_como_leida(self, ahora: Optional[datetime] = None) -> None:
        """NUEVA → LEÍDA al abrirla. Idempotente: no toca una ya leída, atendida o descartada."""
        self.es_leido = True
        if self.estado == NUEVA:
            self.estado = LEIDA
            self.fecha_lectura = ahora

    def _exigir_abierta(self) -> None:
        if not self.puede_atenderse:
            raise FlowError(
                code="NOTIFICACION_CERRADA",
                message="Esta notificación ya fue atendida o descartada.",
                field="estado",
            )

    def atender(self, accion: Optional[str], ahora: datetime) -> None:
        """→ ATENDIDA. En una CRÍTICA la acción es obligatoria y debe decir qué se hizo."""
        self._exigir_abierta()
        accion = (accion or "").strip() or None
        if self.nivel == CRITICA and (accion is None or not _accion_informativa(accion)):
            raise ValidationError(
                code="VAL_ENTRADA",
                message=("Cuenta qué hiciste para atender la alerta, con al menos 20 caracteres "
                         "(por ejemplo, «Se revisó el bebedero y se cambió la válvula»)."),
                field="accion_documentada",
            )
        if self.estado == NUEVA:
            self.fecha_lectura = ahora
        self.es_leido = True
        self.estado = ATENDIDA
        self.accion_documentada = accion
        self.fecha_atencion = ahora

    def descartar(self, ahora: datetime) -> None:
        """→ DESCARTADA. Solo ADVERTENCIA e INFORMATIVA; una crítica se cierra atendiéndola."""
        if self.nivel == CRITICA:
            raise BusinessRuleError(
                code="CRITICA_NO_DESCARTABLE",
                message="Las alertas críticas no se pueden descartar: márcala como atendida contando qué hiciste.",
                field="estado",
            )
        self._exigir_abierta()
        if self.estado == NUEVA:
            self.fecha_lectura = ahora
        self.es_leido = True
        self.estado = DESCARTADA
        self.fecha_descarte = ahora
