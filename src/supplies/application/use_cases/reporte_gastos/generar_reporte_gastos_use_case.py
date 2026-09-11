"""Caso de uso: generar el reporte de gastos acumulados (RF-77).

Decide síncrono vs. asíncrono según el rango solicitado (Restricción 8/12-14
de RF-77) y orquesta la recolección de líneas de gasto (período actual +
período anterior equivalente para la tendencia) delegando el cálculo puro en
:class:`CalculadoraReporteGasto`. ``commit()``/``rollback()`` viven aquí.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Union

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError, NotFoundError, TooManyRequestsError, ValidationError
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto, ReporteGasto
from src.supplies.domain.entities.trabajo_reporte_gasto import TrabajoReporteGasto
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.configuracion_batch_reporte_gasto_repository import (
    ConfiguracionBatchReporteGastoRepository,
)
from src.supplies.domain.repositories.detalle_gasto_read_port import DetalleGastoReadPort
from src.supplies.domain.repositories.reporte_gasto_repository import ReporteGastoRepository
from src.supplies.domain.repositories.trabajo_reporte_gasto_repository import TrabajoReporteGastoRepository
from src.supplies.domain.services.calculadora_reporte_gasto import CalculadoraReporteGasto

_DIAS_UMBRAL_ASYNC_INDIVIDUAL = 366  # > 12 meses (Restricción 8/13 RF-77)
_DIAS_UMBRAL_ASYNC_AGREGADO = 183  # > 6 meses para consultas agregadas (Restricción 13)
_CERO = Decimal("0")


class GenerarReporteGastosUseCase:
    def __init__(
        self,
        db: Session,
        detalle_port: DetalleGastoReadPort,
        activo_port: ActivoConsultaPort,
        reporte_repo: ReporteGastoRepository,
        trabajo_repo: TrabajoReporteGastoRepository,
        config_repo: ConfiguracionBatchReporteGastoRepository,
        calculadora: Optional[CalculadoraReporteGasto] = None,
    ) -> None:
        self.db = db
        self.detalle_port = detalle_port
        self.activo_port = activo_port
        self.reporte_repo = reporte_repo
        self.trabajo_repo = trabajo_repo
        self.config_repo = config_repo
        self.calculadora = calculadora or CalculadoraReporteGasto()

    def execute(
        self, filtros: FiltrosReporteGasto, id_usuario: int
    ) -> Union[ReporteGasto, TrabajoReporteGasto]:
        activo = self._validar(filtros)

        if self._requiere_async(filtros):
            return self._encolar(filtros, id_usuario)
        return self._generar_sincrono(filtros, id_usuario, activo)

    def generar_forzado(self, filtros: FiltrosReporteGasto, id_usuario: int) -> ReporteGasto:
        """Genera el reporte sin evaluar el umbral síncrono/asíncrono.

        Usado por el worker del motor async (``ProcesarColaReportesGastosUseCase``),
        que ya sabe que este trabajo requiere ese procesamiento porque fue
        encolado por ``execute()`` precisamente por superar el umbral.
        """
        activo = self._validar(filtros)
        return self._generar_sincrono(filtros, id_usuario, activo)

    # ── Validaciones (E2, E3, E7, E9) ────────────────────────────────────────
    def _validar(self, filtros: FiltrosReporteGasto):
        hoy = datetime.now(timezone.utc).date()
        if filtros.fecha_inicio > filtros.fecha_fin:
            raise ValidationError(
                code="RANGO_FECHAS_INVALIDO",
                message=(
                    f"El rango de fechas es inválido. La fecha de inicio ({filtros.fecha_inicio}) "
                    f"no puede ser posterior a la fecha de fin ({filtros.fecha_fin})."
                ),
                field="fecha_inicio_reporte",
            )
        if filtros.fecha_fin > hoy:
            raise ValidationError(
                code="FECHA_FIN_FUTURA",
                message="fecha_fin_reporte no puede ser posterior a la fecha actual.",
                field="fecha_fin_reporte",
            )

        if filtros.id_activo_biologico is None:
            if filtros.id_infraestructura is None and filtros.id_especie is None:
                raise ValidationError(
                    code="REPORTE_SIN_ALCANCE",
                    message=(
                        "Las consultas agregadas requieren id_infraestructura o id_especie, "
                        "o especificar activo_biologico_id para un reporte individual."
                    ),
                    field="activo_biologico_id",
                )
            return None

        activo = self.activo_port.obtener(filtros.id_activo_biologico)
        if activo is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico {filtros.id_activo_biologico} no existe.",
                field="activo_biologico_id",
            )
        if activo.fecha_inicio_ciclo is None:
            raise BusinessRuleError(
                code="ACTIVO_SIN_CICLO",
                message=(
                    f"El activo {filtros.id_activo_biologico} no tiene un ciclo productivo registrado. "
                    "No es posible generar el reporte de gastos sin una referencia temporal del ciclo."
                ),
                field="activo_biologico_id",
            )
        if filtros.fecha_inicio < activo.fecha_inicio_ciclo:
            raise ValidationError(
                code="FECHA_INICIO_ANTERIOR_CICLO",
                message=(
                    f"La fecha de inicio del reporte ({filtros.fecha_inicio}) es anterior a la fecha de "
                    f"inicio del ciclo productivo del activo ({activo.fecha_inicio_ciclo})."
                ),
                field="fecha_inicio_reporte",
            )
        return activo

    def _requiere_async(self, filtros: FiltrosReporteGasto) -> bool:
        umbral = _DIAS_UMBRAL_ASYNC_AGREGADO if filtros.es_agregado else _DIAS_UMBRAL_ASYNC_INDIVIDUAL
        return filtros.dias > umbral

    # ── Camino asíncrono ──────────────────────────────────────────────────────
    def _encolar(self, filtros: FiltrosReporteGasto, id_usuario: int) -> TrabajoReporteGasto:
        config = self.config_repo.obtener()
        if self.trabajo_repo.contar_activos() >= config.limite_concurrencia:
            raise TooManyRequestsError(
                code="LIMITE_CONCURRENCIA_EXCEDIDO",
                message=(
                    "El sistema ha alcanzado el límite de reportes en generación simultánea. "
                    "Por favor, intente nuevamente en unos minutos."
                ),
            )
        trabajo = TrabajoReporteGasto(
            parametros=self._filtros_a_dict(filtros),
            id_usuario_solicitante=id_usuario,
        )
        try:
            trabajo = self.trabajo_repo.encolar(trabajo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return trabajo

    @staticmethod
    def _filtros_a_dict(filtros: FiltrosReporteGasto) -> dict:
        return {
            "fecha_inicio": filtros.fecha_inicio.isoformat(),
            "fecha_fin": filtros.fecha_fin.isoformat(),
            "tipo_periodo": filtros.tipo_periodo,
            "id_activo_biologico": filtros.id_activo_biologico,
            "id_infraestructura": filtros.id_infraestructura,
            "id_especie": filtros.id_especie,
            "categorias_incluidas": filtros.categorias_incluidas,
        }

    # ── Camino síncrono ───────────────────────────────────────────────────────
    def _generar_sincrono(self, filtros: FiltrosReporteGasto, id_usuario: int, activo) -> ReporteGasto:
        lineas = self.detalle_port.consultar(
            fecha_inicio=filtros.fecha_inicio,
            fecha_fin=filtros.fecha_fin,
            id_activo_biologico=filtros.id_activo_biologico,
            id_infraestructura=filtros.id_infraestructura,
            id_especie=filtros.id_especie,
            categorias=filtros.categorias_incluidas,
        )

        gasto_anterior, recortado, fecha_recorte = self._periodo_anterior(filtros, activo)

        resultado_calc = self.calculadora.calcular(
            lineas=lineas,
            tipo_periodo=filtros.tipo_periodo,
            gasto_periodo_anterior=gasto_anterior,
            periodo_anterior_recortado=recortado,
            fecha_inicio_ciclo_recorte=fecha_recorte,
        )

        gasto_promedio_individuo = None
        causa_no_calculable_promedio = None
        if activo is not None and activo.es_poblacional:
            if not activo.cantidad_actual:
                causa_no_calculable_promedio = (
                    "La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."
                )
            else:
                gasto_promedio_individuo = resultado_calc.gasto_total_acumulado / activo.cantidad_actual

        reporte = ReporteGasto(
            fecha_inicio=filtros.fecha_inicio,
            fecha_fin=filtros.fecha_fin,
            tipo_periodo=filtros.tipo_periodo,
            gasto_total_acumulado=resultado_calc.gasto_total_acumulado,
            desglose_categorias=resultado_calc.desglose_categorias,
            desglose_temporal=resultado_calc.desglose_temporal,
            registros_sin_costo=resultado_calc.registros_sin_costo,
            tendencia=resultado_calc.tendencia,
            id_activo_biologico=filtros.id_activo_biologico,
            id_infraestructura=filtros.id_infraestructura,
            id_especie=filtros.id_especie,
            gasto_promedio_individuo=gasto_promedio_individuo,
            causa_no_calculable_promedio=causa_no_calculable_promedio,
            sin_datos=resultado_calc.sin_datos,
            id_usuario=id_usuario,
        )

        try:
            reporte = self.reporte_repo.guardar(reporte)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return reporte

    def _periodo_anterior(self, filtros: FiltrosReporteGasto, activo) -> tuple[Decimal, bool, Optional[date]]:
        """Calcula el gasto del período anterior equivalente (Proceso paso 6 de RF-77)."""
        dias = filtros.dias
        fecha_fin_anterior = filtros.fecha_inicio - timedelta(days=1)
        fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=dias - 1)

        recortado = False
        fecha_recorte: Optional[date] = None
        if (
            activo is not None
            and activo.fecha_inicio_ciclo is not None
            and fecha_inicio_anterior < activo.fecha_inicio_ciclo
        ):
            fecha_inicio_anterior = activo.fecha_inicio_ciclo
            fecha_recorte = activo.fecha_inicio_ciclo
            recortado = fecha_inicio_anterior <= fecha_fin_anterior

        if fecha_inicio_anterior > fecha_fin_anterior:
            return _CERO, False, None

        lineas_anteriores = self.detalle_port.consultar(
            fecha_inicio=fecha_inicio_anterior,
            fecha_fin=fecha_fin_anterior,
            id_activo_biologico=filtros.id_activo_biologico,
            id_infraestructura=filtros.id_infraestructura,
            id_especie=filtros.id_especie,
            categorias=filtros.categorias_incluidas,
        )
        gasto_anterior = sum((l.monto for l in lineas_anteriores if l.monto is not None), _CERO)
        return gasto_anterior, recortado, fecha_recorte
