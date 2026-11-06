# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98: registro y transiciones de las versiones del contrato AAEF |
"""Versiones del contrato AAEF (RF-98 v1.1).

Registro siempre en PENDIENTE. La activación ocurre al llegar la fecha de vigencia (proceso de fondo)
o a pedido del Administrador; en ambos casos con las mismas condiciones (anexo, transformadores, cupo
de dos versiones vigentes). Un MAJOR depreca las anteriores con su período de gracia; al terminar la
gracia la versión queda INACTIVA. Las versiones se bloquean ``FOR UPDATE`` (CA-30) y la auditoría
va en la misma transacción: si no se puede auditar, la transición no ocurre (RF-102 4.1)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.accounting_integration.domain.entities.contrato import (
    GRACIA_DEFECTO_DIAS,
    GRACIA_MINIMA_DIAS,
    VersionContrato,
    exigir_cupo,
    motivo_bloqueo_activacion,
    validar_formato_version,
    versiones_a_deprecar,
)
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import AuditoriaIntegracionRepository
from src.accounting_integration.domain.repositories.contrato_repository import ContratoRepository
from src.accounting_integration.domain.services.aaef import MAPPERS_DISPONIBLES
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True)
class SolicitudContrato:
    contrato_version: str
    tipo_cambio: str
    fecha_vigencia: date
    id_mapeo_anexo_aaef: int
    mapeadores: list[str]
    periodo_gracia_dias: Optional[int] = None
    descripcion: Optional[str] = None


class GestionarContratosUseCase:
    _avisados: dict[str, date] = {}  # versión -> último día avisado; un aviso diario por versión bloqueada

    def __init__(self, contratos: ContratoRepository, auditoria: AuditoriaIntegracionRepository, db: Session,
                 es_produccion: Callable[[], bool], alertar: Callable[[str, dict], None]):
        self.contratos = contratos
        self.auditoria = auditoria
        self.db = db
        self.es_produccion = es_produccion
        self.alertar = alertar

    def _evento(self, tipo: str, contrato: VersionContrato, id_usuario: Optional[int], **detalle) -> None:
        self.auditoria.registrar(EventoIntegracion(
            tipo_evento=tipo, tipo_actor="USUARIO" if id_usuario else "SISTEMA", id_usuario=id_usuario,
            version_contrato=contrato.contrato_version, codigo_resultado="OK",
            json_detalle={"estado": contrato.estado, **detalle}))

    def registrar(self, s: SolicitudContrato, id_usuario: int) -> VersionContrato:
        version = validar_formato_version(s.contrato_version)
        if s.tipo_cambio == "MAJOR":
            gracia = s.periodo_gracia_dias if s.periodo_gracia_dias is not None else GRACIA_DEFECTO_DIAS
            if gracia < GRACIA_MINIMA_DIAS:  # FA-10
                raise ValidationError(code="PERIODO_GRACIA_INVALIDO", field="periodo_gracia_dias",
                                      message=f"El período de gracia debe ser de al menos {GRACIA_MINIMA_DIAS} días.")
        else:
            gracia = None
        if not s.mapeadores or any(m not in MAPPERS_DISPONIBLES for m in s.mapeadores):  # FA-3
            raise ValidationError(code="MAPPERS_INVALIDOS", field="mapeadores",
                                  message="Indique transformadores válidos: compras y, si aplica, comprobante NIC 41.")
        anexo = self.contratos.obtener_anexo(s.id_mapeo_anexo_aaef)
        if anexo is None or not anexo.usable(self.es_produccion()):  # FA-2
            raise BusinessRuleError(code="ANEXO_MAPEO_INVALIDO", field="id_mapeo_anexo_aaef",
                                    message="El contrato necesita un anexo de mapeo aprobado.")
        if any(c.contrato_version == version for c in self.contratos.listar_contratos()):  # FA-1
            raise ConflictError(code="VERSION_DUPLICADA", field="contrato_version",
                                message=f"La versión {version} ya está registrada.")
        contrato = VersionContrato(None, version, s.tipo_cambio, s.fecha_vigencia, anexo.id_mapeo_anexo_aaef,
                                   sorted(set(s.mapeadores)), periodo_gracia_dias=gracia, descripcion=s.descripcion)
        try:
            contrato = self.contratos.guardar_contrato(contrato)
            self._evento("CONTRATO_REGISTRADO", contrato, id_usuario, fecha_vigencia=s.fecha_vigencia.isoformat())
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return contrato

    def activar(self, id_version_contrato_aaef: int, id_usuario: Optional[int]) -> VersionContrato:
        """Activación manual (Administrador) o automática (fecha de vigencia). Atómica con las deprecaciones."""
        try:
            contratos = self.contratos.listar_contratos(bloquear=True)
            contrato = next((c for c in contratos if c.id_version_contrato_aaef == id_version_contrato_aaef), None)
            if contrato is None:
                raise NotFoundError(code="CONTRATO_NO_ENCONTRADO", message="La versión del contrato no existe.")
            motivo = motivo_bloqueo_activacion(
                contrato, self.contratos.obtener_anexo(contrato.id_mapeo_anexo_aaef) if contrato.id_mapeo_anexo_aaef else None,
                self.es_produccion())
            if motivo:  # FA-5: queda PENDIENTE
                raise BusinessRuleError(code="CONTRATO_NO_VALIDO", message=motivo)
            ahora = datetime.now(timezone.utc)
            anteriores = versiones_a_deprecar(contrato, contratos)
            exigir_cupo(contrato, contratos)  # las que pasan a DEPRECADO siguen contando (RF-98 5.3)
            for anterior in anteriores:  # RF-98 5.4
                anterior.deprecar(ahora, contrato.periodo_gracia_dias or GRACIA_DEFECTO_DIAS)
                self.contratos.guardar_contrato(anterior)
                self._evento("CONTRATO_DEPRECADO", anterior, id_usuario, por_version=contrato.contrato_version,
                             fecha_inactivacion=anterior.fecha_inactivacion.date().isoformat())
            contrato.activar(ahora)
            self.contratos.guardar_contrato(contrato)
            self._evento("CONTRATO_ACTIVADO", contrato, id_usuario)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return contrato

    def deprecar(self, id_version_contrato_aaef: int, dias_gracia: int, id_usuario: int) -> VersionContrato:
        try:
            contrato = next((c for c in self.contratos.listar_contratos(bloquear=True)
                             if c.id_version_contrato_aaef == id_version_contrato_aaef), None)
            if contrato is None:
                raise NotFoundError(code="CONTRATO_NO_ENCONTRADO", message="La versión del contrato no existe.")
            contrato.deprecar(datetime.now(timezone.utc), dias_gracia)
            self.contratos.guardar_contrato(contrato)
            self._evento("CONTRATO_DEPRECADO", contrato, id_usuario,
                         fecha_inactivacion=contrato.fecha_inactivacion.date().isoformat())
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return contrato

    def procesar_vigencias(self, hoy: date) -> int:
        """Proceso de fondo: activa las PENDIENTE vigentes (Fase 2) e inactiva las DEPRECADO sin gracia (Fase 6)."""
        cambios = 0
        ahora = datetime.now(timezone.utc)
        for contrato in self.contratos.listar_contratos():
            if contrato.estado == "PENDIENTE" and contrato.fecha_vigencia <= hoy:
                try:
                    self.activar(contrato.id_version_contrato_aaef, None)
                    cambios += 1
                except (BusinessRuleError, ConflictError) as exc:  # queda PENDIENTE y se avisa (CA-24)
                    if self._avisados.get(contrato.contrato_version) != hoy:
                        self._avisados[contrato.contrato_version] = hoy
                        self._avisar_bloqueo(contrato, exc.message)
            elif contrato.estado == "DEPRECADO" and contrato.fecha_inactivacion and contrato.fecha_inactivacion <= ahora:
                try:
                    vigente = next(c for c in self.contratos.listar_contratos(bloquear=True)
                                   if c.id_version_contrato_aaef == contrato.id_version_contrato_aaef)
                    vigente.inactivar(ahora)
                    self.contratos.guardar_contrato(vigente)
                    self._evento("CONTRATO_INACTIVADO", vigente, None)
                    self.db.commit()
                    cambios += 1
                except Exception:
                    self.db.rollback()
                    raise
        return cambios

    def _avisar_bloqueo(self, contrato: VersionContrato, motivo: str) -> None:
        # ponytail: el control de "una vez al día" vive en memoria del proceso; con varias réplicas
        # cada una avisaría una vez. Pasar a la auditoría si se escala.
        try:
            self.auditoria.registrar(EventoIntegracion(
                tipo_evento="CONTRATO_ACTIVACION_BLOQUEADA", severidad="WARNING", version_contrato=contrato.contrato_version,
                codigo_resultado="CONTRATO_NO_VALIDO", json_detalle={"motivo": motivo}))
            self.db.commit()
        except Exception:
            self.db.rollback()
        self.alertar(f"La versión {contrato.contrato_version} del contrato contable no pudo activarse: {motivo}",
                     {"version_contrato": contrato.contrato_version})
