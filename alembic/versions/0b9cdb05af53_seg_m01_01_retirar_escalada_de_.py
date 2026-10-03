"""seg_m01_01 retirar escalada de privilegios rol supervisor y renombrar permisos vet_eliminar

Revision ID: 0b9cdb05af53
Revises: c4e8f1a2b603
Create Date: 2026-09-13 14:19:55.357852

Issue #289 [SEG-M01-01]: el rol Supervisor (id_rol=6, "permisos de
supervisión y reportes") solo tenía dos permisos sembrados de prueba:
crear (C) sobre usuarios y crear (C) sobre roles — escalada de
privilegios sin relación con su descripción. Se retiran y se siembran
en su lugar permisos coherentes con el rol: leer (R) sobre eventos de
auditoría y ejecutar (E) sobre generación de reportes.

De paso (mismo informe de auditoría, item 3): los 4 permisos
"vet_eliminar_*" del Veterinario protegen endpoints que hacen
desactivación lógica (`es_activo = false`), nunca DELETE físico — se
renombran a "vet_desactivar_*" para que el nombre no sugiera borrado
irreversible que no ocurre.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0b9cdb05af53'
down_revision: Union[str, Sequence[str], None] = 'c4e8f1a2b603'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles
                WHERE id_rol = 6 AND lower(btrim(nombre_rol)) = 'supervisor'
            ) THEN
                RAISE EXCEPTION 'SEG_M01_01: id_rol=6 no corresponde al rol Supervisor';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos WHERE id_recurso = 6 AND lower(btrim(nombre_recurso)) = 'eventos'
            ) THEN
                RAISE EXCEPTION 'SEG_M01_01: id_recurso=6 no corresponde al recurso eventos';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos WHERE id_recurso = 15 AND lower(btrim(nombre_recurso)) = 'generacion_reportes'
            ) THEN
                RAISE EXCEPTION 'SEG_M01_01: id_recurso=15 no corresponde al recurso generacion_reportes';
            END IF;

            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                ('sup_leer_evento', 'Consultar el historial de auditoría del sistema (rol de supervisión)', 6, 6, 2, TRUE),
                ('sup_ejecutar_reporte', 'Generar reportes del sistema', 6, 15, 5, TRUE)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;

            -- Escalada de privilegios (issue #289): crear usuarios/roles no tiene
            -- relación con "supervisión y reportes" y no lo exige ningún RF.
            DELETE FROM modulo1.permisos
            WHERE id_rol = 6 AND nombre IN ('Supervisor_permiso_1_1', 'Supervisor_permiso_2_1');

            UPDATE modulo1.permisos SET nombre = 'vet_desactivar_ciclo_biologico' WHERE nombre = 'vet_eliminar_ciclo_biologico';
            UPDATE modulo1.permisos SET nombre = 'vet_desactivar_patologia' WHERE nombre = 'vet_eliminar_patologia';
            UPDATE modulo1.permisos SET nombre = 'vet_desactivar_metrica_produccion' WHERE nombre = 'vet_eliminar_metrica_produccion';
            UPDATE modulo1.permisos SET nombre = 'vet_desactivar_umbral_ambiental' WHERE nombre = 'vet_eliminar_umbral_ambiental';
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            UPDATE modulo1.permisos SET nombre = 'vet_eliminar_ciclo_biologico' WHERE nombre = 'vet_desactivar_ciclo_biologico';
            UPDATE modulo1.permisos SET nombre = 'vet_eliminar_patologia' WHERE nombre = 'vet_desactivar_patologia';
            UPDATE modulo1.permisos SET nombre = 'vet_eliminar_metrica_produccion' WHERE nombre = 'vet_desactivar_metrica_produccion';
            UPDATE modulo1.permisos SET nombre = 'vet_eliminar_umbral_ambiental' WHERE nombre = 'vet_desactivar_umbral_ambiental';

            -- Insertar antes de borrar: trg_validar_permiso_minimo_rol bloquea
            -- dejar al rol sin ningún permiso activo, aunque sea momentáneamente
            -- dentro de la misma sentencia.
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                ('Supervisor_permiso_1_1', 'Permiso asignado al rol Supervisor', 6, 1, 1, TRUE),
                ('Supervisor_permiso_2_1', 'Permiso asignado al rol Supervisor', 6, 2, 1, TRUE)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;

            DELETE FROM modulo1.permisos
            WHERE id_rol = 6 AND nombre IN ('sup_leer_evento', 'sup_ejecutar_reporte');
        END
        $$;
        """
    )
