"""RF-45: el trigger de baja reconoce el enum POBLACIONAL de PostgreSQL.

Requiere una base de integración actualizada con ``alembic upgrade head``.
Todas las filas se crean dentro de la transacción exterior de ``db_session``.
"""
from __future__ import annotations

import random
import string
import uuid

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.integration


def _id_temporal() -> int:
    return uuid.uuid4().int % (10**9)


def _nombre_temporal(prefijo: str) -> str:
    sufijo = ''.join(random.choices(string.ascii_letters, k=12))
    return f'{prefijo} {sufijo}'


def _crear_contexto(db_session, crear_usuario_db) -> tuple[int, int]:
    usuario = crear_usuario_db()
    sid = _id_temporal()
    tipo_infraestructura = db_session.execute(
        text(
            """
            SELECT tipo::text
            FROM modulo9.infraestructuras
            WHERE es_activo = true
            ORDER BY id_infraestructura
            LIMIT 1
            """
        )
    ).scalar_one()
    db_session.execute(
        text('SET LOCAL app.usuario_id = :uid'),
        {'uid': usuario['id_usuario']},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (
                id_finca, nombre, ubicacion, tamano_h,
                fecha_actualizacion, fecha_creacion, es_activo
            ) VALUES (:id, :nombre, '{}', 10, now(), now(), true)
            """
        ),
        {'id': sid, 'nombre': _nombre_temporal('Finca Prueba')},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (
                id_infraestructura, nombre, id_finca, superficie, es_activo, tipo
            ) VALUES (:id, :nombre, :id, 100, true, :tipo)
            """
        ),
        {
            'id': sid,
            'nombre': _nombre_temporal('Infra Prueba'),
            'tipo': tipo_infraestructura,
        },
    )
    return sid, usuario['id_usuario']


def _crear_activo(db_session, *, sid: int, usuario_id: int, tipo: str) -> int:
    id_activo = _id_temporal()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (
                id_activo_biologico, id_especie, identificador,
                id_infraestructura, tipo, fecha_inicio_ciclo, id_estado,
                descripcion, origen_financiero, costo_adquisicion,
                atributos_dinamicos, id_usuario, fecha_creacion,
                soporte_documental, detalles_procedencia
            ) VALUES (
                :id_activo, 2, :identificador, :id_infra, :tipo,
                current_date, 1, 'Integración RF45', 'compra', 100,
                '{}', :id_usuario, now() - interval '1 hour', 'doc', ''
            )
            """
        ),
        {
            'id_activo': id_activo,
            'identificador': f'RF45-{id_activo}' if tipo == 'INDIVIDUAL' else None,
            'id_infra': sid,
            'tipo': tipo,
            'id_usuario': usuario_id,
        },
    )
    if tipo == 'POBLACIONAL':
        db_session.execute(
            text(
                """
                INSERT INTO modulo2.detalles_activos_biologicos_poblacionales (
                    id_detalle_activo_biologico_poblacional,
                    id_activo_biologico, cantidad_inicial, cantidad_actual
                ) VALUES (:id, :id_activo, 5, 5)
                """
            ),
            {'id': _id_temporal(), 'id_activo': id_activo},
        )
    return id_activo


def _registrar_baja(
    db_session,
    *,
    id_activo: int,
    usuario_id: int,
    cantidad: int,
) -> None:
    id_evento = _id_temporal()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_activos (
                id_eventos, id_activo_biologico, fecha, id_usuario
            ) VALUES (:id_evento, :id_activo, now(), :id_usuario)
            """
        ),
        {
            'id_evento': id_evento,
            'id_activo': id_activo,
            'id_usuario': usuario_id,
        },
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_bajas (
                id_evento, cantidad_afectada, tipo, detalles
            ) VALUES (:id_evento, :cantidad, 'venta', 'Integración RF45')
            """
        ),
        {'id_evento': id_evento, 'cantidad': cantidad},
    )
    db_session.flush()


def test_baja_individual_no_intenta_convertir_literal_invalido(
    db_session,
    crear_usuario_db,
) -> None:
    sid, usuario_id = _crear_contexto(db_session, crear_usuario_db)
    id_activo = _crear_activo(
        db_session,
        sid=sid,
        usuario_id=usuario_id,
        tipo='INDIVIDUAL',
    )

    _registrar_baja(
        db_session,
        id_activo=id_activo,
        usuario_id=usuario_id,
        cantidad=1,
    )

    assert db_session.execute(
        text('SELECT count(*) FROM modulo2.eventos_bajas WHERE id_evento IN '
             '(SELECT id_eventos FROM modulo2.eventos_activos '
             ' WHERE id_activo_biologico = :id)'),
        {'id': id_activo},
    ).scalar_one() == 1


def test_baja_poblacional_actualiza_cantidad_del_lote(
    db_session,
    crear_usuario_db,
) -> None:
    sid, usuario_id = _crear_contexto(db_session, crear_usuario_db)
    id_activo = _crear_activo(
        db_session,
        sid=sid,
        usuario_id=usuario_id,
        tipo='POBLACIONAL',
    )

    _registrar_baja(
        db_session,
        id_activo=id_activo,
        usuario_id=usuario_id,
        cantidad=2,
    )

    cantidad = db_session.execute(
        text(
            """
            SELECT cantidad_actual
            FROM modulo2.detalles_activos_biologicos_poblacionales
            WHERE id_activo_biologico = :id
            """
        ),
        {'id': id_activo},
    ).scalar_one()
    assert cantidad == 3
