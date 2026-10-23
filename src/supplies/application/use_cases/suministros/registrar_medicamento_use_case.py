# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-76: mensajes y E11 del RF, ledger      |
"""Caso de uso: registrar una aplicación de medicamento (RF-76).

Valida estado del activo, ciclo abierto, vía de administración, evento
sanitario asociado y cálculos POBLACIONAL. Persiste el registro y, si hay
período de retiro, invoca RF-44 (vía puerto) para poner el activo
EN_TRATAMIENTO dentro de la misma transacción. El costo total lo calcula un
trigger; otro lo lleva al ledger de RF-78, y aquí se emiten sus efectos
(RF-80 y evento INCREMENTAL de RF-79).

Códigos (RF-76): E1 estado no permitido → 422; E2 fecha futura → 400; E3 fecha
anterior al inicio del ciclo → 400; E4/E6 → 400 (DTO); E7 sin ciclo → 422; E10
fallo al cambiar el estado → 500 con rollback; E11 activo ya EN_TRATAMIENTO →
se registra y responde 200 con los tratamientos activos; E12 evento sanitario
inválido → 422; E13 duplicado → 409.

Tras el commit, si hay período de retiro, notifica al Productor/Veterinario
(paso 9) de forma best-effort.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, InfrastructureError, NotFoundError, ValidationError
from src.shared.fechas import hoy_colombia
from src.supplies.application.use_cases.costeo_suministros.movimiento_ledger import RegistradorMovimientoLedger
from src.supplies.domain.entities.medicamento import Medicamento
from src.supplies.domain.repositories.activo_consulta_port import (
    ESTADO_ACTIVO,
    ESTADO_EN_TRATAMIENTO,
    ActivoConsultaPort,
)
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.estado_activo_port import EstadoActivoPort
from src.supplies.domain.repositories.evento_sanitario_consulta_port import EventoSanitarioConsultaPort
from src.supplies.domain.repositories.medicamento_repository import MedicamentoRepository
from src.supplies.domain.repositories.notificacion_medicamento_port import NotificacionMedicamentoPort
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.domain.repositories.rol_usuario_port import RolUsuarioPort
from src.supplies.domain.value_objects.via_aplicacion import ViaAplicacion
from src.supplies.infrastructure.dto.registrar_medicamento_dto import RegistrarMedicamentoDTO

_CUATRO_DECIMALES = Decimal("0.0001")
# E1 pide ACTIVO; E11 permite además registrar sobre un activo EN_TRATAMIENTO.
_ESTADOS_PERMITIDOS = {ESTADO_ACTIVO, ESTADO_EN_TRATAMIENTO}


@dataclass
class ResultadoRegistroMedicamento:
    """Resultado del registro: la aplicación persistida y el retiro vigente del activo."""

    medicamento: Medicamento
    fecha_fin_retiro_vigente: Optional[date]
    activo_ya_en_tratamiento: bool = False
    tratamientos_activos: int = 0

    @property
    def mensaje(self) -> Optional[str]:
        """Mensaje de RF-76 E11; ``None`` en el registro normal."""
        if not self.activo_ya_en_tratamiento:
            return None
        hasta = self.fecha_fin_retiro_vigente.isoformat() if self.fecha_fin_retiro_vigente else "-"
        return (
            f"El medicamento fue registrado correctamente. El activo {self.medicamento.id_activo_biologico} "
            f"tiene {self.tratamientos_activos} tratamientos activos. El período de retiro vigente se "
            f"extiende hasta {hasta}."
        )


class RegistrarMedicamentoUseCase:
    """Registra una aplicación de medicamento e invoca RF-44 si hay período de retiro."""

    def __init__(
        self,
        db: Session,
        medicamento_repo: MedicamentoRepository,
        activo_port: ActivoConsultaPort,
        ciclo_port: CicloAbiertoPort,
        evento_port: EventoSanitarioConsultaPort,
        estado_port: EstadoActivoPort,
        notificacion_port: NotificacionMedicamentoPort,
        rol_port: RolUsuarioPort,
        registro_repo: RegistroSuministroRepository,
        movimiento: RegistradorMovimientoLedger,
    ) -> None:
        self.db = db
        self.medicamento_repo = medicamento_repo
        self.activo_port = activo_port
        self.ciclo_port = ciclo_port
        self.evento_port = evento_port
        self.estado_port = estado_port
        self.notificacion_port = notificacion_port
        self.rol_port = rol_port
        self.registro_repo = registro_repo
        self.movimiento = movimiento

    def execute(
        self, dto: RegistrarMedicamentoDTO, usuario_actual: UsuarioActual
    ) -> ResultadoRegistroMedicamento:
        activo = self.activo_port.obtener(dto.id_activo_biologico)
        if activo is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico con ID {dto.id_activo_biologico} no existe.",
                field="id_activo_biologico",
            )

        if activo.id_estado not in _ESTADOS_PERMITIDOS:
            raise BusinessRuleError(
                code="ACTIVO_ESTADO_INVALIDO",
                message=(
                    "No es posible registrar una aplicación de medicamento para el activo "
                    f"{activo.id_activo_biologico} porque su estado actual es {activo.nombre_estado}. Solo se "
                    "permite el registro sobre activos en estado ACTIVO."
                ),
                field="id_activo_biologico",
            )

        ciclo = self.ciclo_port.obtener_abierto(dto.id_activo_biologico)
        if ciclo is None:
            raise BusinessRuleError(
                code="CICLO_NO_ABIERTO",
                message=(
                    f"El activo {activo.id_activo_biologico} no tiene un ciclo productivo activo. No es posible "
                    "registrar tratamientos sobre un activo sin ciclo abierto. Inicie el ciclo productivo antes "
                    "de continuar."
                ),
                field="id_activo_biologico",
            )

        hoy = hoy_colombia()
        if dto.fecha_aplicacion > hoy:
            raise ValidationError(
                code="FECHA_FUTURA",
                message=(
                    f"La fecha de aplicación {dto.fecha_aplicacion.isoformat()} es posterior a la fecha actual "
                    f"del sistema ({hoy.isoformat()}). No se permiten registros con fechas futuras."
                ),
                field="fecha_aplicacion",
            )
        if activo.fecha_inicio_ciclo is not None and dto.fecha_aplicacion < activo.fecha_inicio_ciclo:
            raise ValidationError(
                code="FECHA_ANTERIOR_A_CICLO",
                message=(
                    f"La fecha de aplicación {dto.fecha_aplicacion.isoformat()} es anterior a la fecha de inicio "
                    f"del ciclo productivo del activo ({activo.fecha_inicio_ciclo.isoformat()}). No es posible "
                    "registrar tratamientos fuera del ciclo vigente."
                ),
                field="fecha_aplicacion",
            )

        via = ViaAplicacion(dto.via_administracion)

        if dto.id_evento_sanitario is not None:
            dueno = self.evento_port.obtener_activo_de_evento(dto.id_evento_sanitario)
            if dueno is None or dueno != dto.id_activo_biologico:
                raise BusinessRuleError(
                    code="EVENTO_SANITARIO_INVALIDO",
                    message=(
                        f"El evento sanitario {dto.id_evento_sanitario} no existe o no está asociado al activo "
                        f"{dto.id_activo_biologico}. Verifique el identificador del evento sanitario antes de "
                        "continuar."
                    ),
                    field="id_evento_sanitario",
                )

        dosis_por_individuo: Optional[Decimal] = None
        if activo.es_poblacional:
            if not activo.cantidad_actual or activo.cantidad_actual <= 0:
                raise BusinessRuleError(
                    code="POBLACIONAL_SIN_CANTIDAD",
                    message=(
                        f"No es posible registrar el medicamento para el activo {activo.id_activo_biologico} "
                        "porque su cantidad actual de individuos es cero o no está definida."
                    ),
                    field="id_activo_biologico",
                )
            dosis_por_individuo = (
                dto.dosis_aplicada / Decimal(activo.cantidad_actual)
            ).quantize(_CUATRO_DECIMALES)

        fecha_fin_retiro: Optional[date] = None
        if dto.periodo_retiro_dias and dto.periodo_retiro_dias > 0:
            fecha_fin_retiro = dto.fecha_aplicacion + timedelta(days=dto.periodo_retiro_dias)

        if self.medicamento_repo.existe_duplicado_validado(
            id_activo_biologico=dto.id_activo_biologico,
            nombre_medicamento=dto.nombre_medicamento,
            fecha_aplicacion=dto.fecha_aplicacion,
            hora_aplicacion=dto.hora_aplicacion,
        ):
            momento = f"{dto.fecha_aplicacion.isoformat()} {dto.hora_aplicacion.strftime('%H:%M')}"
            raise ConflictError(
                code="MEDICAMENTO_DUPLICADO",
                message=(
                    f"Ya existe un registro de {dto.nombre_medicamento} para el activo {dto.id_activo_biologico} "
                    f"el {dto.fecha_aplicacion.isoformat()} a las {dto.hora_aplicacion.strftime('%H:%M')}. No se "
                    "permiten registros duplicados. Si se trata de una dosis subsecuente, registre una nueva "
                    f"aplicación con fecha y hora posteriores al {momento}."
                ),
            )

        id_usuario_veterinario = (
            usuario_actual.id_usuario if self.rol_port.es_veterinario(usuario_actual.id_usuario) else None
        )
        ya_en_tratamiento = activo.id_estado == ESTADO_EN_TRATAMIENTO

        medicamento = Medicamento.crear(
            id_activo_biologico=dto.id_activo_biologico,
            nombre_medicamento=dto.nombre_medicamento,
            descripcion_clinica=dto.motivo_aplicacion,
            unidad_dosis=dto.unidad_dosis,
            cantidad=dto.dosis_aplicada,
            fecha_aplicacion=dto.fecha_aplicacion,
            costo_unitario_medicamento=dto.costo_unitario,
            motivo_aplicacion=dto.motivo_aplicacion,
            nombre_veterinario=dto.nombre_veterinario,
            id_usuario=usuario_actual.id_usuario,
            via_aplicacion=via.codigo_bd,
            hora_aplicacion=dto.hora_aplicacion,
            periodo_retiro_dias=dto.periodo_retiro_dias,
            fecha_fin_retiro=fecha_fin_retiro,
            dosis_por_individuo=dosis_por_individuo,
            id_evento_sanitario=dto.id_evento_sanitario,
            id_usuario_veterinario=id_usuario_veterinario,
            lote_medicameto=dto.lote,
            fehca_vencimietno_lote=dto.fecha_vencimiento_lote,
            observaciones=dto.observaciones,
        )

        try:
            guardado = self.medicamento_repo.guardar(medicamento)
            ledger = self.registro_repo.obtener_por_origen("MEDICAMENTO", guardado.id_registro_medicamento)
            if ledger is not None:
                self.movimiento.registrar(ledger, id_usuario=usuario_actual.id_usuario, precio_manual=False)
            if fecha_fin_retiro is not None:
                self._marcar_en_tratamiento(dto, usuario_actual)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        vigente = self.medicamento_repo.max_fecha_fin_retiro_vigente(dto.id_activo_biologico)
        activos = self.medicamento_repo.contar_tratamientos_activos(dto.id_activo_biologico, hoy)

        if fecha_fin_retiro is not None:
            self.notificacion_port.notificar_inicio_retiro(
                id_activo=dto.id_activo_biologico,
                id_usuario_veterinario=id_usuario_veterinario,
                nombre_medicamento=dto.nombre_medicamento,
                fecha_fin_retiro=fecha_fin_retiro,
            )

        return ResultadoRegistroMedicamento(
            medicamento=guardado,
            fecha_fin_retiro_vigente=vigente,
            activo_ya_en_tratamiento=ya_en_tratamiento,
            tratamientos_activos=activos,
        )

    def _marcar_en_tratamiento(self, dto: RegistrarMedicamentoDTO, usuario_actual: UsuarioActual) -> None:
        """Invoca RF-44. Si el cambio de estado falla, E10: 500 y se revierte todo."""
        try:
            self.estado_port.marcar_en_tratamiento(
                id_activo=dto.id_activo_biologico,
                id_usuario=usuario_actual.id_usuario,
                motivo=f"Inicio de período de retiro por aplicación de '{dto.nombre_medicamento}' (RF-76).",
            )
        except Exception as exc:
            raise InfrastructureError(
                code="ERROR_ESTADO_EN_TRATAMIENTO",
                message=(
                    "El medicamento fue registrado correctamente, pero ocurrió un error al actualizar el estado "
                    "del activo a EN_TRATAMIENTO. El sistema ha revertido la operación completa. Intente nuevamente."
                ),
                original_error=exc,
            ) from exc
