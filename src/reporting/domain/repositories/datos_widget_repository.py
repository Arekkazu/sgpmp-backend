# | Fecha      | Nombre   | Que se hizo                                         |
# |------------|----------|-----------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: puerto de lectura de datos de los widgets |
# | 2026-11-21 | destroyerban | INC-M08-380-G002 RF-103: activos valorados acotados a las fincas del usuario |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de lectura de los datos que muestran los widgets del dashboard (RF-103).

Solo lecturas: el dashboard no persiste nada (Postcondición 4). Cada consulta de finca recibe un
``id_finca`` ya validado contra las fincas del usuario; ``areas``/``especies`` en ``None`` = todas.
Las filas salen como diccionarios planos listos para el JSON del widget.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

Fila = dict[str, Any]


class DatosWidgetRepository(ABC):
    """Puerto de consultas de los widgets del tablero."""

    # Opciones elegibles
    @abstractmethod
    def areas_de_finca(self, id_finca: int) -> list[Fila]:
        """Lista las áreas activas de la finca."""
        ...

    @abstractmethod
    def especies_de_finca(self, id_finca: int) -> list[Fila]:
        """Lista las especies de la finca."""
        ...

    @abstractmethod
    def sensores_de_finca(self, id_finca: int) -> list[Fila]:
        """Lista los sensores de la finca."""
        ...

    # Telemetría (M03) y predicción (M04)
    @abstractmethod
    def semaforo_areas(self, id_finca: int, areas: Optional[list[int]]) -> list[Fila]:
        """Por área: alertas críticas y de advertencia (M03 activas, sin técnicas, más la última
        inferencia de M04 de cada animal en 24 h) y si el área no tiene de dónde medir."""

    @abstractmethod
    def lecturas(self, id_finca: int, id_area: Optional[int]) -> list[Fila]:
        """Última lectura de cada sensor con el semáforo del monitoreo de M03."""

    @abstractmethod
    def historico(self, id_finca: int, id_area: Optional[int], patron_variable: str,
                  desde: datetime, paso: str) -> list[Fila]:
        """Promedio de lecturas válidas por sensor en intervalos de ``paso``."""

    @abstractmethod
    def alertas_activas(self, id_finca: int, areas: Optional[list[int]], solo_criticas: bool,
                        limite: int) -> tuple[list[Fila], int]:
        """Lista las alertas activas de la finca con su total."""
        ...

    @abstractmethod
    def alertas_sanitarias(self, id_finca: int) -> list[Fila]:
        """Lista las alertas sanitarias de la finca."""
        ...

    @abstractmethod
    def riesgo_alto(self, id_finca: int, especies: Optional[list[int]], limite: int) -> tuple[list[Fila], int]:
        """Lista los activos con riesgo alto con su total."""
        ...

    @abstractmethod
    def distribucion_riesgo(self, id_finca: int, especies: Optional[list[int]], horas: int) -> list[Fila]:
        """Devuelve la distribución de niveles de riesgo en las últimas horas."""
        ...

    @abstractmethod
    def retroalimentacion_pendiente(self, id_finca: int, id_usuario: int, hasta: datetime,
                                    limite: int) -> tuple[list[Fila], int]:
        """Lista las predicciones pendientes de retroalimentación del usuario."""
        ...

    # Activos biológicos (M02) y suministros (M05)
    @abstractmethod
    def inventario(self, id_finca: int, especies: Optional[list[int]]) -> list[Fila]:
        """Devuelve el inventario de activos de la finca."""
        ...

    @abstractmethod
    def eventos(self, id_finca: int, limite: int) -> list[Fila]:
        """Lista los eventos recientes de la finca."""
        ...

    @abstractmethod
    def conversion(self, id_finca: int, especies: Optional[list[int]]) -> list[Fila]:
        """Devuelve la conversión alimenticia de la finca."""
        ...

    # Finanzas (M06) e integración contable (M07); id_finca en None = alcance del Contador en Finanzas
    @abstractmethod
    def activos_valorados(self, id_finca: Optional[int],
                          fincas_permitidas: Optional[list[int]]) -> list[Fila]:
        """Activos reconocidos de ``id_finca`` (o de todas las permitidas si es ``None``).

        ``fincas_permitidas`` en ``None`` = alcance global. No depende de los permisos de Finanzas del
        rol: el Productor ve el valor de su inventario sin leer la valoración (INC-M08-380-G002)."""

    @abstractmethod
    def periodos_abiertos(self, id_finca: Optional[int]) -> list[Fila]:
        """Lista los periodos contables abiertos."""
        ...

    @abstractmethod
    def sin_reconocimiento(self, id_finca: Optional[int]) -> list[Fila]:
        """Lista los activos sin reconocimiento contable."""
        ...

    @abstractmethod
    def integraciones_fallidas(self, dias: int, limite: int) -> tuple[list[Fila], int]:
        """Lista las integraciones fallidas recientes con su total."""
        ...

    @abstractmethod
    def precios_por_vencer(self, dias: int, limite: int) -> tuple[list[Fila], int]:
        """Lista los precios por vencer con su total."""
        ...

    # Configuración (M09)
    @abstractmethod
    def dispositivos(self, id_finca: int, areas: Optional[list[int]]) -> list[Fila]:
        """Dispositivos de la finca con su estado de RF-60, último contacto y última calibración."""

    @abstractmethod
    def configuracion_pendiente(self, id_finca: int, areas: Optional[list[int]]) -> list[Fila]:
        """Lista la configuración pendiente de la finca."""
        ...

    @abstractmethod
    def estado_fincas(self, ids_fincas: Optional[list[int]]) -> list[Fila]:
        """Devuelve el estado general de las fincas."""
        ...
