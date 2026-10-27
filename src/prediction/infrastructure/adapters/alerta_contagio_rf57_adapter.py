# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
"""RF-68 paso 8 → RF-57: alerta RIESGO_CONTAGIO del lote en ``modulo3.alertas``.

Usa el repositorio de alertas de M03: la alerta entra al mismo ciclo que las demás
(historial por trigger, SLA, notificación y escalamiento). Una alerta del lote ya activa
se consolida (``frecuencia_evento``) en vez de duplicarse.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.riesgo_contagio import ResultadoRiesgoContagio
from src.prediction.domain.repositories.alerta_contagio_port import AlertaContagioPort
from src.telemetry.domain.entities.alerta import Alerta, EstadoAlerta, OrigenEventoAlerta, TipoAlerta
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository

_VARIABLE = "PROBABILIDAD_CONTAGIO"


class AlertaContagioRf57Adapter(AlertaContagioPort):

    def __init__(self, db: Session) -> None:
        self.db = db
        self.alertas = SqlAlchemyAlertaRepository(db)

    def area_del_lote(self, id_lote: int) -> Optional[int]:
        return self.db.execute(
            text("SELECT id_infraestructura FROM modulo2.activos_biologicos WHERE id_activo_biologico = :id"),
            {"id": id_lote},
        ).scalar_one_or_none()

    def emitir(self, resultado: ResultadoRiesgoContagio) -> int:
        ahora = datetime.now(timezone.utc)
        existente = self.db.execute(text(
            "SELECT id_alerta FROM modulo3.alertas WHERE tipo_alerta = 'RIESGO_CONTAGIO' "
            "AND id_activo_biologico = :lote AND estado_alerta IN ('ACTIVA', 'EN_ATENCION') "
            "ORDER BY fecha_generacion DESC LIMIT 1 FOR UPDATE"
        ), {"lote": resultado.id_lote}).scalar_one_or_none()
        if existente is not None:
            self.alertas.actualizar_deduplicacion(id_alerta=existente, ultima_ocurrencia=ahora)
            return existente

        alerta = Alerta(
            tipo_alerta=TipoAlerta.RIESGO_CONTAGIO,
            severidad="CRITICO",
            estado_alerta=EstadoAlerta.ACTIVA,
            origen_evento=OrigenEventoAlerta.IA,
            tipo_variable=_VARIABLE,
            fecha_evento=resultado.fecha_calculo,
            fecha_generacion=ahora,
            reglas_activas=[{"id": resultado.id_configuracion_motor, "nombre": "MODELO_RIESGO_CONTAGIO_ALTO",
                             "config_version": resultado.config_version}],
            valor=resultado.probabilidad_contagio,
            id_activo_biologico=resultado.id_lote,
            id_infraestructura=resultado.id_area_productiva,
            accion_sugerida="Evaluar protocolo de cuarentena o bioseguridad del lote.",
            metadato_evento={
                "id_resultado_contagio": resultado.id_resultado_contagio,
                "probabilidad_contagio": str(resultado.probabilidad_contagio),
                "factores": {k: str(v) if v is not None else None for k, v in (
                    ("fs", resultado.factor_sanitario), ("fa", resultado.factor_ambiental),
                    ("fd", resultado.factor_densidad))},
                "data_quality_score": str(resultado.data_quality_score),
            },
        )
        alerta.fecha_vencimiento = alerta.calcular_fecha_vencimiento()
        return self.alertas.guardar(alerta).id_alerta
