"""Worker del motor async de historial de suministros (RF-81).

Análogo a ``ProcesarColaReportesGastosUseCase`` (RF-77) y, en última
instancia, a ``EjecutarBatchICAUseCase`` (RF-74): procesa hasta
``num_workers_max`` trabajos PENDIENTE en paralelo (``asyncio.Semaphore`` +
``to_thread``, sesión propia por trabajo), con reintentos y backoff
configurables. Despacha según ``tipo_trabajo``: ``CONSULTA_PESADA`` reutiliza
``ConsultarHistorialSuministrosUseCase.consultar_forzado``; ``EXPORTACION``
reutiliza ``ExportarHistorialSincronoUseCase.exportar_forzado``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Callable

from sqlalchemy.orm import Session

from src.shared.errors import AppError
from src.supplies.application.use_cases.historial_suministros.consultar_historial_suministros_use_case import (
    ConsultarHistorialSuministrosUseCase,
)
from src.supplies.application.use_cases.historial_suministros.exportar_historial_sincrono_use_case import (
    ExportarHistorialSincronoUseCase,
)
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro
from src.supplies.domain.entities.trabajo_historial_suministro import (
    EjecucionHistorialSuministro,
    FalloHistorialSuministro,
)
from src.supplies.domain.repositories.configuracion_batch_historial_repository import (
    ConfiguracionBatchHistorialRepository,
)
from src.supplies.domain.repositories.fallo_historial_suministro_repository import (
    FalloHistorialSuministroRepository,
)
from src.supplies.domain.repositories.trabajo_historial_suministro_repository import (
    TrabajoHistorialSuministroRepository,
)
from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync
from src.supplies.domain.value_objects.historial_suministro_enums import TipoTrabajoHistorial

logger = logging.getLogger(__name__)


def _filtros_desde_parametros(parametros: dict) -> FiltrosHistorialSuministro:
    return FiltrosHistorialSuministro(
        id_activo_biologico=parametros["id_activo_biologico"],
        id_ciclo_productivo=parametros.get("id_ciclo_productivo"),
        fecha_inicio_filtro=(
            date.fromisoformat(parametros["fecha_inicio_filtro"]) if parametros.get("fecha_inicio_filtro") else None
        ),
        fecha_fin_filtro=(
            date.fromisoformat(parametros["fecha_fin_filtro"]) if parametros.get("fecha_fin_filtro") else None
        ),
        tipo_suministro_filtro=parametros.get("tipo_suministro_filtro") or "TODOS",
        origen_precio_filtro=parametros.get("origen_precio_filtro") or "TODOS",
        costo_min=Decimal(parametros["costo_min"]) if parametros.get("costo_min") is not None else None,
        costo_max=Decimal(parametros["costo_max"]) if parametros.get("costo_max") is not None else None,
        pagina=parametros.get("pagina", 1),
        registros_por_pagina=parametros.get("registros_por_pagina", 50),
    )


def _resumen_a_json(resumen) -> dict:
    return {
        "total_registros_filtrados": resumen.total_registros_filtrados,
        "monto_total_filtrado": str(resumen.monto_total_filtrado),
        "desglose_por_tipo_suministro": {
            k: {"total": v["total"], "monto": str(v["monto"])} for k, v in resumen.desglose_por_tipo_suministro.items()
        },
        "desglose_por_ciclo": {
            k: {"total": v["total"], "monto": str(v["monto"])} for k, v in resumen.desglose_por_ciclo.items()
        },
        "nivel_volumen": resumen.nivel_volumen,
    }


class ProcesarColaHistorialSuministrosUseCase:
    def __init__(
        self,
        trabajo_repo: TrabajoHistorialSuministroRepository,
        config_repo: ConfiguracionBatchHistorialRepository,
        session_factory: Callable[[], Session],
        construir_trabajo_repo: Callable[[Session], TrabajoHistorialSuministroRepository],
        construir_fallo_repo: Callable[[Session], FalloHistorialSuministroRepository],
        construir_consultar: Callable[[Session], ConsultarHistorialSuministrosUseCase],
        construir_exportar: Callable[[Session], ExportarHistorialSincronoUseCase],
    ) -> None:
        self.trabajo_repo = trabajo_repo
        self.config_repo = config_repo
        self.session_factory = session_factory
        self.construir_trabajo_repo = construir_trabajo_repo
        self.construir_fallo_repo = construir_fallo_repo
        self.construir_consultar = construir_consultar
        self.construir_exportar = construir_exportar

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
            logger.exception("No se pudo marcar EN_PROCESO el trabajo de historial %s", id_cola)
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
                ejecucion = trabajo_repo.crear_ejecucion(
                    EjecucionHistorialSuministro(id_cola=id_cola, intento=intento)
                )
                db.commit()

                filtros = _filtros_desde_parametros(trabajo.parametros)
                id_rol = trabajo.parametros["id_rol_solicitante"]

                if trabajo.tipo_trabajo == TipoTrabajoHistorial.CONSULTA_PESADA.value:
                    consultar = self.construir_consultar(db)
                    resultado = consultar.consultar_forzado(
                        filtros, id_usuario=trabajo.id_usuario_solicitante, id_rol=id_rol
                    )
                    ejecucion.completar_consulta(
                        hora_fin=datetime.now(timezone.utc),
                        total_registros=resultado.resumen.total_registros_filtrados,
                        resultado_json=_resumen_a_json(resultado.resumen),
                    )
                else:  # EXPORTACION
                    exportar = self.construir_exportar(db)
                    contenido_csv, nombre_archivo, total = exportar.exportar_forzado(
                        filtros, id_usuario=trabajo.id_usuario_solicitante, id_rol=id_rol
                    )
                    ejecucion.completar_exportacion(
                        hora_fin=datetime.now(timezone.utc),
                        total_registros=total,
                        contenido_csv=contenido_csv,
                        nombre_archivo=nombre_archivo,
                    )

                trabajo_repo.guardar_ejecucion(ejecucion)
                trabajo_repo.marcar_estado(
                    id_cola, EstadoTrabajoAsync.COMPLETADO, fecha_procesado=datetime.now(timezone.utc)
                )
                db.commit()
                return
            except AppError as exc:
                # Regla de negocio/dato inválido (p.ej. activo inexistente): no se reintenta.
                db.rollback()
                self._marcar_fallido_definitivo(id_cola, str(exc.message), intento)
                return
            except Exception as exc:  # fallo técnico → reintento con backoff
                db.rollback()
                logger.warning("Trabajo de historial %s: fallo técnico intento %s: %s", id_cola, intento, exc)
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
                FalloHistorialSuministro(
                    id_cola=id_cola,
                    causa_fallo=causa,
                    intentos=intentos,
                    timestamp_ultimo_intento=datetime.now(timezone.utc),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo registrar el fallo del trabajo de historial %s", id_cola)
        finally:
            db.close()
