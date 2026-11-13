# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74: alerta interna de batch y cola     |
# | 2026-11-08 | Arekkazu         | INC-M05-259-G07 RF-74: fallo técnico 500/503, aviso de fallo persistente y pendientes |
# | 2026-11-12 | Arekkazu         | USAB-M05-M06 N-07 RF-74/80: el cálculo automático queda firmado por el usuario de servicio |
# | 2026-11-12 | Leandro | INC-M05-350/351-G05 RF-74: preservar el corte manual al finalizar y evitar un aviso de ventana duplicado. |
"""Caso de uso: motor batch de cálculo ICA (RF-74, Flujo C — alcance completo).

Orquesta una corrida completa:

- Lee la configuración (``configuracion_batch_ica``) y selecciona los activos ACTIVO
  (o solo la cola pendiente si ``solo_cola``).
- Prioriza (CRITICA del vigente primero, luego antigüedad de ciclo) y aplica el
  **límite**: los excedentes se **encolan** (``LIMITE_SUPERADO`` — FA-07).
- Procesa con **workers paralelos** (``asyncio`` + ``to_thread``, una sesión/transacción
  independiente por activo); el paralelismo solo se activa si el nº de activos supera el
  ``umbral_paralelizacion``.
- **Reintentos** por fallo técnico (también un ``AppError`` 5xx, p. ej. el error de BD traducido)
  tras el intento inicial, uno por cada espera de ``backoff_minutos`` hasta ``max_reintentos``;
  agotados → ``fallos_calculo_ica`` (``CA_FALLO_PERSISTENTE`` — E5) y aviso a quien puede
  reintentarlo a mano.
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

from src.shared.database import id_usuario_servicio
from src.shared.errors import AppError, BusinessRuleError, ConflictError, es_fallo_tecnico
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
from src.supplies.domain.repositories.notificacion_suministros_port import NotificacionSuministrosPort
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

# administracion_batch_ica (50), acción E: Administrador y Productor reactivan el batch.
_RECURSO_BATCH_ICA, _ACCION_EJECUTAR = 50, 5

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
        notificador: Optional[NotificacionSuministrosPort] = None,
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
        self.notificador = notificador

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

        if excedentes:
            self._alertar(
                f"El proceso batch de cálculo de CA superó el límite configurado de {limite} activos. "
                f"{len(excedentes)} activos quedaron en cola para el siguiente ciclo; puede reactivar el "
                "procesado de forma manual.",
                {"id_ejecucion": ejecucion.id_ejecucion, "en_cola": len(excedentes)},
            )

        procesados, fallos, interrumpido = await self._procesar(
            seleccionados, config, ejecucion, num_workers
        )

        return self._finalizar(ejecucion.id_ejecucion, procesados, fallos, interrumpido, len(excedentes))

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
        contadores = {"procesados": 0, "interrumpido": False}
        fallos: list[dict] = []

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
                fallo = await asyncio.to_thread(
                    self._procesar_activo, trabajo.id_activo, config, ejecucion.id_ejecucion
                )
                async with lock:
                    contadores["procesados"] += 1
                    if fallo is not None:
                        fallos.append(fallo)
                if trabajo.id_cola is not None:
                    await asyncio.to_thread(self._marcar_cola, trabajo.id_cola)

        await asyncio.gather(*(worker(t) for t in seleccionados))
        return contadores["procesados"], fallos, contadores["interrumpido"]

    # ── Trabajo por activo (en hilo, sesión propia) ──────────────────────────
    def _procesar_activo(self, id_activo: int, config, id_ejecucion: int) -> Optional[dict]:
        """``None`` si el activo quedó resuelto; si no, el fallo persistente registrado (E5)."""
        intentos = 1 + config.max_reintentos
        for intento in range(1, intentos + 1):
            db = self.session_factory()
            try:
                uc = self.construir_calculo(db)
                tipo = TipoCalculo.AUTOMATICO if intento == 1 else TipoCalculo.REINTENTO_AUTOMATICO
                for periodo in _PERIODOS:
                    uc.execute(
                        id_activo_biologico=id_activo,
                        periodo=periodo,
                        tipo_calculo=tipo,
                        # N-07: lo calcula el Sistema; sin id, la auditoría lo firmaba con el usuario 1.
                        id_usuario=id_usuario_servicio(db),
                        intento=intento,
                    )
                return None
            except Exception as exc:
                db.rollback()
                if not es_fallo_tecnico(exc):
                    # Regla de negocio/dato (p.ej. activo no ACTIVO): no se reintenta.
                    return None
                causa = exc.message if isinstance(exc, AppError) else str(exc)
                logger.warning("Batch ICA: fallo técnico activo %s intento %s: %s", id_activo, intento, causa)
                if intento < intentos:
                    time.sleep(self._backoff_segundos(config, intento))
                    continue
                ahora = datetime.now(timezone.utc)
                self._registrar_fallo(id_activo, causa, config.max_reintentos, id_ejecucion, ahora)
                return {"id_activo_biologico": id_activo, "causa_fallo": causa[:300],
                        "timestamp_ultimo_intento": ahora.isoformat()}
            finally:
                db.close()
        return None  # pragma: no cover — el bucle siempre retorna

    @staticmethod
    def _backoff_segundos(config, intento: int) -> float:
        minutos = config.backoff_minutos or [2, 4, 6]
        idx = min(intento - 1, len(minutos) - 1)
        return float(minutos[idx]) * 60.0

    def _registrar_fallo(self, id_activo: int, causa: str, intentos: int, id_ejecucion: int,
                         ultimo_intento: datetime) -> None:
        db = self.session_factory()
        try:
            repo = self.construir_fallo_repo(db)
            repo.registrar(
                FalloCalculoICA(
                    id_activo_biologico=id_activo,
                    causa_fallo=causa,
                    intentos=intentos,
                    id_ejecucion_batch=id_ejecucion,
                    timestamp_ultimo_intento=ultimo_intento,
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
    def _finalizar(self, id_ejecucion: int, procesados: int, fallos: list[dict], interrumpido: bool,
                   en_cola_por_limite: int) -> EjecucionBatchICA:
        ejecucion = self.ejecucion_repo.obtener(id_ejecucion, para_actualizar=True)
        ejecucion.cantidad_activos_procesados = procesados
        ejecucion.cantidad_fallidos = len(fallos)
        ahora = datetime.now(timezone.utc)
        corte_por_ventana = interrumpido and ejecucion.esta_en_ejecucion
        if ejecucion.esta_en_ejecucion:
            if corte_por_ventana:
                ejecucion.interrumpir(causa=CausaInterrupcionBatch.VENTANA_EXCEDIDA.value, hora_corte=ahora)
            else:
                ejecucion.completar(hora_fin=ahora)
        # Pendientes = los que no alcanzaron a procesarse + los que el límite dejó en cola (FA-07);
        # completar()/interrumpir() solo ven los primeros.
        ejecucion.cantidad_activos_pendientes = (
            max(ejecucion.cantidad_activos_total - procesados, 0) + en_cola_por_limite
        )
        guardada = self.ejecucion_repo.guardar(ejecucion)
        self.db.commit()
        if corte_por_ventana:
            self._alertar(
                "El proceso batch de cálculo de CA no completó su ejecución. Se procesaron "
                f"{procesados} de {guardada.cantidad_activos_total} activos. El proceso continuará en el "
                "siguiente ciclo o reactive el procesado de forma manual.",
                {"id_ejecucion": id_ejecucion, "procesados": procesados},
            )
        if fallos:
            # E5: un aviso por corrida con cada activo, su causa y su último intento (no uno por activo).
            self._alertar(
                f"El cálculo de CA falló en {len(fallos)} activo(s) después de agotar los reintentos. "
                "Revíselos en Fallos persistentes y reintente el cálculo de forma manual.",
                {"id_ejecucion": id_ejecucion, "fallos": fallos},
            )
        return guardada

    def _alertar(self, mensaje: str, detalle: dict) -> None:
        """RF-74: alerta interna al Administrador y al Productor (quienes operan el batch, recurso 50)."""
        if self.notificador is not None:
            self.notificador.a_permiso(_RECURSO_BATCH_ICA, _ACCION_EJECUTAR, "BATCH_ICA_INTERRUMPIDO", mensaje, detalle)
