# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-21 | Arekkazu | INC-M08-390-G023 RF-106: la predicción pedida desde el historial entra siempre a la bandeja |
"""RF-106 CA-4 contra PostgreSQL real: «Registrar retroalimentación» del historial predictivo pide la bandeja con
``id_resultado_inferencia``. Una predicción de riesgo bajo no abre episodio ni tiene alerta, así que no entraba y
el formulario no se abría. Pedida por id entra, va primero y sigue sin entrar cuando no se pide."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from src.prediction.domain.entities.bandeja_retroalimentacion import FiltrosBandejaRetroalimentacion
from src.prediction.infrastructure.repositories.bandeja_retroalimentacion_repository import (
    SqlAlchemyBandejaRetroalimentacionRepository,
)
from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

pytestmark = pytest.mark.integration

AHORA = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def test_la_prediccion_pedida_entra_aunque_sea_de_riesgo_bajo(db_session, crear_usuario_db):
    db = db_session
    usuario = crear_usuario_db()["id_usuario"]
    db.execute(text("SET LOCAL session_replication_role = replica"))
    _, _, activo = _finca_con_activo(db, usuario)

    def inferencia(dias, nivel):
        return db.execute(text(
            "INSERT INTO modulo4.resultados_inferencia (id_resultado_inferencia, id_activo_biologico, id_especie, "
            "tipo_modelo, id_version_modelo, nivel_riesgo, probabilidad_riesgo, probabilidad_enfermedad, "
            "confianza_global, modo_ejecucion, fecha_inferencia) VALUES "
            "(gen_random_uuid(), :a, 1, 'MODELO_AVES', 1, :n, '{}', '{}', 0.9, 'SERVIDOR', :f) "
            "RETURNING id_resultado_inferencia"), {"a": activo, "n": nivel, "f": AHORA - timedelta(days=dias)}
        ).scalar_one()

    alta = inferencia(27, 3)
    baja = inferencia(33, 1)
    db.execute(text("SET LOCAL session_replication_role = origin"))
    repo = SqlAlchemyBandejaRetroalimentacionRepository(db)

    def bandeja(**kw):
        items, _, _ = repo.consultar(FiltrosBandejaRetroalimentacion(
            ids_fincas=None, desde=AHORA - timedelta(days=120), hasta=AHORA, ahora=AHORA, ventana_dias=90,
            id_usuario=usuario, id_activo_biologico=activo, **kw))
        return [i.id_resultado_inferencia for i in items]

    assert bandeja() == [alta]
    pedida = bandeja(id_resultado_inferencia=baja)
    assert pedida == [baja, alta]  # primero aunque la de riesgo alto sea más reciente: se pidió esa
