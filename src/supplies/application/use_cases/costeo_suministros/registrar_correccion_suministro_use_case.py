# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78: corrección aditiva y códigos del RF |
"""Caso de uso: corregir un registro de suministro existente (RF-78, tipo_operacion=CORRECCION).

A diferencia del registro directo (que delega la concurrencia al lock de fila
nativo de ``INSERT ... ON CONFLICT DO UPDATE``, ver Gap 6 de
``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``), aquí la app sí necesita
leer el acumulado **antes** de decidir si la corrección es válida (FA-09: no
puede dejarlo negativo) — por eso usa ``SELECT ... FOR UPDATE`` con
``lock_timeout`` explícito. Un ``LockNotAvailable``/``DeadlockDetected`` bajo
contención real se clasifica como ``CONFLICTO_CONCURRENCIA`` (FA-08); otro
fallo técnico se trata como ``REGISTRO_FALLIDO`` genérico (E5).

La corrección es un ajuste que SUMA al acumulado (R12, CA-8), negativo si
compensa (RNF-09); el acumulado resultante no puede quedar negativo (422).
Códigos: E7 original inexistente → 422; ciclo cerrado → 409 (R2, el monto
consolidado es inmutable); E2 sin justificación de precio → 422; E8
idempotencia → 200. Acepta ``id_registro_original`` de cualquier tipo de
suministro (ALIMENTO, MEDICAMENTO, SERVICIO_VETERINARIO, INSEMINACION).
"""
from __future__ import annotations

import time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from psycopg2 import errors as pg_errors
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import (
    AppError,
    BusinessRuleError,
    ConflictError,
    InfrastructureError,
    ServiceUnavailableError,
)
from src.supplies.application.use_cases.costeo_suministros.movimiento_ledger import RegistradorMovimientoLedger
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto
from src.supplies.domain.repositories.acumulado_ciclo_repository import AcumuladoCicloRepository
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import (
    ResultadoAuditoriaSuministro,
    TipoEventoAuditoriaSuministro,
)
from src.supplies.domain.value_objects.justificacion_precio import JustificacionPrecio
from src.supplies.domain.value_objects.motivo_correccion import MotivoCorreccion
from src.supplies.application.use_cases.costeo_suministros.registrar_suministro_directo_use_case import (
    ResultadoRegistroDirecto,
)
from src.supplies.infrastructure.dto.registrar_correccion_suministro_dto import (
    RegistrarCorreccionSuministroDTO,
)

_MAX_REINTENTOS = 3
_BACKOFF_SEGUNDOS = (1, 3, 5)
_ESCALA_CANTIDAD = Decimal("0.0001")
_ESCALA_PRECIO = Decimal("0.01")
_ERRORES_CONCURRENCIA = (pg_errors.LockNotAvailable, pg_errors.DeadlockDetected)
# Errores transitorios de infraestructura que justifican reintentar. Desde
# INC-M01-06-024 un fallo de conectividad sale como ServiceUnavailableError en
# vez de InfrastructureError, así que el reintento tiene que cubrir ambos.
_ERRORES_REINTENTABLES = (InfrastructureError, ServiceUnavailableError)


class RegistrarCorreccionSuministroUseCase:
    """Registra una corrección (ajuste) de un suministro ya persistido."""

    def __init__(
        self,
        db: Session,
        registro_repo: RegistroSuministroRepository,
        acumulado_repo: AcumuladoCicloRepository,
        auditoria_port: AuditoriaSuministroPort,
        ciclo_port: CicloAbiertoPort,
        movimiento: RegistradorMovimientoLedger,
    ) -> None:
        self.db = db
        self.registro_repo = registro_repo
        self.acumulado_repo = acumulado_repo
        self.auditoria_port = auditoria_port
        self.ciclo_port = ciclo_port
        self.movimiento = movimiento

    def execute(
        self,
        id_registro_original: UUID,
        dto: RegistrarCorreccionSuministroDTO,
        usuario_actual: UsuarioActual,
    ) -> ResultadoRegistroDirecto:
        existente = self.registro_repo.existe_idempotente(dto.id_idempotencia)
        if existente is not None:
            return ResultadoRegistroDirecto(registro=existente, estado="YA_PROCESADO")

        original = self.registro_repo.obtener_por_id(id_registro_original)
        if original is None:
            raise BusinessRuleError(
                code="REGISTRO_ORIGINAL_INVALIDO",
                message=(
                    "Las correcciones requieren id_registro_original válido que referencie el registro que se "
                    f"ajusta. El registro {id_registro_original} no existe."
                ),
                field="id_registro_original",
            )
        if original.tipo_operacion != "REGISTRO":
            raise BusinessRuleError(
                code="CORRECCION_SOBRE_CORRECCION",
                message=(
                    f"El registro {id_registro_original} ya es una corrección; no se puede "
                    "corregir una corrección. Referencie el registro original."
                ),
                field="id_registro_original",
            )

        fase = self.ciclo_port.obtener_por_id(original.id_gestion_fases) if original.id_gestion_fases else None
        if fase is None or not fase.es_activa:
            raise ConflictError(
                code="CICLO_NO_ACTIVO",
                message=(
                    f"No existe un ciclo productivo activo para el activo {original.id_activo_biologico}. "
                    "Verifique el estado del ciclo en M02 antes de registrar suministros."
                ),
            )

        cantidad = dto.cantidad.quantize(_ESCALA_CANTIDAD)
        precio = dto.precio_unitario.quantize(_ESCALA_PRECIO)
        if cantidad <= 0 or precio == 0:
            raise BusinessRuleError(
                code="CORRECCION_INVALIDA",
                message=(
                    "La corrección requiere cantidad mayor a cero y un precio unitario distinto de cero "
                    "(negativo si el ajuste compensa costo)."
                ),
            )
        justificacion = JustificacionPrecio(dto.justificacion_precio)
        motivo = MotivoCorreccion(dto.motivo_correccion)
        costo_nuevo = cantidad * precio

        return self._persistir_con_reintentos(
            original, cantidad, precio, costo_nuevo, motivo.valor, justificacion.valor, dto, usuario_actual
        )

    def _persistir_con_reintentos(
        self,
        original: RegistroSuministroDirecto,
        cantidad: Decimal,
        precio: Decimal,
        costo_nuevo: Decimal,
        motivo_correccion: str,
        justificacion_precio: str,
        dto: RegistrarCorreccionSuministroDTO,
        usuario_actual: UsuarioActual,
    ) -> ResultadoRegistroDirecto:
        ultimo_error: Optional[AppError] = None
        for intento in range(1, _MAX_REINTENTOS + 1):
            try:
                acumulado = self.acumulado_repo.obtener_bloqueando(original.id_gestion_fases)
                if acumulado is None:
                    raise InfrastructureError(
                        code="ACUMULADO_INEXISTENTE",
                        message="El acumulado del ciclo del registro original no existe.",
                    )
                # R12 — determinístico, no se reintenta (propaga como BusinessRuleError).
                acumulado.validar_correccion_no_negativa(costo_nuevo)

                entidad = RegistroSuministroDirecto.crear_correccion(
                    original=original,
                    cantidad_corregida=cantidad,
                    precio_unitario_corregido=precio,
                    motivo_correccion=motivo_correccion,
                    id_idempotencia=dto.id_idempotencia,
                    justificacion_precio=justificacion_precio,
                )
                guardado = self.registro_repo.guardar(entidad)
                self.movimiento.registrar(guardado, id_usuario=usuario_actual.id_usuario, precio_manual=True)
                self.db.commit()
                return ResultadoRegistroDirecto(registro=guardado)
            except _ERRORES_REINTENTABLES as exc:
                self.db.rollback()
                ultimo_error = exc
                if intento < _MAX_REINTENTOS:
                    time.sleep(_BACKOFF_SEGUNDOS[intento - 1])
                    continue
                if self._es_conflicto_concurrencia(exc):
                    self._registrar_evento(
                        original, usuario_actual, TipoEventoAuditoriaSuministro.CONFLICTO_CONCURRENCIA, str(exc.message)
                    )
                    raise ConflictError(
                        code="CONFLICTO_CONCURRENCIA",
                        message=(
                            "No fue posible aplicar la corrección por conflicto de concurrencia en "
                            "el acumulado del ciclo tras agotar los reintentos. Intente nuevamente."
                        ),
                    ) from exc
                self._registrar_evento(
                    original, usuario_actual, TipoEventoAuditoriaSuministro.REGISTRO_FALLIDO, str(exc.message)
                )
                raise
            except AppError:
                self.db.rollback()
                raise
        raise ultimo_error  # pragma: no cover — inalcanzable, el loop siempre retorna o lanza

    @staticmethod
    def _es_conflicto_concurrencia(exc: AppError) -> bool:
        original = getattr(exc, "original_error", None)
        orig = getattr(original, "orig", None)
        return isinstance(orig, _ERRORES_CONCURRENCIA)

    def _registrar_evento(
        self,
        original: RegistroSuministroDirecto,
        usuario_actual: UsuarioActual,
        tipo_evento: TipoEventoAuditoriaSuministro,
        causa: str,
    ) -> None:
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="registro_suministro",
                    tipo_operacion=tipo_evento.value,
                    id_usuario=usuario_actual.id_usuario,
                    resultado=ResultadoAuditoriaSuministro.FALLIDO.value,
                    id_activo_biologico=original.id_activo_biologico,
                    id_ciclo_productivo=original.id_ciclo_productivo,
                    id_gestion_fases=original.id_gestion_fases,
                    detalle_causa=causa,
                    numero_reintentos=_MAX_REINTENTOS,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
