# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-75: mensajes del RF, CA-10 y ledger    |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""Caso de uso: registrar un consumo de alimento (RF-75).

Orquesta las validaciones de negocio que requieren datos cross-module (estado
del activo, ciclo abierto, catálogo de alimento) y persiste el registro. El
costo total lo calcula un trigger de la BD; otro trigger lleva el costo al
ledger de RF-78, y aquí se emiten sus efectos (RF-80 y evento INCREMENTAL de
RF-79) en la misma transacción.

Códigos (RF-75): E1 activo no ACTIVO → 422; E2 fecha futura → 400; E3 fecha
anterior a la fase activa → 400; E4 cantidad ≤ 0 → 400 (DTO); E7 POBLACIONAL
sin individuos → 422; E8 duplicado → 409. CA-10: el mismo alimento solo se
acepta con fecha/hora posteriores al último registro VALIDADO (409).
"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from src.shared.fechas import fecha_usuario, hoy_usuario
from src.supplies.application.use_cases.costeo_suministros.movimiento_ledger import RegistradorMovimientoLedger
from src.supplies.domain.entities.consumo_alimento import ConsumoAlimento
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.consumo_alimento_repository import ConsumoAlimentoRepository
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.infrastructure.dto.registrar_consumo_alimento_dto import RegistrarConsumoAlimentoDTO

_CUATRO_DECIMALES = Decimal("0.0001")
_MEDIANOCHE = time(0, 0)


def _hora(valor: Optional[time]) -> str:
    return valor.strftime("%H:%M") if valor else "00:00"


class RegistrarConsumoAlimentoUseCase:
    """Registra un consumo de alimento sobre un activo con ciclo abierto (RF-75)."""

    def __init__(
        self,
        db: Session,
        consumo_repo: ConsumoAlimentoRepository,
        activo_port: ActivoConsultaPort,
        ciclo_port: CicloAbiertoPort,
        registro_repo: RegistroSuministroRepository,
        movimiento: RegistradorMovimientoLedger,
    ) -> None:
        self.db = db
        self.consumo_repo = consumo_repo
        self.activo_port = activo_port
        self.ciclo_port = ciclo_port
        self.registro_repo = registro_repo
        self.movimiento = movimiento

    def execute(self, dto: RegistrarConsumoAlimentoDTO, usuario_actual: UsuarioActual) -> ConsumoAlimento:
        activo = self.activo_port.obtener(dto.id_activo_biologico)
        if activo is None:
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico con ID {dto.id_activo_biologico} no existe.",
                field="id_activo_biologico",
            )

        if not activo.esta_activo:
            raise BusinessRuleError(
                code="ACTIVO_ESTADO_INVALIDO",
                message=(
                    f"No es posible registrar consumo de alimento para el activo {activo.id_activo_biologico} "
                    f"porque su estado actual es {activo.nombre_estado}. Solo se permite el registro sobre "
                    "activos en estado ACTIVO."
                ),
                field="id_activo_biologico",
            )

        ciclo = self.ciclo_port.obtener_abierto(dto.id_activo_biologico)
        if ciclo is None:
            raise BusinessRuleError(
                code="CICLO_NO_ABIERTO",
                message=(
                    f"El activo {activo.id_activo_biologico} no tiene un ciclo productivo activo. No es posible "
                    "registrar consumo sobre un activo sin ciclo abierto. Inicie el ciclo productivo antes de continuar."
                ),
                field="id_activo_biologico",
            )

        tipo = self.consumo_repo.obtener_tipo_alimento(dto.id_tipo_alimento)
        if tipo is None:
            raise BusinessRuleError(
                code="TIPO_ALIMENTO_NO_ENCONTRADO",
                message=f"El tipo de alimento con ID {dto.id_tipo_alimento} no existe en el catálogo.",
                field="id_tipo_alimento",
            )
        if not tipo.esta_activo:
            raise BusinessRuleError(
                code="TIPO_ALIMENTO_INACTIVO",
                message=(
                    f"El tipo de alimento con ID {dto.id_tipo_alimento} no está en estado ACTIVO "
                    "y no puede usarse para nuevos registros de consumo."
                ),
                field="id_tipo_alimento",
            )

        if dto.fecha_consumo > hoy_usuario():
            raise ValidationError(
                code="FECHA_FUTURA",
                message=(
                    f"La fecha de consumo {dto.fecha_consumo.isoformat()} es posterior a la fecha actual del "
                    "sistema. No se permiten registros de consumo con fechas futuras."
                ),
                field="fecha_consumo",
            )

        cota_inferior = self._cota_inferior(ciclo.fecha_inicio, activo.fecha_inicio_ciclo)
        if cota_inferior is not None and dto.fecha_consumo < cota_inferior:
            raise ValidationError(
                code="FECHA_ANTERIOR_A_FASE",
                message=(
                    f"La fecha de consumo {dto.fecha_consumo.isoformat()} es anterior a la fecha de inicio de "
                    f"la fase productiva activa del activo ({cota_inferior.isoformat()}). Verifique la fecha ingresada."
                ),
                field="fecha_consumo",
            )

        consumo_por_individuo: Optional[Decimal] = None
        if activo.es_poblacional:
            if not activo.cantidad_actual or activo.cantidad_actual <= 0:
                raise BusinessRuleError(
                    code="POBLACIONAL_SIN_CANTIDAD",
                    message=(
                        f"No es posible registrar el consumo para el activo {activo.id_activo_biologico} porque "
                        "su cantidad actual de individuos es cero o no está definida. Verifique el estado del "
                        "POBLACIONAL en RF-36 antes de registrar el consumo."
                    ),
                    field="id_activo_biologico",
                )
            consumo_por_individuo = (
                dto.cantidad_alimento / Decimal(activo.cantidad_actual)
            ).quantize(_CUATRO_DECIMALES)

        self._validar_no_duplicado(dto, tipo.nombre)

        consumo = ConsumoAlimento.crear(
            id_activo_biologico=dto.id_activo_biologico,
            id_tipo_alimento=tipo.id_tipo_elemento,
            tipo_alimento=tipo.nombre,
            tipo_unidad=tipo.unidad_medida,
            cantidad_suministrada=dto.cantidad_alimento,
            fecha_consumo=dto.fecha_consumo,
            id_usuario=usuario_actual.id_usuario,
            hora_suministro=dto.hora_suministro,
            costo_unitario=dto.costo_unitario,
            consumo_por_individuo_kg=consumo_por_individuo,
            observacion=dto.observaciones,
        )

        try:
            guardado = self.consumo_repo.guardar(consumo)
            ledger = self.registro_repo.obtener_por_origen("ALIMENTO", guardado.id_consumo_alimeto)
            if ledger is not None:
                self.movimiento.registrar(ledger, id_usuario=usuario_actual.id_usuario, precio_manual=False)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return guardado

    def _validar_no_duplicado(self, dto: RegistrarConsumoAlimentoDTO, tipo_alimento: str) -> None:
        """E8 (mismo activo, fecha, hora y alimento) y CA-10 (solo suministros posteriores)."""
        ultimo = self.consumo_repo.ultimo_validado(
            id_activo_biologico=dto.id_activo_biologico, tipo_alimento=tipo_alimento
        )
        if ultimo is None:
            return
        nuevo = (dto.fecha_consumo, dto.hora_suministro or _MEDIANOCHE)
        if nuevo > (ultimo[0], ultimo[1] or _MEDIANOCHE):
            return
        duplicado = self.consumo_repo.existe_duplicado_validado(
            id_activo_biologico=dto.id_activo_biologico,
            fecha_consumo=dto.fecha_consumo,
            hora_suministro=dto.hora_suministro,
            tipo_alimento=tipo_alimento,
        )
        fecha, hora = (dto.fecha_consumo, dto.hora_suministro) if duplicado else ultimo
        raise ConflictError(
            code="CONSUMO_DUPLICADO",
            message=(
                f"Ya existe un registro de {tipo_alimento} para el activo {dto.id_activo_biologico} el "
                f"{fecha.isoformat()} a las {_hora(hora)}. No se permiten registros duplicados. Si se trata "
                "de un suministro subsecuente, registre una nueva entrada con fecha u hora posteriores a "
                f"{ultimo[0].isoformat()} {_hora(ultimo[1])}."
            ),
        )

    @staticmethod
    def _cota_inferior(fecha_fase: Optional[datetime], fecha_inicio_ciclo: Optional[date]) -> Optional[date]:
        if fecha_fase is not None:
            return fecha_usuario(fecha_fase)
        return fecha_inicio_ciclo
