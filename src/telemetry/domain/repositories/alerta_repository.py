# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: contrato de bateria unica y recuperacion |
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.alerta import Alerta


class AlertaRepository(ABC):

    def bloquear_dispositivo(self, id_dispositivo: int) -> None:
        """Serializa condiciones técnicas con el lock de DEV-05 hasta el commit."""
        raise NotImplementedError

    def escalar_bateria(self, id_alerta: int, causa: str, severidad: str, metadatos: dict) -> None:
        raise NotImplementedError

    def listar_conectividad_abierta(self, id_dispositivo: int) -> list[Alerta]:
        raise NotImplementedError

    def buscar_tecnica_activa_dispositivo(self, id_dispositivo: int, causa: str, *, sensores_fallidos: Optional[list[str]] = None):
        """Alerta vigente de la misma causa técnica, sin ventana temporal inventada."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, alerta: Alerta) -> Alerta: ...

    @abstractmethod
    def buscar_activa_duplicada(
        self,
        id_sensor: int,
        tipo_variable: str,
        ventana_min: int = 30,
    ) -> Optional[Alerta]: ...

    @abstractmethod
    def buscar_tecnica_abierta(self, id_dispositivo_ioit: int, tipo_variable: str) -> Optional[Alerta]:
        """Alerta TECNICA ACTIVA o EN_ATENCION del dispositivo con ese tipo, si hay."""

    @abstractmethod
    def actualizar_deduplicacion(
        self,
        id_alerta: int,
        ultima_ocurrencia: datetime,
        nueva_severidad: Optional[str] = None,
    ) -> None: ...

    @abstractmethod
    def actualizar_estado(
        self,
        id_alerta: int,
        nuevo_estado: str,
        id_usuario: Optional[int],
        motivo: Optional[str],
        fecha_atencion: Optional[datetime] = None,
        fecha_resolucion: Optional[datetime] = None,
    ) -> Alerta: ...

    @abstractmethod
    def obtener_por_id(
        self,
        id_alerta: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[Alerta]: ...

    @abstractmethod
    def listar(
        self,
        estado: Optional[str] = None,
        severidad: Optional[str] = None,
        tipo_alerta: Optional[str] = None,
        id_sensor: Optional[int] = None,
        id_activo_biologico: Optional[int] = None,
        origen_evento: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
        excluir_tipo_alerta: Optional[str] = None,
    ) -> tuple[list[Alerta], int]: ...
