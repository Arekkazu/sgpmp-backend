"""Adaptador para generar la alerta de conversión alimenticia crítica (RF-74 / CA-3).

Inserta una alerta ``CONVERSION_ALIMENTICIA`` / ``CRITICO`` en ``modulo3.alertas``
mediante SQL directo (mismo patrón que ``evento_sanitario_m02_adapter``). Se evita el
modelo ORM ``AlertaModel`` de telemetría porque arrastra FKs cross-module cuya
resolución de metadatos acopla este módulo al registro de otro. Usa ``flush()`` — la
notificación push/email real ocurre después del ``commit`` en otra capa.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.repositories.alerta_ica_port import AlertaICAPort

_TIPO_ALERTA = "CONVERSION_ALIMENTICIA"
_SEVERIDAD = "CRITICO"
_TIPO_VARIABLE = "conversion_alimenticia"
_ACCION_SUGERIDA = (
    "Revisar dieta, calidad del alimento y estado sanitario del activo: "
    "la conversión alimenticia es crítica."
)

_INSERT = text(
    """
    INSERT INTO modulo3.alertas (
        tipo_alerta, severidad, estado_alerta, origen_evento, tipo_variable,
        valor, reglas_activas, metadato_evento, accion_sugerida,
        id_activo_biologico, fecha_evento, fecha_generacion
    ) VALUES (
        CAST(:tipo AS modulo3.enum_tipo_alerta),
        CAST(:severidad AS modulo3.enum_buffer_nivel_severidad),
        CAST('ACTIVA' AS modulo3.enum_estado_alerta),
        CAST(:origen AS modulo3.enum_origen_evento_alerta),
        :tipo_variable,
        :valor,
        CAST('[]' AS jsonb),
        CAST(:metadato AS jsonb),
        :accion,
        :id_activo,
        :fecha_evento,
        :fecha_generacion
    )
    RETURNING id_alerta
    """
)


class AlertaICAM03Adapter(AlertaICAPort):
    """Persiste alertas críticas de ICA en ``modulo3.alertas`` (SQL directo)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def generar_alerta_critica(
        self,
        *,
        id_activo_biologico: int,
        ca_calculado: Decimal,
        periodo_evaluacion: str,
        origen_evento: str,
        fecha_evento: datetime,
    ) -> Optional[int]:
        ahora = datetime.now(timezone.utc)
        metadato = json.dumps(
            {"periodo_evaluacion": periodo_evaluacion, "regla": "CA > 5.0 (CRITICA)"}
        )
        try:
            row = self.db.execute(
                _INSERT,
                {
                    "tipo": _TIPO_ALERTA,
                    "severidad": _SEVERIDAD,
                    "origen": origen_evento,
                    "tipo_variable": _TIPO_VARIABLE,
                    "valor": ca_calculado,
                    "metadato": metadato,
                    "accion": _ACCION_SUGERIDA,
                    "id_activo": id_activo_biologico,
                    "fecha_evento": fecha_evento,
                    "fecha_generacion": ahora,
                },
            ).fetchone()
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})
        return row.id_alerta if row else None
