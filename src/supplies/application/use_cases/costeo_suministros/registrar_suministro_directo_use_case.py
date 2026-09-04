"""Caso de uso: registrar un suministro directo (SERVICIO_VETERINARIO/INSEMINACION, RF-78).

ALIMENTO y MEDICAMENTO NO pasan por aquí — se acumulan automáticamente desde
RF-75/RF-76 vía los triggers de CU-04 (``fn_trg_poblar_registro_suministro_*``)
más el trigger de acumulación de este CU (``trg_acumular_costo_ciclo``, Gap 6
de ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``). Este flujo es el único
que la app inicia directamente para persistir en ``registro_suministro``.

Orden de validación (RF-78 Fase 1 a 7): idempotencia → ciclo productivo activo
→ fecha dentro de rango → deduplicación por contenido → justificación de
precio (siempre MANUAL — no hay integración M40 en este sistema, mismo
precedente que CU-01) → construir entidad → persistir con reintentos.

La actualización del acumulado la hace el trigger de BD dentro de la misma
transacción (``INSERT ... ON CONFLICT DO UPDATE``, atómico por lock de fila);
no hay conflicto de versión que resolver desde la app en este camino — por
eso el agotamiento de reintentos siempre se clasifica como fallo técnico
genérico (``REGISTRO_FALLIDO``, E5), nunca como ``CONFLICTO_CONCURRENCIA``
(esa clasificación es propia del flujo de corrección, que sí usa
``SELECT ... FOR UPDATE`` desde la app).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import (
    AppError,
    BusinessRuleError,
    ConflictError,
    InfrastructureError,
    ServiceUnavailableError,
    ValidationError,
)
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.domain.services.politica_naturaleza_costo import resolver_naturaleza_costo
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import (
    ResultadoAuditoriaSuministro,
    TipoEventoAuditoriaSuministro,
)
from src.supplies.domain.value_objects.justificacion_precio import JustificacionPrecio
from src.supplies.infrastructure.dto.registrar_suministro_directo_dto import RegistrarSuministroDirectoDTO

_MAX_REINTENTOS = 3
_BACKOFF_SEGUNDOS = (1, 3, 5)
_ESCALA_CANTIDAD = Decimal("0.0001")
_ESCALA_PRECIO = Decimal("0.01")
# Errores transitorios de infraestructura que justifican reintentar. Desde
# INC-M01-06-024 un fallo de conectividad sale como ServiceUnavailableError en
# vez de InfrastructureError, así que el reintento tiene que cubrir ambos.
_ERRORES_REINTENTABLES = (InfrastructureError, ServiceUnavailableError)


@dataclass(frozen=True)
class ResultadoRegistroDirecto:
    """Envuelve el registro con si ya había sido procesado (E8 — HTTP 200 vs 201)."""

    registro: RegistroSuministroDirecto
    ya_procesado: bool


class RegistrarSuministroDirectoUseCase:
    """Registra un suministro SERVICIO_VETERINARIO/INSEMINACION y actualiza el acumulado del ciclo."""

    def __init__(
        self,
        db: Session,
        registro_repo: RegistroSuministroRepository,
        ciclo_port: CicloAbiertoPort,
        auditoria_port: AuditoriaSuministroPort,
    ) -> None:
        self.db = db
        self.registro_repo = registro_repo
        self.ciclo_port = ciclo_port
        self.auditoria_port = auditoria_port

    def execute(
        self, dto: RegistrarSuministroDirectoDTO, usuario_actual: UsuarioActual
    ) -> ResultadoRegistroDirecto:
        # Fase 3 (RF-78) — idempotencia verificada ANTES que cualquier otra validación (E8).
        existente = self.registro_repo.existe_idempotente(dto.id_idempotencia)
        if existente is not None:
            return ResultadoRegistroDirecto(registro=existente, ya_procesado=True)

        # Fase 1 — ciclo productivo activo (E1).
        ciclo = self.ciclo_port.obtener_abierto(dto.id_activo_biologico)
        if ciclo is None or ciclo.id_gestion_fases is None:
            raise BusinessRuleError(
                code="CICLO_NO_ACTIVO",
                message=(
                    f"No existe un ciclo productivo activo para el activo {dto.id_activo_biologico}. "
                    "Verifique el estado del ciclo en M02 antes de registrar suministros."
                ),
            )

        # Fase 2 — fecha dentro del rango del ciclo (E3).
        self._validar_fecha_aplicacion(dto.fecha_aplicacion, ciclo.fecha_inicio)

        cantidad = dto.cantidad.quantize(_ESCALA_CANTIDAD)
        precio = dto.precio_unitario.quantize(_ESCALA_PRECIO)

        # Fase 4 — deduplicación por contenido (E6).
        if self.registro_repo.existe_duplicado_contenido(
            id_activo_biologico=dto.id_activo_biologico,
            id_ciclo_productivo=ciclo.id_ciclo_productivo,
            tipo_suministro=dto.tipo_suministro,
            fecha_aplicacion=dto.fecha_aplicacion,
            cantidad=cantidad,
            precio_unitario_resuelto=precio,
        ):
            raise ConflictError(
                code="SUMINISTRO_DUPLICADO",
                message=(
                    "Registro de suministro idéntico ya existe. Si es una corrección, use "
                    "tipo_operacion=CORRECCION con id_registro_original."
                ),
            )

        # Fase 5 — resolución de precio: siempre MANUAL, justificación obligatoria (E2).
        justificacion = JustificacionPrecio(dto.justificacion_precio)

        entidad = RegistroSuministroDirecto.crear(
            id_activo_biologico=dto.id_activo_biologico,
            id_ciclo_productivo=ciclo.id_ciclo_productivo,
            id_gestion_fases=ciclo.id_gestion_fases,
            tipo_suministro=dto.tipo_suministro,
            cantidad=cantidad,
            unidad_medida=dto.unidad_medida,
            precio_unitario_resuelto=precio,
            fecha_aplicacion=dto.fecha_aplicacion,
            naturaleza_costo=resolver_naturaleza_costo(dto.tipo_suministro),
            id_idempotencia=dto.id_idempotencia,
            justificacion_precio=justificacion.valor,
            observacion=dto.observacion,
        )

        return self._persistir_con_reintentos(entidad, usuario_actual)

    @staticmethod
    def _validar_fecha_aplicacion(fecha_aplicacion: date, fecha_inicio_ciclo) -> None:
        if fecha_inicio_ciclo is not None and fecha_aplicacion < fecha_inicio_ciclo.date():
            raise ValidationError(
                code="FECHA_FUERA_DE_RANGO",
                message=(
                    f"La fecha {fecha_aplicacion.isoformat()} está fuera del rango del ciclo "
                    f"productivo activo (inicio: {fecha_inicio_ciclo.date().isoformat()})."
                ),
                field="fecha_aplicacion",
            )
        if fecha_aplicacion > date.today():
            raise ValidationError(
                code="FECHA_FUTURA_NO_PERMITIDA",
                message="La fecha de aplicación no puede ser posterior a la fecha actual del servidor.",
                field="fecha_aplicacion",
            )

    def _persistir_con_reintentos(
        self, entidad: RegistroSuministroDirecto, usuario_actual: UsuarioActual
    ) -> ResultadoRegistroDirecto:
        ultimo_error: Optional[AppError] = None
        for intento in range(1, _MAX_REINTENTOS + 1):
            try:
                guardado = self.registro_repo.guardar(entidad)
                self.auditoria_port.registrar(
                    EventoAuditoriaSuministro(
                        entidad_afectada="registro_suministro",
                        tipo_operacion=TipoEventoAuditoriaSuministro.SUMINISTRO_REGISTRADO.value,
                        id_usuario=usuario_actual.id_usuario,
                        resultado=ResultadoAuditoriaSuministro.EXITOSO.value,
                        id_activo_biologico=guardado.id_activo_biologico,
                        id_ciclo_productivo=guardado.id_ciclo_productivo,
                        id_gestion_fases=guardado.id_gestion_fases,
                        costo_afectado=guardado.costo_registro,
                        origen_precio=guardado.origen_precio,
                    )
                )
                self.auditoria_port.registrar(
                    EventoAuditoriaSuministro(
                        entidad_afectada="registro_suministro",
                        tipo_operacion=TipoEventoAuditoriaSuministro.PROVISION_INCREMENTAL_ENTREGADA.value,
                        id_usuario=usuario_actual.id_usuario,
                        resultado=ResultadoAuditoriaSuministro.EXITOSO.value,
                        id_activo_biologico=guardado.id_activo_biologico,
                        id_ciclo_productivo=guardado.id_ciclo_productivo,
                        id_gestion_fases=guardado.id_gestion_fases,
                        costo_afectado=guardado.costo_registro,
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
                self._registrar_fallo(entidad, usuario_actual, str(exc.message))
                raise
            except AppError:
                self.db.rollback()
                raise
        raise ultimo_error  # pragma: no cover — inalcanzable, el loop siempre retorna o lanza

    def _registrar_fallo(
        self, entidad: RegistroSuministroDirecto, usuario_actual: UsuarioActual, causa: str
    ) -> None:
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="registro_suministro",
                    tipo_operacion=TipoEventoAuditoriaSuministro.REGISTRO_FALLIDO.value,
                    id_usuario=usuario_actual.id_usuario,
                    resultado=ResultadoAuditoriaSuministro.FALLIDO.value,
                    id_activo_biologico=entidad.id_activo_biologico,
                    id_ciclo_productivo=entidad.id_ciclo_productivo,
                    id_gestion_fases=entidad.id_gestion_fases,
                    detalle_causa=causa,
                    numero_reintentos=_MAX_REINTENTOS,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
