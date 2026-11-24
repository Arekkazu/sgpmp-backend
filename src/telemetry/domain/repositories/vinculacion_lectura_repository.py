# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: lectura vigente y configuracion temporal |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y métodos |
"""Puerto de dominio de las vinculaciones lectura-activo (RF-61).

Resuelve la vinculación vigente de una lectura, conserva su contexto histórico
y expone el CRUD y el listado paginado que consume la aplicación. Los métodos
con ``NotImplementedError`` son ganchos que cada implementación concreta
resuelve.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura


class VinculacionLecturaRepository(ABC):
    """Contrato de persistencia y consulta de vinculaciones de lectura."""

    def bloquear_lectura(self, identificador):
        """Bloquea la lectura para resolver su vinculación de forma exclusiva."""
        raise NotImplementedError

    def vigente(self, identificador):
        """Devuelve la vinculación vigente de la lectura indicada."""
        raise NotImplementedError

    def ultima(self, identificador):
        """Devuelve la última vinculación registrada para la lectura."""
        raise NotImplementedError

    def contexto_lectura(self, identificador, captura):
        """Devuelve el contexto (activo, área, variable) de una captura."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, vinculacion: VinculacionLectura) -> VinculacionLectura:
        """Persiste una vinculación nueva y devuelve la entidad resultante."""
        ...

    @abstractmethod
    def obtener_por_id(
        self,
        id_vinculacion_lectura: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[VinculacionLectura]:
        """Busca una vinculación por id, opcionalmente acotada a fincas permitidas."""
        ...

    @abstractmethod
    def actualizar(self, vinculacion: VinculacionLectura) -> VinculacionLectura:
        """Actualiza una vinculación existente y devuelve la entidad resultante."""
        ...

    @abstractmethod
    def listar(
        self,
        id_telemetria: Optional[int] = None,
        estado_vinculacion: Optional[str] = None,
        mecanismo_vinculacion: Optional[str] = None,
        id_infraestructura: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
        modelo_manejo: Optional[str] = None,
    ) -> tuple[List[VinculacionLectura], int]:
        """Lista vinculaciones con filtros y paginación.

        Returns:
            Tupla con la página de vinculaciones y el total de coincidencias.
        """
        ...
