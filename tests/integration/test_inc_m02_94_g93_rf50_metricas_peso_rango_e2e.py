"""[INC-M02-94-G93][RF-50] Prueba de integración de
`SqlAlchemyIndicadoresRepository.existen_metricas_peso_en_rango` contra
Postgres real: un evento de crecimiento PESO dentro del rango solicitado
debe contarse; uno fuera del rango (u otro tipo_medicion) no debe contarse.
"""
from __future__ import annotations

import random
import string
import uuid

import pytest
from sqlalchemy import text

from src.biological_assets.infrastructure.repositories.indicadores_repository import (
    SqlAlchemyIndicadoresRepository,
)

pytestmark = pytest.mark.integration


def _sid() -> int:
    return uuid.uuid4().int % (10**9)


def _letras(n: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters, k=n))


def _crear_activo_individual(db_session, crear_usuario_db) -> int:
    sid = _sid()
    usuario = crear_usuario_db()
    db_session.execute(text("SET app.usuario_id = :uid"), {"uid": str(usuario["id_usuario"])})
    db_session.execute(
        text(
            "INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h, "
            "fecha_actualizacion, fecha_creacion, es_activo) "
            "VALUES (:id_finca, :nombre, '{}', 10, now(), now(), TRUE)"
        ),
        {"id_finca": sid, "nombre": f"Finca Integracion {_letras()}"},
    )
    db_session.execute(
        text(
            "INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca, "
            "superficie, es_activo, tipo) VALUES (:id, :nombre, :id_finca, 100, TRUE, 'Estanque')"
        ),
        {"id": sid, "nombre": f"Infra Integracion {_letras()}", "id_finca": sid},
    )
    db_session.execute(
        text(
            "INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre) "
            "VALUES (1, 'ACTIVO') ON CONFLICT (id_estado_activo_biologico) DO NOTHING"
        )
    )
    db_session.execute(
        text(
            "INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie, "
            "identificador, id_infraestructura, tipo, fecha_inicio_ciclo, id_estado, "
            "descripcion, origen_financiero, costo_adquisicion, atributos_dinamicos, "
            "id_usuario, fecha_creacion, id_dispositivo_iot, soporte_documental, detalles_procedencia) "
            "VALUES (:id, 2, :identificador, :id, 'INDIVIDUAL', DATE '2026-01-01', 1, '', 'compra', "
            "100, '{}', :id_usuario, TIMESTAMPTZ '2026-01-01', 0, 'doc', '')"
        ),
        {"id": sid, "identificador": f"RF50-{sid}", "id_usuario": usuario["id_usuario"]},
    )
    db_session.flush()
    return sid


def _insertar_evento_crecimiento(
    db_session, id_activo: int, fecha: str, tipo_medicion: str, *, unidad_medida: str = 'kg'
) -> None:
    eid = _sid()
    db_session.execute(
        text(
            "INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha, id_usuario) "
            "SELECT :id_eventos, :id_activo, CAST(:fecha AS date), id_usuario FROM modulo2.activos_biologicos "
            "WHERE id_activo_biologico = :id_activo"
        ),
        {"id_eventos": eid, "id_activo": id_activo, "fecha": fecha},
    )
    db_session.execute(
        text(
            "INSERT INTO modulo2.eventos_crecimeinto (id_evento, tipo_medicion, valor_medicion, unidad_medida) "
            "VALUES (:id_evento, :tipo_medicion, 25, :unidad_medida)"
        ),
        {"id_evento": eid, "tipo_medicion": tipo_medicion, "unidad_medida": unidad_medida},
    )
    db_session.flush()


def test_peso_dentro_del_rango_se_detecta(db_session, crear_usuario_db) -> None:
    id_activo = _crear_activo_individual(db_session, crear_usuario_db)
    _insertar_evento_crecimiento(db_session, id_activo, '2026-07-15', 'PESO')

    repo = SqlAlchemyIndicadoresRepository(db_session)

    assert repo.existen_metricas_peso_en_rango(id_activo, None, None) is True
    from datetime import date
    assert repo.existen_metricas_peso_en_rango(id_activo, date(2026, 6, 1), date(2026, 8, 31)) is True


def test_peso_fuera_del_rango_no_se_detecta(db_session, crear_usuario_db) -> None:
    from datetime import date

    id_activo = _crear_activo_individual(db_session, crear_usuario_db)
    _insertar_evento_crecimiento(db_session, id_activo, '2026-09-10', 'PESO')

    repo = SqlAlchemyIndicadoresRepository(db_session)

    assert repo.existen_metricas_peso_en_rango(id_activo, date(2026, 6, 1), date(2026, 8, 31)) is False


def test_otro_tipo_medicion_no_cuenta_como_peso(db_session, crear_usuario_db) -> None:
    from datetime import date

    id_activo = _crear_activo_individual(db_session, crear_usuario_db)
    _insertar_evento_crecimiento(db_session, id_activo, '2026-07-15', 'TALLA', unidad_medida='cm')

    repo = SqlAlchemyIndicadoresRepository(db_session)

    assert repo.existen_metricas_peso_en_rango(id_activo, date(2026, 6, 1), date(2026, 8, 31)) is False
