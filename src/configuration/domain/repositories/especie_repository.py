"""Puerto de persistencia del agregado ``Especie`` (capa de dominio).

Define el contrato que la capa de aplicación usa para leer y guardar especies,
expresado en términos del dominio: recibe y devuelve la entidad :class:`Especie`
y el value object :class:`NombreEspecie`, nunca modelos ORM ni filas.

La implementación concreta vive en
``infrastructure/repositories/especie_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie


class EspecieRepository(ABC):
    """Contrato de acceso a datos para el agregado :class:`Especie`."""

    @abstractmethod
    def obtener_por_id(self, id_especie: int) -> Optional[Especie]:
        """Obtiene una especie por su identidad.

        Args:
            id_especie: PK de la especie.

        Returns:
            La entidad :class:`Especie` o ``None`` si no existe.
        """
        raise NotImplementedError

    @abstractmethod
    def obtener_por_nombre(self, nombre: NombreEspecie) -> Optional[Especie]:
        """Busca una especie cuyo nombre normalizado coincida (case-insensitive).

        Usado para validar unicidad antes de insertar o actualizar.

        Args:
            nombre: Value object con el nombre a comparar.

        Returns:
            La entidad :class:`Especie` que coincide o ``None`` si no existe.
        """
        raise NotImplementedError

    @abstractmethod
    def guardar(self, especie: Especie) -> Especie:
        """Inserta una especie nueva y retorna la entidad con ``id_especie`` asignado.

        Hace ``flush`` interno. El ``commit`` lo emite el caso de uso.

        Args:
            especie: Entidad nueva (``id_especie`` es ``None``).

        Returns:
            La entidad re-hidratada con ``id_especie`` y ``fecha_creacion``
            poblados por la base de datos.

        Raises:
            ConflictError: Si el nombre ya existe en el catálogo. HTTP 409.
        """
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, especie: Especie) -> Especie:
        """Persiste los cambios de una especie existente.

        Hace ``flush`` interno. El ``commit`` lo emite el caso de uso.

        Args:
            especie: Entidad con los campos ya modificados.

        Returns:
            La entidad re-hidratada desde la base de datos.

        Raises:
            ConflictError: Si el nuevo nombre ya pertenece a otra especie. HTTP 409.
        """
        raise NotImplementedError

    @abstractmethod
    def listar(self, *, solo_activas: bool = False) -> list[Especie]:
        """Retorna el catálogo completo de especies.

        Args:
            solo_activas: Si es ``True`` filtra solo las especies con
                ``es_activo=True``.

        Returns:
            Lista de entidades :class:`Especie` ordenadas por nombre.
        """
        raise NotImplementedError
