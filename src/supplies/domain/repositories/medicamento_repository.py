"""Puerto del repositorio de aplicaciones de medicamento (RF-76).

Expresado en términos de dominio: recibe y devuelve la entidad ``Medicamento``.
La implementación SQLAlchemy hace ``flush`` interno; el ``commit`` lo emite el
caso de uso.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, time
from typing import Optional

from src.supplies.domain.entities.medicamento import Medicamento


class MedicamentoRepository(ABC):
    """Contrato de persistencia de registros de aplicación de medicamento."""

    @abstractmethod
    def existe_duplicado_validado(
        self,
        *,
        id_activo_biologico: int,
        nombre_medicamento: str,
        fecha_aplicacion: date,
        hora_aplicacion: Optional[time],
    ) -> bool:
        """Indica si ya existe un medicamento VALIDADO con la misma clave de duplicidad."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, medicamento: Medicamento) -> Medicamento:
        """Persiste una aplicación nueva y devuelve la entidad con campos derivados."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_id(self, id_medicamento: int) -> Optional[Medicamento]:
        """Devuelve la aplicación por id o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def anular(self, medicamento: Medicamento) -> Medicamento:
        """Aplica la anulación (solo estado y campos de anulación)."""
        raise NotImplementedError

    @abstractmethod
    def max_fecha_fin_retiro_vigente(self, id_activo: int) -> Optional[date]:
        """Devuelve la mayor ``fecha_fin_retiro`` entre los tratamientos VALIDADOS activos."""
        raise NotImplementedError

    @abstractmethod
    def obtener_tratamiento_vigente(self, id_activo: int) -> Optional[Medicamento]:
        """Devuelve el tratamiento VALIDADO con la ``fecha_fin_retiro`` más lejana (o ``None``).

        A diferencia de ``max_fecha_fin_retiro_vigente`` (que solo expone la
        fecha), devuelve la entidad completa: el scheduler de reversión
        (RF-76 pasos 11-13) necesita también su ``id_usuario`` como actor de
        auditoría del cambio de estado.
        """
        raise NotImplementedError

    @abstractmethod
    def listar(
        self,
        *,
        id_activo_biologico: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        estado_registro: Optional[str] = None,
    ) -> list[Medicamento]:
        """Lista aplicaciones aplicando los filtros de búsqueda de RF-76."""
        raise NotImplementedError
