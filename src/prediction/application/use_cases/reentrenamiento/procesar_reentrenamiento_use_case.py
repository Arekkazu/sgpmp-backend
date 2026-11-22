# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71 BE-2/BE-3/BE-5: el motor toma, reporta y cierra procesos; vigilante de latidos |
"""Lo que hace el motor de IA (token de servicio) sobre los procesos, más el vigilante.

- ``tomar``: el PENDIENTE más antiguo pasa a EN_CURSO (``FOR UPDATE SKIP LOCKED``: dos
  motores no toman el mismo). Evento REENTRENAMIENTO_INICIADO.
- ``actualizar``: latido con fase, progreso y recursos; o cierre COMPLETADO / FALLIDO.
  Al completar sin ``id_version_modelo``, se toma la versión que RF-69 registró con
  ``id_proceso_rf71`` = este proceso (BE-3, sin tocar el contrato de registro).
- ``vigilar``: EN_CURSO sin latido por más de 15 min → INTERRUMPIDO (contenedor reiniciado).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.proceso_reentrenamiento import ProcesoReentrenamiento
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.proceso_reentrenamiento_repository import ProcesoReentrenamientoRepository
from src.shared.errors import BusinessRuleError, NotFoundError, ValidationError

SISTEMA = "motor-ia"


@dataclass(frozen=True)
class ActualizacionProceso:
    fase: Optional[int] = None
    progreso: Optional[int] = None
    cpu: Optional[Decimal] = None
    ram_mb: Optional[int] = None
    #: None = latido; COMPLETADO o FALLIDO = cierre.
    estado: Optional[str] = None
    id_version_modelo: Optional[int] = None
    codigo_error: Optional[str] = None
    motivos: Optional[list] = None
    #: Métricas de validación de la versión (para el evento REENTRENAMIENTO_COMPLETADO).
    metricas: Optional[dict[str, Any]] = None


class ProcesarReentrenamientoUseCase:
    def __init__(self, *, db: Session, procesos: ProcesoReentrenamientoRepository,
                 auditoria_repo: EventoAuditoriaM04Repository) -> None:
        self._db = db
        self._procesos = procesos
        self._auditoria = auditoria_repo

    def tomar(self, ahora: Optional[datetime] = None) -> Optional[ProcesoReentrenamiento]:
        ahora = ahora or datetime.now(timezone.utc)
        try:
            proceso = self._procesos.tomar_siguiente()
            if proceso is None:
                self._db.rollback()
                return None
            datos = self._procesos.datos_animal(proceso.id_activo_biologico)
            proceso.iniciar(ahora, datos.id_version_vigente if datos else None)
            proceso = self._procesos.guardar(proceso)
            self._evento(proceso, "REENTRENAMIENTO_INICIADO", {
                "tipo_modelo": proceso.tipo_modelo,
                "trigger_reentrenamiento": proceso.disparador,
                "version_modelo_base": proceso.id_version_modelo_referencia,
                # RF-73: el disparo MANUAL lleva quién lo pidió.
                "id_usuario_ejecucion": proceso.id_usuario_solicitante,
            })
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return self._procesos.obtener(proceso.id_proceso_reentrenamiento) or proceso

    def actualizar(self, id_proceso: uuid.UUID, cambio: ActualizacionProceso,
                   ahora: Optional[datetime] = None) -> ProcesoReentrenamiento:
        ahora = ahora or datetime.now(timezone.utc)
        if cambio.estado not in (None, "COMPLETADO", "FALLIDO"):
            raise ValidationError("ESTADO_INVALIDO", "estado solo puede ser COMPLETADO o FALLIDO.", field="estado")
        try:
            proceso = self._procesos.obtener(id_proceso)
            if proceso is None:
                raise NotFoundError("PROCESO_NO_ENCONTRADO", "El proceso de reentrenamiento no existe.")
            if cambio.estado is None:
                proceso.reportar(ahora=ahora, fase=cambio.fase, progreso=cambio.progreso, cpu=cambio.cpu, ram_mb=cambio.ram_mb)
            elif cambio.estado == "COMPLETADO":
                id_version = cambio.id_version_modelo or self._procesos.version_de_proceso(id_proceso)
                if id_version is None:
                    raise BusinessRuleError(
                        "VERSION_NO_REGISTRADA",
                        "No hay una versión registrada para este proceso: regístrala por RF-69 con su id_proceso_rf71.",
                        field="id_version_modelo",
                    )
                proceso.completar(ahora=ahora, id_version_modelo=id_version)
            else:
                proceso.fallar(ahora=ahora, codigo_error=cambio.codigo_error or "", motivos=cambio.motivos)
            proceso = self._procesos.guardar(proceso)
            if cambio.estado == "COMPLETADO":
                metricas = cambio.metricas or {}
                self._evento(proceso, "REENTRENAMIENTO_COMPLETADO", {
                    "tipo_modelo": proceso.tipo_modelo,
                    "id_version_generada": proceso.id_version_modelo_resultante,
                    "roc_auc_score": metricas.get("roc_auc_score"),
                    "estado_resultado": metricas.get("estado_resultado", "REGISTRADA"),
                    "f1_score_global": metricas.get("f1_score_global"),
                    "recall_clase_riesgo_alto": metricas.get("recall_clase_riesgo_alto"),
                })
            elif cambio.estado == "FALLIDO":
                self._evento(proceso, "REENTRENAMIENTO_FALLIDO", {
                    "tipo_modelo": proceso.tipo_modelo, "codigo_error": proceso.codigo_error,
                    "motivos": proceso.motivos, "fase": proceso.fase_actual,
                }, severidad="WARNING", resultado="FALLIDO", codigo_error=proceso.codigo_error)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return proceso

    def vigilar(self, ahora: Optional[datetime] = None) -> int:
        """BE-5: devuelve cuántos procesos se dieron por interrumpidos."""
        ahora = ahora or datetime.now(timezone.utc)
        n = 0
        try:
            for proceso in self._procesos.en_curso():
                if proceso.sin_latido(ahora):
                    proceso.interrumpir(ahora)
                    self._procesos.guardar(proceso)
                    self._evento(proceso, "REENTRENAMIENTO_INTERRUMPIDO", {
                        "tipo_modelo": proceso.tipo_modelo, "fase": proceso.fase_actual,
                        "ultimo_latido": proceso.fecha_ultimo_latido.isoformat() if proceso.fecha_ultimo_latido else None,
                    }, severidad="WARNING", resultado="FALLIDO")
                    n += 1
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return n

    def _evento(self, proceso: ProcesoReentrenamiento, tipo: str, payload: dict, *, severidad: str = "INFO",
                resultado: str = "EXITOSO", codigo_error: Optional[str] = None) -> None:
        payload = {**payload, "id_activo_biologico": proceso.id_activo_biologico,
                   "id_proceso_reentrenamiento": str(proceso.id_proceso_reentrenamiento)}
        # La bitácora no detiene el proceso (RF-73 E1): un rechazo queda en su respaldo.
        self._auditoria.registrar(
            tipo_evento=tipo, tipo_actor="SISTEMA", id_sistema=SISTEMA, payload_evento=payload,
            severidad_evento=severidad, id_referencia=str(proceso.id_proceso_reentrenamiento),
            entidad_referencia="proceso_reentrenamiento", resultado_operacion=resultado, codigo_error=codigo_error,
        )
