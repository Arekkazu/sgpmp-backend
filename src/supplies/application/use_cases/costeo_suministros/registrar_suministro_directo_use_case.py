# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78: fases, códigos y efectos del RF    |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-11-08 | Arekkazu | INC-M05-264-G31 RF-78: 3 reintentos tras el intento inicial (esperas de 1, 3 y 5 s) |
# | 2026-11-08 | Arekkazu | INC-M05-265-G32: textos visibles sin códigos de requisito ni de módulo |
# | 2026-11-08 | Leandro | INC-M05-275-G37 RF-80: auditar rechazos de negocio sin conservar escrituras parciales. |
# | 2026-11-10 | Arekkazu | INC-M05-340-G27/341-G30 RF-78: unidad del tipo (CA-13) y réplicas simultáneas → YA_PROCESADO (CA-15) |
"""Caso de uso: registrar un suministro en el ledger de RF-78.

Orden (RF-78): Fase 3 idempotencia (E8 → 200 YA_PROCESADO) → tipo de
suministro del catálogo (E4 → 422) → Fase 1/1b ciclo ACTIVO (E1 → 409) y
registro fuente de ALIMENTO/MEDICAMENTO (E9/E10 → 422) → Fase 2 fecha en el
rango del ciclo (E3 → 422) → Fase 4 duplicado por contenido (E6 → 409) → Fase 5
precio (siempre MANUAL: no hay fuente M40; sin justificación E2 → 422) → Fase 6
costo > 0 (422) → Fase 7 persistencia con reintentos 1 s/3 s/5 s (E5 → 500 +
REGISTRO_FALLIDO).

ALIMENTO y MEDICAMENTO ya los acumula el trigger al registrarse en RF-75/RF-76
(con sus eventos de RF-79/RF-80 emitidos en esa misma transacción). Recibir su
``id_registro_rf75``/``id_registro_rf76`` aquí valida el registro fuente y
devuelve la fila acumulada (200, ``YA_ACUMULADO``) sin duplicar el costo.

La actualización del acumulado la hace el trigger ``trg_acumular_costo_ciclo``
dentro de la misma transacción. Los efectos (RF-80 y evento INCREMENTAL de
RF-79) los emite :class:`RegistradorMovimientoLedger`.
"""
from __future__ import annotations

import logging
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
)
from src.shared.fechas import fecha_usuario, hoy_usuario
from src.supplies.application.use_cases.costeo_suministros.movimiento_ledger import RegistradorMovimientoLedger
from src.supplies.domain.entities.registro_suministro_directo import RegistroSuministroDirecto
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbierto, CicloAbiertoPort
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.domain.services.politica_naturaleza_costo import resolver_naturaleza_costo
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import (
    ResultadoAuditoriaSuministro,
    TipoEventoAuditoriaSuministro,
)
from src.supplies.domain.value_objects.justificacion_precio import JustificacionPrecio
from src.supplies.domain.value_objects.tipo_suministro import ETIQUETA_TIPO, UNIDAD_POR_TIPO, TipoSuministro
from src.supplies.infrastructure.dto.registrar_suministro_directo_dto import RegistrarSuministroDirectoDTO

_MAX_REINTENTOS = 3
_BACKOFF_SEGUNDOS = (1, 3, 5)
_ESCALA_CANTIDAD = Decimal("0.0001")
_ESCALA_PRECIO = Decimal("0.01")
# Errores transitorios de infraestructura que justifican reintentar. Desde
# INC-M01-06-024 un fallo de conectividad sale como ServiceUnavailableError en
# vez de InfrastructureError, así que el reintento tiene que cubrir ambos.
_ERRORES_REINTENTABLES = (InfrastructureError, ServiceUnavailableError)
_TIPOS_CON_FUENTE = {TipoSuministro.ALIMENTO.value: "rf75", TipoSuministro.MEDICAMENTO.value: "rf76"}
_LOGGER = logging.getLogger(__name__)
_MOTIVOS_RECHAZO = {
    "CICLO_NO_ACTIVO": "El activo no tiene un ciclo productivo abierto.",
    "TIPO_SUMINISTRO_NO_CONFIGURADO": "El tipo de suministro no está habilitado.",
    "DATOS_SUMINISTRO_INCOMPLETOS": "Faltan datos obligatorios del suministro.",
    "FECHA_FUERA_DE_RANGO": "La fecha está fuera del período permitido del ciclo.",
    "SUMINISTRO_DUPLICADO": "Ya existe un suministro con el mismo contenido.",
    "RECURSO_DUPLICADO": "El suministro coincide con un registro ya existente.",
    "JUSTIFICACION_PRECIO_REQUERIDA": "Falta una justificación válida del precio manual.",
    "JUSTIFICACION_PRECIO_MUY_LARGA": "La justificación del precio supera la longitud permitida.",
    "COSTO_REGISTRO_INVALIDO": "La cantidad y el precio deben producir un costo mayor que cero.",
    "REGISTRO_RF75_INVALIDO": "El consumo de alimento de origen no es válido para el activo.",
    "REGISTRO_RF76_INVALIDO": "La aplicación de medicamento de origen no es válida para el activo.",
}


@dataclass(frozen=True)
class ResultadoRegistroDirecto:
    """El registro y cómo se resolvió: REGISTRADO, YA_PROCESADO (E8) o YA_ACUMULADO (Fase 1b)."""

    registro: RegistroSuministroDirecto
    estado: str = "REGISTRADO"

    @property
    def ya_procesado(self) -> bool:
        return self.estado == "YA_PROCESADO"

    @property
    def mensaje(self) -> str:
        if self.estado == "YA_PROCESADO":
            return (
                "Operación ya procesada. Se retorna el resultado original sin crear un nuevo registro."
            )
        if self.estado == "YA_ACUMULADO":
            return (
                "El registro fuente ya está acumulado en el ciclo productivo desde que se registró el consumo o la aplicación. "
                "Se retorna el registro de suministro existente."
            )
        return "Suministro registrado y acumulado en el ciclo productivo."


class RegistrarSuministroDirectoUseCase:
    """Registra un suministro en el ledger de RF-78 y actualiza el acumulado del ciclo."""

    def __init__(
        self,
        db: Session,
        registro_repo: RegistroSuministroRepository,
        ciclo_port: CicloAbiertoPort,
        auditoria_port: AuditoriaSuministroPort,
        movimiento: RegistradorMovimientoLedger,
        activo_port: ActivoConsultaPort,
    ) -> None:
        self.db = db
        self.registro_repo = registro_repo
        self.ciclo_port = ciclo_port
        self.auditoria_port = auditoria_port
        self.movimiento = movimiento
        self.activo_port = activo_port

    def execute(
        self, dto: RegistrarSuministroDirectoDTO, usuario_actual: UsuarioActual
    ) -> ResultadoRegistroDirecto:
        contexto: dict[str, Optional[CicloAbierto]] = {}
        try:
            return self._ejecutar(dto, usuario_actual, contexto)
        except (BusinessRuleError, ConflictError) as exc:
            self._registrar_rechazo(dto, usuario_actual, exc, contexto.get("ciclo"))
            raise

    def _ejecutar(
        self,
        dto: RegistrarSuministroDirectoDTO,
        usuario_actual: UsuarioActual,
        contexto: dict[str, Optional[CicloAbierto]],
    ) -> ResultadoRegistroDirecto:
        # Fase 3 — idempotencia, ANTES de cualquier otra validación (E8).
        existente = self.registro_repo.existe_idempotente(dto.id_idempotencia)
        if existente is not None:
            return ResultadoRegistroDirecto(registro=existente, estado="YA_PROCESADO")

        # E4 — tipo de suministro del catálogo.
        if dto.tipo_suministro not in {t.value for t in TipoSuministro}:
            raise BusinessRuleError(
                code="TIPO_SUMINISTRO_NO_CONFIGURADO",
                message=(
                    f"El tipo de suministro {dto.tipo_suministro} no está en el catálogo activo. Configúrelo "
                    "en Configuración antes de continuar."
                ),
                field="tipo_suministro",
            )

        # Fase 1 — ciclo productivo activo (E1).
        ciclo = self.ciclo_port.obtener_abierto(dto.id_activo_biologico)
        contexto["ciclo"] = ciclo
        if ciclo is None or ciclo.id_gestion_fases is None:
            raise ConflictError(
                code="CICLO_NO_ACTIVO",
                message=(
                    f"No existe un ciclo productivo activo para el activo {dto.id_activo_biologico}. "
                    "Verifique el estado del ciclo en Activos biológicos antes de registrar suministros."
                ),
            )

        # Fase 1b — ALIMENTO/MEDICAMENTO vienen de RF-75/RF-76 (E9/E10).
        if dto.tipo_suministro in _TIPOS_CON_FUENTE:
            return ResultadoRegistroDirecto(registro=self._registro_fuente(dto), estado="YA_ACUMULADO")

        # Fase 2 — fecha dentro del rango del ciclo (E3).
        if dto.fecha_aplicacion is None or dto.cantidad is None or dto.precio_unitario is None or not dto.unidad_medida:
            raise BusinessRuleError(
                code="DATOS_SUMINISTRO_INCOMPLETOS",
                message=(
                    f"Para {dto.tipo_suministro} se requieren cantidad, unidad_medida, fecha_aplicacion y "
                    "precio_unitario."
                ),
            )
        self._validar_fecha_aplicacion(dto.fecha_aplicacion, ciclo.fecha_inicio)
        unidad = UNIDAD_POR_TIPO.get(dto.tipo_suministro)
        if unidad is not None and dto.unidad_medida != unidad:  # Restricción 11 / CA-13
            raise BusinessRuleError(
                code="UNIDAD_MEDIDA_NO_COINCIDE",
                message=(
                    f"La unidad de medida «{dto.unidad_medida}» no coincide con la configurada para "
                    f"{ETIQUETA_TIPO.get(dto.tipo_suministro, 'este tipo de suministro')}: «{unidad}»."
                ),
                field="unidad_medida",
            )

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
                    "Ya existe un registro de suministro idéntico. Si quiere ajustarlo, registre una corrección "
                    "sobre ese registro."
                ),
            )

        # Fase 5 — precio: siempre MANUAL, justificación obligatoria (E2).
        justificacion = JustificacionPrecio(dto.justificacion_precio)

        # Fase 6 — costo del registro > 0.
        if cantidad <= 0 or precio <= 0:
            raise BusinessRuleError(
                code="COSTO_REGISTRO_INVALIDO",
                message=(
                    "El costo del registro (cantidad × precio unitario) debe ser mayor a cero. "
                    f"Cantidad: {cantidad}, precio unitario: {precio}."
                ),
            )

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

    def _registro_fuente(self, dto: RegistrarSuministroDirectoDTO) -> RegistroSuministroDirecto:
        es_alimento = dto.tipo_suministro == TipoSuministro.ALIMENTO.value
        referencia = dto.id_registro_rf75 if es_alimento else dto.id_registro_rf76
        ledger = (
            self.registro_repo.obtener_por_referencia_rf(dto.tipo_suministro, referencia)
            if referencia is not None
            else None
        )
        if ledger is None or ledger.id_activo_biologico != dto.id_activo_biologico:
            if es_alimento:
                raise BusinessRuleError(
                    code="REGISTRO_RF75_INVALIDO",
                    message=(
                        f"El registro de consumo de alimento {referencia} no existe, no corresponde al activo "
                        "indicado o no está en estado VALIDADO. Verifique el registro en Consumo de alimentos "
                        "antes de registrar la acumulación."
                    ),
                    field="id_registro_rf75",
                )
            raise BusinessRuleError(
                code="REGISTRO_RF76_INVALIDO",
                message=(
                    f"El registro de aplicación de medicamento {referencia} no existe, no corresponde al activo "
                    "indicado o no está en estado VALIDADO. Verifique el registro en Aplicación de medicamentos "
                    "antes de registrar la acumulación."
                ),
                field="id_registro_rf76",
            )
        return ledger

    @staticmethod
    def _validar_fecha_aplicacion(fecha_aplicacion: date, fecha_inicio_ciclo) -> None:
        hoy = hoy_usuario()
        inicio: Optional[date] = fecha_usuario(fecha_inicio_ciclo) if fecha_inicio_ciclo is not None else None
        if fecha_aplicacion > hoy or (inicio is not None and fecha_aplicacion < inicio):
            raise BusinessRuleError(
                code="FECHA_FUERA_DE_RANGO",
                message=(
                    f"La fecha {fecha_aplicacion.isoformat()} está fuera del rango del ciclo productivo activo "
                    f"({inicio.isoformat() if inicio else '-'} — {hoy.isoformat()})."
                ),
                field="fecha_aplicacion",
            )

    def _persistir_con_reintentos(
        self, entidad: RegistroSuministroDirecto, usuario_actual: UsuarioActual
    ) -> ResultadoRegistroDirecto:
        ultimo_error: Optional[AppError] = None
        # Restricción 9: intento inicial + 3 reintentos, con esperas de 1 s, 3 s y 5 s antes de cada uno.
        for intento in range(1, _MAX_REINTENTOS + 2):
            try:
                guardado = self.registro_repo.guardar(entidad)
                self.movimiento.registrar(guardado, id_usuario=usuario_actual.id_usuario, precio_manual=True)
                self.db.commit()
                return ResultadoRegistroDirecto(registro=guardado)
            except _ERRORES_REINTENTABLES as exc:
                self.db.rollback()
                ultimo_error = exc
                if intento <= _MAX_REINTENTOS:
                    time.sleep(_BACKOFF_SEGUNDOS[intento - 1])
                    continue
                self._registrar_fallo(entidad, usuario_actual, str(exc.message))
                raise
            except ConflictError:
                self.db.rollback()
                # CA-15: una réplica simultánea pasó la consulta previa y chocó con la unicidad de
                # id_idempotencia; la que ganó ya está guardada, así que se responde con ella.
                existente = self.registro_repo.existe_idempotente(entidad.id_idempotencia)
                if existente is not None:
                    return ResultadoRegistroDirecto(registro=existente, estado="YA_PROCESADO")
                raise
            except AppError:
                self.db.rollback()
                raise
        raise ultimo_error  # pragma: no cover — inalcanzable, el loop siempre retorna o lanza

    def _registrar_rechazo(
        self,
        dto: RegistrarSuministroDirectoDTO,
        usuario_actual: UsuarioActual,
        error: AppError,
        ciclo: Optional[CicloAbierto],
    ) -> None:
        """Revierte el intento y confirma solo su evidencia en una nueva transacción.

        La consulta del activo conserva la identidad/RLS de la sesión. No se
        enlazan claves ajenas, inexistentes ni una fase inferida tras el rechazo.
        Si la auditoría no está disponible se conserva el error de negocio y se
        registra un diagnóstico seguro, sin afirmar una persistencia inexistente.
        """
        try:
            self.db.rollback()
            activo = self.activo_port.obtener(dto.id_activo_biologico)
            ciclo_verificado = ciclo if activo is not None else None
            motivo = _MOTIVOS_RECHAZO.get(error.code, "La operación incumple una regla de negocio.")
            detalle = (
                f"Registro de suministro rechazado: {motivo} "
                f"Activo solicitado: {dto.id_activo_biologico}. Solicitud: {dto.id_idempotencia}."
            )
            incompleto = ciclo_verificado is None or ciclo_verificado.id_gestion_fases is None
            if incompleto:
                detalle += " No se pudo acreditar una fase productiva abierta para el intento."
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="registro_suministro",
                    tipo_operacion=TipoEventoAuditoriaSuministro.REGISTRO_FALLIDO.value,
                    id_usuario=usuario_actual.id_usuario,
                    resultado=ResultadoAuditoriaSuministro.RECHAZADO.value,
                    id_activo_biologico=activo.id_activo_biologico if activo is not None else None,
                    id_ciclo_productivo=ciclo_verificado.id_ciclo_productivo if ciclo_verificado else None,
                    id_gestion_fases=ciclo_verificado.id_gestion_fases if ciclo_verificado else None,
                    detalle_causa=detalle,
                    numero_reintentos=0,
                    registro_incompleto=incompleto,
                )
            )
            self.db.commit()
        except Exception:
            _LOGGER.error(
                "No se pudo auditar el rechazo de suministro: usuario=%s solicitud=%s codigo=%s",
                usuario_actual.id_usuario, dto.id_idempotencia, error.code,
            )
            try:
                self.db.rollback()
            except Exception:
                _LOGGER.error("No se pudo revertir la transacción de auditoría de rechazo.")

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
