"""RF-40: el trigger ``trg_fn_evento_crecimiento_tipo_activo`` cumple el contrato del DTO.

La migración ``543cddec52a7`` corrige tres desincronizaciones entre el trigger y
``RegistrarEventoCrecimientoDTO``:

1. PESO acepta ``gr`` (antes el trigger solo aceptaba ``kg``, ``g``, ``lb``).
2. BIOMASA exige ``kg/m2`` (antes no validaba ninguna unidad).
3. La rama de ``tipo_agregacion`` obligatorio para activos POBLACIONAL compara
   contra ``'POBLACIONAL'`` (antes comparaba contra ``'poblacional'``, minúscula,
   y nunca se ejecutaba).

Estas pruebas requieren una base de integración con la migración aplicada
(``alembic upgrade head``). Si la base está en una revisión anterior fallan hasta
aplicar la migración — ese es el guard esperado.
"""
from __future__ import annotations

import random
import string
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


def _sid() -> int:
    return uuid.uuid4().int % (10**9)


def _letras(n: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters, k=n))


def _setup(
    db_session,
    crear_usuario_db,
    tipo_activo: str,
) -> tuple[int, dict[str, int]]:
    """Crea usuario, finca, infraestructura, catálogo de estado y un activo sintético.

    Devuelve ``(id_activo, datos)`` con los ids auxiliares necesarios para insertar
    eventos. Todo queda dentro de la transacción exterior de la prueba y se revierte.
    """
    sid = _sid()
    usuario = crear_usuario_db()

    db_session.execute(text("SET app.usuario_id = :uid"), {"uid": str(usuario['id_usuario'])})

    db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h,
                fecha_actualizacion, fecha_creacion, es_activo)
            VALUES (:id_finca, :nombre, '{}', 10, now(), now(), TRUE)
            """
        ),
        {"id_finca": sid, "nombre": f"Finca Integracion {_letras()}"},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca,
                superficie, es_activo, tipo)
            VALUES (:id_infra, :nombre, :id_finca, 100, TRUE, 'Estanque')
            """
        ),
        {"id_infra": sid, "nombre": f"Infra Integracion {_letras()}", "id_finca": sid},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
            VALUES (1, 'ACTIVO')
            ON CONFLICT (id_estado_activo_biologico) DO NOTHING
            """
        ),
    )
    id_activo = sid
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie,
                identificador, id_infraestructura, tipo, fecha_inicio_ciclo, id_estado,
                descripcion, origen_financiero, costo_adquisicion, atributos_dinamicos,
                id_usuario, fecha_creacion, id_dispositivo_iot, soporte_documental,
                detalles_procedencia)
            VALUES (:id_activo, :id_especie, :identificador, :id_infra, :tipo,
                current_date, 1, '', 'compra', 100, '{}', :id_usuario,
                now() - interval '1 hour', 0, 'doc', '')
            """
        ),
        {
            "id_activo": id_activo,
            "id_especie": 2,
            "identificador": f"RF40-{sid}" if tipo_activo == 'INDIVIDUAL' else None,
            "id_infra": sid,
            "tipo": tipo_activo,
            "id_usuario": usuario['id_usuario'],
        },
    )
    if tipo_activo == 'POBLACIONAL':
        db_session.execute(
            text(
                """
                INSERT INTO modulo2.detalles_activos_biologicos_poblacionales
                    (id_detalle_activo_biologico_poblacional, id_activo_biologico,
                     cantidad_inicial, cantidad_actual)
                VALUES (:id_detalle, :id_activo, 10, 10)
                """
            ),
            {"id_detalle": sid, "id_activo": id_activo},
        )
    db_session.flush()
    return id_activo, {"sid": sid, "id_usuario": usuario['id_usuario']}


def _insertar_evento_crecimiento(
    db_session,
    id_activo: int,
    id_usuario: int,
    sid: int,
    *,
    tipo_medicion: str,
    valor_medicion,
    unidad_medida: str,
    tipo_agregacion: str | None = None,
) -> None:
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha, id_usuario)
            VALUES (:id_eventos, :id_activo, now(), :id_usuario)
            """
        ),
        {"id_eventos": sid, "id_activo": id_activo, "id_usuario": id_usuario},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_crecimeinto (id_evento, tipo_medicion,
                valor_medicion, unidad_medida, tipo_agregacion)
            VALUES (:id_evento, :tipo_medicion, :valor, :unidad, :tipo_agregacion)
            """
        ),
        {
            "id_evento": sid,
            "tipo_medicion": tipo_medicion,
            "valor": valor_medicion,
            "unidad": unidad_medida,
            "tipo_agregacion": tipo_agregacion,
        },
    )
    db_session.flush()


def test_peso_gr_sobre_individual_es_aceptado(db_session, crear_usuario_db) -> None:
    id_activo, datos = _setup(db_session, crear_usuario_db, 'INDIVIDUAL')

    _insertar_evento_crecimiento(
        db_session, id_activo, datos['id_usuario'], _sid(),
        tipo_medicion='PESO', valor_medicion=3.5, unidad_medida='gr',
    )

    total = db_session.execute(
        text("SELECT count(*) FROM modulo2.eventos_crecimeinto e JOIN modulo2.eventos_activos ev ON ev.id_eventos = e.id_evento WHERE ev.id_activo_biologico = :id"),
        {"id": id_activo},
    ).scalar_one()
    assert total == 1


def test_biomasa_kg_m2_sobre_individual_es_aceptado(db_session, crear_usuario_db) -> None:
    id_activo, datos = _setup(db_session, crear_usuario_db, 'INDIVIDUAL')

    _insertar_evento_crecimiento(
        db_session, id_activo, datos['id_usuario'], _sid(),
        tipo_medicion='BIOMASA', valor_medicion=1.5, unidad_medida='kg/m2',
    )


def test_biomasa_con_unidad_invalida_es_rechazado_p0218(db_session, crear_usuario_db) -> None:
    id_activo, datos = _setup(db_session, crear_usuario_db, 'INDIVIDUAL')

    with pytest.raises(DBAPIError, match='BIOMASA'):
        with db_session.begin_nested():
            _insertar_evento_crecimiento(
                db_session, id_activo, datos['id_usuario'], _sid(),
                tipo_medicion='BIOMASA', valor_medicion=1.5, unidad_medida='g',
            )


def test_poblacional_sin_tipo_agregacion_es_rechazado_p0216(db_session, crear_usuario_db) -> None:
    id_activo, datos = _setup(db_session, crear_usuario_db, 'POBLACIONAL')

    with pytest.raises(DBAPIError, match='tipo_agregacion'):
        with db_session.begin_nested():
            _insertar_evento_crecimiento(
                db_session, id_activo, datos['id_usuario'], _sid(),
                tipo_medicion='PESO', valor_medicion=3.5, unidad_medida='kg',
            )


def test_individual_con_tipo_agregacion_es_rechazado_p0216(db_session, crear_usuario_db) -> None:
    id_activo, datos = _setup(db_session, crear_usuario_db, 'INDIVIDUAL')

    with pytest.raises(DBAPIError, match='tipo_agregacion'):
        with db_session.begin_nested():
            _insertar_evento_crecimiento(
                db_session, id_activo, datos['id_usuario'], _sid(),
                tipo_medicion='PESO', valor_medicion=3.5, unidad_medida='kg',
                tipo_agregacion='PROMEDIO',
            )


def test_poblacional_con_tipo_agregacion_valido_es_aceptado(db_session, crear_usuario_db) -> None:
    id_activo, datos = _setup(db_session, crear_usuario_db, 'POBLACIONAL')

    _insertar_evento_crecimiento(
        db_session, id_activo, datos['id_usuario'], _sid(),
        tipo_medicion='PESO', valor_medicion=3.5, unidad_medida='kg',
        tipo_agregacion='PROMEDIO',
    )


def test_valor_no_positivo_es_rechazado_p0217(db_session, crear_usuario_db) -> None:
    id_activo, datos = _setup(db_session, crear_usuario_db, 'INDIVIDUAL')

    with pytest.raises(DBAPIError, match='positivo'):
        with db_session.begin_nested():
            _insertar_evento_crecimiento(
                db_session, id_activo, datos['id_usuario'], _sid(),
                tipo_medicion='PESO', valor_medicion=0, unidad_medida='kg',
            )
