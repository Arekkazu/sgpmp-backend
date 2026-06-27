from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DetalleIndividual:
    raza: str
    sexo: str
    fecha_nacimiento: datetime
    peso_inicial: Optional[Decimal] = None
    id_detalle: Optional[int] = None
    fecha_creacion: Optional[datetime] = None


@dataclass
class DetallePoblacional:
    cantidad_inicial: int
    cantidad_actual: int
    peso_promedio_inicial: Optional[Decimal] = None
    peso_promedio: Optional[Decimal] = None
    biomasa_total: Optional[Decimal] = None
    densidad: Optional[Decimal] = None
    id_detalle: Optional[int] = None


@dataclass
class HistorialInfraestructura:
    id_historial: int
    id_activo_biologico: int
    id_infraestructura: int
    nombre_infraestructura: str
    tipo_infraestructura: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]


@dataclass(eq=False)
class ActivoBiologico:
    id_especie: int
    tipo: str
    origen_financiero: str
    id_infraestructura: int
    id_estado: int
    id_usuario: int
    identificador: Optional[str] = None
    fecha_inicio_ciclo: Optional[date] = None
    detalles_procedencia: Optional[str] = None
    costo_adquisicion: Optional[Decimal] = None
    soporte_documental: Optional[str] = None
    descripcion: Optional[str] = None
    atributos_dinamicos: Optional[dict] = None
    detalle_individual: Optional[DetalleIndividual] = None
    detalle_poblacional: Optional[DetallePoblacional] = None
    id_activo_biologico: Optional[int] = None
    fecha_creacion: Optional[datetime] = None
    nombre_estado: Optional[str] = None

    @classmethod
    def crear(cls, dto: object, id_usuario: int) -> ActivoBiologico:
        from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo

        detalle_individual: Optional[DetalleIndividual] = None
        detalle_poblacional: Optional[DetallePoblacional] = None

        if getattr(dto, 'tipo_activo') == 'INDIVIDUAL':
            detalle_individual = DetalleIndividual(
                raza=dto.raza,
                sexo=dto.sexo,
                fecha_nacimiento=dto.fecha_nacimiento,
                peso_inicial=dto.peso_inicial,
            )
        else:
            detalle_poblacional = DetallePoblacional(
                cantidad_inicial=dto.cantidad_inicial,
                cantidad_actual=dto.cantidad_inicial,  # se inicializa = cantidad_inicial
                peso_promedio_inicial=dto.peso_promedio_inicial,
            )

        return cls(
            id_especie=dto.id_especie,
            tipo=dto.tipo_activo,
            origen_financiero=dto.origen_financiero,
            id_infraestructura=dto.id_infraestructura,
            id_estado=EstadoActivo.ACTIVO,
            id_usuario=id_usuario,
            identificador=dto.identificador,
            fecha_inicio_ciclo=dto.fecha_inicio_ciclo,
            detalles_procedencia=dto.detalles_procedencia,
            costo_adquisicion=dto.costo_adquisicion,
            soporte_documental=dto.soporte_documental,
            atributos_dinamicos=dto.atributos_dinamicos,
            detalle_individual=detalle_individual,
            detalle_poblacional=detalle_poblacional,
        )

    def _snapshot(self) -> dict:
        return {
            'id_activo_biologico': self.id_activo_biologico,
            'id_especie': self.id_especie,
            'tipo': self.tipo,
            'identificador': self.identificador,
            'origen_financiero': self.origen_financiero,
            'id_infraestructura': self.id_infraestructura,
            'id_estado': self.id_estado,
            'fecha_inicio_ciclo': self.fecha_inicio_ciclo.isoformat() if self.fecha_inicio_ciclo else None,
            'costo_adquisicion': str(self.costo_adquisicion) if self.costo_adquisicion else None,
            'soporte_documental': self.soporte_documental,
            'detalles_procedencia': self.detalles_procedencia,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ActivoBiologico):
            return NotImplemented
        if self.id_activo_biologico is None or other.id_activo_biologico is None:
            return self is other
        return self.id_activo_biologico == other.id_activo_biologico

    def __hash__(self) -> int:
        return hash(self.id_activo_biologico)
