"""INC-M02-75-G53: `now()` fijo por transacción rechazaba eventos válidos.

`modulo2.trg_fn_evento_fecha_coherente` y el CHECK `chk_eventos_fecha_no_futura`
comparaban `NEW.fecha` contra `now()`, que en Postgres queda congelado al inicio
de la transacción. El caso de uso siempre abre la transacción con una consulta
previa (ej. `obtener_por_id` del activo) antes de calcular
`fecha = datetime.now(timezone.utc)`, así que `NEW.fecha` (reloj real, posterior)
terminaba siendo "futura" respecto al `now()` congelado aunque nunca lo fue en
tiempo real -> 500 en el primer evento (de cualquier tipo, no solo reproductivo)
de toda petición. La migración `68232a1efcc2` cambia ambos a `clock_timestamp()`,
que se reevalúa en cada llamada.

Requiere una base de integración con la migración aplicada (`alembic upgrade head`).
"""
from __future__ import annotations

import random
import string
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


def _sid() -> int:
    return uuid.uuid4().int % (10**9)


def _letras(n: int = 10) -> str:
    return ''.join(random.choices(string.ascii_letters, k=n))


def _crear_activo_individual(db_session, id_usuario: int) -> int:
    sid = _sid()
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h,
                fecha_actualizacion, fecha_creacion, es_activo)
            VALUES (:id, :nombre, '{}', 10, now(), now(), TRUE)
            """
        ),
        {"id": sid, "nombre": f"Finca Integracion {_letras()}"},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca,
                superficie, es_activo, tipo)
            VALUES (:id, :nombre, :id_finca, 100, TRUE, 'Estanque')
            """
        ),
        {"id": sid, "nombre": f"Infra Integracion {_letras()}", "id_finca": sid},
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
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie,
                identificador, id_infraestructura, tipo, fecha_inicio_ciclo, id_estado,
                descripcion, origen_financiero, costo_adquisicion, atributos_dinamicos,
                id_usuario, fecha_creacion, id_dispositivo_iot, soporte_documental,
                detalles_procedencia)
            VALUES (:id, 2, :identificador, :id, 'INDIVIDUAL', current_date, 1,
                '', 'compra', 100, '{}', :id_usuario, now() - interval '1 hour',
                0, 'doc', '')
            """
        ),
        {"id": sid, "identificador": f"INC7553-{sid}", "id_usuario": id_usuario},
    )
    db_session.flush()
    return sid


def test_evento_con_fecha_calculada_tras_abrir_transaccion_es_aceptado(
    db_session, crear_usuario_db
) -> None:
    """Reproduce la carrera real: la transacción ya está abierta (fixture +
    setup) antes de calcular `fecha` como lo hace el use case, y aun así el
    evento debe aceptarse."""
    usuario = crear_usuario_db()
    db_session.execute(text("SET app.usuario_id = :uid"), {"uid": str(usuario["id_usuario"])})
    id_activo = _crear_activo_individual(db_session, usuario["id_usuario"])

    # Deja pasar tiempo real dentro de la misma transacción -- exactamente la
    # ventana que antes hacía que `NEW.fecha` superara al `now()` congelado.
    time.sleep(0.05)
    fecha = datetime.now(timezone.utc)

    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha, id_usuario)
            VALUES (:id, :id_activo, :fecha, :id_usuario)
            """
        ),
        {"id": _sid(), "id_activo": id_activo, "fecha": fecha, "id_usuario": usuario["id_usuario"]},
    )
    db_session.flush()


def test_evento_con_fecha_realmente_futura_sigue_siendo_rechazado(
    db_session, crear_usuario_db
) -> None:
    """El fix cambia la referencia de tiempo, no desactiva la validación."""
    usuario = crear_usuario_db()
    db_session.execute(text("SET app.usuario_id = :uid"), {"uid": str(usuario["id_usuario"])})
    id_activo = _crear_activo_individual(db_session, usuario["id_usuario"])

    fecha_futura = datetime.now(timezone.utc) + timedelta(days=1)

    with pytest.raises(DBAPIError, match="INVALID_DATE"):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """
                    INSERT INTO modulo2.eventos_activos (id_eventos, id_activo_biologico, fecha, id_usuario)
                    VALUES (:id, :id_activo, :fecha, :id_usuario)
                    """
                ),
                {
                    "id": _sid(),
                    "id_activo": id_activo,
                    "fecha": fecha_futura,
                    "id_usuario": usuario["id_usuario"],
                },
            )
            db_session.flush()
