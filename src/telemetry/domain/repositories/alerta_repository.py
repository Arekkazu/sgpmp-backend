# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-31 RF-57: vencer alertas activas con SLA cumplido (E10) |
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: pendientes de notificar y conteos de tormenta (Fase 8, E8) |
# | 2026-10-21 | Leandro | DEV-41 RF-57: bloqueo por condicion operativa     |
# | 2026-10-21 | Leandro | DEV-43 RF-62: puerto de alerta tecnica idempotente |
# | 2026-10-22 | Leandro | DEV-42 RF-60: contrato de bateria unica y recuperacion |
# | 2026-10-24 | Arekkazu | USAB-M03 M3-06/M3-08 RF-57: ubicación con nombres y filtro por fecha de resolución |
# | 2026-10-25 | Arekkazu | USAB-M03 T-18 RF-57: filtro de alertas por área (id_infraestructura) |
# | 2026-10-28 | destroyerban | INC-M03-164-G71 RF-57 E14: buscar y consolidar la compuesta abierta del área |
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.alerta import Alerta


class AlertaRepository(ABC):
    def buscar_compuesta_activa(self, tipo_alerta: str, id_infraestructura: int, ventana_min: int):
        """E14: alerta compuesta abierta del mismo tipo en el área, bloqueada para consolidar."""
        raise NotImplementedError

    def consolidar_compuesta(self, id_alerta: int, ultima_ocurrencia, reglas_nuevas: list,
                             nueva_severidad, correlacion: dict) -> None:
        """E14: suma la ocurrencia y agrega las reglas simples nuevas a la alerta compuesta."""
        raise NotImplementedError

    def bloquear_condicion(self, id_sensor: int, tipo_variable: str) -> None:
        """Serializa creación/consolidación por sensor y variable entre canales."""
        raise NotImplementedError

    def bloquear_condicion_calidad(self, id_sensor: int, anomalia: str):
        raise NotImplementedError

    def buscar_tecnica_calidad(self, id_sensor: int, anomalia: str, id_telemetria: int):
        raise NotImplementedError

    def contexto_sensor_calidad(self, id_sensor: int) -> dict:
        raise NotImplementedError

    def escalar_calidad(self, id_alerta: int, severidad: str):
        raise NotImplementedError

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
        fecha_resolucion_desde: Optional[datetime] = None,
        id_infraestructura: Optional[int] = None,
    ) -> tuple[list[Alerta], int]: ...

    @abstractmethod
    def reclamar_pendientes_notificacion(self, ahora: datetime, ventana_min: int = 10, limite: int = 100) -> list[Alerta]:
        """RF-57 Fase 8: alertas operativas generadas en los últimos ``ventana_min`` minutos
        sin notificar; las marca con ``fecha_notificacion = ahora`` y las devuelve. Sin commit.
        Se saltan las filas bloqueadas (otra instancia del job)."""

    @abstractmethod
    def contar_generadas_desde(self, desde: datetime) -> tuple[int, dict[int, int]]:
        """RF-57 E8: alertas operativas generadas desde ``desde``: total y por área."""

    @abstractmethod
    def existe_tormenta_desde(self, desde: datetime) -> bool:
        """RF-57 E8: ya hay una alerta TORMENTA_DE_ALERTAS generada desde ``desde``."""

    @abstractmethod
    def vencer_activas_con_sla_cumplido(self, ahora: datetime, limite: int = 200) -> list[Alerta]:
        """RF-57 E10: pasa a VENCIDA las alertas operativas ACTIVA cuya ``fecha_vencimiento``
        ya pasó y las devuelve. Sin commit. Las filas bloqueadas por otra transacción
        (otra instancia del job o un usuario atendiéndola) se saltan."""
