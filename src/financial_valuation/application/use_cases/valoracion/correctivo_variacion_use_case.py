# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: correctivo de variaciones con aprobación del Contador |
"""Casos de uso RF-86 restricción 5 y CA-13: corregir una variación errónea sin tocar el registro original.

1. Un Contador solicita el correctivo con su motivo: la solicitud queda PENDIENTE.
2. Otro Contador (doble control) la aprueba: se inserta la variación correctiva con el monto opuesto
   y ``id_variacion_corregida`` = la original, y las líneas de asiento inversas de las de la original.
   O la rechaza con su motivo.
El original y el correctivo quedan visibles en el historial del período; ninguno se modifica ni elimina.
Solo se corrige una variación de un período ABIERTO (RF-86 R5); la de un período cerrado se corrige con un
ajuste de período anterior en el cierre (RF-87)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.entities.valoracion import VariacionRegistro
from src.financial_valuation.domain.repositories.correctivo_variacion_repository import CorrectivoVariacionRepository
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.value_objects.nic41 import Severidad
from src.shared.errors import AuthorizationError, BusinessRuleError, ConflictError, NotFoundError, ValidationError
from src.shared.fechas import hoy_usuario

MIN_MOTIVO = 20
TABLA = "variaciones_valor_razonable"


def _motivo(texto: Optional[str], campo: str, que: str) -> str:
    limpio = (texto or "").strip()
    if len(limpio) < MIN_MOTIVO:
        raise ValidationError(code="MOTIVO_REQUERIDO", field=campo,
                              message=f"Explique {que} con al menos {MIN_MOTIVO} caracteres.")
    return limpio


class _Base:
    def __init__(self, db: Session, correctivos: CorrectivoVariacionRepository, valoraciones: ValoracionRepository,
                 contabilizador: Contabilizador) -> None:
        self.db = db
        self.correctivos = correctivos
        self.valoraciones = valoraciones
        self.contabilizador = contabilizador

    def _periodo_abierto(self, variacion: VariacionRegistro):
        periodo = self.contabilizador.periodos.obtener(variacion.id_periodo_contable)
        if periodo is None or not periodo.esta_abierto:
            raise BusinessRuleError(code="PERIODO_NO_ABIERTO", message=(
                "El período de la variación ya no está abierto: no admite correctivos. La corrección de un período "
                "cerrado se registra como ajuste de período anterior en el período vigente."))
        return periodo

    def _auditar(self, tipo, severidad, variacion, id_usuario, id_referencia, payload) -> None:
        self.contabilizador.auditar(EventoAuditoria(
            tipo_evento=tipo, severidad=severidad.value, payload=payload, id_usuario=id_usuario,
            id_activo_biologico=variacion.id_activo_biologico, id_periodo_contable=variacion.id_periodo_contable,
            id_referencia=id_referencia, monto_afectado=variacion.monto_variacion,
        ))


class SolicitarCorrectivoVariacionUseCase(_Base):
    def execute(self, id_variacion: int, motivo: Optional[str], id_usuario: int) -> dict:
        texto = _motivo(motivo, "motivo", "por qué la variación es errónea")
        variacion = self.correctivos.variacion(id_variacion)
        if variacion is None:
            raise NotFoundError(code="VARIACION_NO_ENCONTRADA", message="La variación de valor razonable no existe.")
        if variacion.es_correctivo:
            raise ConflictError(code="CORRECTIVO_NO_CORREGIBLE", message=(
                "Este registro ya es un correctivo: no se corrige otra vez. Si la variación original sigue siendo "
                "correcta, registre una nueva medición."))
        vigente = self.correctivos.solicitud_vigente(id_variacion)
        if vigente is not None:
            raise ConflictError(code="CORRECTIVO_EXISTENTE", message=(
                "La variación ya tiene un correctivo pendiente de aprobación." if vigente.esta_pendiente
                else "La variación ya fue corregida."))
        self._periodo_abierto(variacion)
        try:
            id_solicitud = self.correctivos.agregar(id_variacion, texto, id_usuario)
            self._auditar("CORRECTIVO_VARIACION_SOLICITADO", Severidad.WARNING, variacion, id_usuario, id_solicitud,
                          {"id_variacion": id_variacion, "tipo": variacion.tipo, "monto": str(variacion.monto_variacion),
                           "motivo": texto})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_solicitud_correctivo_variacion": id_solicitud, "id_variacion_valor_razonable": id_variacion,
                "estado": "PENDIENTE", "monto_correctivo": -variacion.monto_variacion}


class ResolverCorrectivoVariacionUseCase(_Base):
    def aprobar(self, id_solicitud: int, id_usuario: int) -> dict:
        solicitud, variacion, periodo = self._pendiente(id_solicitud, id_usuario)
        try:
            correctivo = variacion.correctivo(id_usuario)
            id_correctivo = self.valoraciones.agregar_variacion(correctivo)
            originales = self.contabilizador.asientos.lineas_de_origen(TABLA, variacion.id_variacion_valor_razonable)
            fecha = min(hoy_usuario(), periodo.fecha_fin)
            inversas = self.contabilizador.revertir_lineas(originales, periodo, fecha, TABLA, id_correctivo,
                                                           solicitud.motivo, id_usuario)
            self.correctivos.aprobar(id_solicitud, id_usuario, id_correctivo)
            self._auditar("CORRECTIVO_VARIACION_APROBADO", Severidad.WARNING, correctivo, id_usuario, id_solicitud,
                          {"id_variacion_corregida": variacion.id_variacion_valor_razonable,
                           "id_variacion_correctiva": id_correctivo, "tipo": correctivo.tipo,
                           "monto": str(correctivo.monto_variacion), "motivo": solicitud.motivo,
                           "id_usuario_solicitante": solicitud.id_usuario_solicitante,
                           "lineas_inversas": [ln.id_linea_asiento_nic41 for ln in inversas]})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_solicitud_correctivo_variacion": id_solicitud, "estado": "APROBADA",
                "id_variacion_corregida": variacion.id_variacion_valor_razonable, "id_variacion_correctiva": id_correctivo,
                "tipo": correctivo.tipo, "monto_variacion": correctivo.monto_variacion,
                "lineas_inversas": [{"id_linea": ln.id_linea_asiento_nic41, "id_linea_corregida": ln.id_linea_corregida,
                                     "tipo_hecho": ln.tipo_hecho, "valor": ln.valor, "cuenta_debito": ln.cuenta_debito,
                                     "cuenta_credito": ln.cuenta_credito, "estado": ln.estado} for ln in inversas]}

    def rechazar(self, id_solicitud: int, motivo_rechazo: Optional[str], id_usuario: int) -> dict:
        texto = _motivo(motivo_rechazo, "motivo_rechazo", "por qué se rechaza el correctivo")
        solicitud, variacion, _ = self._pendiente(id_solicitud, id_usuario)
        try:
            self.correctivos.rechazar(id_solicitud, id_usuario, texto)
            self._auditar("CORRECTIVO_VARIACION_RECHAZADO", Severidad.INFO, variacion, id_usuario, id_solicitud,
                          {"id_variacion": variacion.id_variacion_valor_razonable, "motivo_rechazo": texto,
                           "id_usuario_solicitante": solicitud.id_usuario_solicitante})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_solicitud_correctivo_variacion": id_solicitud, "estado": "RECHAZADA",
                "id_variacion_valor_razonable": variacion.id_variacion_valor_razonable}

    def _pendiente(self, id_solicitud: int, id_usuario: int):
        solicitud = self.correctivos.obtener(id_solicitud, bloquear=True)
        if solicitud is None:
            raise NotFoundError(code="CORRECTIVO_NO_ENCONTRADO", message="La solicitud de correctivo no existe.")
        if not solicitud.esta_pendiente:
            raise ConflictError(code="CORRECTIVO_YA_RESUELTO", message=(
                f"La solicitud de correctivo ya fue {'aprobada' if solicitud.estado == 'APROBADA' else 'rechazada'}."))
        if solicitud.id_usuario_solicitante == id_usuario:  # doble control
            raise AuthorizationError(code="APROBADOR_DEBE_SER_OTRO", message=(
                "Quien solicitó el correctivo no puede resolverlo: debe aprobarlo o rechazarlo otro Contador."))
        variacion = self.correctivos.variacion(solicitud.id_variacion_valor_razonable)
        return solicitud, variacion, self._periodo_abierto(variacion)
