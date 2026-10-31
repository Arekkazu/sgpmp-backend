# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 T-18 RF-66: nombre de cada patología de la distribución |
# | 2026-10-30 | Arekkazu | RF-66: modo_sombra del resultado                                   |
"""Read-models del monitor de predicción (RF-66) y del riesgo de contagio (RF-68).

El monitor y la pestaña de contagio pintaban datos simulados (monitorMock.ts,
contagioMock.ts). La inferencia la ejecuta el motor de IoT/IA y queda en
``modulo4.resultados_inferencia``; el contagio, ``POST /prediccion/riesgo-contagio``.
Aquí solo se leen, con los nombres que la pantalla necesita.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class InferenciaMonitor:
    id_resultado_inferencia: uuid.UUID
    id_activo_biologico: int
    identificador_activo: Optional[str]
    nombre_area: str
    nombre_finca: str
    especie: Optional[str]
    tipo_modelo: str
    id_version_modelo: int
    nombre_version: Optional[str]
    nivel_riesgo: int
    probabilidad_riesgo: dict
    id_patologia: Optional[int]
    nombre_patologia: Optional[str]
    probabilidad_enfermedad: dict
    confianza_global: Decimal
    contexto_incompleto: bool
    latencia_excedida: bool
    modo_ejecucion: str
    latencia_ms: Optional[int]
    fecha_inicio_ventana: Optional[datetime]
    fecha_fin_ventana: Optional[datetime]
    fecha_inferencia: datetime
    tiene_alerta_generada: bool
    id_alerta_generada: Optional[int]
    modo_sombra: bool
    # T-18: probabilidad_enfermedad viene por id_patologia ("8"); su nombre para mostrarlo.
    nombres_patologias: Optional[dict] = None


@dataclass(frozen=True)
class RiesgoContagioMonitor:
    id_resultado_contagio: int
    id_activo_biologico: int
    identificador_activo: Optional[str]
    nombre_area: str
    nombre_finca: str
    especie: Optional[str]
    probabilidad_contagio: Decimal
    nivel_riesgo_contagio: int
    factor_sanitario_fs: Decimal
    factor_ambiental_fa: Optional[Decimal]
    factor_densidad_fd: Optional[Decimal]
    w_fs_aplicado: Decimal
    w_fa_aplicado: Decimal
    w_fd_aplicado: Decimal
    confianza_baja: bool
    data_quality_score: Optional[Decimal]
    factores_ausentes: Optional[list]
    modo_ejecucion_calculo: Optional[str]
    n_enfermos_detectados: Optional[int]
    total_activos_lote: Optional[int]
    porcentaje_sensores_activos: Optional[Decimal]
    fecha_calculo: datetime
    id_alerta_generada: Optional[int]
    # Trazabilidad del cálculo (definicion_fs, motivos_degradacion, config_version, id_alerta_rf57...).
    detalle_calculo: Optional[dict]
