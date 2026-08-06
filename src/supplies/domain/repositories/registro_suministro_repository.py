"""Puerto del repositorio de registros directos de suministro (RF-78, CU-05).

Expresado en términos de dominio: recibe y devuelve
``RegistroSuministroDirecto``. Cubre el camino de escritura app-owned
(SERVICIO_VETERINARIO/INSEMINACION y correcciones de cualquier tipo) — el
camino ALIMENTO/MEDICAMENTO sigue poblado por los triggers de CU-04 y no pasa
por este puerto. La implementación SQLAlchemy hace ``flush`` interno; el
``commit`` lo emite el caso de uso.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto


class RegistroSuministroRepository(ABC):
    """Contrato de persistencia de registros directos de suministro."""

    @abstractmethod
    def existe_idempotente(self, id_idempotencia: UUID) -> Optional[RegistroSuministroDirecto]:
        """Devuelve el registro ya procesado con ese ``id_idempotencia``, o ``None``."""
        raise NotImplementedError

    @abstractmethod
    def existe_duplicado_contenido(
        self,
        *,
        id_activo_biologico: int,
        id_ciclo_productivo: int,
        tipo_suministro: str,
        fecha_aplicacion: date,
        cantidad: Decimal,
        precio_unitario_resuelto: Decimal,
    ) -> bool:
        """Indica si ya existe un ``REGISTRO`` con la misma combinación de contenido (RF-78 R.8)."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, registro: RegistroSuministroDirecto) -> RegistroSuministroDirecto:
        """Persiste un registro nuevo (REGISTRO o CORRECCION) y devuelve la entidad completa."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_id(self, id_registro_suministro: UUID) -> Optional[RegistroSuministroDirecto]:
        """Devuelve un registro por id, o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def listar_por_gestion_fase(self, id_gestion_fases: int) -> list[RegistroSuministroDirecto]:
        """Lista todos los registros (REGISTRO y CORRECCION) de una instancia de ciclo."""
        raise NotImplementedError
