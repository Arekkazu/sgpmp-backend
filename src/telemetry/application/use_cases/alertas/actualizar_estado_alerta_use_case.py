# | Fecha      | Nombre  | Que se hizo                                            |
# |------------|---------|--------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-30 RF-57: impide vencimientos por el flujo manual   |
# | 2026-10-21 | Leandro | DEV-49 RF-57: elimina el historial redundante     |
# | 2026-10-22 | Leandro | DEV-42 RF-60: resuelve conectividad en transaccion externa |
from __future__ import annotations

from sqlalchemy.orm import Session

from src.shared.errors import AppError, BusinessRuleError, NotFoundError
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo, SeveridadLog, TipoResultado
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.entities.alerta import Alerta, AmbitoAlerta, EstadoAlerta
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.historico_estado_alerta_repository import HistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.dto.actualizar_estado_alerta_dto import ActualizarEstadoAlertaDTO


class ActualizarEstadoAlertaUseCase:

    @staticmethod
    def resolver_conectividad(alerta, alerta_repo, ahora):
        """Recuperación interna RF-60; conserva las transiciones de RF-57.

        ACTIVA pasa por EN_ATENCION antes de RESUELTA. El trigger registra
        ambas transiciones reales; no se agrega historia ni se hace commit.
        """
        if alerta.tipo_alerta != 'TECNICA' or alerta.tipo_variable not in {
            'DISPOSITIVO_SIN_SEÑAL', 'DISPOSITIVO_INACTIVO', 'FALLO_CONECTIVIDAD', 'HEARTBEAT_AUSENTE',
        }:
            return
        destinos = ('EN_ATENCION', 'RESUELTA') if alerta.estado_alerta == 'ACTIVA' else (
            ('RESUELTA',) if alerta.estado_alerta == 'EN_ATENCION' else ())
        for destino in destinos:
            alerta.transicionar(destino, None, 'Reconexión confirmada por RF-60.')
            alerta.diagnostico = 'Reconexión confirmada por RF-60.'
            alerta_repo.actualizar_estado(alerta.id_alerta, destino, None, alerta.diagnostico,
                fecha_atencion=alerta.fecha_atencion, fecha_resolucion=alerta.fecha_resolucion)

    def __init__(
        self,
        db: Session,
        alerta_repo: AlertaRepository,
        historico_repo: HistoricoEstadoAlertaRepository,
        ambito: AmbitoAlerta,
        auditoria_repo: BitacoraAuditoriaIotRepository | None = None,
    ) -> None:
        self.db = db
        self.alerta_repo = alerta_repo
        # Se conserva la firma de ensamblado; la escritura pertenece al trigger.
        self.historico_repo = historico_repo
        self.ambito = ambito
        self.auditoria_repo = auditoria_repo

    def execute(self, id_alerta: int, dto: ActualizarEstadoAlertaDTO, id_usuario: int) -> Alerta:
        alerta = self.alerta_repo.obtener_por_id(id_alerta)
        # RF-60 D-09: el Productor no resuelve alertas técnicas por /iot/alertas,
        # ni el Ingeniero alertas operativas por /iot/alertas-tecnicas.
        if alerta is None or not self.ambito.admite(alerta.tipo_alerta):
            raise NotFoundError(code="ALERTA_NO_ENCONTRADA", message=f"Alerta {id_alerta} no encontrada.")

        try:
            # El vencimiento pertenece al procesamiento interno por SLA.
            # La entidad conserva esa transición para DEV-31, no para REST.
            if dto.nuevo_estado == EstadoAlerta.VENCIDA:
                raise BusinessRuleError(
                    code="TRANSICION_INVALIDA",
                    message="El estado VENCIDA solo puede establecerse automáticamente por SLA.",
                )
            alerta.transicionar(dto.nuevo_estado, id_usuario, dto.motivo)
            alerta_actualizada = self.alerta_repo.actualizar_estado(
                id_alerta=id_alerta,
                nuevo_estado=alerta.estado_alerta,
                id_usuario=id_usuario,
                motivo=dto.motivo,
                fecha_atencion=alerta.fecha_atencion,
                fecha_resolucion=alerta.fecha_resolucion,
            )
            # El trigger de UPDATE guarda actor y motivo de forma atómica.
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            if isinstance(exc, AppError) and exc.code == "TRANSICION_INVALIDA" and self.auditoria_repo is not None:
                # Una transacción nueva: el trigger ya abortó la operación.
                # RF-63 guarda el rechazo, nunca un cambio de estado ficticio.
                RegistrarEventoAuditoriaIotUseCase(self.db, self.auditoria_repo).execute(
                    tipo_evento="TRANSICION_ALERTA_RECHAZADA",
                    resultado=TipoResultado.RECHAZADO,
                    componente_origen=ComponenteOrigen.RF57,
                    severidad_log=SeveridadLog.WARNING,
                    descripcion="Transición de estado de alerta rechazada.",
                    entidad_afectada_tipo=EntidadAfectadaTipo.ALERTA,
                    entidad_afectada_id=str(id_alerta),
                    id_usuario=id_usuario,
                    accion_detallada={"error_code": exc.code, "estado_solicitado": dto.nuevo_estado},
                )
            raise

        return alerta_actualizada
