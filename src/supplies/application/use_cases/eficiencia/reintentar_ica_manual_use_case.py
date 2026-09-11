"""Caso de uso: reintento manual del cálculo ICA de un activo (RF-74, panel admin, <<extend>>).

Fuerza el recálculo de los tres períodos de un activo que quedó en
``CA_FALLO_PERSISTENTE`` (``tipo_calculo=REINTENTO_MANUAL``). Si el recálculo tiene
éxito, marca el fallo abierto como resuelto (``MANUAL``).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError, FlowError
from src.supplies.application.use_cases.eficiencia.calcular_ica_use_case import CalcularICAUseCase
from src.supplies.domain.entities.resultado_ica import ResultadoICA
from src.supplies.domain.repositories.fallo_calculo_ica_repository import FalloCalculoICARepository
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion, TipoCalculo

_PERIODOS = (PeriodoEvaluacion.SEMANAL, PeriodoEvaluacion.MENSUAL, PeriodoEvaluacion.POR_CICLO)


class ReintentarICAManualUseCase:
    def __init__(
        self,
        db: Session,
        calcular_uc: CalcularICAUseCase,
        fallo_repo: FalloCalculoICARepository,
    ) -> None:
        self.db = db
        self.calcular_uc = calcular_uc
        self.fallo_repo = fallo_repo

    def execute(self, id_activo_biologico: int, id_usuario: int) -> list[ResultadoICA]:
        fallo = self.fallo_repo.obtener_abierto(id_activo_biologico, None)
        intento = (fallo.intentos + 1) if fallo else 1

        resultados: list[ResultadoICA] = []
        for periodo in _PERIODOS:
            # CalcularICAUseCase hace su propio commit por período; un fallo técnico
            # re-lanza (deja el fallo abierto). Un período no computable por regla de
            # negocio (p.ej. POR_CICLO sin ciclo abierto) se omite sin abortar el resto;
            # un NotFoundError del activo sí se propaga.
            try:
                resultados.append(
                    self.calcular_uc.execute(
                        id_activo_biologico=id_activo_biologico,
                        periodo=periodo,
                        tipo_calculo=TipoCalculo.REINTENTO_MANUAL,
                        id_usuario=id_usuario,
                        intento=intento,
                    )
                )
            except (BusinessRuleError, FlowError):
                continue

        if fallo is not None and fallo.id_fallo is not None:
            try:
                self.fallo_repo.marcar_resuelto(
                    fallo.id_fallo,
                    tipo_resolucion="MANUAL",
                    cuando=datetime.now(timezone.utc),
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

        return resultados
