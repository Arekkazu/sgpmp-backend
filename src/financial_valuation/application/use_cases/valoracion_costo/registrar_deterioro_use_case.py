# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-88 paso 5: deterioro de un activo valorado por costo (NIC 41 ¶30, ¶55) |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-281-G68-07 RF-88: alerta persistente al llevar el valor en libros a cero |
"""Caso de uso RF-88 paso 5: el Contador cuantifica el impacto económico de un evento sanitario de
RF-41 sobre un activo valorado por costo. RF-41 aporta el hecho clínico; M06, el monto.

INC-M06-281-G68-07: si costo − depreciación − deterioro da negativo, el valor en libros queda en cero y se
registra la alerta persistente ``VALOR_LIBROS_AJUSTADO_A_CERO`` (valor calculado y aplicado, consultable por
activo); después del commit se avisa al Contador."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.nic41 import CERO, truncar2, valor_libros_calculado
from src.financial_valuation.domain.value_objects.nic41 import Sentido, Severidad, TipoEvidencia, TipoHecho
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError
from src.shared.fechas import hoy_usuario

logger = logging.getLogger(__name__)


class RegistrarDeterioroUseCase:
    def __init__(self, db: Session, activos: ActivoFinancieroPort, valoraciones: ValoracionRepository,
                 contabilizador: Contabilizador, notificador: Optional[NotificacionFinancieraPort] = None) -> None:
        self.db = db
        self.activos = activos
        self.valoraciones = valoraciones
        self.contabilizador = contabilizador
        self.notificador = notificador

    def execute(self, id_activo_biologico: int, id_evento_sanitario: int, impacto: Decimal, justificacion: str,
                id_usuario: int) -> dict:
        activo = self.activos.obtener(id_activo_biologico)
        if activo is None:
            raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message="El activo biológico no existe.")
        costo = self.valoraciones.valoracion_costo_activa(id_activo_biologico)
        if costo is None:
            raise ConflictError(code="ACTIVO_NO_VALORADO_POR_COSTO", message=(
                "El deterioro solo se registra en activos valorados por costo; a valor razonable la pérdida ya se mide."))
        if impacto <= 0 or len((justificacion or "").strip()) < 30:
            raise BusinessRuleError(code="DETERIORO_INVALIDO", message=(
                "El impacto debe ser mayor a cero y la justificación contable debe tener al menos 30 caracteres."))
        if not self.activos.evento_sanitario_del_activo(id_evento_sanitario, id_activo_biologico):
            raise BusinessRuleError(code="EVENTO_SANITARIO_INVALIDO", field="id_evento_sanitario",
                                    message="El evento sanitario no existe o no es de este activo.")
        reduccion = truncar2(min(Decimal(impacto), costo.valor_contable_por_costo))
        try:
            hoy = hoy_usuario()
            periodo = self.contabilizador.periodo_para(activo.numero_id_tributaria, hoy, id_usuario)
            id_deterioro = self.valoraciones.agregar_deterioro(costo.id_valoracion_por_costo, id_evento_sanitario,
                                                               impacto, justificacion.strip(), id_usuario)
            costo.deterioro_acumulado += Decimal(impacto)
            calculado = valor_libros_calculado(costo.costos_adquisicion, costo.depreciacion_acumulada,
                                               costo.deterioro_acumulado)
            costo.valor_contable_por_costo = max(CERO, calculado)
            self.valoraciones.actualizar_valoracion_costo(costo)
            if reduccion > 0:
                self.contabilizador.asentar(LineaAsiento(
                    tipo_hecho=TipoHecho.DETERIORO_ACTIVO_COSTO.value, sentido=Sentido.UNICO.value, valor=reduccion,
                    fecha_hecho=hoy, id_periodo_contable=periodo.id_periodo_contable,
                    id_activo_biologico=id_activo_biologico, id_especie=activo.id_especie, id_finca=activo.id_finca,
                    numero_id_tributaria=activo.numero_id_tributaria, tabla_origen="deterioros_activos",
                    id_origen=id_deterioro, tipo_evidencia=TipoEvidencia.EVENTO_SANITARIO.value,
                    justificacion=justificacion.strip(), id_usuario=id_usuario,
                ), id_usuario)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="DETERIORO_REGISTRADO", severidad=Severidad.WARNING.value, id_usuario=id_usuario,
                payload={"id_evento_sanitario": id_evento_sanitario, "impacto": str(impacto),
                         "valor_contable": str(costo.valor_contable_por_costo)},
                id_activo_biologico=id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
                id_referencia=id_deterioro, monto_afectado=impacto, metodo_nuevo="VALORACION_POR_COSTO",
            ))
            if calculado < 0:
                self.contabilizador.auditar(evento_valor_libros_cero(
                    costo, calculado, "DETERIORO", id_activo_biologico, periodo.id_periodo_contable, id_deterioro,
                    id_usuario))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        aviso = None
        if costo.valor_contable_por_costo <= 0:  # FA-1
            aviso = (f"El activo {activo.identificador} llegó a valor contable cero por depreciación y deterioro. Evalúe "
                     "registrar su baja o revisar la vida útil de la especie.")
        if calculado < 0:
            self._avisar(activo, calculado)
        return {"id_deterioro_activo": id_deterioro, "valor_contable": costo.valor_contable_por_costo, "aviso": aviso,
                "valor_libros_calculado": calculado}

    def _avisar(self, activo, calculado: Decimal) -> None:
        if self.notificador is None:
            return
        try:
            self.notificador.a_contadores("ALERTA_FINANCIERA_NIC41", (
                f"El valor en libros del activo {activo.identificador} dio ${calculado:,.2f} (costo menos depreciación "
                "y deterioro) y se ajustó a $0.00. Evalúe registrar su baja."), {
                "id_activo_biologico": activo.id_activo_biologico, "valor_calculado": str(calculado),
                "valor_aplicado": "0"}, id_finca=activo.id_finca)
        except Exception:
            logger.exception("M06: no se pudo avisar el ajuste a cero del activo %s.", activo.id_activo_biologico)


def evento_valor_libros_cero(costo, calculado: Decimal, origen: str, id_activo_biologico: int, id_periodo: int,
                             id_referencia: Optional[int], id_usuario: Optional[int]) -> EventoAuditoria:
    """RF-88: alerta persistente del ajuste a cero (la usan el deterioro y la depreciación del cierre)."""
    return EventoAuditoria(
        tipo_evento="VALOR_LIBROS_AJUSTADO_A_CERO", severidad=Severidad.WARNING.value, id_usuario=id_usuario,
        payload={"origen": origen, "valor_calculado": str(calculado), "valor_aplicado": "0.0000",
                 "costo_adquisicion": str(costo.costos_adquisicion),
                 "depreciacion_acumulada": str(costo.depreciacion_acumulada),
                 "deterioro_acumulado": str(costo.deterioro_acumulado)},
        id_activo_biologico=id_activo_biologico, id_periodo_contable=id_periodo, id_referencia=id_referencia,
        monto_afectado=-calculado, metodo_nuevo="VALORACION_POR_COSTO",
    )
