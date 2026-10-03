"""v5.4.0_rf49_permiso_patch_asociacion_sensor

Revision ID: 1ee808f9ee6b
Revises: c8d4f1a9b7e2
Create Date: 2026-09-23 04:00:00.000000

Tarea Taiga "RF-49: Compatibilidad de especie sensor-activo y ciclo de vida
completo". Al investigar se confirmó que ambos gaps descritos en el ticket ya
estaban resueltos en `dev` (código real, con tests pasando):

- Compatibilidad de especie (Restricción 3 del RF): `AsociarSensorActivoUseCase`
  bloque V7 ya valida contra `modulo9.compatibilidad_sensores_especies`
  (commit `07035caa fix(m02): validar compatibilidad sensor especie en RF-49`).
  Confirmado en vivo: 156 filas reales sembradas en `sgpmp_dev`.
- Ciclo de vida completo: `GET /{id}/sensores` (listar, commit `2b3e3772`) y
  `PATCH /{id}/sensores/{id_asociacion}` (activar/desactivar, commit
  `c1eaf765`) ya existen como endpoints reales, no solo `POST`.

El gap real encontrado en esta iteración: `anotaciones/modulo_2/
inc_m02_65_g89_patch_ciclo_vida_asociacion_sensor.md` documenta que el PATCH
requiere `(recurso 30, accion U=3)`, y que ese permiso se insertó para
Administrador e Ingeniero de Campo -- pero el propio documento aclara que se
aplicó directamente por SQL contra `sgpmp` y `pruebas`, nunca se formalizó
como migración Alembic. Confirmado en vivo contra `sgpmp_dev`
(`SELECT * FROM modulo1.permisos WHERE id_recurso=30 AND id_accion=3` → 0
filas): ese INSERT nunca llegó a `dev`, así que hoy el PATCH responde 403 de
forma silenciosa para los 4 roles, incluido Administrador -- exactamente el
escenario que el Paso 0 de este documento (CLAUDE.md) advierte que hay que
verificar antes de dar una tarea de RBAC por resuelta.

Esta migración formaliza ese mismo INSERT (mismos roles, mismo recurso,
mismo `nombre` de permiso que ya usan `sgpmp`/`pruebas`, confirmado leyendo
el doc de la iteración original) para que quede versionado y se aplique
también en `dev` y en cualquier entorno futuro que corra `alembic upgrade
head`.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1ee808f9ee6b"
down_revision: Union[str, Sequence[str], None] = "c8d4f1a9b7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles
                WHERE id_rol = 1 AND lower(btrim(nombre_rol)) = 'administrador'
            ) THEN
                RAISE EXCEPTION 'RF49: id_rol=1 no corresponde al rol Administrador';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles
                WHERE id_rol = 4 AND lower(btrim(nombre_rol)) = 'ingeniero de campo'
            ) THEN
                RAISE EXCEPTION 'RF49: id_rol=4 no corresponde al rol Ingeniero de Campo';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos
                WHERE id_recurso = 30
                  AND lower(btrim(nombre_recurso)) = 'asociacion_sensor_activo'
            ) THEN
                RAISE EXCEPTION 'RF49: id_recurso=30 no corresponde a asociacion_sensor_activo';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.acciones
                WHERE id_accion = 3 AND upper(btrim(codigo)) = 'U'
            ) THEN
                RAISE EXCEPTION 'RF49: id_accion=3 no corresponde a UPDATE';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
        VALUES (
            'admin_actualizar_asociacion_sensor_activo',
            'Permite al Administrador activar/desactivar (ciclo de vida) asociaciones sensor-activo (RF-49).',
            1, 30, 3, TRUE
        )
        ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
        VALUES (
            'ing_actualizar_asociacion_sensor_activo',
            'Permite al Ingeniero de Campo activar/desactivar (ciclo de vida) asociaciones sensor-activo (RF-49).',
            4, 30, 3, TRUE
        )
        ON CONFLICT (id_rol, id_recurso, id_accion)
        DO UPDATE SET
            nombre = EXCLUDED.nombre,
            descripcion = EXCLUDED.descripcion,
            es_activo = TRUE;
        """
    )


def downgrade() -> None:
    # El permiso admin_* NO se elimina aqui: trg_fn_proteger_permisos_admin_delete
    # bloquea cualquier DELETE sobre filas 'admin_%' con el error
    # ADMIN_PERM_NO_DELETE ("registros permanentes e inmutables") -- confirmado
    # en vivo al intentar revertir esta misma migracion contra sgpmp_dev. Es el
    # comportamiento esperado del trigger, no un bug: una vez otorgado, un
    # permiso administrativo solo se desactiva (es_activo=false) manualmente
    # por decision de negocio, nunca por un downgrade automatico.
    op.execute(
        """
        DELETE FROM modulo1.permisos
        WHERE id_recurso = 30 AND id_accion = 3
          AND nombre = 'ing_actualizar_asociacion_sensor_activo';
        """
    )
