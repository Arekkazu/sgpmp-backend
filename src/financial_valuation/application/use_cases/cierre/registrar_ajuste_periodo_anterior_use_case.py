# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | INC-M06-351-G45 RF-87 CA-14: ajuste de un hecho de un período cerrado |
"""Caso de uso RF-87 v1.1 (CA-14): corrige un hecho de un período CERRADO sin tocarlo. Registra una
línea ``AJUSTE_PERIODO_ANTERIOR`` en el período abierto del titular, con referencia a la línea
original (``id_linea_corregida``) y justificación en RF-94. ``DISMINUIR`` usa el par de cuentas
invertido (RF-86: nunca valores negativos); ``AUMENTAR`` repite el par de la original."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.value_objects.nic41 import ETIQUETA_HECHO, EstadoPeriodo, Severidad, TipoEvidencia, TipoHecho
from src.shared.errors import BusinessRuleError, NotFoundError
from src.shared.fechas import hoy_usuario


class RegistrarAjustePeriodoAnteriorUseCase:
    def __init__(self, db: Session, contabilizador: Contabilizador) -> None:
        self.db = db
        self.contabilizador = contabilizador

    def execute(self, id_linea: int, tipo_ajuste: str, valor: Decimal, justificacion: str, id_usuario: int) -> dict:
        asientos, periodos = self.contabilizador.asientos, self.contabilizador.periodos
        try:
            original = asientos.obtener(id_linea)
            if original is None:
                raise NotFoundError(code="LINEA_ASIENTO_NO_ENCONTRADA", message="La línea de asiento no existe.")
            if original.tipo_hecho == TipoHecho.AJUSTE_PERIODO_ANTERIOR.value:
                raise BusinessRuleError(code="AJUSTE_SOBRE_AJUSTE", field="id_linea", message=(
                    "Esta línea ya es un ajuste. Ajuste el hecho original al que se refiere."))
            cerrado = periodos.obtener(original.id_periodo_contable)
            if cerrado.estado != EstadoPeriodo.CERRADO.value:
                raise BusinessRuleError(code="AJUSTE_SOLO_PERIODO_CERRADO", field="id_linea", message=(
                    f"El período {cerrado.fecha_inicio:%Y-%m} sigue abierto: corrija el registro original."))
            disminuye = tipo_ajuste == "DISMINUIR"
            vigente = original.valor + sum((-a.valor if a.es_reverso != original.es_reverso else a.valor)
                                           for a in asientos.ajustes_de(id_linea))
            if disminuye and valor > vigente:
                raise BusinessRuleError(code="AJUSTE_SUPERA_VALOR", field="valor", message=(
                    f"El ajuste ({valor}) supera el valor vigente del hecho ({vigente})."))
            hoy = hoy_usuario()
            abierto = self.contabilizador.periodo_para(original.numero_id_tributaria, hoy, id_usuario)
            linea = LineaAsiento(
                tipo_hecho=TipoHecho.AJUSTE_PERIODO_ANTERIOR.value, tipo_hecho_corregido=original.tipo_hecho,
                sentido=original.sentido, valor=valor, fecha_hecho=hoy, id_periodo_contable=abierto.id_periodo_contable,
                id_activo_biologico=original.id_activo_biologico, id_especie=original.id_especie, id_finca=original.id_finca,
                numero_id_tributaria=original.numero_id_tributaria, tabla_origen="lineas_asiento_nic41", id_origen=id_linea,
                tipo_evidencia=TipoEvidencia.REGISTRO_MANUAL.value, subtipo_costo=original.subtipo_costo,
                es_reverso=original.es_reverso != disminuye, id_linea_corregida=id_linea, justificacion=justificacion,
                id_usuario=id_usuario,
            )
            if original.cuenta_debito and original.cuenta_credito:  # mismo par que el hecho corregido
                linea.cuenta_debito, linea.cuenta_credito = original.cuenta_debito, original.cuenta_credito
                if disminuye:
                    linea.cuenta_debito, linea.cuenta_credito = linea.cuenta_credito, linea.cuenta_debito
                linea.estado = "REGISTRADA"
            guardada = self.contabilizador.asentar(linea, id_usuario)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="LINEA_ASIENTO_REGISTRADA", severidad=Severidad.INFO.value, id_usuario=id_usuario,
                payload={"ajuste_periodo_anterior": True, "tipo_ajuste": tipo_ajuste, "id_linea_corregida": id_linea,
                         "periodo_corregido": f"{cerrado.fecha_inicio:%Y-%m}", "justificacion": justificacion},
                id_activo_biologico=original.id_activo_biologico, id_periodo_contable=abierto.id_periodo_contable,
                id_referencia=guardada.id_linea_asiento_nic41, monto_afectado=valor,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_linea_asiento_nic41": guardada.id_linea_asiento_nic41, "id_linea_corregida": id_linea,
                "hecho_corregido": ETIQUETA_HECHO.get(original.tipo_hecho, "Hecho contable"), "tipo_ajuste": tipo_ajuste,
                "valor": valor, "estado": guardada.estado, "id_periodo_contable": abierto.id_periodo_contable,
                "periodo": f"{abierto.fecha_inicio:%Y-%m}", "periodo_corregido": f"{cerrado.fecha_inicio:%Y-%m}"}
