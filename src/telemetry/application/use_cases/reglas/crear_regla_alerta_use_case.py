# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: crear regla de alerta sin SQL manual |
"""Crear una regla de alerta (RF-55/RF-57, BE-0).

Una compuesta marcada para el Edge se propaga a sus Gateway después del commit,
como pide DEV-08; si el broker no confirma, la regla queda creada y el resultado
por nodo dice qué reintentar (``POST /iot/reglas-alertas/{id}/sincronizar-edge``).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.telemetry.application.use_cases.reglas.sincronizar_regla_edge_use_case import SincronizarReglaEdgeUseCase
from src.telemetry.domain.entities.alerta import ReglaAlerta
from src.telemetry.domain.entities.sincronizacion_regla_edge import ResultadoSincronizacionRegla
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository
from src.telemetry.infrastructure.dto.regla_alerta_dto import CrearReglaAlertaDTO


class CrearReglaAlertaUseCase:

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
        self, dto: CrearReglaAlertaDTO, id_usuario: int,
    ) -> tuple[ReglaAlerta, Optional[ResultadoSincronizacionRegla]]:
        regla = ReglaAlerta(**dto.model_dump(), es_activa=True, id_usuario=id_usuario)
        regla.validar()
        try:
            regla = self.regla_repo.crear(regla)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        sincronizacion = (
            self.sincronizar.execute(regla.id_regla_alertas, id_usuario) if regla.se_propaga_al_edge else None
        )
        return regla, sincronizacion
