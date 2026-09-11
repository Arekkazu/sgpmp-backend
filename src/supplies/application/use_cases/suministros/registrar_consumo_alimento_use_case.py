"""Caso de uso: registrar un consumo de alimento (RF-75).

Orquesta las validaciones de negocio que requieren datos cross-module (estado
del activo, ciclo abierto, catálogo de alimento) y persiste el registro. El
costo total y la auditoría los gestionan triggers de la BD.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from src.supplies.domain.entities.consumo_alimento import ConsumoAlimento
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.consumo_alimento_repository import ConsumoAlimentoRepository
from src.supplies.infrastructure.dto.registrar_consumo_alimento_dto import RegistrarConsumoAlimentoDTO

_CUATRO_DECIMALES = Decimal("0.0001")


class RegistrarConsumoAlimentoUseCase:
    """Registra un consumo de alimento sobre un activo con ciclo abierto (RF-75)."""

    def __init__(
        self,
        db: Session,
        consumo_repo: ConsumoAlimentoRepository,
        activo_port: ActivoConsultaPort,
        ciclo_port: CicloAbiertoPort,
    ) -> None:
        self.db = db
        self.consumo_repo = consumo_repo
        self.activo_port = activo_port
        self.ciclo_port = ciclo_port

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
                    f"No es posible registrar consumo para el activo {activo.id_activo_biologico} "
                    f"porque su estado actual es {activo.nombre_estado}. Solo se permite el "
                    "registro sobre activos en estado ACTIVO."
                ),
                field="id_activo_biologico",
            )

        ciclo = self.ciclo_port.obtener_abierto(dto.id_activo_biologico)
        if ciclo is None:
            raise BusinessRuleError(
                code="CICLO_NO_ABIERTO",
                message=(
                    f"El activo {activo.id_activo_biologico} no tiene un ciclo productivo abierto. "
                    "No es posible registrar consumo sin un ciclo abierto."
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

        hoy = datetime.now(timezone.utc).date()
        if dto.fecha_consumo > hoy:
            raise ValidationError(
                code="FECHA_FUTURA",
                message=(
                    f"La fecha de consumo {dto.fecha_consumo.isoformat()} es posterior a la fecha "
                    "actual del sistema. No se permiten registros con fechas futuras."
                ),
                field="fecha_consumo",
            )

        cota_inferior = self._cota_inferior(ciclo.fecha_inicio, activo.fecha_inicio_ciclo)
        if cota_inferior is not None and dto.fecha_consumo < cota_inferior:
            raise ValidationError(
                code="FECHA_ANTERIOR_A_FASE",
                message=(
                    f"La fecha de consumo {dto.fecha_consumo.isoformat()} es anterior al inicio de "
                    f"la fase productiva activa del activo ({cota_inferior.isoformat()})."
                ),
                field="fecha_consumo",
            )

        consumo_por_individuo: Optional[Decimal] = None
        if activo.es_poblacional:
            if not activo.cantidad_actual or activo.cantidad_actual <= 0:
                raise BusinessRuleError(
                    code="POBLACIONAL_SIN_CANTIDAD",
                    message=(
                        f"No es posible registrar el consumo para el activo {activo.id_activo_biologico} "
                        "porque su cantidad actual de individuos es cero o no está definida."
                    ),
                    field="id_activo_biologico",
                )
            consumo_por_individuo = (
                dto.cantidad_alimento / Decimal(activo.cantidad_actual)
            ).quantize(_CUATRO_DECIMALES)

        if self.consumo_repo.existe_duplicado_validado(
            id_activo_biologico=dto.id_activo_biologico,
            fecha_consumo=dto.fecha_consumo,
            hora_suministro=dto.hora_suministro,
            tipo_alimento=tipo.nombre,
        ):
            raise ConflictError(
                code="CONSUMO_DUPLICADO",
                message=(
                    f"Ya existe un registro de {tipo.nombre} para el activo {dto.id_activo_biologico} "
                    f"el {dto.fecha_consumo.isoformat()}"
                    + (f" a las {dto.hora_suministro.isoformat()}" if dto.hora_suministro else "")
                    + ". No se permiten registros duplicados."
                ),
            )

        consumo = ConsumoAlimento.crear(
            id_activo_biologico=dto.id_activo_biologico,
            id_tipo_alimento=tipo.id_tipo_elemento,
            tipo_alimento=tipo.nombre,
            tipo_unidad=tipo.unidad_medida,
            cantidad_suministrada=dto.cantidad_alimento,
            fecha_consumo=dto.fecha_consumo,
            id_usuario=usuario_actual.id_usuario,
            hora_suministro=dto.hora_suministro,
            costo_unitario=tipo.costo_unitario,
            consumo_por_individuo_kg=consumo_por_individuo,
            observacion=dto.observaciones,
        )

        try:
            guardado = self.consumo_repo.guardar(consumo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return guardado

    @staticmethod
    def _cota_inferior(fecha_fase: Optional[datetime], fecha_inicio_ciclo: Optional[date]) -> Optional[date]:
        if fecha_fase is not None:
            return fecha_fase.date()
        return fecha_inicio_ciclo
