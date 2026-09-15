"""INC-M02-66-G90 (issue #216): el trigger `trg_fn_asociacion_sensor_activo_unica`
evaluaba `fecha_fin > now()` para detectar conflicto de unicidad en
asociaciones DIRECTA. `now()` (alias de `transaction_timestamp()`) queda
congelado al inicio de la transacción; `AsociarSensorActivoUseCase` marca la
asociación previa como SUPERADA con `fecha_fin = clock_timestamp()` (posterior
al inicio de la transacción) y luego inserta la nueva -- `fecha_fin > now()`
evaluaba TRUE incluso para la fila que la propia transacción acababa de
superar, bloqueando el INSERT con `P0229` y devolviendo 500 al reemplazar un
sensor DIRECTA sobre el mismo activo (mismo patrón de bug que INC-M02-75-G53,
otro trigger de este módulo). Tampoco excluía el propio `id_activo_biologico`
ni las filas ya `SUPERADA`/`INACTIVA` del conteo.

La migración `d014e2cc785d` corrige el trigger a `estado_asociacion = 'ACTIVA'
AND fecha_fin IS NULL AND id_activo_biologico IS DISTINCT FROM
NEW.id_activo_biologico` -- formaliza una corrección que ya estaba aplicada
manualmente en `sgpmp_dev` (fuera de Alembic, sin ninguna revisión que la
registrara).

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


def _crear_infraestructura(db_session) -> int:
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
    db_session.flush()
    return sid


def _crear_activo_individual(db_session, id_usuario: int, id_infraestructura: int) -> int:
    sid = _sid()
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
            VALUES (:id, 2, :identificador, :id_infra, 'INDIVIDUAL', current_date, 1,
                '', 'compra', 100, '{}', :id_usuario, now() - interval '1 hour',
                0, 'doc', '')
            """
        ),
        {
            "id": sid, "identificador": f"INC6690-{sid}",
            "id_infra": id_infraestructura, "id_usuario": id_usuario,
        },
    )
    db_session.flush()
    return sid


def _crear_sensor(db_session, id_infraestructura: int) -> int:
    id_dispositivo = _sid()
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.dispositivos_iot (id_dispositivo_iot, serial, descripcion,
                es_activo, fecha_creacion, id_infraestructura)
            VALUES (:id, :serial, 'Gateway integracion', TRUE, now(), :id_infra)
            """
        ),
        {"id": id_dispositivo, "serial": _letras(12), "id_infra": id_infraestructura},
    )
    id_sensor = _sid()
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.sensores (id_sensores, id_dispositivo_iot, es_activo, nombre)
            VALUES (:id, :id_dispositivo, TRUE, :nombre)
            """
        ),
        {"id": id_sensor, "id_dispositivo": id_dispositivo, "nombre": f"Sensor {_letras()}"},
    )
    db_session.flush()
    return id_sensor


def _crear_asociacion_activa(
    db_session, *, id_sensor: int, id_activo: int, id_usuario: int, id_infraestructura: int,
) -> int:
    id_asociacion = _sid()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.asociaciones_activos_sensores (
                id_asociacion_activo_sensor, id_sensor, id_usuario, fecha_inicio,
                fecha_fin, id_activo_biologico, tipo, tipo_activo, id_infraestructura,
                estado_asociacion
            ) VALUES (
                :id, :id_sensor, :id_usuario, now() - interval '1 hour',
                NULL, :id_activo, CAST('directa' AS modulo2.enum_asociaciones_activos_sensores_tipo),
                'INDIVIDUAL', :id_infra, 'ACTIVA'
            )
            """
        ),
        {
            "id": id_asociacion, "id_sensor": id_sensor, "id_usuario": id_usuario,
            "id_activo": id_activo, "id_infra": id_infraestructura,
        },
    )
    db_session.flush()
    return id_asociacion


def test_reemplazo_directa_sobre_el_mismo_activo_es_aceptado(
    db_session, crear_usuario_db
) -> None:
    """Reproduce TC-M02-217: superar una asociación DIRECTA con una nueva
    sobre el mismo sensor y el mismo activo, dentro de la misma transacción
    -- exactamente la secuencia que ejecuta AsociarSensorActivoUseCase."""
    usuario = crear_usuario_db()
    id_infra = _crear_infraestructura(db_session)
    id_activo = _crear_activo_individual(db_session, usuario["id_usuario"], id_infra)
    id_sensor = _crear_sensor(db_session, id_infra)

    id_previa = _crear_asociacion_activa(
        db_session, id_sensor=id_sensor, id_activo=id_activo,
        id_usuario=usuario["id_usuario"], id_infraestructura=id_infra,
    )

    # Igual que el use case: marca la previa SUPERADA con clock_timestamp()
    # (posterior al fecha_inicio congelado de la transacción) y luego inserta
    # la nueva -- la ventana real que disparaba el falso conflicto.
    time.sleep(0.05)
    db_session.execute(
        text(
            """
            UPDATE modulo2.asociaciones_activos_sensores
            SET estado_asociacion = 'SUPERADA', fecha_fin = clock_timestamp()
            WHERE id_asociacion_activo_sensor = :id
            """
        ),
        {"id": id_previa},
    )
    db_session.flush()

    id_nueva = _sid()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.asociaciones_activos_sensores (
                id_asociacion_activo_sensor, id_sensor, id_usuario, fecha_inicio,
                fecha_fin, id_activo_biologico, tipo, tipo_activo, id_infraestructura,
                estado_asociacion
            ) VALUES (
                :id, :id_sensor, :id_usuario, clock_timestamp(),
                NULL, :id_activo, CAST('directa' AS modulo2.enum_asociaciones_activos_sensores_tipo),
                'INDIVIDUAL', :id_infra, 'ACTIVA'
            )
            """
        ),
        {
            "id": id_nueva, "id_sensor": id_sensor, "id_usuario": usuario["id_usuario"],
            "id_activo": id_activo, "id_infra": id_infra,
        },
    )
    db_session.flush()


def test_directa_en_otro_activo_sigue_siendo_rechazada(
    db_session, crear_usuario_db
) -> None:
    """El fix no debe desactivar la unicidad real: un sensor DIRECTA ya
    ACTIVA en OTRO activo sigue bloqueando la nueva asociación."""
    usuario = crear_usuario_db()
    id_infra = _crear_infraestructura(db_session)
    id_activo_a = _crear_activo_individual(db_session, usuario["id_usuario"], id_infra)
    id_activo_b = _crear_activo_individual(db_session, usuario["id_usuario"], id_infra)
    id_sensor = _crear_sensor(db_session, id_infra)

    _crear_asociacion_activa(
        db_session, id_sensor=id_sensor, id_activo=id_activo_a,
        id_usuario=usuario["id_usuario"], id_infraestructura=id_infra,
    )

    with pytest.raises(DBAPIError, match="SENSOR_CONFLICT"):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    """
                    INSERT INTO modulo2.asociaciones_activos_sensores (
                        id_asociacion_activo_sensor, id_sensor, id_usuario, fecha_inicio,
                        fecha_fin, id_activo_biologico, tipo, tipo_activo, id_infraestructura,
                        estado_asociacion
                    ) VALUES (
                        :id, :id_sensor, :id_usuario, now(),
                        NULL, :id_activo, CAST('directa' AS modulo2.enum_asociaciones_activos_sensores_tipo),
                        'INDIVIDUAL', :id_infra, 'ACTIVA'
                    )
                    """
                ),
                {
                    "id": _sid(), "id_sensor": id_sensor, "id_usuario": usuario["id_usuario"],
                    "id_activo": id_activo_b, "id_infra": id_infra,
                },
            )
            db_session.flush()
