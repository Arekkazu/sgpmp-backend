# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-167-G75 RF-57 E16: reevaluación por IA tras la recuperación del motor |
"""RF-57 E16 (y E3/CA-6): el motor de IA, ya recuperado, reevalúa el evento de una alerta generada sin él.

- La alerta original no se modifica (inmutabilidad del historial).
- Si el tipo o la severidad difieren: alerta nueva con origen IA, ``referencia_alerta_original`` y
  ``tiene_generada_por_reevaluacion``.
- Si confirma tipo y severidad: no hay alerta nueva; ``REEVALUACION_CONFIRMADA`` en la bitácora RF-63.
- Solo dentro de la ventana (valor base 60 min desde la generación, configurable) y una vez por alerta.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
from src.telemetry.domain.entities.alerta import (
    TIPO_ALERTA_TECNICA,
    Alerta,
    EstadoAlerta,
    OrigenEventoAlerta,
)
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo, SeveridadLog, TipoResultado
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.parametros_alertas_port import ParametrosAlertasPort
from src.telemetry.infrastructure.dto.reevaluar_alerta_dto import ReevaluarAlertaDTO

CONFIRMADA = "CONFIRMADA"
ALERTA_GENERADA = "ALERTA_GENERADA"


@dataclass
class ResultadoReevaluacion:
    resultado: str
    id_alerta_original: int
    id_alerta_nueva: Optional[int] = None
    tipo_alerta: Optional[str] = None
    severidad: Optional[str] = None


class ReevaluarAlertaUseCase:
    def __init__(self, db: Session, alerta_repo: AlertaRepository, parametros_port: ParametrosAlertasPort,
                 auditoria_repo: Optional[BitacoraAuditoriaIotRepository] = None) -> None:
        self.db = db
        self.alerta_repo = alerta_repo
        self.parametros_port = parametros_port
        self.auditoria_repo = auditoria_repo

    def execute(self, id_alerta: int, dto: ReevaluarAlertaDTO,
                ahora: Optional[datetime] = None) -> ResultadoReevaluacion:
        ahora = ahora or datetime.now(timezone.utc)
        original = self.alerta_repo.obtener_por_id(id_alerta)
        if original is None:
            raise NotFoundError(code="ALERTA_NO_ENCONTRADA", message=f"No existe la alerta {id_alerta}.")
        if (original.tipo_alerta == TIPO_ALERTA_TECNICA or original.tiene_generada_por_reevaluacion
                or not original.tiene_inferencia_no_disponible):
            raise BusinessRuleError(
                code="REEVALUACION_NO_APLICA",
                message="Solo se reevalúan alertas operativas generadas sin motor de inferencia (E3), "
                        "y no las que ya son producto de una reevaluación.")

        ventana = self.parametros_port.obtener_ventana_reevaluacion_min()
        generada = original.fecha_generacion
        if generada.tzinfo is None:
            generada = generada.replace(tzinfo=timezone.utc)
        transcurrido = ahora - generada
        if transcurrido > timedelta(minutes=ventana):
            self._auditar(original, "REEVALUACION_FUERA_DE_VENTANA", TipoResultado.RECHAZADO, SeveridadLog.WARNING,
                          "Reevaluación recibida fuera de la ventana de E16.", dto, transcurrido, ventana)
            raise BusinessRuleError(
                code="VENTANA_REEVALUACION_VENCIDA",
                message=f"La reevaluación llegó {self._minutos(transcurrido)} min después de generar la alerta; "
                        f"la ventana es de {ventana} min.")

        try:
            if self.alerta_repo.buscar_reevaluacion(original.id_alerta) is not None:
                raise ConflictError(code="REEVALUACION_YA_REGISTRADA",
                                    message=f"La alerta {original.id_alerta} ya tiene una alerta de reevaluación.")
            tipo = dto.tipo_alerta_ia or original.tipo_alerta
            if tipo == original.tipo_alerta and dto.severidad_ia == original.severidad:
                self.db.rollback()  # libera el lock: solo queda escribir la bitácora
                self._auditar(original, "REEVALUACION_CONFIRMADA", TipoResultado.EXITOSO, SeveridadLog.INFO,
                              "La IA confirma el tipo y la severidad de la alerta (E16): sin alerta nueva.",
                              dto, transcurrido, ventana)
                return ResultadoReevaluacion(CONFIRMADA, original.id_alerta, tipo_alerta=tipo,
                                             severidad=dto.severidad_ia)

            nueva = Alerta(
                tipo_alerta=tipo,
                severidad=dto.severidad_ia,
                estado_alerta=EstadoAlerta.ACTIVA,
                origen_evento=OrigenEventoAlerta.IA,
                tipo_variable=original.tipo_variable,
                fecha_evento=original.fecha_evento,
                fecha_generacion=ahora,
                reglas_activas=list(original.reglas_activas or []),
                valor=original.valor,
                unidad=original.unidad,
                contexto_activo_biologico=original.contexto_activo_biologico,
                metadato_evento={"reevaluacion": {**self._detalle(original, dto, transcurrido, ventana),
                                                  **(dto.metadata_reevaluacion or {})}},
                tiene_inferencia_no_disponible=False,
                tiene_contexto_incompleto=original.tiene_contexto_incompleto,
                tiene_generada_por_reevaluacion=True,
                referencia_alerta_original=original.id_alerta,
                severidad_ia=dto.severidad_ia,
                id_evento_edge_computing=original.id_evento_edge_computing,
                id_telemetria=original.id_telemetria,
                id_paquete_inferencia=dto.id_paquete_inferencia or original.id_paquete_inferencia,
                id_sensor=original.id_sensor,
                id_dispositivo_ioit=original.id_dispositivo_ioit,
                id_activo_biologico=original.id_activo_biologico,
                id_infraestructura=original.id_infraestructura,
            )
            nueva.fecha_vencimiento = nueva.calcular_fecha_vencimiento()
            guardada = self.alerta_repo.guardar(nueva)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ResultadoReevaluacion(ALERTA_GENERADA, original.id_alerta, guardada.id_alerta,
                                     guardada.tipo_alerta, guardada.severidad)

    @staticmethod
    def _minutos(transcurrido: timedelta) -> str:
        return f"{transcurrido.total_seconds() / 60:.2f}"

    def _detalle(self, original, dto, transcurrido, ventana) -> dict:
        return {"id_alerta_original": original.id_alerta, "tipo_original": original.tipo_alerta,
                "severidad_original": original.severidad, "tipo_ia": dto.tipo_alerta_ia or original.tipo_alerta,
                "severidad_ia": dto.severidad_ia,
                "probabilidad_ia": str(dto.probabilidad_ia) if dto.probabilidad_ia is not None else None,
                "minutos_desde_original": self._minutos(transcurrido), "ventana_min": ventana}

    def _auditar(self, original, tipo_evento, resultado, severidad_log, descripcion, dto, transcurrido, ventana) -> None:
        if self.auditoria_repo is None:
            return
        RegistrarEventoAuditoriaIotUseCase(self.db, self.auditoria_repo).execute(
            tipo_evento=tipo_evento,
            resultado=resultado,
            componente_origen=ComponenteOrigen.RF57,
            severidad_log=severidad_log,
            descripcion=descripcion,
            entidad_afectada_tipo=EntidadAfectadaTipo.ALERTA,
            entidad_afectada_id=str(original.id_alerta),
            accion_detallada=self._detalle(original, dto, transcurrido, ventana),
        )
