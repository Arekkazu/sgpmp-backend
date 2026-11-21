# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: editar regla de alerta con concurrencia optimista (412) |
"""Editar una regla de alerta (RF-55/RF-57, BE-0).

Concurrencia optimista con ``fecha_actualizacion`` (412), que el trigger
``trg_aux_02_version_regla_alerta`` renueva en cada UPDATE. El mismo trigger sube
``version_regla`` si cambió algo de lo que recibe el Edge, y con esa versión
el Gateway descarta la anterior. Después del commit se repropaga.
"""
from __future__ import annotations

from datetime import timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import PreconditionFailedError
from src.telemetry.application.use_cases.reglas.consultar_reglas_alertas_use_case import obtener_regla_o_404
from src.telemetry.application.use_cases.reglas.sincronizar_regla_edge_use_case import SincronizarReglaEdgeUseCase
from src.telemetry.domain.entities.alerta import ReglaAlerta
from src.telemetry.domain.entities.sincronizacion_regla_edge import ResultadoSincronizacionRegla
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository
from src.telemetry.infrastructure.dto.regla_alerta_dto import EditarReglaAlertaDTO



def _conflicto() -> PreconditionFailedError:
    return PreconditionFailedError(
        code="CONFLICTO_CONCURRENCIA",
        message="La regla fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
    )


class EditarReglaAlertaUseCase:

    def __init__(
        self,
        db: Session,
        regla_repo: ReglaAlertaRepository,
        sincronizar: SincronizarReglaEdgeUseCase,
    ) -> None:
        self.db = db
        self.regla_repo = regla_repo
        self.sincronizar = sincronizar

    def execute(
        self, id_regla_alertas: int, dto: EditarReglaAlertaDTO, id_usuario: int,
    ) -> tuple[ReglaAlerta, Optional[ResultadoSincronizacionRegla]]:
        try:
            regla = obtener_regla_o_404(self.regla_repo, id_regla_alertas, bloquear=True)
            ts_actual = regla.fecha_actualizacion
            ts_dto = dto.fecha_actualizacion
            if ts_actual is not None and ts_dto is not None:
                if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                    raise _conflicto()
            elif ts_actual != ts_dto:
                raise _conflicto()

            regla.actualizar(id_usuario=id_usuario, **dto.campos())
            regla = self.regla_repo.actualizar(regla)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        sincronizacion = (
            self.sincronizar.execute(regla.id_regla_alertas, id_usuario) if regla.se_propaga_al_edge else None
        )
        return regla, sincronizacion
