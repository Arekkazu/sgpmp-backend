"""Entidad de dominio ``Finca`` — unidad organizacional productiva (RF-19)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.configuration.domain.value_objects.nombre_finca import NombreFinca
from src.configuration.domain.value_objects.tamano_h import TamanoH
from src.configuration.domain.value_objects.ubicacion_finca import UbicacionFinca


@dataclass(eq=False)
class Finca:
    nombre: NombreFinca
    ubicacion: UbicacionFinca
    tamano_h: TamanoH
    es_activo: bool
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    id_finca: Optional[int] = None
    id_usuario: Optional[int] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: NombreFinca,
        ubicacion: UbicacionFinca,
        tamano_h: TamanoH,
        id_usuario: Optional[int],
        fecha_creacion: datetime,
        fecha_actualizacion: datetime,
    ) -> Finca:
        return cls(
            nombre=nombre,
            ubicacion=ubicacion,
            tamano_h=tamano_h,
            id_usuario=id_usuario,
            es_activo=True,
            fecha_creacion=fecha_creacion,
            fecha_actualizacion=fecha_actualizacion,
        )

    def actualizar(
        self,
        *,
        nombre: NombreFinca,
        ubicacion: UbicacionFinca,
        tamano_h: TamanoH,
        fecha_actualizacion: datetime,
    ) -> None:
        self.nombre = nombre
        self.ubicacion = ubicacion
        self.tamano_h = tamano_h
        self.fecha_actualizacion = fecha_actualizacion

    def desactivar(self) -> None:
        self.es_activo = False

    def _snapshot(self) -> dict:
        return {
            "nombre": self.nombre.valor,
            "ubicacion": self.ubicacion.to_dict(),
            "tamano_h": str(self.tamano_h.valor),
            "id_usuario": self.id_usuario,
            "es_activo": self.es_activo,
            "fecha_creacion": self.fecha_creacion.isoformat(),
            "fecha_actualizacion": self.fecha_actualizacion.isoformat(),
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Finca):
            return NotImplemented
        if self.id_finca is None or other.id_finca is None:
            return self is other
        return self.id_finca == other.id_finca

    def __hash__(self) -> int:
        return hash(self.id_finca)
