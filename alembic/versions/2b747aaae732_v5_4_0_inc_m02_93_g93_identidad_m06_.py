"""v5.4.0_inc_m02_93_g93_identidad_m06_scope_metricas

Revision ID: 2b747aaae732
Revises: d944f4d8c215
Create Date: 2026-09-23 00:00:00.000000

INC-M02-93-G93 / issue #391 (TC-M02-157): RF-50 lista a M06 como consumidor
de "consistencia fuerte" para valoración NIC-41, pero no existía ninguna
identidad autenticable que lo representara -- QA no podía construir la
precondición de TC-M02-157 (módulo M06 autenticado con scope de
valoración/NIC-41). Mismo patrón que INC-M02-90-G92/INC-M02-92-G93 usaron
para M04: rol técnico 'Integración M0<n>' + usuario + permiso general sobre
recurso 29 + scope sobre el recurso de tipo_dato correspondiente.

Depende de la migración d944f4d8c215 (INC-M02-92-G93, issue #390): el
recurso 62 ('datos_analiticos_metricas') que aquí se referencia se crea ahí.
Si ese PR no se ha mergeado todavía, este down_revision debe re-verificarse
contra el head real de la cadena antes de abrir este PR (mismo problema que
ya ocurrió una vez con d944f4d8c215 -- ver su propio historial de commits).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2b747aaae732'
down_revision: Union[str, Sequence[str], None] = 'd944f4d8c215'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_rec_metricas   INT;
            v_id_rol_m06     INT;
            v_id_usuario_m06 INT;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos
                WHERE id_recurso = 29 AND lower(btrim(nombre_recurso)) = 'activos_biologicos'
            ) THEN
                RAISE EXCEPTION 'INC-M02-93-G93: id_recurso=29 no corresponde a activos_biologicos';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos
                WHERE nombre_recurso = 'datos_analiticos_metricas'
            ) THEN
                RAISE EXCEPTION
                    'INC-M02-93-G93: no existe el recurso datos_analiticos_metricas -- '
                    'aplica primero la migracion d944f4d8c215 (INC-M02-92-G93)';
            END IF;
            SELECT id_recurso INTO v_rec_metricas FROM modulo1.recursos WHERE nombre_recurso = 'datos_analiticos_metricas';

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.acciones
                WHERE id_accion = 2 AND upper(btrim(codigo)) = 'R'
            ) THEN
                RAISE EXCEPTION 'INC-M02-93-G93: id_accion=2 no corresponde a Leer (R)';
            END IF;

            -- Identidad técnica M06 (mismo patrón que INC-M02-90-G92 para M04).
            -- Idempotente: si ya existe (ej. aplicado manualmente por un DBA), no la toca.
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles WHERE lower(btrim(nombre_rol)) = 'integración m06'
            ) THEN
                INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido)
                VALUES (
                    'Integración M06',
                    'Identidad técnica de solo lectura para que el módulo 6 (valoración financiera / NIC-41) consuma los endpoints analíticos de M02 (RF-50 datos-consolidados). Creado para INC-M02-93-G93.',
                    FALSE
                )
                RETURNING id_rol INTO v_id_rol_m06;

                INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
                VALUES (
                    'm06_leer_activo_biologico',
                    'Lectura de datos consolidados de activos biológicos para consumo del módulo 6 (RF-50, valoración NIC-41).',
                    v_id_rol_m06, 29, 2, TRUE
                );

                -- Contraseña aleatoria: nunca se hardcodea un secreto en un
                -- script versionado. Quien active esta identidad la rota
                -- después por un canal seguro (mismo patrón que M04, ver
                -- inc_m02_90_g92_identidad_m04.md).
                INSERT INTO modulo1.usuarios (nombre, apellidos, correo_electronico, contrasena_cifrada, id_rol)
                VALUES (
                    'Integración', 'Módulo Seis', 'integracion.m06.test@pecuaria.co',
                    crypt(gen_random_uuid()::text || gen_random_uuid()::text, gen_salt('bf', 12)), v_id_rol_m06
                )
                RETURNING id_usuario INTO v_id_usuario_m06;

                INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado)
                VALUES (v_id_usuario_m06, 2, TRUE);
            ELSE
                SELECT id_rol INTO v_id_rol_m06 FROM modulo1.roles WHERE lower(btrim(nombre_rol)) = 'integración m06';
            END IF;

            -- Scope de valoración/NIC-41 (INC-M02-93-G93): solo metricas --
            -- es lo único que TC-M02-157 pide, y coincide con lo que RF-50
            -- describe como dato de valoración (peso, biomasa, indicadores).
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES (
                'm06_leer_datos_analiticos_metricas',
                'RF-50: scope de valoración NIC-41 (metricas) para Integración M06.',
                v_id_rol_m06, v_rec_metricas, 2, TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE
                SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion, es_activo = TRUE;
        END
        $$;
        """
    )


def downgrade() -> None:
    # A diferencia de d944f4d8c215, ningún permiso de M06 empieza con
    # 'admin_' (esa identidad no toca el rol Administrador), así que sí es
    # reversible: no hereda la inmutabilidad de los permisos admin_*. El rol
    # se borra directo -- fk_recurso_rol (permisos->roles) tiene ON DELETE
    # CASCADE desde c4a19e7d2b63 (RF-03), así que sus permisos se limpian
    # solos. usuarios.id_rol sigue en NO ACTION, así que el usuario/cuenta se
    # borran primero.
    op.execute(
        """
        DO $$
        DECLARE
            v_id_rol_m06 INT;
        BEGIN
            SELECT id_rol INTO v_id_rol_m06 FROM modulo1.roles WHERE lower(btrim(nombre_rol)) = 'integración m06';
            IF v_id_rol_m06 IS NOT NULL THEN
                DELETE FROM modulo1.cuentas_usuarios WHERE id_usuario IN (
                    SELECT id_usuario FROM modulo1.usuarios WHERE id_rol = v_id_rol_m06
                );
                DELETE FROM modulo1.usuarios WHERE id_rol = v_id_rol_m06;
                DELETE FROM modulo1.roles WHERE id_rol = v_id_rol_m06;
            END IF;
        END
        $$;
        """
    )
