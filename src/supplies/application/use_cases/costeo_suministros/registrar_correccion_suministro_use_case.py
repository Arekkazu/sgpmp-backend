"""Caso de uso: corregir un registro de suministro existente (RF-78, tipo_operacion=CORRECCION).

A diferencia del registro directo (que delega la concurrencia al lock de fila
nativo de ``INSERT ... ON CONFLICT DO UPDATE``, ver Gap 6 de
``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``), aquí la app sí necesita
leer el acumulado **antes** de decidir si la corrección es válida (FA-09: no
puede dejarlo negativo) — por eso usa ``SELECT ... FOR UPDATE`` con
``lock_timeout`` explícito. Un ``LockNotAvailable``/``DeadlockDetected`` bajo
contención real se clasifica como ``CONFLICTO_CONCURRENCIA`` (FA-08); otro
fallo técnico se trata como ``REGISTRO_FALLIDO`` genérico (E5).

Acepta ``id_registro_original`` de cualquier tipo de suministro (ALIMENTO,
MEDICAMENTO, SERVICIO_VETERINARIO, INSEMINACION) — es también la mitigación
documentada (Gap 10) para reflejar manualmente una anulación de RF-75/76 que
no dispara reversión automática.
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
    NotFoundError,
    ServiceUnavailableError,
)
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
    ) -> None:
        self.db = db
        self.registro_repo = registro_repo
        self.acumulado_repo = acumulado_repo
        self.auditoria_port = auditoria_port

    def execute(
        self,
        id_registro_original: UUID,
        dto: RegistrarCorreccionSuministroDTO,
        usuario_actual: UsuarioActual,
    ) -> ResultadoRegistroDirecto:
        existente = self.registro_repo.existe_idempotente(dto.id_idempotencia)
        if existente is not None:
            return ResultadoRegistroDirecto(registro=existente, ya_procesado=True)

        original = self.registro_repo.obtener_por_id(id_registro_original)
        if original is None:
            raise NotFoundError(
                code="REGISTRO_ORIGINAL_NO_ENCONTRADO",
                message=(
                    f"El registro de suministro {id_registro_original} no existe. Las "
                    "correcciones requieren un id_registro_original válido que referencie el "
                    "registro que se ajusta."
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

        justificacion = JustificacionPrecio(dto.justificacion_precio)
        motivo = MotivoCorreccion(dto.motivo_correccion)
        cantidad = dto.cantidad_corregida.quantize(_ESCALA_CANTIDAD)
        precio = dto.precio_unitario_corregido.quantize(_ESCALA_PRECIO)
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
                # FA-09 — determinístico, no se reintenta (propaga como BusinessRuleError).
                acumulado.validar_correccion_no_negativa(original.costo_registro, costo_nuevo)

                entidad = RegistroSuministroDirecto.crear_correccion(
                    original=original,
                    cantidad_corregida=cantidad,
                    precio_unitario_corregido=precio,
                    motivo_correccion=motivo_correccion,
                    id_idempotencia=dto.id_idempotencia,
                    justificacion_precio=justificacion_precio,
                )
                guardado = self.registro_repo.guardar(entidad)
                self.auditoria_port.registrar(
                    EventoAuditoriaSuministro(
                        entidad_afectada="registro_suministro",
                        tipo_operacion=TipoEventoAuditoriaSuministro.SUMINISTRO_CORREGIDO.value,
                        id_usuario=usuario_actual.id_usuario,
                        resultado=ResultadoAuditoriaSuministro.EXITOSO.value,
                        id_activo_biologico=guardado.id_activo_biologico,
                        id_ciclo_productivo=guardado.id_ciclo_productivo,
                        id_gestion_fases=guardado.id_gestion_fases,
                        costo_afectado=guardado.costo_registro,
                        origen_precio=guardado.origen_precio,
                    )
                )
                self.db.commit()
                return ResultadoRegistroDirecto(registro=guardado, ya_procesado=False)
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
