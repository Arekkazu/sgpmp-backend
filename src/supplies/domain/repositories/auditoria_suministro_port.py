# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-80: emisión, reintentos y sus fechas   |
# | 2026-11-07 | Leandro | INC-M05-272-G25 RF-77: admitir contexto estructurado del reporte o archivo auditado. |
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: emitir UUID estable y documentar datos ausentes en eventos incompletos. |
# | 2026-11-09 | LuisfNarvaez01   | INC-M05-284-G43 RF-81: el evento guarda filtros aplicados y total retornado |
# | 2026-11-14 | destroyerban     | INC-M05-353-G37 RF-80: registro y tipo de suministro; incompleto según los campos mínimos de cada tipo |
"""Puerto de auditoría de eventos de negocio RF-78/RF-79/RF-81 (CU-05).

Puerto angosto de escritura (patrón ``NotificacionMedicamentoPort``): el use
case construye un ``EventoAuditoriaSuministro`` y lo entrega tal cual; la
implementación mapea a una fila de ``modulo5.auditorias_suministros``.
``hash_integridad`` lo calcula el trigger de BD (``trg_audit_hash``), no se
recibe aquí. Los 8 valores de ``tipo_operacion`` de negocio se agregaron al
enum PG en el Gap 4 de ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4


# RF-80 Restricción 8: campos mínimos de cada tipo, además de los de todos los eventos
# (tipo, resultado y emisión los pone siempre el emisor). Se nombran como los ve el usuario
# en la bitácora; ``id_usuario`` no figura porque la columna es obligatoria.
_CAMPOS_BASE = ("id_activo_biologico", "id_ciclo_productivo")
_CAMPOS_POR_TIPO: dict[str, tuple[str, ...]] = {
    "SUMINISTRO_REGISTRADO": ("id_registro_suministro", "id_tipo_suministro", "costo_afectado", "origen_precio"),
    "SUMINISTRO_CORREGIDO": ("id_registro_suministro", "id_tipo_suministro", "costo_afectado", "origen_precio"),
    "ACUMULADO_ACTUALIZADO": ("id_registro_suministro", "costo_afectado"),
    "CICLO_CONSOLIDADO": ("costo_afectado",),
    "PRECIO_MANUAL_INGRESADO": ("id_registro_suministro", "origen_precio"),
    "REPORTE_COSTOS_GENERADO": ("costo_afectado",),
    "PROVISION_INCREMENTAL_ENTREGADA": ("id_registro_suministro",),
    "PROVISION_INCREMENTAL_FALLIDA": ("id_registro_suministro", "numero_reintentos", "fecha_intentos"),
    "PROVISION_PENDIENTE": ("numero_reintentos",),
    "REGISTRO_FALLIDO": ("id_tipo_suministro", "numero_reintentos"),
}
_NOMBRE_VISIBLE = {
    "id_activo_biologico": "activo biológico",
    "id_ciclo_productivo": "ciclo productivo",
    "id_registro_suministro": "registro de suministro",
    "id_tipo_suministro": "tipo de suministro",
    "costo_afectado": "costo afectado",
    "origen_precio": "origen del precio",
    "numero_reintentos": "número de reintentos",
    "fecha_intentos": "fechas de los intentos",
}


@dataclass(frozen=True)
class EventoAuditoriaSuministro:
    """Evento de negocio de RF-78/RF-79/RF-81 a registrar en ``auditorias_suministros``.

    Al construirse verifica los campos mínimos de su tipo (RF-80 Restricción 8, E2):
    si falta alguno queda ``registro_incompleto`` y ``detalle_causa`` los nombra.
    ``id_registro_suministro`` e ``id_tipo_suministro`` viajan en ``datos_nuevos``
    (la tabla no tiene columna propia; el hash de la fila los cubre igual).
    """

    entidad_afectada: str
    tipo_operacion: str
    id_usuario: int
    resultado: str
    id_activo_biologico: Optional[int] = None
    id_ciclo_productivo: Optional[int] = None
    id_gestion_fases: Optional[int] = None
    costo_afectado: Optional[Decimal] = None
    origen_precio: Optional[str] = None
    detalle_causa: Optional[str] = None
    numero_reintentos: Optional[int] = None
    registro_incompleto: bool = False
    fecha_intentos: list[datetime] = field(default_factory=list)
    fecha_emision: Optional[datetime] = None
    # RF-77/RF-81 CA-8: contexto del reporte o archivo, o filtros aplicados y total retornado del historial.
    datos_nuevos: Optional[dict] = None
    id_evento_m05: UUID = field(default_factory=uuid4)
    # RF-80 Restricción 8: registro de suministro al que aplica y su tipo (ALIMENTO, MEDICAMENTO…).
    id_registro_suministro: Optional[str] = None
    id_tipo_suministro: Optional[str] = None

    def __post_init__(self) -> None:
        if self.id_registro_suministro is not None:
            object.__setattr__(self, "id_registro_suministro", str(self.id_registro_suministro))
        faltantes = [_NOMBRE_VISIBLE[c] for c in self.campos_minimos_faltantes()]
        if not faltantes and not self.registro_incompleto:
            return
        object.__setattr__(self, "registro_incompleto", True)
        detalle = (self.detalle_causa or "").strip()
        if faltantes:
            campos = "Campos faltantes: " + ", ".join(faltantes) + "."
            if campos not in detalle:
                detalle = f"{detalle} {campos}".strip()
        elif not detalle:
            detalle = (
                "Campos faltantes: detalle de la causa. "
                "El emisor no identificó otros datos ausentes."
            )
        object.__setattr__(self, "detalle_causa", detalle)

    def campos_minimos_faltantes(self) -> list[str]:
        """Campos de la Restricción 8 que el evento no trae, en el orden en que se listan."""
        exigidos = _CAMPOS_BASE + _CAMPOS_POR_TIPO.get(self.tipo_operacion, ())
        return [c for c in exigidos if getattr(self, c) in (None, [], "")]

    def datos_nuevos_con_referencias(self) -> Optional[dict]:
        """``datos_nuevos`` más el registro y el tipo de suministro, si el evento los trae."""
        referencias = {
            clave: valor
            for clave, valor in (
                ("id_registro_suministro", self.id_registro_suministro),
                ("id_tipo_suministro", self.id_tipo_suministro),
            )
            if valor is not None
        }
        if not referencias:
            return self.datos_nuevos
        return {**(self.datos_nuevos or {}), **referencias}


class AuditoriaSuministroPort(ABC):
    """Contrato de registro de eventos de auditoría de RF-78/RF-79."""

    @abstractmethod
    def registrar(self, evento: EventoAuditoriaSuministro) -> None:
        """Persiste el evento de auditoría. No hace ``commit``."""
        raise NotImplementedError
