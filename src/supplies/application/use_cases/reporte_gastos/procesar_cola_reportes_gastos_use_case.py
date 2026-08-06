"""Worker del motor async de generación de reportes de gastos (RF-77).

Análogo a ``EjecutarBatchICAUseCase`` (RF-74): procesa hasta
``num_workers_max`` trabajos PENDIENTE en paralelo (``asyncio.Semaphore`` +
``to_thread``, sesión propia por trabajo vía ``session_factory``), con
reintentos y backoff configurables. Tras agotar los reintentos, el fallo
queda persistido en ``fallos_generacion_reportes_gastos``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from src.shared.errors import AppError
from src.supplies.application.use_cases.reporte_gastos.generar_reporte_gastos_use_case import (
    GenerarReporteGastosUseCase,
)
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto
from src.supplies.domain.entities.trabajo_reporte_gasto import EjecucionReporteGasto, FalloReporteGasto
from src.supplies.domain.repositories.configuracion_batch_reporte_gasto_repository import (
    ConfiguracionBatchReporteGastoRepository,
)
from src.supplies.domain.repositories.fallo_reporte_gasto_repository import FalloReporteGastoRepository
from src.supplies.domain.repositories.trabajo_reporte_gasto_repository import TrabajoReporteGastoRepository
from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync

logger = logging.getLogger(__name__)


def _filtros_desde_parametros(parametros: dict) -> FiltrosReporteGasto:
    return FiltrosReporteGasto(
        fecha_inicio=date.fromisoformat(parametros["fecha_inicio"]),
        fecha_fin=date.fromisoformat(parametros["fecha_fin"]),
        tipo_periodo=parametros.get("tipo_periodo") or "CICLO_COMPLETO",
        id_activo_biologico=parametros.get("id_activo_biologico"),
        id_infraestructura=parametros.get("id_infraestructura"),
        id_especie=parametros.get("id_especie"),
        categorias_incluidas=parametros.get("categorias_incluidas"),
    )


def _resultado_json(reporte) -> dict:
    return {
        "gasto_total_acumulado": str(reporte.gasto_total_acumulado),
        "gasto_promedio_individuo": (
            str(reporte.gasto_promedio_individuo) if reporte.gasto_promedio_individuo is not None else None
        ),
        "causa_no_calculable_promedio": reporte.causa_no_calculable_promedio,
        "registros_sin_costo": [
            {"categoria": s.categoria, "id_origen": s.id_origen, "fecha": s.fecha.isoformat(), "descripcion": s.descripcion}
            for s in reporte.registros_sin_costo
        ],
        "desglose_categorias": [
            {
                "categoria": d.categoria,
                "subtotal": str(d.subtotal),
                "num_registros": d.num_registros,
                "porcentaje": str(d.porcentaje),
            }
            for d in reporte.desglose_categorias
        ],
        "desglose_temporal": [
            {
                "etiqueta": p.etiqueta,
                "fecha_inicio": p.fecha_inicio.isoformat(),
                "fecha_fin": p.fecha_fin.isoformat(),
                "monto": str(p.monto),
            }
            for p in reporte.desglose_temporal
        ],
        "tendencia": {
            "gasto_periodo_actual": str(reporte.tendencia.gasto_periodo_actual),
            "gasto_periodo_anterior": str(reporte.tendencia.gasto_periodo_anterior),
            "variacion_porcentual": (
                str(reporte.tendencia.variacion_porcentual)
                if reporte.tendencia.variacion_porcentual is not None
                else None
            ),
            "estado": reporte.tendencia.estado,
            "nota": reporte.tendencia.nota,
        },
        "sin_datos": reporte.sin_datos,
    }


class ProcesarColaReportesGastosUseCase:
    def __init__(
        self,
        trabajo_repo: TrabajoReporteGastoRepository,
        config_repo: ConfiguracionBatchReporteGastoRepository,
        session_factory: Callable[[], Session],
        construir_trabajo_repo: Callable[[Session], TrabajoReporteGastoRepository],
        construir_fallo_repo: Callable[[Session], FalloReporteGastoRepository],
        construir_generador: Callable[[Session], GenerarReporteGastosUseCase],
    ) -> None:
        self.trabajo_repo = trabajo_repo
        self.config_repo = config_repo
        self.session_factory = session_factory
        self.construir_trabajo_repo = construir_trabajo_repo
        self.construir_fallo_repo = construir_fallo_repo
        self.construir_generador = construir_generador

    async def ejecutar(self) -> int:
        config = self.config_repo.obtener()
        if not config.es_activo:
            return 0
        pendientes = self.trabajo_repo.listar_pendientes(config.num_workers_max)
        if not pendientes:
            return 0

        sem = asyncio.Semaphore(config.num_workers_max)

        async def worker(id_cola: int) -> None:
            async with sem:
                await asyncio.to_thread(self._procesar, id_cola, config)

        await asyncio.gather(*(worker(t.id_cola) for t in pendientes))
        return len(pendientes)

    def _procesar(self, id_cola: int, config) -> None:
        db = self.session_factory()
        try:
            self.construir_trabajo_repo(db).marcar_estado(id_cola, EstadoTrabajoAsync.EN_PROCESO)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo marcar EN_PROCESO el trabajo de reporte %s", id_cola)
            return
        finally:
            db.close()

        for intento in range(1, config.max_reintentos + 1):
            db = self.session_factory()
            try:
                trabajo_repo = self.construir_trabajo_repo(db)
                trabajo = trabajo_repo.obtener(id_cola)
                if trabajo is None:
                    return
                ejecucion = trabajo_repo.crear_ejecucion(EjecucionReporteGasto(id_cola=id_cola, intento=intento))
                db.commit()

                generador = self.construir_generador(db)
                filtros = _filtros_desde_parametros(trabajo.parametros)
                reporte = generador.generar_forzado(filtros, trabajo.id_usuario_solicitante)

                ejecucion.completar(
                    hora_fin=datetime.now(timezone.utc),
                    id_reporte_resultado=reporte.id_reporte_gasto_acumulado,
                    resultado_json=_resultado_json(reporte),
                )
                trabajo_repo.guardar_ejecucion(ejecucion)
                trabajo_repo.marcar_estado(
                    id_cola, EstadoTrabajoAsync.COMPLETADO, fecha_procesado=datetime.now(timezone.utc)
                )
                db.commit()
                return
            except AppError as exc:
                # Regla de negocio/dato inválido (p.ej. activo sin ciclo): no se reintenta.
                db.rollback()
                self._marcar_fallido_definitivo(id_cola, str(exc.message), intento)
                return
            except Exception as exc:  # fallo técnico → reintento con backoff
                db.rollback()
                logger.warning("Reporte de gastos %s: fallo técnico intento %s: %s", id_cola, intento, exc)
                if intento < config.max_reintentos:
                    time.sleep(self._backoff_segundos(config, intento))
                    continue
                self._marcar_fallido_definitivo(id_cola, str(exc), intento)
                return
            finally:
                db.close()

    @staticmethod
    def _backoff_segundos(config, intento: int) -> float:
        minutos = config.backoff_minutos or [1, 3, 5]
        idx = min(intento - 1, len(minutos) - 1)
        return float(minutos[idx]) * 60.0

    def _marcar_fallido_definitivo(self, id_cola: int, causa: str, intentos: int) -> None:
        db = self.session_factory()
        try:
            self.construir_trabajo_repo(db).marcar_estado(
                id_cola, EstadoTrabajoAsync.FALLIDO, fecha_procesado=datetime.now(timezone.utc)
            )
            self.construir_fallo_repo(db).registrar(
                FalloReporteGasto(
                    id_cola=id_cola,
                    causa_fallo=causa,
                    intentos=intentos,
                    timestamp_ultimo_intento=datetime.now(timezone.utc),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo registrar el fallo del trabajo de reporte %s", id_cola)
        finally:
            db.close()
