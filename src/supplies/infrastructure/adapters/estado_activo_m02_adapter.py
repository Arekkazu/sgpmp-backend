"""Adaptador de cambio de estado del activo (RF-44) contra ``modulo2``.

Implementa el ``EstadoActivoPort`` reutilizando el flujo real de RF-44 de
biological_assets: lee el activo, valida la transición con la entidad de dominio
(``cambiar_estado``) e inserta el histórico de estado. El ``SqlAlchemyHistoricoEstadoRepository``
ejecuta ``SET LOCAL app.usuario_id`` y dispara el trigger de sincronización que
actualiza ``activos_biologicos.id_estado``. Todo ocurre con ``flush`` (sin
``commit``): participa en la MISMA transacción del caso de uso de suministros,
garantizando bajo acoplamiento y consistencia.

Es idempotente: si el activo ya está EN_TRATAMIENTO no realiza cambios (RF-76
E11 — múltiples tratamientos concurrentes mantienen el estado).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.biological_assets.infrastructure.repositories.historico_estado_repository import (
    SqlAlchemyHistoricoEstadoRepository,
)
from src.supplies.domain.repositories.estado_activo_port import EstadoActivoPort


class EstadoActivoM02Adapter(EstadoActivoPort):
    """Transiciona el activo a EN_TRATAMIENTO vía el flujo de RF-44 (módulo 2)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._activo_repo = SqlAlchemyActivoBiologicoRepository(db)
        self._historico_repo = SqlAlchemyHistoricoEstadoRepository(db)

    def marcar_en_tratamiento(self, id_activo: int, id_usuario: int, motivo: str) -> None:
        activo = self._activo_repo.obtener_por_id(id_activo)
        if activo is None:
            return

        objetivo = int(EstadoActivo.EN_TRATAMIENTO)
        if activo.id_estado == objetivo:
            return  # idempotente: ya está en tratamiento

        id_estado_anterior = activo.id_estado
        # La entidad valida la matriz de transición (RF-44).
        activo.cambiar_estado(objetivo)
        # flush interno + SET LOCAL app.usuario_id (dispara sincronización del estado).
        self._historico_repo.registrar(
            id_activo=id_activo,
            id_estado_anterior=id_estado_anterior,
            id_estado_nuevo=objetivo,
            fecha=datetime.now(timezone.utc),
            motivo=motivo,
            usuario_id=id_usuario,
            modulo_origen="modulo5",
        )

    def revertir_a_activo(self, id_activo: int, id_usuario: int, motivo: str) -> None:
        """Revierte el activo a ACTIVO (RF-76 pasos 11-13), espejo de ``marcar_en_tratamiento``."""
        activo = self._activo_repo.obtener_por_id(id_activo)
        if activo is None:
            return

        objetivo = int(EstadoActivo.ACTIVO)
        if activo.id_estado == objetivo:
            return  # idempotente: ya está activo

        id_estado_anterior = activo.id_estado
        activo.cambiar_estado(objetivo)
        self._historico_repo.registrar(
            id_activo=id_activo,
            id_estado_anterior=id_estado_anterior,
            id_estado_nuevo=objetivo,
            fecha=datetime.now(timezone.utc),
            motivo=motivo,
            usuario_id=id_usuario,
            modulo_origen="modulo5",
        )
