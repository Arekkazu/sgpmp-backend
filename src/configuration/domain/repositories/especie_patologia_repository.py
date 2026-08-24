"""Puerto de persistencia de patologías por especie (capa de dominio).

Gestiona la entidad M09 ``EspeciePatologia`` sobre la tabla
`modulo9.especies_patologias`. La unicidad del nombre es **por especie**
(case-insensitive). El catálogo clínico global `modulo9.patologias` (M04) no se
gestiona desde aquí.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia


class EspeciePatologiaRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_especies_patologias: int) -> Optional[EspeciePatologia]:
        """Obtiene una patología por especie por su identidad. ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_especie_y_nombre(
        self, id_especie: int, nombre: NombrePatologia
    ) -> Optional[EspeciePatologia]:
        """Busca una patología por especie por nombre normalizado (case-insensitive)."""
        raise NotImplementedError

    @abstractmethod
    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[EspeciePatologia]:
        """Retorna las patologías configuradas para una especie."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: EspeciePatologia) -> EspeciePatologia:
        """Inserta una patología por especie. Hace ``flush``."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: EspeciePatologia) -> EspeciePatologia:
        """Persiste cambios de nombre, descripcion y es_activo. Hace ``flush``."""
        raise NotImplementedError

    @abstractmethod
    def eliminar_todas_de_especie(self, id_especie: int) -> None:
        """Elimina (físicamente) todas las patologías de una especie. Hace ``flush``."""
        raise NotImplementedError

    @abstractmethod
    def vincular_desde_snapshot(self, id_especie: int, datos: dict) -> None:
        """Inserta una patología por especie desde un snapshot de plantilla (RF-32).

        ``datos`` lleva ``nombre``/``descripcion``/``es_activo``. Hace ``flush``.
        """
        raise NotImplementedError
