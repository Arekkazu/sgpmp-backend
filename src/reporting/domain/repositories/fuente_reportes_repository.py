# | Fecha      | Nombre   | Que se hizo                                                   |
# |------------|----------|---------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104/RF-106: puerto de lectura de los datos de reportes |
"""Puerto de lectura de los datos que consolidan los reportes (RF-104) y el historial predictivo (RF-106).

Todo es de solo lectura y se acota a ``fincas`` (``None`` = alcance global, una lista = esas fincas). Las
fechas ``desde``/``hasta`` son instantes UTC (inicio y fin del día del usuario); ``inicio``/``fin`` son días
calendario. Cada método devuelve filas planas (``dict``); armar el reporte es tarea de la aplicación.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Optional

Fila = dict[str, Any]
Fincas = Optional[list[int]]


class FuenteReportesRepository(ABC):

    # --- Referencias (validación de filtros) ----------------------------------------------------

    @abstractmethod
    def ubicar(self, tipo: str, id_referencia: int) -> Optional[Fila]:
        """Finca de un animal, lote, área, sensor o especie (``id_finca``), sin importar si es del usuario,
        para distinguir 404 (no existe) de 403 (es de otra finca)."""

    @abstractmethod
    def periodo(self, id_periodo: int) -> Optional[Fila]:
        """Período contable: fechas, estado, titular (NIT) y si el usuario puede verlo (``accesible``)."""

    @abstractmethod
    def fincas(self, fincas: Fincas) -> list[Fila]:
        """Nombre, razón social, NIT e id de logo de las fincas del alcance."""

    @abstractmethod
    def fincas_de_titular(self, nit: str, fincas: Fincas) -> list[int]:
        """Fincas del alcance cuyo titular es ``nit`` (los períodos cuelgan del titular)."""

    @abstractmethod
    def ruta_logo(self, id_finca: int) -> Optional[str]:
        """Logo PNG/JPEG de la identidad visual de la finca, si existe en disco."""

    @abstractmethod
    def nombres_usuarios(self, ids: list[int]) -> dict[int, Optional[str]]:
        """Nombre visible de cada usuario (la RLS de usuarios oculta a los demás; solo se lee el nombre)."""

    @abstractmethod
    def opciones(self, tipo: str, fincas: Fincas) -> list[Fila]:
        """Valores elegibles de un filtro de referencia (``valor``, ``etiqueta``) dentro del alcance."""

    # --- Productivos ---------------------------------------------------------------------------

    @abstractmethod
    def inventario(self, *, fincas: Fincas, inicio: date, fin: date, hasta: datetime, especie: Optional[int],
                   estado: Optional[str]) -> list[Fila]: ...

    @abstractmethod
    def costos(self, *, fincas: Fincas, inicio: Optional[date], fin: date, especie: Optional[int],
               tipo: Optional[str], activo: Optional[int] = None) -> list[Fila]: ...

    @abstractmethod
    def produccion(self, *, fincas: Fincas, desde: Optional[datetime], hasta: datetime, especie: Optional[int],
                   activo: Optional[int]) -> list[Fila]: ...

    @abstractmethod
    def conversion(self, *, fincas: Fincas, inicio: date, fin: date, especie: Optional[int],
                   activo: Optional[int]) -> list[Fila]: ...

    @abstractmethod
    def salidas(self, *, fincas: Fincas, desde: datetime, hasta: datetime, especie: Optional[int]) -> list[Fila]: ...

    # --- Contables -----------------------------------------------------------------------------

    @abstractmethod
    def valoracion_periodo(self, *, id_periodo: int, fincas: list[int]) -> list[Fila]: ...

    @abstractmethod
    def exportaciones(self, id_periodo: int) -> list[Fila]: ...

    @abstractmethod
    def variacion_periodos(self, *, base: int, comparacion: int, fincas: list[int]) -> list[Fila]: ...

    # --- Sanitarios ----------------------------------------------------------------------------

    @abstractmethod
    def eventos_sanitarios(self, *, fincas: Fincas, desde: Optional[datetime], hasta: datetime,
                           especie: Optional[int], activo: Optional[int]) -> list[Fila]: ...

    @abstractmethod
    def ficha(self, id_activo: int) -> Optional[Fila]: ...

    @abstractmethod
    def valoracion_por_periodo(self, id_activo: int) -> list[Fila]: ...

    @abstractmethod
    def predicciones_activas(self, *, fincas: Fincas, especie: Optional[int], activo: Optional[int],
                             desde: Optional[datetime]) -> list[Fila]: ...

    @abstractmethod
    def medicamentos(self, *, fincas: Fincas, inicio: date, fin: date, especie: Optional[int],
                     activo: Optional[int]) -> list[Fila]: ...

    @abstractmethod
    def retiros_vigentes(self, *, fincas: Fincas, hoy: date, especie: Optional[int],
                         activo: Optional[int]) -> list[Fila]: ...

    # --- IoT -----------------------------------------------------------------------------------

    @abstractmethod
    def telemetria(self, *, infraestructura: int, desde: datetime, hasta: datetime, sensor: Optional[int],
                   patron_variable: Optional[str]) -> list[Fila]: ...

    @abstractmethod
    def dispositivos(self, *, fincas: Fincas, corte: datetime, es_hoy: bool,
                     infraestructura: Optional[int]) -> list[Fila]: ...

    @abstractmethod
    def calibraciones(self, *, fincas: Fincas, desde: datetime, hasta: datetime, sensor: Optional[int],
                      infraestructura: Optional[int]) -> list[Fila]: ...

    @abstractmethod
    def sensores_sin_calibrar(self, *, fincas: Fincas, antes_de: datetime, sensor: Optional[int],
                              infraestructura: Optional[int]) -> list[Fila]: ...

    @abstractmethod
    def alertas_sensores(self, *, fincas: Fincas, desde: datetime, hasta: datetime,
                         infraestructura: Optional[int]) -> list[Fila]: ...

    # --- Agregados (gerenciales: solo totales, RNF-11) -----------------------------------------

    @abstractmethod
    def animales_por_especie(self, *, fincas: Fincas, fin: date) -> list[Fila]:
        """Animales en inventario al cierre del día ``fin`` por finca y especie."""

    @abstractmethod
    def valor_portafolio(self, *, fincas: Fincas, fin: date) -> list[Fila]:
        """Suma del valor del inventario por finca al cierre de ``fin`` (sin filas por animal)."""

    @abstractmethod
    def bajas_por_tipo(self, *, fincas: Fincas, desde: datetime, hasta: datetime) -> list[Fila]: ...

    @abstractmethod
    def costos_por_tipo(self, *, fincas: Fincas, inicio: date, fin: date) -> list[Fila]: ...

    @abstractmethod
    def riesgo_por_nivel(self, *, fincas: Fincas, desde: datetime, hasta: datetime) -> list[Fila]:
        """Eventos sanitarios y predicciones del período por finca y nivel de riesgo."""

    @abstractmethod
    def animales_con_riesgo_activo(self, *, fincas: Fincas) -> list[Fila]: ...

    @abstractmethod
    def dispositivos_por_estado(self, *, fincas: Fincas) -> list[Fila]: ...

    @abstractmethod
    def variacion_total_periodo(self, *, id_periodo: int, fincas: list[int]) -> Any: ...

    @abstractmethod
    def ultimo_periodo_cerrado(self, *, nit: str, hasta: date) -> Optional[Fila]: ...

    # --- Historial predictivo (RF-106) ---------------------------------------------------------

    @abstractmethod
    def inferencias(self, *, activo: int, desde: datetime, hasta: datetime) -> list[Fila]: ...

    @abstractmethod
    def retroalimentaciones(self, *, activo: int, desde: datetime, hasta: datetime) -> list[Fila]: ...

    @abstractmethod
    def eventos_sanitarios_aislados(self, *, activo: int, desde: datetime, hasta: datetime) -> list[Fila]:
        """Como :meth:`eventos_sanitarios`, sin abortar la instantánea si falla (las tres fuentes son independientes)."""

    @abstractmethod
    def parametro(self, nombre: str) -> Any:
        """Valor vigente de un parámetro configurable de M09 (``modulo4.parametros_mlops``)."""
