# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: desactivar regla de alerta y retirarla del Edge |
"""Desactivar una regla de alerta (RF-55/RF-57, BE-0).

Baja lógica (``es_activa = false``): la regla sigue referenciada por alertas y
eventos Edge. Si estaba en el Edge, se le envía con ``es_activa = false`` para que
el Gateway la retire (DEV-08).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.telemetry.application.use_cases.reglas.consultar_reglas_alertas_use_case import obtener_regla_o_404
from src.telemetry.application.use_cases.reglas.sincronizar_regla_edge_use_case import SincronizarReglaEdgeUseCase
from src.telemetry.domain.entities.alerta import ReglaAlerta
from src.telemetry.domain.entities.sincronizacion_regla_edge import ResultadoSincronizacionRegla
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository


class DesactivarReglaAlertaUseCase:

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
        self, id_regla_alertas: int, id_usuario: int,
    ) -> tuple[ReglaAlerta, Optional[ResultadoSincronizacionRegla]]:
        try:
            regla = obtener_regla_o_404(self.regla_repo, id_regla_alertas, bloquear=True)
            regla.desactivar(id_usuario)
            regla = self.regla_repo.actualizar(regla)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        sincronizacion = (
            self.sincronizar.execute(regla.id_regla_alertas, id_usuario) if regla.se_propaga_al_edge else None
        )
        return regla, sincronizacion
