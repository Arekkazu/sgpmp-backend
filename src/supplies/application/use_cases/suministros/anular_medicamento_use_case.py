# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-76: anular compensa ledger y retiro    |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Caso de uso: anular una aplicación de medicamento VALIDADA (RF-76).

- E8: un registro ANULADO no puede volver a anularse (409).
- E9: la justificación exige al menos 20 caracteres (400).
- El costo que había sumado al acumulado del ciclo (RF-78) se compensa en la
  misma transacción: un registro anulado queda fuera de los cálculos.
- R10/R11: el retiro vigente es el MAX de los tratamientos VALIDADOS. Si el
  tratamiento anulado era el que mantenía el retiro y ya no queda ninguno
  vigente, se invoca RF-44 para devolver el activo a ACTIVO y se avisa el fin
  del retiro (pasos 12-13), igual que el scheduler diario.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, NotFoundError
from src.shared.fechas import hoy_usuario
from src.supplies.application.use_cases.costeo_suministros.compensar_anulacion import CompensadorAnulacion
from src.supplies.domain.entities.medicamento import Medicamento
from src.supplies.domain.repositories.activo_consulta_port import ESTADO_EN_TRATAMIENTO, ActivoConsultaPort
from src.supplies.domain.repositories.estado_activo_port import EstadoActivoPort
from src.supplies.domain.repositories.medicamento_repository import MedicamentoRepository
from src.supplies.domain.repositories.notificacion_medicamento_port import NotificacionMedicamentoPort
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro
from src.supplies.domain.value_objects.justificacion_anulacion import MENSAJE_RF76, JustificacionAnulacion
from src.supplies.infrastructure.dto.anular_registro_dto import AnularRegistroDTO

_MOTIVO_FIN_RETIRO = "Anulación del único tratamiento con retiro vigente (RF-76)."


class AnularMedicamentoUseCase:
    """Anula una aplicación de medicamento VALIDADA con justificación obligatoria."""

    def __init__(
        self,
        db: Session,
        medicamento_repo: MedicamentoRepository,
        compensador: CompensadorAnulacion,
        activo_port: ActivoConsultaPort,
        estado_port: EstadoActivoPort,
        notificacion_port: NotificacionMedicamentoPort,
    ) -> None:
        self.db = db
        self.medicamento_repo = medicamento_repo
        self.compensador = compensador
        self.activo_port = activo_port
        self.estado_port = estado_port
        self.notificacion_port = notificacion_port

    def execute(
        self, id_medicamento: int, dto: AnularRegistroDTO, usuario_actual: UsuarioActual
    ) -> Medicamento:
        medicamento = self.medicamento_repo.obtener_por_id(id_medicamento)
        if medicamento is None:
            raise NotFoundError(
                code="MEDICAMENTO_NO_ENCONTRADO",
                message=f"El registro de aplicación de medicamento con ID {id_medicamento} no existe.",
            )

        if medicamento.estado_registro == EstadoRegistro.ANULADO.value:
            fecha = medicamento.fecha_hora_anulacion.isoformat() if medicamento.fecha_hora_anulacion else "-"
            raise ConflictError(
                code="MEDICAMENTO_YA_ANULADO",
                message=(
                    f"El registro de aplicación {id_medicamento} ya se encuentra en estado ANULADO desde "
                    f"el {fecha}. No es posible anular un registro que ya fue anulado previamente."
                ),
            )

        justificacion = JustificacionAnulacion(dto.justificacion_anulacion, MENSAJE_RF76)
        ledger = self.compensador.validar("MEDICAMENTO", id_medicamento)
        hoy = hoy_usuario()
        sostenia_retiro = medicamento.fecha_fin_retiro is not None and medicamento.fecha_fin_retiro > hoy
        medicamento.anular(justificacion.valor, datetime.now(timezone.utc))

        fin_retiro = False
        try:
            anulado = self.medicamento_repo.anular(medicamento)
            if ledger is not None:
                self.compensador.compensar(
                    ledger,
                    f"Anulación del medicamento {id_medicamento} (RF-76): {justificacion.valor}",
                    usuario_actual.id_usuario,
                )
            if sostenia_retiro:
                fin_retiro = self._levantar_retiro_si_no_queda_otro(medicamento.id_activo_biologico, hoy, usuario_actual)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if fin_retiro:
            self.notificacion_port.notificar_fin_retiro(medicamento.id_activo_biologico, hoy)
        return anulado

    def _levantar_retiro_si_no_queda_otro(self, id_activo: int, hoy, usuario_actual: UsuarioActual) -> bool:
        restante = self.medicamento_repo.max_fecha_fin_retiro_vigente(id_activo)
        if restante is not None and restante > hoy:
            return False
        activo = self.activo_port.obtener(id_activo)
        if activo is None or activo.id_estado != ESTADO_EN_TRATAMIENTO:
            return False
        self.estado_port.revertir_a_activo(id_activo, usuario_actual.id_usuario, _MOTIVO_FIN_RETIRO)
        return True
