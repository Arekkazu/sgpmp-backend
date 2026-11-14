# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-13 | Arekkazu | INC-M06-90-G97 RF-88: consulta de la depreciación lineal de un activo al costo |
"""Caso de uso RF-88 pasos 4-6: depreciación en línea recta de un activo valorado por costo a una fecha,
sin registrar nada (la registra cada cierre, paso 4.1).

La vida útil es la que quedó al reconocerlo al costo; un registro antiguo sin ella usa la de la
especie, como el cierre. Sin ninguna, RF-88 FA-2 responde 422."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.nic41 import meses_transcurridos, q4, valor_por_costo
from src.shared.errors import BusinessRuleError, NotFoundError


class ConsultarDepreciacionUseCase:
    def __init__(self, activos: ActivoFinancieroPort, valoraciones: ValoracionRepository,
                 config: ConfiguracionContableRepository) -> None:
        self.activos = activos
        self.valoraciones = valoraciones
        self.config = config

    def execute(self, id_activo_biologico: int, fecha: date) -> dict:
        activo = self.activos.obtener(id_activo_biologico)
        if activo is None:
            raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message="El activo biológico no existe.")
        costo = self.valoraciones.valoracion_costo_activa(id_activo_biologico)
        if costo is None:
            raise NotFoundError(code="VALORACION_COSTO_NO_ENCONTRADA", message=(
                f"El activo {activo.identificador} no está valorado por costo: se mide a valor razonable y no se deprecia."))
        parametro = self.config.parametro_especie(activo.id_especie)
        vida_util = costo.vida_util_meses or (parametro.vida_util_meses if parametro else None)
        if not vida_util:  # FA-2
            raise BusinessRuleError(code="VIDA_UTIL_NO_CONFIGURADA", message=(
                f"No se puede calcular la depreciación: la vida útil de la especie {activo.especie} no está configurada. "
                "Configúrela en Configuración contable."))
        meses = meses_transcurridos(costo.fecha_adquisicion, fecha)
        valor = valor_por_costo(costo.costos_adquisicion, vida_util, meses, costo.deterioro_acumulado)
        base = Decimal(costo.costos_adquisicion)
        return {
            "id_activo_biologico": id_activo_biologico, "identificador": activo.identificador, "especie": activo.especie,
            "metodo_depreciacion": "Línea recta", "costo_adquisicion": base, "vida_util_meses": vida_util,
            "depreciacion_mensual": q4(base / vida_util), "depreciacion_anual": q4(base * 12 / vida_util),
            "fecha_adquisicion": costo.fecha_adquisicion, "fecha_calculo": fecha, "meses_transcurridos": meses,
            "depreciacion_acumulada": valor.depreciacion_acumulada,
            "depreciacion_registrada": costo.depreciacion_acumulada,  # la que ya asentaron los cierres
            "deterioro_acumulado": valor.deterioro_acumulado, "valor_contable": valor.valor_contable,
            "totalmente_depreciado": valor.totalmente_depreciado,
        }
