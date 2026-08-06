"""Caso de uso: motor batch de cálculo ICA (RF-74, Flujo C — alcance completo).

Orquesta una corrida completa:

- Lee la configuración (``configuracion_batch_ica``) y selecciona los activos ACTIVO
  (o solo la cola pendiente si ``solo_cola``).
- Prioriza (CRITICA del vigente primero, luego antigüedad de ciclo) y aplica el
  **límite**: los excedentes se **encolan** (``LIMITE_SUPERADO`` — FA-07).
- Procesa con **workers paralelos** (``asyncio`` + ``to_thread``, una sesión/transacción
  independiente por activo); el paralelismo solo se activa si el nº de activos supera el
  ``umbral_paralelizacion``.
- **Reintentos** por fallo técnico con backoff; agotados → ``fallos_calculo_ica``
  (``CA_FALLO_PERSISTENTE`` — E5).
- **Control de ventana**: si se excede ``ventana_horas`` se interrumpe, se preservan los
  pendientes en la cola (``VENTANA_EXCEDIDA`` — FA-06) y la corrida queda ``INTERRUMPIDO``.

``CalcularICAUseCase`` (que ya hace su propio ``commit`` por activo/período) se construye
por sesión mediante las fábricas inyectadas, de modo que la aplicación no importa
infraestructura directamente.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.shared.errors import AppError, BusinessRuleError, ConflictError
from src.supplies.application.use_cases.eficiencia.calcular_ica_use_case import CalcularICAUseCase
from src.supplies.domain.entities.ejecucion_batch_ica import EjecucionBatchICA
from src.supplies.domain.entities.fallo_calculo_ica import FalloCalculoICA
from src.supplies.domain.entities.item_cola_ica import ItemColaICA
from src.supplies.domain.repositories.activos_batch_port import ActivosBatchPort
from src.supplies.domain.repositories.cola_calculo_ica_repository import ColaCalculoICARepository
from src.supplies.domain.repositories.configuracion_batch_ica_repository import (
    ConfiguracionBatchICARepository,
)
from src.supplies.domain.repositories.ejecucion_batch_ica_repository import EjecucionBatchICARepository
from src.supplies.domain.repositories.fallo_calculo_ica_repository import FalloCalculoICARepository
from src.supplies.domain.repositories.resultado_ica_repository import ResultadoICARepository
from src.supplies.domain.value_objects.eficiencia_enums import (
    CausaInterrupcionBatch,
    EstadoEjecucionBatch,
    EstadoItemCola,
    MotivoEncolado,
    PeriodoEvaluacion,
    TipoCalculo,
)

logger = logging.getLogger(__name__)

_PERIODOS = (PeriodoEvaluacion.SEMANAL, PeriodoEvaluacion.MENSUAL, PeriodoEvaluacion.POR_CICLO)
_PRIORIDAD_CRITICA = 1
_PRIORIDAD_NORMAL = 100
# Fecha sentinela para ordenar activos sin fecha de inicio de ciclo al final.
_FECHA_MAX = date.max


class _Trabajo:
    __slots__ = ("id_activo", "prioridad", "fecha_inicio_ciclo", "id_cola")

    def __init__(self, id_activo, prioridad, fecha_inicio_ciclo, id_cola=None):
        self.id_activo = id_activo
        self.prioridad = prioridad
        self.fecha_inicio_ciclo = fecha_inicio_ciclo
        self.id_cola = id_cola


class EjecutarBatchICAUseCase:
    def __init__(
        self,
        db: Session,
        ejecucion_repo: EjecucionBatchICARepository,
        cola_repo: ColaCalculoICARepository,
        config_repo: ConfiguracionBatchICARepository,
        activos_batch_port: ActivosBatchPort,
        resultado_repo: ResultadoICARepository,
        session_factory: Callable[[], Session],
        construir_calculo: Callable[[Session], CalcularICAUseCase],
        construir_fallo_repo: Callable[[Session], FalloCalculoICARepository],
    ) -> None:
        self.db = db
        self.ejecucion_repo = ejecucion_repo
        self.cola_repo = cola_repo
        self.config_repo = config_repo
        self.activos_batch_port = activos_batch_port
        self.resultado_repo = resultado_repo
        self.session_factory = session_factory
        self.construir_calculo = construir_calculo
        self.construir_fallo_repo = construir_fallo_repo

    async def ejecutar(
        self,
        *,
        tipo_disparo: str = "AUTOMATICO",
        id_usuario: Optional[int] = None,
        solo_cola: bool = False,
    ) -> EjecucionBatchICA:
        config = self.config_repo.obtener()
        if not config.es_activo:
            raise BusinessRuleError(
                code="BATCH_DESACTIVADO",
                message="El motor batch de cálculo ICA está desactivado en la configuración.",
            )
        if self.ejecucion_repo.obtener_en_ejecucion() is not None:
            raise ConflictError(
                code="BATCH_EN_CURSO",
                message="Ya hay una ejecución del batch ICA en curso. Espere a que finalice.",
            )

        trabajos = self._seleccionar_trabajos(solo_cola=solo_cola)
        limite = config.limite_activos
        seleccionados = trabajos[:limite]
        excedentes = trabajos[limite:]

        # FA-07: los excedentes por límite se encolan.
        for t in excedentes:
            self.cola_repo.encolar(
                ItemColaICA(
                    id_activo_biologico=t.id_activo,
                    prioridad=t.prioridad,
                    estado=EstadoItemCola.EN_COLA,
                    motivo=MotivoEncolado.LIMITE_SUPERADO.value,
                )
            )

        num_workers = (
            config.num_workers_max if len(seleccionados) > config.umbral_paralelizacion else 1
        )
        ejecucion = self.ejecucion_repo.crear(
            EjecucionBatchICA(
                tipo_disparo=tipo_disparo,
                hora_inicio=datetime.now(timezone.utc),
                num_workers=num_workers,
                limite_configurado=limite,
                cantidad_activos_total=len(seleccionados),
                cantidad_activos_pendientes=len(excedentes),
                id_usuario_disparo=id_usuario,
            )
        )
        self.db.commit()

        procesados, fallidos, interrumpido = await self._procesar(
            seleccionados, config, ejecucion, num_workers
        )

        return self._finalizar(ejecucion.id_ejecucion, procesados, fallidos, interrumpido)

    # ── Selección / priorización ─────────────────────────────────────────────
    def _seleccionar_trabajos(self, *, solo_cola: bool) -> list[_Trabajo]:
        if solo_cola:
            pendientes = self.cola_repo.listar_pendientes()
            trabajos = [
                _Trabajo(
                    id_activo=item.id_activo_biologico,
                    prioridad=item.prioridad,
                    fecha_inicio_ciclo=None,
                    id_cola=item.id_cola,
                )
                for item in pendientes
            ]
        else:
            refs = self.activos_batch_port.listar_activos_para_batch()
            trabajos = [
                _Trabajo(
                    id_activo=r.id_activo_biologico,
                    prioridad=(
                        _PRIORIDAD_CRITICA
                        if self.resultado_repo.tiene_vigente_critica(r.id_activo_biologico)
                        else _PRIORIDAD_NORMAL
                    ),
                    fecha_inicio_ciclo=r.fecha_inicio_ciclo,
                )
                for r in refs
            ]
        trabajos.sort(
            key=lambda t: (
                t.prioridad,
                (t.fecha_inicio_ciclo is None, t.fecha_inicio_ciclo or _FECHA_MAX),
                t.id_activo,
            )
        )
        return trabajos

    # ── Procesamiento paralelo ───────────────────────────────────────────────
    async def _procesar(self, seleccionados, config, ejecucion, num_workers):
        deadline = ejecucion.hora_inicio + timedelta(hours=config.ventana_horas)
        sem = asyncio.Semaphore(num_workers)
        lock = asyncio.Lock()
        contadores = {"procesados": 0, "fallidos": 0, "interrumpido": False}

        async def worker(trabajo: _Trabajo) -> None:
            async with sem:
                ventana_excedida = datetime.now(timezone.utc) > deadline
                interrumpido_manual = await asyncio.to_thread(
                    self._esta_interrumpido, ejecucion.id_ejecucion
                )
                if ventana_excedida or interrumpido_manual:
                    # FA-06 (ventana) / FA-12 (manual): se preserva en cola y no se procesa.
                    motivo = (
                        MotivoEncolado.VENTANA_EXCEDIDA if ventana_excedida else MotivoEncolado.INTERRUMPIDO
                    )
                    async with lock:
                        if ventana_excedida:
                            contadores["interrumpido"] = True
                    await asyncio.to_thread(self._encolar_pendiente, trabajo, motivo)
                    return
                estado = await asyncio.to_thread(
                    self._procesar_activo, trabajo.id_activo, config, ejecucion.id_ejecucion
                )
                async with lock:
                    contadores["procesados"] += 1
                    if estado == "FALLO":
                        contadores["fallidos"] += 1
                if trabajo.id_cola is not None:
                    await asyncio.to_thread(self._marcar_cola, trabajo.id_cola)

        await asyncio.gather(*(worker(t) for t in seleccionados))
        return contadores["procesados"], contadores["fallidos"], contadores["interrumpido"]

    # ── Trabajo por activo (en hilo, sesión propia) ──────────────────────────
    def _procesar_activo(self, id_activo: int, config, id_ejecucion: int) -> str:
        for intento in range(1, config.max_reintentos + 1):
            db = self.session_factory()
            try:
                uc = self.construir_calculo(db)
                tipo = TipoCalculo.AUTOMATICO if intento == 1 else TipoCalculo.REINTENTO_AUTOMATICO
                for periodo in _PERIODOS:
                    uc.execute(
                        id_activo_biologico=id_activo,
                        periodo=periodo,
                        tipo_calculo=tipo,
                        id_usuario=None,
                        intento=intento,
                    )
                return "OK"
            except AppError:
                # Regla de negocio/dato (p.ej. activo no ACTIVO): no se reintenta.
                db.rollback()
                return "OK"
            except Exception as exc:  # fallo técnico → reintento con backoff
                db.rollback()
                logger.warning("Batch ICA: fallo técnico activo %s intento %s: %s", id_activo, intento, exc)
                if intento < config.max_reintentos:
                    time.sleep(self._backoff_segundos(config, intento))
                    continue
                self._registrar_fallo(id_activo, str(exc), config.max_reintentos, id_ejecucion)
                return "FALLO"
            finally:
                db.close()
        return "FALLO"

    @staticmethod
    def _backoff_segundos(config, intento: int) -> float:
        minutos = config.backoff_minutos or [2, 4, 6]
        idx = min(intento - 1, len(minutos) - 1)
        return float(minutos[idx]) * 60.0

    def _registrar_fallo(self, id_activo: int, causa: str, intentos: int, id_ejecucion: int) -> None:
        db = self.session_factory()
        try:
            repo = self.construir_fallo_repo(db)
            repo.registrar(
                FalloCalculoICA(
                    id_activo_biologico=id_activo,
                    causa_fallo=causa,
                    intentos=intentos,
                    id_ejecucion_batch=id_ejecucion,
                    timestamp_ultimo_intento=datetime.now(timezone.utc),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Batch ICA: no se pudo registrar el fallo del activo %s", id_activo)
        finally:
            db.close()

    def _esta_interrumpido(self, id_ejecucion: int) -> bool:
        db = self.session_factory()
        try:
            from src.supplies.infrastructure.repositories.ejecucion_batch_ica_repository import (
                SqlAlchemyEjecucionBatchICARepository,
            )

            ejec = SqlAlchemyEjecucionBatchICARepository(db).obtener(id_ejecucion)
            return ejec is not None and ejec.estado == EstadoEjecucionBatch.INTERRUMPIDO
        finally:
            db.close()

    def _encolar_pendiente(self, trabajo: _Trabajo, motivo: MotivoEncolado) -> None:
        db = self.session_factory()
        try:
            from src.supplies.infrastructure.repositories.cola_calculo_ica_repository import (
                SqlAlchemyColaCalculoICARepository,
            )

            SqlAlchemyColaCalculoICARepository(db).encolar(
                ItemColaICA(
                    id_activo_biologico=trabajo.id_activo,
                    prioridad=trabajo.prioridad,
                    estado=EstadoItemCola.EN_COLA,
                    motivo=motivo.value,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _marcar_cola(self, id_cola: int) -> None:
        db = self.session_factory()
        try:
            from src.supplies.infrastructure.repositories.cola_calculo_ica_repository import (
                SqlAlchemyColaCalculoICARepository,
            )

            SqlAlchemyColaCalculoICARepository(db).marcar(
                id_cola, EstadoItemCola.COMPLETADO, fecha_procesado=datetime.now(timezone.utc)
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    # ── Cierre de la corrida ─────────────────────────────────────────────────
    def _finalizar(self, id_ejecucion: int, procesados: int, fallidos: int, interrumpido: bool) -> EjecucionBatchICA:
        ejecucion = self.ejecucion_repo.obtener(id_ejecucion)
        ejecucion.cantidad_activos_procesados = procesados
        ejecucion.cantidad_fallidos = fallidos
        ahora = datetime.now(timezone.utc)
        if ejecucion.estado == EstadoEjecucionBatch.INTERRUMPIDO:
            # Interrumpido manualmente (FA-12) mientras corría: solo se actualizan métricas.
            ejecucion.cantidad_activos_pendientes = max(
                ejecucion.cantidad_activos_total - procesados, 0
            )
        elif interrumpido:
            ejecucion.interrumpir(causa=CausaInterrupcionBatch.VENTANA_EXCEDIDA.value, hora_corte=ahora)
        else:
            ejecucion.completar(hora_fin=ahora)
        guardada = self.ejecucion_repo.guardar(ejecucion)
        self.db.commit()
        return guardada
