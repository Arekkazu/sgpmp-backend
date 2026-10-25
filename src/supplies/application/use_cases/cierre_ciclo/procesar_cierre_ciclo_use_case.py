# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-38→RF-74/76/77/78/79: cierre de ciclo  |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Efectos en M05 del cierre del ciclo productivo (RF-38 en M02).

Corre dentro de la transacción del cierre (no hace ``commit``), así el cierre y
sus efectos se confirman o se revierten juntos:

1. RF-76 (dependencia RF-38): no se cierra un activo con tratamientos de retiro
   vigente → 409.
2. RF-74 (dependencia RF-38): CA final del ciclo completo (POR_CICLO hasta la
   fecha de cierre), mientras el activo sigue ACTIVO y la fase abierta.
3. RF-78 Fase 9 / RF-79 Fase 2: consolidación de la inversión y envío a M06.
4. RF-77 (dependencia RF-38): reporte final de gastos del ciclo como documento
   histórico (asíncrono si el ciclo pasa de 12 meses).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.shared.errors import ConflictError
from src.shared.fechas import hoy_usuario
from src.supplies.application.use_cases.eficiencia.calcular_ica_use_case import CalcularICAUseCase
from src.supplies.application.use_cases.provision_nic41.consolidar_ciclo_use_case import ConsolidarCicloUseCase
from src.supplies.application.use_cases.reporte_gastos.generar_reporte_gastos_use_case import (
    GenerarReporteGastosUseCase,
)
from src.supplies.domain.entities.provision_nic41 import ProvisionNic41
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto
from src.supplies.domain.entities.trabajo_reporte_gasto import TrabajoReporteGasto
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.medicamento_repository import MedicamentoRepository
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion, TipoCalculo
from src.supplies.domain.value_objects.reporte_gasto_enums import GranularidadDesglose

_DIAS_REPORTE_SINCRONO = 366


class ProcesarCierreCicloSuministrosUseCase:
    def __init__(
        self,
        activo_port: ActivoConsultaPort,
        medicamento_repo: MedicamentoRepository,
        calcular_ica: CalcularICAUseCase,
        consolidar: ConsolidarCicloUseCase,
        generar_reporte: GenerarReporteGastosUseCase,
    ) -> None:
        self.activo_port = activo_port
        self.medicamento_repo = medicamento_repo
        self.calcular_ica = calcular_ica
        self.consolidar = consolidar
        self.generar_reporte = generar_reporte
        self._provision: Optional[ProvisionNic41] = None

    def antes_de_cerrar(self, id_activo: int, id_usuario: int, fecha_cierre: date) -> None:
        vigente = self.medicamento_repo.max_fecha_fin_retiro_vigente(id_activo)
        if vigente is not None and vigente >= hoy_usuario():
            raise ConflictError(
                code="TRATAMIENTO_ACTIVO",
                message=(
                    f"El activo biológico {id_activo} tiene tratamientos con período de retiro vigente hasta "
                    f"{vigente.isoformat()}. No es posible cerrar el ciclo productivo mientras el activo esté "
                    "EN_TRATAMIENTO (RF-76)."
                ),
            )
        activo = self.activo_port.obtener(id_activo)
        if activo is not None and activo.esta_activo:
            self.calcular_ica.calcular_sin_commit(
                id_activo_biologico=id_activo,
                periodo=PeriodoEvaluacion.POR_CICLO,
                tipo_calculo=TipoCalculo.MANUAL,
                id_usuario=id_usuario,
                fecha_corte=fecha_cierre,
            )

    def despues_de_cerrar(self, id_activo: int, id_gestion_fases: int, id_usuario: int, fecha_cierre: date) -> None:
        self._provision = self.consolidar.consolidar_sin_commit(id_gestion_fases, id_usuario, exigir_registros=False)

        activo = self.activo_port.obtener(id_activo)
        if activo is None or activo.fecha_inicio_ciclo is None or activo.fecha_inicio_ciclo > fecha_cierre:
            return
        filtros = FiltrosReporteGasto(
            fecha_inicio=activo.fecha_inicio_ciclo,
            fecha_fin=fecha_cierre,
            tipo_periodo=GranularidadDesglose.CICLO_COMPLETO.value,
            id_activo_biologico=id_activo,
        )
        if filtros.dias > _DIAS_REPORTE_SINCRONO:
            self.generar_reporte.trabajo_repo.encolar(
                TrabajoReporteGasto(parametros=filtros.a_dict(), id_usuario_solicitante=id_usuario)
            )
            return
        self.generar_reporte.reporte_repo.guardar(self.generar_reporte.construir(filtros, id_usuario, activo))

    def despues_del_commit(self) -> None:
        self.consolidar.avisar_si_incompleto(self._provision)
