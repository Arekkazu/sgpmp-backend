# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
# | 2026-10-30 | Leandro | INC-M04-221-G032 RF-68: exponer el perfil aplicado independientemente de la calidad de ejecución. |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.prediction.domain.entities.riesgo_contagio import ResultadoRiesgoContagio


class RiesgoContagioResponse(BaseModel):
    """RF-68 Salida."""
    id_resultado_contagio: Optional[int]
    id_lote_afectado: int
    id_area_productiva: Optional[int]
    probabilidad_contagio: Decimal
    nivel_riesgo_contagio: int
    nivel_riesgo_contagio_texto: str
    confianza_baja: bool
    modo_ejecucion: str
    perfil_calculo_contagio: str = "ESTANDAR"
    data_quality_score: Decimal
    definicion_fs: Optional[str]
    factor_sanitario: Optional[Decimal]
    factor_ambiental: Optional[Decimal]
    factor_densidad: Optional[Decimal]
    pesos_aplicados: dict[str, Decimal]
    factores_ausentes: list[str]
    motivos_degradacion: list[str]
    densidad_asumida: bool
    n_enfermos_detectados: Optional[int]
    total_activos_lote: Optional[int]
    config_version: Optional[int]
    timestamp_calculo: datetime
    alerta_id: Optional[int]
    desde_cache: bool

    @classmethod
    def from_resultado(cls, r: ResultadoRiesgoContagio) -> "RiesgoContagioResponse":
        return cls(
            id_resultado_contagio=r.id_resultado_contagio, id_lote_afectado=r.id_lote,
            id_area_productiva=r.id_area_productiva, probabilidad_contagio=r.probabilidad_contagio,
            nivel_riesgo_contagio=r.nivel_riesgo_contagio, nivel_riesgo_contagio_texto=r.nivel_texto,
            confianza_baja=r.confianza_baja, modo_ejecucion=r.modo_ejecucion,
            perfil_calculo_contagio=r.perfil_calculo_contagio,
            data_quality_score=r.data_quality_score, definicion_fs=r.definicion_fs,
            factor_sanitario=r.factor_sanitario, factor_ambiental=r.factor_ambiental,
            factor_densidad=r.factor_densidad, pesos_aplicados=r.pesos_aplicados,
            factores_ausentes=r.factores_ausentes, motivos_degradacion=r.motivos_degradacion,
            densidad_asumida=r.densidad_asumida, n_enfermos_detectados=r.n_enfermos_detectados,
            total_activos_lote=r.total_activos_lote, config_version=r.config_version,
            timestamp_calculo=r.fecha_calculo, alerta_id=r.alerta_id, desde_cache=r.desde_cache,
        )
