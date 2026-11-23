# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: transportar UUID y versión del hash sin objetos ORM. |
# | 2026-11-11 | Arekkazu | USAB-M05-M06 T-01 RF-75/76/80: nombre del activo y del usuario en las consultas, no su id |
# | 2026-11-14 | destroyerban | INC-M05-353-G37 RF-80: registro y tipo de suministro del evento, leídos de datos_nuevos |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Entidad de lectura de un evento de ``modulo5.auditorias_suministros`` (RF-80, CU-06).

Distinta de ``EventoAuditoriaSuministro`` (``auditoria_suministro_port.py``),
que es el DTO angosto de escritura de RF-78/79 sin PK/hash/fechas. Esta
entidad refleja la fila completa tal como la persistió el trigger
``trg_audit_hash`` (hash, retención, timestamps).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class EventoAuditoriaSuministroConsulta:
    """Evento de auditoría de suministros para consulta."""
    id_auditoria_suministro: int
    entidad_afectada: str
    tipo_operacion: str
    id_usuario: int
    resultado: str
    fecha_evento: datetime
    datos_anteriores: Optional[dict]
    datos_nuevos: Optional[dict]
    ip_origen: Optional[str]
    id_sesion: Optional[int]
    fecha_emision: Optional[datetime]
    id_activo_biologico: Optional[int]
    id_ciclo_productivo: Optional[int]
    costo_afectado: Optional[Decimal]
    origen_precio: Optional[str]
    clasificacion_registro: Optional[str]
    retencion_aplicable: Optional[str]
    hash_integridad: Optional[str]
    registro_incompleto: Optional[bool]
    detalle_causa: Optional[str]
    numero_reintentos: Optional[int]
    fecha_intentos: Optional[list[datetime]]
    id_gestion_fases: Optional[int]
    id_evento_m05: Optional[UUID] = None
    version_hash_integridad: int = 1
    # Nombres visibles (los llena la consulta); el del usuario queda en None si la RLS no deja leerlo.
    nombre_activo: Optional[str] = None
    nombre_usuario: Optional[str] = None

    @property
    def id_registro_suministro(self) -> Optional[str]:
        """RF-80 Restricción 8: registro de suministro al que aplica el evento (va en ``datos_nuevos``)."""
        valor = self._dato("id_registro_suministro")
        return str(valor) if valor is not None else None

    @property
    def id_tipo_suministro(self) -> Optional[str]:
        """RF-80 Restricción 8: tipo de suministro del evento (va en ``datos_nuevos``)."""
        valor = self._dato("id_tipo_suministro")
        return str(valor) if valor is not None else None

    def _dato(self, clave: str):
        return self.datos_nuevos.get(clave) if isinstance(self.datos_nuevos, dict) else None
