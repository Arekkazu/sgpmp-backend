"""fix_trg_sensor_finca_fija_reasignacion_mod9

Revision ID: 56cd2038ff06
Revises: 2c1e6bb33a79
Create Date: 2026-09-06 00:50:23.071792

INC-M09-107-G64 / issue #135: `POST /configuracion/sensores/{id}/asociar`
respondía 500 `ERROR_INTERNO` al confirmar una reasignación (`confirmar: true`)
a un área productiva distinta de la actual, aunque el flujo de creación
inicial funcionaba bien. El caso de uso (`AsociarSensorAreaUseCase.execute`)
sí hace lo correcto: termina la asociación anterior y luego inserta la nueva
dentro de la misma transacción — pero el `INSERT` disparaba el trigger
`modulo9.trg_sensor_asociacion_infraestructura_fija`, que bloquea *cualquier*
reasignación del sensor a una infraestructura distinta de la primera que tuvo
"de por vida", contradiciendo el propio flujo de reasignación que exige RF-22
(y el docstring del use case). Su `RAISE EXCEPTION ... USING ERRCODE 'P0140'`
tampoco estaba mapeado en `src/shared/db_error_translator.py` (SQLSTATE clase
`P0`, psycopg2 no la traduce a `IntegrityError`), así que caía al 500
genérico en vez de un error de negocio.

Esta migración reemplaza esa regla por una correcta: el sensor no queda fijo
a un área exacta, sino a la **finca** de su dispositivo (que sí es fija — un
dispositivo no se reasigna a otra finca). Compara la finca del área destino
contra la finca del área donde está instalado el dispositivo del sensor, en
cada INSERT (primera asociación o reasignación), no contra el historial de
asociaciones del propio sensor como hacía la versión anterior. Esto:

1. Desbloquea la reasignación entre áreas de la MISMA finca (el bug de este
   issue).
2. Sigue impidiendo cualquier reasignación a una finca DISTINTA, incluso en
   la primera asociación del sensor (issue relacionado #142, ya corregido a
   nivel de aplicación en `AsociarSensorAreaUseCase`; este trigger queda como
   defensa en profundidad a nivel de base de datos).

Investigando el 500 con el servidor local real apareció una SEGUNDA causa
apilada en el mismo flujo, que de hecho es la que se dispara primero: el
CHECK constraint `auditorias_sensores_areas_tipo_operacion_check` solo
permite `('CREATE', 'GET')`, pero `AsociarSensorAreaUseCase.execute()`
audita el cierre de la asociación anterior con `tipo_operacion="UPDATE"`
(línea ya existente en el use case, no es un cambio de este PR) — cae en el
mismo 500 genérico, antes incluso de llegar al `INSERT` que dispara el
trigger de arriba. Todas las tablas `auditorias_*` hermanas de `modulo9`
(`auditorias_infraestructuras`, `auditorias_fincas`, etc.) sí incluyen
`'UPDATE'` en su constraint; esta se quedó corta. Esta migración también la
alinea, renombrándola al prefijo `ck_` de
`anotaciones/convencion_nomenclatura_bd.md` ya que se está modificando de
todos modos.

Ver revisión y autorización de @SamuelPR21 en el PR de este cambio antes de
mergear a `dev` — dos objetos de BD (trigger + constraint), conviene doble
verificación además del Análisis correspondiente.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '56cd2038ff06'
down_revision: Union[str, Sequence[str], None] = '2c1e6bb33a79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sensor_asociacion_infraestructura_fija ON modulo9.sensores_areas_asociadas;")
    op.execute("DROP FUNCTION IF EXISTS modulo9.trg_fn_sensor_asociacion_infraestructura_fija();")

    op.execute("""
    CREATE FUNCTION modulo9.trg_fn_sensor_asociacion_finca_fija()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_finca_dispositivo INTEGER;
        v_finca_destino     INTEGER;
    BEGIN
        SELECT i.id_finca INTO v_finca_dispositivo
        FROM modulo9.dispositivos_iot d
        JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
        WHERE d.id_dispositivo_iot = NEW.id_dispositivo_iot;

        SELECT id_finca INTO v_finca_destino
        FROM modulo9.infraestructuras
        WHERE id_infraestructura = NEW.id_infraestructura;

        IF v_finca_dispositivo IS NOT NULL AND v_finca_destino IS NOT NULL
           AND v_finca_dispositivo <> v_finca_destino THEN
            RAISE EXCEPTION
                'SENSOR_FINCA_DISTINTA: El sensor ID % pertenece al dispositivo de la finca ID %. '
                'No puede asociarse a un area de la finca ID %.',
                NEW.id_sensor, v_finca_dispositivo, v_finca_destino
                USING ERRCODE = 'P0140';
        END IF;

        RETURN NEW;
    END;
    $$;
    """)

    op.execute("""
    CREATE TRIGGER trg_sensor_asociacion_finca_fija
        BEFORE INSERT ON modulo9.sensores_areas_asociadas
        FOR EACH ROW EXECUTE FUNCTION modulo9.trg_fn_sensor_asociacion_finca_fija();
    """)

    op.execute("""
    ALTER TABLE modulo9.auditorias_sensores_areas
        DROP CONSTRAINT IF EXISTS auditorias_sensores_areas_tipo_operacion_check,
        DROP CONSTRAINT IF EXISTS chk_tipo_operacion_sensor_area,
        ADD CONSTRAINT ck_auditoria_sensor_area_tipo_operacion
            CHECK (tipo_operacion IN ('CREATE', 'UPDATE', 'GET'));
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE modulo9.auditorias_sensores_areas
        DROP CONSTRAINT IF EXISTS ck_auditoria_sensor_area_tipo_operacion,
        ADD CONSTRAINT auditorias_sensores_areas_tipo_operacion_check
            CHECK (tipo_operacion IN ('CREATE', 'GET'));
    """)

    op.execute("DROP TRIGGER IF EXISTS trg_sensor_asociacion_finca_fija ON modulo9.sensores_areas_asociadas;")
    op.execute("DROP FUNCTION IF EXISTS modulo9.trg_fn_sensor_asociacion_finca_fija();")

    op.execute("""
    CREATE FUNCTION modulo9.trg_fn_sensor_asociacion_infraestructura_fija()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_infra_actual INTEGER;
    BEGIN
        SELECT DISTINCT id_infraestructura
        INTO v_infra_actual
        FROM modulo9.sensores_areas_asociadas
        WHERE id_sensor = NEW.id_sensor
        LIMIT 1;

        IF v_infra_actual IS NOT NULL AND v_infra_actual <> NEW.id_infraestructura THEN
            RAISE EXCEPTION
                'SENSOR_INFRAESTRUCTURA_FIJA: El sensor ID % ya esta vinculado '
                'de por vida a la infraestructura ID %. No puede ser reasignado a '
                'la infraestructura ID %. Los sensores no se reubican en el sistema.',
                NEW.id_sensor, v_infra_actual, NEW.id_infraestructura
                USING ERRCODE = 'P0140';
        END IF;

        RETURN NEW;
    END;
    $$;
    """)

    op.execute("""
    CREATE TRIGGER trg_sensor_asociacion_infraestructura_fija
        BEFORE INSERT ON modulo9.sensores_areas_asociadas
        FOR EACH ROW EXECUTE FUNCTION modulo9.trg_fn_sensor_asociacion_infraestructura_fija();
    """)
