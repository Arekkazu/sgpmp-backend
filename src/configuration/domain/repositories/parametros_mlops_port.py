# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de parámetros operativos configurables."""
from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.configuration.domain.entities.parametro_mlops import ParametroMLOps


class ParametrosMLOpsPort(ABC):
    """Puerto de lectura y escritura de parámetros operativos."""
    @abstractmethod
    def bloquear_configuracion(self) -> None:
        """Serializa la validación y escritura administrativa del grupo de parámetros."""

    @abstractmethod
    def obtener(self, nombres: Sequence[str]) -> dict[str, ParametroMLOps]:
        """Lee un snapshot de los parámetros solicitados, sin caché de proceso."""

    @abstractmethod
    def guardar(self, parametros: Sequence[ParametroMLOps], id_usuario: int) -> None:
        """Inserta/actualiza la configuración; la aplicación controla el commit."""
