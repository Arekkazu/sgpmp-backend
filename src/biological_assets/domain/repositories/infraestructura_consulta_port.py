# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: el área expone sus especies y la capacidad derivada a M02 (RFC-012) |
# | 2026-10-23 | destroyerban | DEV-23 RF-33/34/36/48: capacidad efectiva del área (RFC-012) |
"""Puerto de lectura de infraestructuras productivas de M09 (RF-34, RF-36, RF-48)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from dataclasses import field
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import SensorEnInfraestructura
from src.configuration.domain.services.capacidad_area import EspecieDelArea


@dataclass
class InfraestructuraConsulta:
    """Infraestructura de M09 con los datos que M02 necesita (superficie, capacidad,
    finca).
    """
    id_infraestructura: int
    nombre: str
    tipo: str
    es_activo: bool
    superficie: Optional[Decimal] = None
    id_finca: Optional[int] = None
    # RFC-012: derivada = capacidad_efectiva (floor(MIN densidad × superficie));
    # None si el área no tiene especies o alguna no tiene densidad.
    capacidad_maxima: Optional[int] = None
    # RFC-012: especies presentes, con grupo y densidad para validar la capacidad
    # (``capacidad_area.validar_capacidad``) y la compatibilidad por grupo.
    especies: list[EspecieDelArea] = field(default_factory=list)

    @property
    def id_especies(self) -> list[int]:
        return [e.id_especie for e in self.especies]


class InfraestructuraConsultaPort(ABC):
    """Consulta a M09 de infraestructuras, su ocupación, sensores y compatibilidad con
    especies.
    """

    @abstractmethod
    def obtener_activa(self, id_infraestructura: int) -> Optional[InfraestructuraConsulta]:
        """Retorna la infraestructura si existe y está activa, None en caso contrario."""

    @abstractmethod
    def existe(self, id_infraestructura: int) -> bool:
        """Retorna True si la infraestructura existe, sin importar si está activa.

        Usado para distinguir "no existe" de "existe pero está inactiva" en
        mensajes de error (INC-M02-89-G83) -- `obtener_activa` devuelve None
        en ambos casos y no permite esa distinción."""

    @abstractmethod
    def listar_activas(self, excluir_id: Optional[int] = None) -> list[InfraestructuraConsulta]:
        """Lista infraestructuras activas, excluyendo opcionalmente una por id."""

    @abstractmethod
    def calcular_ocupacion(self, id_infraestructura: int) -> int:
        """Retorna la cantidad total de individuos activos en la infraestructura."""

    @abstractmethod
    def obtener_especie(self, id_especie: int) -> Optional[EspecieDelArea]:
        """RFC-012: grupo de manejo y densidad de una especie activa (None si no existe o está inactiva)."""

    @abstractmethod
    def asociar_especie(self, id_infraestructura: int, id_especie: int) -> None:
        """RFC-012: asocia la especie al área (tabla puente de DB-06), dentro de la transacción en curso."""

    @abstractmethod
    def bloquear_capacidad(self, id_infraestructura: int) -> None:
        """Serializa hasta el fin de la transacción las entradas de individuos al área,
        para que dos altas simultáneas no pasen ambas el chequeo de capacidad."""

    @abstractmethod
    def listar_sensores_activos(self, id_infraestructura: int) -> list[SensorEnInfraestructura]:
        """Retorna los sensores con asociación de área activa en la infraestructura (enriquecimiento RF-22)."""

    @abstractmethod
    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        """C2 (RF-48): compatibilidad entre el tipo de infraestructura y la especie del activo.

        Si no hay ninguna regla configurada para ``tipo_infraestructura``, es
        compatible por defecto (sin restricción todavía definida para ese tipo).
        Si hay al menos una regla, solo son compatibles las especies listadas.
        """
