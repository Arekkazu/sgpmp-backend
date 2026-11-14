# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-COT v1.1: registrar una cotización de venta (sin efecto contable) |
# | 2026-11-08 | Arekkazu | INC-M06-332-G88 RF-COT FA-3: con el período de la emisión cerrado responde 422, no usa el siguiente |
"""Caso de uso RF-COT fases 1-6. La cotización no transfiere propiedad, no cambia el valor del activo
y no genera asientos ni documentos (RFC-018 D-18.8). Su valor de referencia es la suma del último
valor razonable neto de los activos (no se admite valor manual)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.cotizacion_repository import CotizacionRepository
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.nic41 import CERO
from src.shared.errors import BusinessRuleError, NotFoundError
from src.shared.fechas import hoy_usuario


class RegistrarCotizacionUseCase:
    def __init__(self, db: Session, cotizaciones: CotizacionRepository, activos: ActivoFinancieroPort,
                 valoraciones: ValoracionRepository, contabilizador: Contabilizador) -> None:
        self.db = db
        self.cotizaciones = cotizaciones
        self.activos = activos
        self.valoraciones = valoraciones
        self.contabilizador = contabilizador

    def execute(self, activos_cotizados: list[int], valor_propuesto: Decimal, condiciones: Optional[str],
                fecha_vencimiento: Optional[date], id_usuario: int) -> dict:
        hoy = hoy_usuario()
        if not activos_cotizados or len(set(activos_cotizados)) != len(activos_cotizados):
            raise BusinessRuleError(code="ACTIVO_NO_DISPONIBLE", message="Indique los activos cotizados sin repetirlos.")
        if valor_propuesto <= 0:  # FA-6
            raise BusinessRuleError(code="VALOR_COTIZACION_INVALIDO", message="El valor propuesto debe ser mayor a cero.")
        if fecha_vencimiento is not None and fecha_vencimiento < hoy:  # FA-5
            raise BusinessRuleError(code="FECHA_VENCIMIENTO_INVALIDA",
                                    message="El vencimiento no puede ser anterior a la fecha de emisión.")
        referencia, titular = CERO, set()
        for id_activo in activos_cotizados:
            activo = self.activos.obtener(id_activo)
            if activo is None:
                raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message=f"El activo {id_activo} no existe.")
            if activo.estado != "ACTIVO" or self.valoraciones.reconocimiento_confirmado(id_activo) is None:  # FA-2
                raise BusinessRuleError(code="ACTIVO_NO_DISPONIBLE", message=(
                    f"El activo {activo.identificador} no está activo o no tiene reconocimiento inicial."))
            calculo = self.valoraciones.ultimo_calculo(id_activo)
            if calculo is None:  # FA-4
                raise BusinessRuleError(code="VALOR_RAZONABLE_NO_DISPONIBLE",
                                        message=f"El activo {activo.identificador} no tiene valor razonable vigente.")
            referencia += calculo.valor_neto
            titular.add(activo.numero_id_tributaria)
        if len(titular) > 1:
            raise BusinessRuleError(code="ACTIVO_NO_DISPONIBLE", message="Los activos de una cotización deben ser del mismo titular.")
        try:
            periodo = self.contabilizador.periodo_para(titular.pop(), hoy, id_usuario)
            if not periodo.contiene(hoy):  # FA-3: la emisión no se traslada al período siguiente
                raise BusinessRuleError(code="PERIODO_CONTABLE_CERRADO", message=(
                    f"El período contable de hoy ({hoy:%Y-%m}) está cerrado: no se pueden registrar cotizaciones en él."))
            id_cotizacion = self.cotizaciones.agregar({
                "fecha_emision": hoy, "id_periodo_contable": periodo.id_periodo_contable,
                "activos_cotizados": activos_cotizados, "valor_cotizacion_propuesto": valor_propuesto,
                "condiciones": condiciones, "fecha_vencimiento": fecha_vencimiento, "id_usuario": id_usuario,
                "valor_razonable_referencia": referencia,
            })
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="COTIZACION_REGISTRADA", severidad="INFO", id_usuario=id_usuario,
                payload={"activos": activos_cotizados, "valor_propuesto": str(valor_propuesto),
                         "valor_razonable_referencia": str(referencia)},
                id_periodo_contable=periodo.id_periodo_contable, id_referencia=id_cotizacion,
                monto_afectado=valor_propuesto,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_cotizacion": id_cotizacion, "valor_razonable_referencia": referencia, "estado": "COTIZADO",
                "id_periodo_contable": periodo.id_periodo_contable}
