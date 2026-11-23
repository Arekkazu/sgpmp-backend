# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-106: TVCO global del modelo y aviso a los Administradores |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador de :class:`TasaValidacionPort`: calcula la TVCO global con las retroalimentaciones de M04 y avisa a los
Administradores por la bandeja (evento tipo 45 por destinatario, mismo patrón que los avisos de M06)."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.reporting.application.use_cases.historial.vigilar_degradacion_modelo_use_case import TasaValidacionPort

logger = logging.getLogger(__name__)

_TIPO = "DEGRADACION_MODELO_PREDICTIVO"
_ID_CANAL_INTERNO = 2
# Por inferencia: conflicto si tiene valoraciones distintas; validada si tiene una sola (R6 de RF-106).
_SQL_TVCO = text("""
    SELECT count(*) FILTER (WHERE x.valoraciones = 1) AS validadas,
           count(*) FILTER (WHERE x.valoraciones = 1 AND x.correcta) AS correctas
    FROM (
        SELECT rc.id_resultado_inferencia, count(DISTINCT rc.estado_retroalimentacion) AS valoraciones,
               bool_and(rc.estado_retroalimentacion::text = 'CORRECTO') AS correcta
        FROM modulo4.retroalimentaciones_clinicas rc
        WHERE rc.fecha_retroalimentacion >= now() - make_interval(days => :dias)
          AND COALESCE(rc.estado_registro, 'VALIDO') NOT IN ('ANULADO', 'ANULADA')
        GROUP BY rc.id_resultado_inferencia
    ) x
""")
_SQL_UMBRAL = text("SELECT COALESCE(valor_actual, valor_por_defecto) FROM modulo4.parametros_mlops "
                   "WHERE nombre_parametro = 'umbral_tvco_degradacion'")
_SQL_AVISADO = text("""
    SELECT EXISTS (SELECT 1 FROM modulo1.eventos e JOIN modulo1.tipos_eventos t ON t.id_tipo_evento = e.tipo_evento
                   WHERE t.nombre = :tipo AND e.fecha_evento >= now() - interval '1 day')
""")
_SQL_ADMINISTRADORES = text("""
    SELECT u.id_usuario FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
    WHERE r.es_protegido AND u.correo_electronico <> 'servicio.sistema@sgpmp.local'
""")
_SQL_TIPO = text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = :n")


class TasaValidacionM04Adapter(TasaValidacionPort):
    """Sesión aparte como sistema: corre después del commit de la retroalimentación."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def _leer(self, consulta, params: Optional[dict] = None):
        db = self.session_factory()
        try:
            return db.execute(consulta, params or {}).first()
        finally:
            db.close()

    def tvco_global(self, dias: int) -> tuple[Optional[float], int]:
        """Calcula la tasa de validación global de los últimos días."""
        fila = self._leer(_SQL_TVCO, {"dias": dias})
        validadas = fila.validadas or 0
        return (round(fila.correctas / validadas * 100, 2) if validadas else None), validadas

    def umbral(self) -> Optional[float]:
        """Umbral configurado de la tasa de validación, o ``None``."""
        fila = self._leer(_SQL_UMBRAL)
        return float(fila[0]) if fila and fila[0] is not None else None

    def avisado_hoy(self) -> bool:
        """Indica si ya se avisó hoy la degradación."""
        return bool(self._leer(_SQL_AVISADO, {"tipo": _TIPO})[0])

    def avisar_administradores(self, mensaje: str, detalle: dict) -> None:
        """Registra el evento y notifica a los administradores."""
        db = self.session_factory()
        try:
            id_tipo = db.execute(_SQL_TIPO, {"n": _TIPO}).scalar()
            if id_tipo is None:
                return
            eventos, notificaciones = SqlAlchemyEventoRepository(db), SqlAlchemyNotificacionRepository(db)
            for (id_usuario,) in db.execute(_SQL_ADMINISTRADORES).all():
                id_evento = eventos.registrar(tipo_evento=id_tipo, exitoso=True, id_usuario=id_usuario, detalle=detalle,
                                              descripcion="Degradación del modelo de predicción", modulo="MODULO8")
                notificaciones.registrar(id_evento=id_evento, id_usuario=id_usuario, id_canal=_ID_CANAL_INTERNO,
                                         mensaje=mensaje, estado="en_cola", contexto={"url": "prediccion"})
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("RF-106: no se pudo avisar la degradación del modelo.")
        finally:
            db.close()
