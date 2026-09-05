from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    GestionFase,
    HistorialInfraestructura,
)


class ActivoBiologicoRepository(ABC):
    @abstractmethod
    def guardar(self, activo: ActivoBiologico) -> ActivoBiologico:
        """Persiste el activo biológico y sus detalles en una sola transacción de DB."""

    @abstractmethod
    def obtener_por_id(self, id_activo: int) -> Optional[ActivoBiologico]:
        """Retorna el activo biológico con sus detalles, o None si no existe."""

    @abstractmethod
    def listar(
        self,
        id_especie: Optional[int],
        tipo: Optional[str],
        id_estado: Optional[int],
        id_infraestructura: Optional[int],
        pagina: int,
        page_size: int,
    ) -> tuple[list[ActivoBiologico], int]:
        """Lista activos con filtros opcionales y paginación. Devuelve (registros, total)."""

    @abstractmethod
    def existe_identificador(self, identificador: str) -> bool:
        """Verifica si el identificador ya está registrado (case-insensitive)."""

    @abstractmethod
    def obtener_asociacion_activa(self, id_activo: int) -> Optional[HistorialInfraestructura]:
        """Retorna la asociación de infraestructura activa (fecha_fin IS NULL)."""

    @abstractmethod
    def obtener_historial_infraestructura(self, id_activo: int) -> list[HistorialInfraestructura]:
        """Retorna el historial completo de asociaciones de infraestructura."""

    @abstractmethod
    def actualizar_detalle_individual(self, activo: ActivoBiologico) -> ActivoBiologico:
        """Persiste los cambios en detalle_individual del activo."""

    @abstractmethod
    def obtener_gestiones_fases(self, id_activo: int) -> list[GestionFase]:
        """Retorna todas las gestiones de fase del activo, con nombre_ciclo y fase_actual calculados."""

    @abstractmethod
    def cerrar_gestion_activa(self, id_activo: int, fecha_fin: datetime, motivo: str, usuario_id: int) -> None:
        """Cierra la gestión de fase activa (es_activa=False, fecha_finalizacion=fecha_fin)."""

    @abstractmethod
    def crear_gestion_fase(self, gestion: GestionFase) -> GestionFase:
        """Inserta un nuevo registro en gestiones_fases."""

    @abstractmethod
    def actualizar_detalle_poblacional(self, activo: ActivoBiologico) -> ActivoBiologico:
        """Persiste los cambios en detalle_poblacional (cantidad_actual, peso_promedio, biomasa_total, densidad)."""

    @abstractmethod
    def actualizar_estado(self, id_activo: int, nuevo_id_estado: int) -> None:
        """Actualiza id_estado en activos_biologicos."""

    @abstractmethod
    def tiene_sensores_activos(self, id_activo: int) -> bool:
        """Retorna True si el activo tiene asociaciones a sensores con fecha_fin > ahora."""

    @abstractmethod
    def obtener_fase_activa(self, id_activo: int) -> Optional[GestionFase]:
        """Retorna la gestión de fase activa del activo, o None si no tiene."""
