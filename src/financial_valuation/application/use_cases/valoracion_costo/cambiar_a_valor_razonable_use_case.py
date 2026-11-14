# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-88 paso 9: paso del modelo de costo a valor razonable (NIC 41 ¶30, ¶56) |
# | 2026-11-05 | Arekkazu | M06: mensajes con rótulos legibles en vez de valores de enum |
"""Caso de uso RF-88 paso 9: cuando hay precio confiable, el activo pasa a valor razonable (¶30 lo
exige). La diferencia entre el valor por costo y el valor razonable neto va a resultados.

El paso contrario (valor razonable → costo, RF-88 escenario B) no existe: la NIC 41 ¶31 lo prohíbe
para activos ya medidos a valor razonable (contradicción C-1)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.nic41 import sentido_por_signo
from src.financial_valuation.domain.value_objects.nic41 import Severidad, TipoEvidencia, TipoHecho, estado_legible
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError
from src.shared.fechas import hoy_usuario


class CambiarAValorRazonableUseCase:
    def __init__(self, db: Session, activos: ActivoFinancieroPort, valoraciones: ValoracionRepository,
                 valorador: Valorador, contabilizador: Contabilizador) -> None:
        self.db = db
        self.activos = activos
        self.valoraciones = valoraciones
        self.valorador = valorador
        self.contabilizador = contabilizador

    def execute(self, id_activo_biologico: int, id_usuario: int) -> dict:
        activo = self.activos.obtener(id_activo_biologico)
        costo = self.valoraciones.valoracion_costo_activa(id_activo_biologico)
        if activo is None or costo is None:
            raise NotFoundError(code="VALORACION_COSTO_NO_ENCONTRADA", message="El activo no está valorado por costo.")
        if not activo.es_valorable:  # FA-4
            raise ConflictError(code="ACTIVO_NO_DISPONIBLE", message=f"El activo está {estado_legible(activo.estado)}.")
        hoy = hoy_usuario()
        try:
            periodo = self.contabilizador.periodo_para(activo.numero_id_tributaria, hoy, id_usuario)
            resultado = self.valorador.valorar(activo, hoy, periodo.id_periodo_contable, id_usuario)
            if not resultado.es_valido:  # FA-3
                raise BusinessRuleError(code="SIN_PRECIO_PARA_VALOR_RAZONABLE", message=(
                    f"No es posible cambiar al valor razonable: {resultado.mensaje}"))
            id_calculo = self.valoraciones.agregar_calculo(resultado.calculo)
            diferencia = resultado.calculo.valor_neto - costo.valor_contable_por_costo
            signo = sentido_por_signo(diferencia)
            if signo is not None:
                self.contabilizador.asentar(LineaAsiento(
                    tipo_hecho=TipoHecho.VARIACION_VR_PM.value, sentido=signo[0].value, valor=signo[1], fecha_hecho=hoy,
                    id_periodo_contable=periodo.id_periodo_contable, id_activo_biologico=id_activo_biologico,
                    id_especie=activo.id_especie, id_finca=activo.id_finca, numero_id_tributaria=activo.numero_id_tributaria,
                    tabla_origen="valoraciones_por_costos", id_origen=costo.id_valoracion_por_costo,
                    tipo_evidencia=TipoEvidencia.VARIACION_PRECIO.value,
                    justificacion="Cambio del modelo de costo a valor razonable (NIC 41 ¶30)", id_usuario=id_usuario,
                ), id_usuario)
            costo.es_activa = False
            self.valoraciones.actualizar_valoracion_costo(costo)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="METODO_VALORACION_CAMBIADO", severidad=Severidad.WARNING.value, id_usuario=id_usuario,
                payload={"valor_por_costo": str(costo.valor_contable_por_costo),
                         "valor_razonable": str(resultado.calculo.valor_neto), "diferencia": str(diferencia),
                         "id_calculo_valor_razonable": id_calculo},
                id_activo_biologico=id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
                id_referencia=costo.id_valoracion_por_costo, monto_afectado=diferencia,
                metodo_anterior="VALORACION_POR_COSTO", metodo_nuevo="VALOR_RAZONABLE",
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_activo_biologico": id_activo_biologico, "valor_razonable": resultado.calculo.valor_neto,
                "valor_por_costo": costo.valor_contable_por_costo, "diferencia": diferencia}
