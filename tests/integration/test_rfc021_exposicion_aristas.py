# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021: aristas de RF-110 y exposición de RF-68 contra PostgreSQL real |
"""RF-110 + C21.4 contra PostgreSQL real, como usuario de servicio (el disparo de RF-68 corre así).

Tres áreas de una finca: el foco (2), una expuesta por AGUA dirigida (3) y otra por PROXIMIDAD
bidireccional (4). El foco tiene un contagio reciente con Fs = 1 y confianza normal.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.infrastructure.repositories.arista_transmision_repository import (
    SqlAlchemyAristaTransmisionRepository,
)
from src.prediction.infrastructure.adapters.exposicion_topologia_m09_adapter import ExposicionTopologiaM09Adapter
from src.shared.database import declarar_identidad_sistema
from src.shared.errors import ConflictError
from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

pytestmark = pytest.mark.integration


def _area_con_activo(db, id_finca, id_usuario):
    id_area = uuid.uuid4().int % 10**9
    db.execute(text("INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, superficie, "
                    "es_activo, tipo) VALUES (:a, :n, :f, 100, TRUE, 'Potrero')"),
               {"a": id_area, "n": f"Potrero {uuid.uuid4().hex[:8]}", "f": id_finca})
    id_activo = db.execute(text(
        "INSERT INTO modulo2.activos_biologicos (id_especie, identificador, id_infraestructura, tipo, "
        "fecha_inicio_ciclo, id_estado, descripcion, origen_financiero, costo_adquisicion, atributos_dinamicos, "
        "id_usuario, fecha_creacion, soporte_documental, detalles_procedencia) VALUES (2, :i, :a, 'INDIVIDUAL', "
        "current_date, 1, 'RFC-021', 'compra', 1, '{}', :u, now(), 'doc', '') RETURNING id_activo_biologico"),
        {"i": f"RFC021-{uuid.uuid4().hex[:10]}", "a": id_area, "u": id_usuario}).scalar_one()
    return id_area, id_activo


@pytest.fixture
def finca(db_session, crear_usuario_db):
    db = db_session
    usuario = crear_usuario_db(id_rol=3)["id_usuario"]
    db.execute(text("SET LOCAL session_replication_role = replica"))
    # El estado 1 (ACTIVO) es catálogo de M02: existe en DEV/TEST, no en una BD construida solo con Alembic.
    db.execute(text("INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre) "
                    "VALUES (1, 'ACTIVO') ON CONFLICT DO NOTHING"))
    id_finca, area_foco, activo_foco = _finca_con_activo(db, usuario)
    area_agua, activo_agua = _area_con_activo(db, id_finca, usuario)
    area_prox, activo_prox = _area_con_activo(db, id_finca, usuario)
    db.execute(text("""
        INSERT INTO modulo4.resultados_riesgo_contagio (id_activo_biologico, id_configuracion_motor, factor_sanitario_fs, factor_ambiental_fa,
            factor_densidad_fd, w_fs_aplicado, w_fa_aplicado, w_fd_aplicado, probabilidad_contagio,
            nivel_riesgo_contagio, confianza_baja, data_quality_score, factores_ausentes, modo_ejecucion_calculo,
            fecha_calculo)
        VALUES (:a, 1, 1, 0.3, 0.05, 0.5, 0.3, 0.2, 0.6, 1, false, 1, '[]', 'NORMAL', :f)
    """), {"a": activo_foco, "f": datetime.now(timezone.utc)})
    db.execute(text("SET LOCAL session_replication_role = origin"))
    declarar_identidad_sistema(db)
    return dict(usuario=usuario, foco=(area_foco, activo_foco), agua=(area_agua, activo_agua),
                prox=(area_prox, activo_prox))


def test_aristas_y_exposicion(db_session, finca):
    repo = SqlAlchemyAristaTransmisionRepository(db_session)
    area_foco, activo_foco = finca["foco"]
    area_agua, activo_agua = finca["agua"]
    area_prox, activo_prox = finca["prox"]
    repo.guardar(AristaTransmision(area_foco, area_agua, "AGUA", "DIRIGIDA", Decimal("0.6"), id_usuario=finca["usuario"]))
    repo.guardar(AristaTransmision(area_prox, area_foco, "PROXIMIDAD", "BIDIRECCIONAL", Decimal("0.8"),
                                   factor_barrera=Decimal("0.5"), id_usuario=finca["usuario"]))
    with pytest.raises(ConflictError):  # misma arista activa dos veces
        with db_session.begin_nested():
            repo.guardar(AristaTransmision(area_foco, area_agua, "AGUA", "DIRIGIDA", Decimal("0.3")))

    exposicion = ExposicionTopologiaM09Adapter(db_session)
    desde = datetime.now(timezone.utc) - timedelta(minutes=30)
    # El foco expone a las dos: la dirigida va origen → destino y la bidireccional en ambos sentidos.
    assert sorted(exposicion.lotes_expuestos(activo_foco)) == sorted([activo_agua, activo_prox])
    # La expuesta por agua ve al foco con w = 0,6; la de proximidad con w = 0,8 × 0,5.
    [foco_agua] = exposicion.focos_hacia(activo_agua, desde)
    assert (foco_agua.id_area, foco_agua.via, foco_agua.peso, foco_agua.factor_sanitario) == (
        area_foco, "AGUA", Decimal("0.6"), Decimal("1"))
    [foco_prox] = exposicion.focos_hacia(activo_prox, desde)
    assert (foco_prox.via, foco_prox.peso) == ("PROXIMIDAD", Decimal("0.400000"))
    # La dirigida no devuelve el contagio: el área de agua no expone al foco.
    assert exposicion.lotes_expuestos(activo_agua) == []

    assert len(repo.listar_activas_por_finca(area_foco)) == 2  # _finca_con_activo usa el mismo id
