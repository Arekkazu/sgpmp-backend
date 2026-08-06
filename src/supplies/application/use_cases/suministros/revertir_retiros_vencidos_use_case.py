"""Caso de uso: revertir a ACTIVO los activos cuyo período de retiro venció (RF-76 pasos 11-13).

Corre como tarea programada diaria (ver ``main.py``), sin usuario interactivo.
Por cada activo EN_TRATAMIENTO abre su propia sesión/transacción — igual que
``EjecutarBatchICAUseCase._procesar_activo`` — de modo que el fallo de uno no
afecte a los demás. El actor de auditoría del cambio de estado es el
``id_usuario`` que registró el tratamiento con el retiro vigente: el proyecto
no tiene una convención de "usuario del sistema", y ese usuario es quien
generó la obligación de retiro que ahora se levanta.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_MOTIVO_REVERSION = "Vencimiento de período de retiro (RF-76)."


class RevertirRetirosVencidosUseCase:
    """Revierte a ACTIVO los activos EN_TRATAMIENTO cuyo retiro vigente ya venció."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def ejecutar(self) -> int:
        """Procesa todos los activos EN_TRATAMIENTO. Devuelve cuántos se revirtieron."""
        from src.supplies.infrastructure.adapters.activo_m02_adapter import ActivoM02Adapter

        db = self.session_factory()
        try:
            activos = ActivoM02Adapter(db).listar_en_tratamiento()
        finally:
            db.close()

        hoy = datetime.now(timezone.utc).date()
        revertidos = 0
        for id_activo in activos:
            if self._revertir_si_vencido(id_activo, hoy):
                revertidos += 1
        return revertidos

    def _revertir_si_vencido(self, id_activo: int, hoy: date) -> bool:
        from src.supplies.infrastructure.adapters.estado_activo_m02_adapter import EstadoActivoM02Adapter
        from src.supplies.infrastructure.repositories.medicamento_repository import (
            SqlAlchemyMedicamentoRepository,
        )

        db = self.session_factory()
        fecha_fin_retiro = None
        try:
            medicamento_repo = SqlAlchemyMedicamentoRepository(db)
            vigente = medicamento_repo.obtener_tratamiento_vigente(id_activo)

            if vigente is not None and vigente.fecha_fin_retiro is not None and vigente.fecha_fin_retiro > hoy:
                return False  # aún hay retiro activo

            if vigente is None or vigente.id_usuario is None:
                logger.warning(
                    "Activo %s EN_TRATAMIENTO sin tratamiento con retiro referenciable; "
                    "se omite la reversión automática.",
                    id_activo,
                )
                return False

            fecha_fin_retiro = vigente.fecha_fin_retiro
            EstadoActivoM02Adapter(db).revertir_a_activo(
                id_activo=id_activo,
                id_usuario=vigente.id_usuario,
                motivo=_MOTIVO_REVERSION,
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Error revirtiendo el retiro vencido del activo %s.", id_activo)
            return False
        finally:
            db.close()

        if fecha_fin_retiro is not None:
            self._notificar_fin_retiro(id_activo, fecha_fin_retiro)
        return True

    def _notificar_fin_retiro(self, id_activo: int, fecha_fin_retiro: date) -> None:
        from src.supplies.infrastructure.adapters.notificacion_medicamento_email_adapter import (
            NotificacionMedicamentoEmailAdapter,
        )

        db = self.session_factory()
        try:
            NotificacionMedicamentoEmailAdapter(db).notificar_fin_retiro(id_activo, fecha_fin_retiro)
        except Exception:
            logger.warning("No se pudo notificar el fin de retiro del activo %s.", id_activo)
        finally:
            db.close()
