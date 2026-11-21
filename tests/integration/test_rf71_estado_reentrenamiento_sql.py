# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71: conteo de retroalimentaciones nuevas, contra PostgreSQL real |
"""``contar_nuevas_por_tipo_modelo`` contra PostgreSQL real: solo cuenta lo retroalimentado
después de la última versión del modelo, y cada resultado una vez aunque lo retroalimenten dos."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from src.shared.database import declarar_identidad_sistema
from src.prediction.infrastructure.repositories.retroalimentacion_clinica_repository import (
    SqlAlchemyRetroalimentacionClinicaRepository,
)
from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

pytestmark = pytest.mark.integration

#: Más tarde que cualquier versión existente: la versión sembrada es la última.
VERSION = datetime(2099, 1, 1, tzinfo=timezone.utc)
TIPOS = ["MODELO_ESPECIES_GRANDES", "MODELO_ESPECIES_MEDIANAS"]


def test_cuenta_solo_lo_nuevo_y_una_vez_por_resultado(db_session, crear_usuario_db):
    db = db_session
    repo = SqlAlchemyRetroalimentacionClinicaRepository(db)
    usuario = crear_usuario_db(id_rol=3)["id_usuario"]
    db.execute(text("SET LOCAL session_replication_role = replica"))
    _, _, activo = _finca_con_activo(db, usuario)
    declarar_identidad_sistema(db)
    medianas_antes = repo.contar_nuevas_por_tipo_modelo(TIPOS)["MODELO_ESPECIES_MEDIANAS"][0]
    db.execute(text("SET LOCAL session_replication_role = replica"))
    db.execute(text(
        "INSERT INTO modulo4.versiones_modelos (nombre_version, tipo_modelo, estado_version, fecha_entrenamiento) "
        "VALUES (:n, 'MODELO_ESPECIES_GRANDES', 'APROBADO', :f)"), {"n": f"rf71-{uuid.uuid4().hex[:6]}", "f": VERSION})

    def resultado(tipo):
        return db.execute(text(
            "INSERT INTO modulo4.resultados_inferencia (id_resultado_inferencia, id_activo_biologico, id_especie, "
            "tipo_modelo, id_version_modelo, nivel_riesgo, probabilidad_riesgo, probabilidad_enfermedad, "
            "confianza_global, modo_ejecucion, fecha_inferencia) VALUES (gen_random_uuid(), :a, 1, "
            "CAST(:t AS modulo4.enum_tipo_modelo), 1, 2, '{}', '{}', 0.9, 'SERVIDOR', :f) "
            "RETURNING id_resultado_inferencia"), {"a": activo, "t": tipo, "f": VERSION}).scalar_one()

    def retro(id_resultado, cuando, vet):
        db.execute(text(
            "INSERT INTO modulo4.retroalimentaciones_clinicas (id_resultado_inferencia, id_activo_biologico, "
            "estado_retroalimentacion, id_usuario_veterinario, fecha_retroalimentacion) "
            "VALUES (:r, :a, 'CORRECTO', :v, :f)"), {"r": id_resultado, "a": activo, "v": vet, "f": cuando})

    nuevo = resultado("MODELO_ESPECIES_GRANDES")
    retro(nuevo, VERSION + timedelta(days=1), 1)
    retro(nuevo, VERSION + timedelta(days=2), 2)        # segundo veterinario: mismo resultado
    retro(resultado("MODELO_ESPECIES_GRANDES"), VERSION - timedelta(days=1), 1)  # antes de la versión
    retro(resultado("MODELO_ESPECIES_MEDIANAS"), VERSION, 1)
    db.execute(text("SET LOCAL session_replication_role = origin"))
    declarar_identidad_sistema(db)

    conteos = repo.contar_nuevas_por_tipo_modelo(TIPOS)
    assert conteos["MODELO_ESPECIES_GRANDES"] == (1, VERSION)
    assert conteos["MODELO_ESPECIES_MEDIANAS"][0] == medianas_antes + 1
