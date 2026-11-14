# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-38→RF-74/76/77/78/79: cierre de ciclo  |
"""Adaptador de :class:`CierreCicloSuministrosPort` hacia M05 (``src/supplies``).

Usa la misma sesión del cierre: los efectos de M05 participan en la transacción
de RF-38 (``flush`` sin ``commit``), igual que M05 invoca RF-44 con
``EstadoActivoM02Adapter``.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.cierre_ciclo_suministros_port import CierreCicloSuministrosPort
from src.supplies.application.use_cases.cierre_ciclo.procesar_cierre_ciclo_use_case import (
    ProcesarCierreCicloSuministrosUseCase,
)
from src.supplies.infrastructure.adapters.activo_m02_adapter import ActivoM02Adapter
from src.supplies.infrastructure.factories.eficiencia_factory import build_calcular_ica_use_case
from src.supplies.infrastructure.factories.provision_nic41_factory import build_consolidar_ciclo_use_case
from src.supplies.infrastructure.factories.reporte_gastos_factory import build_generar_reporte_gastos_use_case
from src.supplies.infrastructure.repositories.medicamento_repository import SqlAlchemyMedicamentoRepository


class CierreCicloSuministrosM05Adapter(CierreCicloSuministrosPort):
    def __init__(self, db: Session) -> None:
        self._servicio = ProcesarCierreCicloSuministrosUseCase(
            activo_port=ActivoM02Adapter(db),
            medicamento_repo=SqlAlchemyMedicamentoRepository(db),
            calcular_ica=build_calcular_ica_use_case(db),
            consolidar=build_consolidar_ciclo_use_case(db),
            generar_reporte=build_generar_reporte_gastos_use_case(db),
        )

    def antes_de_cerrar(self, id_activo: int, id_usuario: int, fecha_cierre: date) -> None:
        self._servicio.antes_de_cerrar(id_activo, id_usuario, fecha_cierre)

    def despues_de_cerrar(self, id_activo: int, id_gestion_fases: int, id_usuario: int, fecha_cierre: date) -> None:
        self._servicio.despues_de_cerrar(id_activo, id_gestion_fases, id_usuario, fecha_cierre)

    def despues_del_commit(self) -> None:
        self._servicio.despues_del_commit()
