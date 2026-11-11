# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: baja del activo cosechado completamente |
"""Adaptador de :class:`BajaActivoPort` sobre el caso de uso de bajas de M02 (RF-45).

Usa el mismo caso de uso que el endpoint de M02, así la baja pasa por sus validaciones, su bitácora y sus
triggers. Corre en una sesión aparte como usuario de servicio, después del commit de M06, y nunca propaga
errores: si M02 rechaza la baja devuelve el mensaje para que M06 alerte al Contador."""
from __future__ import annotations

import logging
from datetime import date
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion.registrar_evento_baja_use_case import RegistrarEventoBajaUseCase
from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
from src.biological_assets.infrastructure.dto.registrar_evento_baja_dto import RegistrarEventoBajaDTO
from src.biological_assets.infrastructure.repositories.activo_biologico_repository import (
    SqlAlchemyActivoBiologicoRepository,
)
from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
    SqlAlchemyBitacoraAuditoriaRepository,
)
from src.biological_assets.infrastructure.repositories.evento_activo_repository import SqlAlchemyEventoActivoRepository
from src.biological_assets.infrastructure.repositories.historico_estado_repository import (
    SqlAlchemyHistoricoEstadoRepository,
)
from src.financial_valuation.domain.repositories.baja_activo_port import BajaActivoPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.database import id_usuario_servicio
from src.shared.errors import AppError

logger = logging.getLogger(__name__)

# La cosecha que consume el activo (peces, bovinos de engorde) es un sacrificio en el catálogo de RF-45.
TIPO_BAJA_COSECHA = "sacrificio"


class BajaActivoM02Adapter(BajaActivoPort):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def dar_de_baja_por_cosecha(self, id_activo_biologico: int, fecha: date, motivo: str) -> Optional[str]:
        db = self.session_factory()
        try:
            caso = RegistrarEventoBajaUseCase(
                db=db, activo_repo=SqlAlchemyActivoBiologicoRepository(db),
                evento_repo=SqlAlchemyEventoActivoRepository(db), infra_port=InfraestructuraM09Adapter(db),
                historico_repo=SqlAlchemyHistoricoEstadoRepository(db),
                bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
            )
            sistema = UsuarioActual(id_usuario=id_usuario_servicio(db), id_token=0, id_rol=0)
            caso.execute(id_activo_biologico, RegistrarEventoBajaDTO(
                tipo_baja=TIPO_BAJA_COSECHA, fecha_baja=fecha, motivo_baja=motivo), sistema)
            return None
        except AppError as exc:  # M02 la rechazó (ya en baja, fecha, etc.): el caso de uso ya hizo rollback
            return exc.message
        except Exception:
            db.rollback()
            logger.exception("M06: no se pudo registrar en M02 la baja del activo %s cosechado completamente.",
                             id_activo_biologico)
            return "No se pudo registrar la baja en Activos biológicos por un error técnico."
        finally:
            db.close()
