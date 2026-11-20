# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98: registro y transiciones de las versiones del contrato AAEF |
# | 2026-11-19 | LuisfNarvaez01 | INC-M07-375 RF-98: transición rechazada auditada (WARNING) y avisada, estado antes que anexo y modificación de pendientes |
# | 2026-11-19 | Arekkazu | INC-M07-373-G37/374-G38 RF-98: gracia desde M09 y aviso de la activación manual bloqueada |
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
from src.accounting_integration.domain.services.aaef import MAPPER_COMPROBANTE_NIC41, MAPPERS_DISPONIBLES
from src.shared.errors import BusinessRuleError, ConflictError, FlowError, NotFoundError, ValidationError

# RF-98 CA-26/CA-27: rechazos del ciclo de vida que se auditan con WARNING y se avisan al Administrador.
_RECHAZOS_AUDITADOS = ("TRANSICION_NO_PERMITIDA", "REACTIVACION_NO_PERMITIDA", "MODIFICACION_NO_PERMITIDA")
_ACCIONES = {"activar": ("POST", "/activar"), "deprecar": ("POST", "/deprecar"), "modificar": ("PATCH", "")}


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
                 es_produccion: Callable[[], bool], alertar: Callable[[str, dict], None],
                 comprobante_habilitado: bool = False,
                 registrar_aparte: Optional[Callable[[EventoIntegracion], None]] = None,
                 gracia: Callable[[], tuple[int, int]] = lambda: (GRACIA_MINIMA_DIAS, GRACIA_DEFECTO_DIAS)):
        """``gracia``: (mínimo, por defecto) en días, configurados en M09 (RNF-98.10)."""
        self.contratos = contratos
        self.gracia = gracia
        self.auditoria = auditoria
        self.db = db
        self.es_produccion = es_produccion
        self.alertar = alertar
        self.comprobante_habilitado = comprobante_habilitado
        self.registrar_aparte = registrar_aparte

    def _rechazo(self, exc: FlowError, contrato: VersionContrato, accion: str, id_usuario: Optional[int],
                 metodo: Optional[str] = None) -> None:
        """RF-98 CA-26/CA-27 + RF-102: el intento rechazado se audita con WARNING en una sesión propia
        (la operación ya hizo rollback y el registro debe quedar) y se avisa al Administrador."""
        if exc.code not in _RECHAZOS_AUDITADOS or self.registrar_aparte is None:
            return
        metodo_defecto, sufijo = _ACCIONES[accion]
        self.registrar_aparte(EventoIntegracion(
            tipo_evento="CONTRATO_TRANSICION_RECHAZADA", severidad="WARNING",
            tipo_actor="USUARIO" if id_usuario else "SISTEMA", id_usuario=id_usuario,
            version_contrato=contrato.contrato_version, metodo_http=metodo or metodo_defecto, codigo_http=422,
            endpoint=f"/integracion/contratos/{contrato.id_version_contrato_aaef}{sufijo}",
            codigo_resultado=exc.code, json_detalle={"estado": contrato.estado, "accion": accion}))
        self.alertar(f"Se rechazó un intento de {accion} la versión {contrato.contrato_version} del contrato "
                     f"contable: {exc.message}", {"version_contrato": contrato.contrato_version, "accion": accion})

    def _bloquear(self, id_version_contrato_aaef: int) -> tuple[VersionContrato, list[VersionContrato]]:
        contratos = self.contratos.listar_contratos(bloquear=True)
        contrato = next((c for c in contratos if c.id_version_contrato_aaef == id_version_contrato_aaef), None)
        if contrato is None:
            raise NotFoundError(code="CONTRATO_NO_ENCONTRADO", message="La versión del contrato no existe.")
        return contrato, contratos

    def _exigir_comprobante_disponible(self, mapeadores: list[str]) -> None:
        if MAPPER_COMPROBANTE_NIC41 in mapeadores and not self.comprobante_habilitado:
            raise BusinessRuleError(code="MAPPER_NO_DISPONIBLE", field="mapeadores", message=(
                "El comprobante NIC 41 todavía no lo recibe la contabilidad externa. Registre la versión solo con compras."))

    def _evento(self, tipo: str, contrato: VersionContrato, id_usuario: Optional[int], **detalle) -> None:
        self.auditoria.registrar(EventoIntegracion(
            tipo_evento=tipo, tipo_actor="USUARIO" if id_usuario else "SISTEMA", id_usuario=id_usuario,
            version_contrato=contrato.contrato_version, codigo_resultado="OK",
            json_detalle={"estado": contrato.estado, **detalle}))

    def registrar(self, s: SolicitudContrato, id_usuario: int) -> VersionContrato:
        version = validar_formato_version(s.contrato_version)
        if s.tipo_cambio == "MAJOR":
            minima, defecto = self.gracia()
            gracia = s.periodo_gracia_dias if s.periodo_gracia_dias is not None else defecto
            if gracia < minima:  # FA-10
                raise ValidationError(code="PERIODO_GRACIA_INVALIDO", field="periodo_gracia_dias",
                                      message=f"El período de gracia debe ser de al menos {minima} días.")
        else:
            gracia = None
        if not s.mapeadores or any(m not in MAPPERS_DISPONIBLES for m in s.mapeadores):  # FA-3
            raise ValidationError(code="MAPPERS_INVALIDOS", field="mapeadores",
                                  message="Indique transformadores válidos: compras y, si aplica, comprobante NIC 41.")
        self._exigir_comprobante_disponible(s.mapeadores)
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
        """Activación manual (Administrador) o automática (fecha de vigencia). Atómica con las deprecaciones.

        Si la manual se bloquea, se avisa al Administrador como en la automática (CA-5 / FA-5)."""
        contrato = None
        try:
            contrato, contratos = self._bloquear(id_version_contrato_aaef)
            contrato.exigir_activable()  # FA-13: el estado manda sobre el anexo
            motivo = motivo_bloqueo_activacion(
                contrato, self.contratos.obtener_anexo(contrato.id_mapeo_anexo_aaef) if contrato.id_mapeo_anexo_aaef else None,
                self.es_produccion())
            if motivo:  # FA-5: queda PENDIENTE
                raise BusinessRuleError(code="CONTRATO_NO_VALIDO", message=motivo)
            self._exigir_comprobante_disponible(contrato.mapeadores)
            ahora = datetime.now(timezone.utc)
            anteriores = versiones_a_deprecar(contrato, contratos)
            exigir_cupo(contrato, contratos)  # las que pasan a DEPRECADO siguen contando (RF-98 5.3)
            for anterior in anteriores:  # RF-98 5.4; la gracia del MAJOR ya se validó al registrarlo
                anterior.deprecar(ahora, contrato.periodo_gracia_dias or self.gracia()[1], minimo_dias=1)
                self.contratos.guardar_contrato(anterior)
                self._evento("CONTRATO_DEPRECADO", anterior, id_usuario, por_version=contrato.contrato_version,
                             fecha_inactivacion=anterior.fecha_inactivacion.date().isoformat())
            contrato.activar(ahora)
            self.contratos.guardar_contrato(contrato)
            self._evento("CONTRATO_ACTIVADO", contrato, id_usuario)
            self.db.commit()
        except FlowError as exc:
            self.db.rollback()
            if contrato is not None:
                self._rechazo(exc, contrato, "activar", id_usuario)
            raise
        except Exception as exc:
            self.db.rollback()
            if id_usuario is not None and contrato is not None and isinstance(exc, BusinessRuleError):
                self._avisar_bloqueo(contrato, exc.message, id_usuario)
            raise
        return contrato

    def deprecar(self, id_version_contrato_aaef: int, dias_gracia: Optional[int], id_usuario: int) -> VersionContrato:
        """Sin ``dias_gracia`` se usa el período por defecto configurado en M09."""
        minima, defecto = self.gracia()
        contrato = None
        try:
            contrato, _ = self._bloquear(id_version_contrato_aaef)
            contrato.deprecar(datetime.now(timezone.utc), dias_gracia if dias_gracia is not None else defecto, minima)
            self.contratos.guardar_contrato(contrato)
            self._evento("CONTRATO_DEPRECADO", contrato, id_usuario,
                         fecha_inactivacion=contrato.fecha_inactivacion.date().isoformat())
            self.db.commit()
        except FlowError as exc:
            self.db.rollback()
            if contrato is not None:
                self._rechazo(exc, contrato, "deprecar", id_usuario)
            raise
        except Exception:
            self.db.rollback()
            raise
        return contrato

    def modificar(self, id_version_contrato_aaef: int, cambios: dict, id_usuario: int,
                  metodo: str = "PATCH") -> VersionContrato:
        """RF-98 5.12 / CA-20 / FA-12: solo una versión PENDIENTE se modifica; ACTIVO, DEPRECADO e
        INACTIVO responden MODIFICACION_NO_PERMITIDA y el intento queda auditado."""
        contrato = None
        try:
            contrato, _ = self._bloquear(id_version_contrato_aaef)
            anterior = {"fecha_vigencia": contrato.fecha_vigencia.isoformat(), "mapeadores": list(contrato.mapeadores),
                        "id_mapeo_anexo_aaef": contrato.id_mapeo_anexo_aaef,
                        "periodo_gracia_dias": contrato.periodo_gracia_dias}
            contrato.modificar(**cambios, minimo_dias=self.gracia()[0])
            self._exigir_comprobante_disponible(contrato.mapeadores)
            if cambios.get("id_mapeo_anexo_aaef") is not None:
                anexo = self.contratos.obtener_anexo(contrato.id_mapeo_anexo_aaef)
                if anexo is None or not anexo.usable(self.es_produccion()):  # FA-2
                    raise BusinessRuleError(code="ANEXO_MAPEO_INVALIDO", field="id_mapeo_anexo_aaef",
                                            message="El contrato necesita un anexo de mapeo aprobado.")
            self.contratos.guardar_datos_contrato(contrato)
            self._evento("CONTRATO_MODIFICADO", contrato, id_usuario, anterior=anterior,
                         campos=sorted(k for k, v in cambios.items() if v is not None))
            self.db.commit()
        except FlowError as exc:
            self.db.rollback()
            if contrato is not None:
                self._rechazo(exc, contrato, "modificar", id_usuario, metodo)
            raise
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

    def _avisar_bloqueo(self, contrato: VersionContrato, motivo: str, id_usuario: Optional[int] = None) -> None:
        # ponytail: el control de "una vez al día" vive en memoria del proceso; con varias réplicas
        # cada una avisaría una vez. Pasar a la auditoría si se escala.
        try:
            self.auditoria.registrar(EventoIntegracion(
                tipo_evento="CONTRATO_ACTIVACION_BLOQUEADA", severidad="WARNING", version_contrato=contrato.contrato_version,
                tipo_actor="USUARIO" if id_usuario else "SISTEMA", id_usuario=id_usuario,
                codigo_resultado="CONTRATO_NO_VALIDO", json_detalle={"motivo": motivo}))
            self.db.commit()
        except Exception:
            self.db.rollback()
        self.alertar(f"La versión {contrato.contrato_version} del contrato contable no pudo activarse: {motivo}",
                     {"version_contrato": contrato.contrato_version})
