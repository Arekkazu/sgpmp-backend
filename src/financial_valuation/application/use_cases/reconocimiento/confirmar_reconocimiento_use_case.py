# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82: confirmar el reconocimiento inicial y generar sus líneas de asiento |
# | 2026-11-09 | destroyerban | INC-M06-318-G20 RF-84: log de auditoría del ajuste manual de costos de venta |
"""Caso de uso RF-82 pasos 7-9: el Contador confirma la propuesta y el reconocimiento queda inmutable.

Cada costo de venta sobrescrito a mano deja su log de ajuste (RF-84 R5, salida 3): ítem, valor
parametrizado original, valor manual, justificación, Contador y fecha."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.application.services.propuesta_reconocimiento import (
    RAZON_SIN_MERCADO,
    ProponedorReconocimiento,
    Propuesta,
)
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.entities.valoracion import ValoracionCosto
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.value_objects.nic41 import IndicadorValoracion, Severidad, TipoEvidencia
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

TABLA = "reconocimientos_iniciales"


class ConfirmarReconocimientoUseCase:
    def __init__(self, db: Session, activos: ActivoFinancieroPort, valoraciones: ValoracionRepository,
                 proponedor: ProponedorReconocimiento, contabilizador: Contabilizador) -> None:
        self.db = db
        self.activos = activos
        self.valoraciones = valoraciones
        self.proponedor = proponedor
        self.contabilizador = contabilizador

    def execute(self, id_activo_biologico: int, id_usuario: int, *, clasificacion: Optional[str] = None,
                costos_manuales: Optional[dict] = None, justificacion: Optional[str] = None) -> dict:
        activo = self.activos.obtener(id_activo_biologico)
        if activo is None:
            raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message="El activo biológico no existe.")
        existente = self.valoraciones.reconocimiento_confirmado(id_activo_biologico)
        if existente is not None:  # FA-1
            raise ConflictError(code="RECONOCIMIENTO_EXISTENTE", message=(
                f"El activo ya fue reconocido el {existente.fecha_reconocimiento:%Y-%m-%d} por "
                f"{existente.valor_razonable_neto_inicial:,.2f} COP."))
        propuesta = self.proponedor.proponer(activo, id_usuario, costos_manuales=costos_manuales,
                                             justificacion=justificacion, clasificacion=clasificacion)
        if not propuesta.es_confirmable:
            self._auditar_bloqueo(propuesta, id_usuario)
            bloqueo = propuesta.bloqueos[0]
            raise BusinessRuleError(code=bloqueo["codigo"], message=bloqueo["mensaje"])
        try:
            resultado = self._registrar(propuesta, id_usuario, justificacion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return resultado

    def _registrar(self, propuesta: Propuesta, id_usuario: int, justificacion: Optional[str]) -> dict:
        activo = propuesta.activo
        periodo = self.contabilizador.periodo_para(activo.numero_id_tributaria, propuesta.fecha_reconocimiento, id_usuario)
        id_calculo = id_valoracion = None
        if propuesta.indicador_valoracion == IndicadorValoracion.VALOR_RAZONABLE.value:
            propuesta.calculo.id_periodo_contable = periodo.id_periodo_contable
            id_calculo = self.valoraciones.agregar_calculo(propuesta.calculo)
            self._auditar_ajustes(propuesta, id_calculo, periodo.id_periodo_contable, id_usuario, justificacion)
        else:
            id_valoracion = self.valoraciones.agregar_valoracion_costo(ValoracionCosto(
                id_activo_biologico=activo.id_activo_biologico, escenario_activacion="INICIAL_RF82",
                costos_adquisicion=propuesta.valor_inicial,
                tasa_depreciacion=(Decimal(1) / propuesta.vida_util_meses).quantize(Decimal("0.0001")),
                vida_util_meses=propuesta.vida_util_meses, fecha_adquisicion=activo.fecha_ingreso,
                depreciacion_acumulada=Decimal(0), deterioro_acumulado=Decimal(0),
                valor_contable_por_costo=propuesta.valor_inicial, razon_sin_mercado=RAZON_SIN_MERCADO,
                id_usuario=id_usuario, justificacion=justificacion,
            ))
        primera = propuesta.hechos[0] if propuesta.hechos else None
        cuenta = (self.contabilizador.config.resolver_cuenta(primera[0], primera[1], activo.id_especie, None)
                  if primera else None)
        id_reconocimiento = self.valoraciones.agregar_reconocimiento({
            "id_activo_biologico": activo.id_activo_biologico, "fecha_reconocimiento": propuesta.fecha_reconocimiento,
            "clasificacion": propuesta.clasificacion, "indicador_valoracion": propuesta.indicador_valoracion,
            "id_precio_mercado": propuesta.precio.id_precio_mercado if propuesta.precio else None,
            "valor_razonable_neto_inicial": propuesta.valor_inicial, "costos_venta_estimados": propuesta.costos_venta,
            "cuenta_debito": cuenta.cuenta_debito if cuenta else None,
            "cuenta_credito": cuenta.cuenta_credito if cuenta else None, "id_usuario": id_usuario,
            "id_periodo_contable": periodo.id_periodo_contable, "costo_adquisicion": activo.costo_adquisicion,
            "origen_financiero": activo.origen_financiero, "id_calculo_valor_razonable": id_calculo,
            "id_valoracion_por_costo": id_valoracion, "es_apertura": propuesta.es_apertura,
        })
        lineas = [self.contabilizador.asentar(LineaAsiento(
            tipo_hecho=tipo, sentido=sentido, valor=valor, fecha_hecho=propuesta.fecha_reconocimiento,
            id_periodo_contable=periodo.id_periodo_contable, id_activo_biologico=activo.id_activo_biologico,
            id_especie=activo.id_especie, id_finca=activo.id_finca, numero_id_tributaria=activo.numero_id_tributaria,
            tabla_origen=TABLA, id_origen=id_reconocimiento, tipo_evidencia=TipoEvidencia.REGISTRO_MANUAL.value,
            es_estimacion=bool(propuesta.calculo and propuesta.calculo.tiene_valor_estimado), id_usuario=id_usuario,
        ), id_usuario) for tipo, sentido, valor in propuesta.hechos]
        por_costo = propuesta.indicador_valoracion == IndicadorValoracion.VALORACION_POR_COSTO.value
        self.contabilizador.auditar(EventoAuditoria(
            tipo_evento="RECONOCIMIENTO_INICIAL", severidad=(Severidad.WARNING if por_costo else Severidad.INFO).value,
            payload={"indicador_valoracion": propuesta.indicador_valoracion, "valor_inicial": str(propuesta.valor_inicial),
                     "id_precio_mercado": propuesta.precio.id_precio_mercado if propuesta.precio else None,
                     "origen_financiero": activo.origen_financiero, "es_apertura": propuesta.es_apertura,
                     "clasificacion": propuesta.clasificacion, "advertencias": propuesta.advertencias,
                     "lineas": [ln.id_linea_asiento_nic41 for ln in lineas]},
            id_usuario=id_usuario, id_activo_biologico=activo.id_activo_biologico,
            id_periodo_contable=periodo.id_periodo_contable, id_referencia=id_reconocimiento,
            monto_afectado=propuesta.valor_inicial, metodo_nuevo=propuesta.indicador_valoracion,
        ))
        return {"id_reconocimiento_inicial": id_reconocimiento, "id_activo_biologico": activo.id_activo_biologico,
                "indicador_valoracion": propuesta.indicador_valoracion, "valor_inicial": propuesta.valor_inicial,
                "fecha_reconocimiento": propuesta.fecha_reconocimiento, "id_periodo_contable": periodo.id_periodo_contable,
                "es_apertura": propuesta.es_apertura, "advertencias": propuesta.advertencias,
                "lineas": [{"id_linea": ln.id_linea_asiento_nic41, "tipo_hecho": ln.tipo_hecho, "sentido": ln.sentido,
                            "valor": ln.valor, "cuenta_debito": ln.cuenta_debito, "cuenta_credito": ln.cuenta_credito,
                            "estado": ln.estado} for ln in lineas]}

    def _auditar_ajustes(self, propuesta: Propuesta, id_calculo: int, id_periodo: int, id_usuario: int,
                         justificacion: Optional[str]) -> None:
        """Un evento AJUSTE_MANUAL_COSTOS_VENTA por componente sobrescrito (RF-84 R5, salida 3)."""
        for ajuste in propuesta.ajustes_manuales:
            original = ajuste["valor_original"]
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="AJUSTE_MANUAL_COSTOS_VENTA", severidad=Severidad.INFO.value,
                payload={"item": ajuste["item"], "valor_original": str(original) if original is not None else None,
                         "metodo_original": "PARAMETRIZADO" if original is not None else "SIN_PARAMETRO",
                         "valor_manual": str(ajuste["valor_manual"]), "justificacion": justificacion,
                         "id_calculo_valor_razonable": id_calculo,
                         "id_parametro_costo_venta": propuesta.calculo.id_parametro_costo_venta},
                id_usuario=id_usuario, id_activo_biologico=propuesta.activo.id_activo_biologico,
                id_periodo_contable=id_periodo, id_referencia=id_calculo, monto_afectado=ajuste["valor_manual"],
                datos_anteriores={"item": ajuste["item"], "valor": str(original) if original is not None else None},
            ))

    def _auditar_bloqueo(self, propuesta: Propuesta, id_usuario: int) -> None:
        if not any(b["codigo"] == "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR" for b in propuesta.bloqueos):
            return
        try:  # FA-7: el bloqueo queda en RF-94 aunque la operación no prospere
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="RECONOCIMIENTO_BLOQUEADO_SIN_VALOR", severidad=Severidad.WARNING.value,
                payload={"bloqueos": propuesta.bloqueos}, id_usuario=id_usuario,
                id_activo_biologico=propuesta.activo.id_activo_biologico,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
