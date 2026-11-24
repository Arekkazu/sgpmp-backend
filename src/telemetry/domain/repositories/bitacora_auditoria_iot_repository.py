# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: contrato de incidentes append-only |
# | 2026-10-25 | Arekkazu | INC-M03-135/136/137 RF-63: filtros id_usuario, rf_origen, registro_incompleto y verificación acotada |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-14 RF-63: bitácora limitada a las fincas del usuario salvo para el auditor |
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56 CA-8: filtro entidad_afectada_tipo y alcance por finca de PAQUETE_IA |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de la bitácora de auditoría IoT (RF-63)."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.telemetry.domain.entities.evento_auditoria_iot import EventoAuditoriaIot


class BitacoraAuditoriaIotRepository(ABC):
    """Puerto de registro y consulta de la bitácora de auditoría IoT."""

    @abstractmethod
    def registrar(self, evento: EventoAuditoriaIot) -> EventoAuditoriaIot:
        """Registra un evento de auditoría y lo devuelve persistido."""
        ...

    @abstractmethod
    def obtener(
        self, id_evento: UUID, *, ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[EventoAuditoriaIot]:
        """``ids_fincas_permitidas`` None = alcance global (auditor)."""

    @abstractmethod
    def listar(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        tipo_evento: Optional[str] = None,
        severidad_log: Optional[str] = None,
        clasificacion_registro: Optional[str] = None,
        entidad_afectada_id: Optional[str] = None,
        resultado: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        id_usuario: Optional[int] = None,
        rf_origen: Optional[str] = None,
        registro_incompleto: Optional[bool] = None,
        entidad_afectada_tipo: Optional[str] = None,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[EventoAuditoriaIot], int]:
        """``ids_fincas_permitidas`` None = alcance global (auditor)."""

    @abstractmethod
    def listar_todos_para_verificacion(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        limite: Optional[int] = None,
    ) -> list[EventoAuditoriaIot]:
        """Lista los eventos del rango para verificar su integridad."""
        ...

    def bloquear_integridad(self, id_evento: UUID) -> None:
        """Serializa la verificación de integridad de un evento."""
        raise NotImplementedError

    def buscar_incidente(self, clave: dict) -> Optional[EventoAuditoriaIot]:
        """Busca un incidente de integridad ya registrado con la clave dada."""
        raise NotImplementedError

    def aviso_confirmado(self, id_incidente: UUID) -> bool:
        """Indica si el aviso del incidente ya quedó confirmado."""
        raise NotImplementedError
