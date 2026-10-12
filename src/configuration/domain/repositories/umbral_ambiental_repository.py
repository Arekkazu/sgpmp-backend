"""Puerto (ABC) de persistencia para el agregado UmbralAmbiental (CU03 RF-17)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental


class UmbralAmbientalRepository(ABC):
    """Contrato de acceso a datos para :class:`UmbralAmbiental` y sus niveles."""

    @abstractmethod
    def obtener_por_id(self, id_umbral_ambiental: int, *, bloquear: bool = False) -> Optional[UmbralAmbiental]:
        """``bloquear=True`` toma la fila con ``SELECT ... FOR UPDATE`` (#498)."""

    @abstractmethod
    def obtener_por_especie_y_variable(
        self, id_especie: int, id_variable_ambiental: int
    ) -> Optional[UmbralAmbiental]:
        """Umbral de la especie para la variable, o ``None`` si no existe."""

    @abstractmethod
    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[UmbralAmbiental]:
        """Umbrales de la especie, opcionalmente solo los activos."""

    @abstractmethod
    def guardar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        """Inserta el umbral y devuelve la entidad con su id asignado."""

    @abstractmethod
    def actualizar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        """Persiste los cambios del umbral y devuelve la entidad actualizada."""

    @abstractmethod
    def actualizar_estado_sincronizacion(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        """Persiste solo estado_sincronizacion/fecha_ultima_sincronizacion/motivo_fallo_sincronizacion.

        No toca valor_min/valor_max/niveles -- se usa después del intento de
        propagación al Nodo Edge (INC-M09-104-G29), en un segundo commit
        separado del guardado del umbral en sí.
        """
        raise NotImplementedError

    @abstractmethod
    def desactivar_todos_por_especie(self, id_especie: int) -> None:
        """Marca como inactivos todos los umbrales activos de una especie. Hace ``flush``."""
        raise NotImplementedError

    @abstractmethod
    def guardar_desde_snapshot(self, datos: dict, id_especie: int, id_usuario: int) -> None:
        """Inserta un umbral + niveles a partir de un dict del params_snapshot. Hace ``flush``."""
        raise NotImplementedError
