# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-88 paso 5: deterioro de un activo valorado por costo (NIC 41 ¶30, ¶55) |
"""Caso de uso RF-88 paso 5: el Contador cuantifica el impacto económico de un evento sanitario de
RF-41 sobre un activo valorado por costo. RF-41 aporta el hecho clínico; M06, el monto."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.nic41 import CERO, truncar2
from src.financial_valuation.domain.value_objects.nic41 import Sentido, Severidad, TipoEvidencia, TipoHecho
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError
from src.shared.fechas import hoy_usuario


class RegistrarDeterioroUseCase:
    def __init__(self, db: Session, activos: ActivoFinancieroPort, valoraciones: ValoracionRepository,
                 contabilizador: Contabilizador) -> None:
        self.db = db
        self.activos = activos
        self.valoraciones = valoraciones
        self.contabilizador = contabilizador

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
            costo.valor_contable_por_costo = max(CERO, costo.costos_adquisicion - costo.depreciacion_acumulada
                                                 - costo.deterioro_acumulado)
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
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        aviso = None
        if costo.valor_contable_por_costo <= 0:  # FA-1
            aviso = (f"El activo {activo.identificador} llegó a valor contable cero por depreciación y deterioro. Evalúe "
                     "registrar su baja o revisar la vida útil de la especie.")
        return {"id_deterioro_activo": id_deterioro, "valor_contable": costo.valor_contable_por_costo, "aviso": aviso}
