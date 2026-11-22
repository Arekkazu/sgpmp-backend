# | Fecha      | Nombre   | Que se hizo                                                            |
# |------------|----------|------------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ampliación de la ventana para un resultado      |
"""rf72: ampliación justificada de la ventana de retroalimentación por resultado

Revision ID: 6bd01d026ac4
Revises: 7efe47d6c76a
Create Date: 2026-10-30

Por qué va por Alembic: es el patrón del repo y CI solo despliega lo que está
en `alembic/versions/`.

INC-M04-229-G070 (#865). RF-72, Ventana Temporal Válida para Registro:
"el administrador puede ampliar la ventana para un resultado específico mediante
una operación técnica justificada, registrada en RF-73". No había dónde guardar
esa excepción, así que un resultado vencido solo se habilitaba ampliando la
ventana global, lo que habilita también todos los demás.

- `modulo4.ampliaciones_ventana_retroalimentacion`: una fila por ampliación
  (resultado, nueva fecha límite, justificación y quién la autorizó). Es de solo
  inserción: sin políticas UPDATE/DELETE la aplicación no puede modificarla.
- RLS forzada. Lectura: las ampliaciones de los resultados que el usuario puede
  ver (misma regla que `pol_retroalimentacion_clinica_select`). Inserción: quien
  tiene Actualizar sobre `configuraciones_globales` (hoy solo Administrador),
  a su propio nombre y sobre un resultado visible.
- `VENTANA_RETROALIMENTACION_AMPLIADA` en `modulo4.enum_tipo_evento_auditoria_m04`.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '6bd01d026ac4'
down_revision: Union[str, Sequence[str], None] = '7efe47d6c76a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLA = 'modulo4.ampliaciones_ventana_retroalimentacion'
# Mismos roles de BD que en las demás migraciones recientes; solo los que existan.
_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"


def upgrade() -> None:
    op.execute(
        "ALTER TYPE modulo4.enum_tipo_evento_auditoria_m04 "
        "ADD VALUE IF NOT EXISTS 'VENTANA_RETROALIMENTACION_AMPLIADA'"
    )
    op.execute(f"""
        CREATE TABLE {_TABLA} (
            id_ampliacion_ventana_retroalimentacion INTEGER GENERATED ALWAYS AS IDENTITY,
            id_resultado_inferencia UUID NOT NULL,
            fecha_limite TIMESTAMPTZ NOT NULL,
            justificacion TEXT NOT NULL,
            id_usuario_autorizador INTEGER NOT NULL,
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ampliaciones_ventana_retroalimentacion_pkey
                PRIMARY KEY (id_ampliacion_ventana_retroalimentacion),
            CONSTRAINT ampliaciones_ventana_retroalimentacion_id_resultado_inferencia_fkey
                FOREIGN KEY (id_resultado_inferencia)
                REFERENCES modulo4.resultados_inferencia (id_resultado_inferencia)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ampliaciones_ventana_retroalimentacion_id_usuario_autorizador_fkey
                FOREIGN KEY (id_usuario_autorizador) REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_ampliacion_ventana_retroalimentacion_justificacion
                CHECK (char_length(btrim(justificacion)) BETWEEN 10 AND 1000),
            CONSTRAINT ck_ampliacion_ventana_retroalimentacion_fecha_limite
                CHECK (fecha_limite > fecha_creacion)
        );

        CREATE INDEX idx_ampliacion_ventana_retroalimentacion_id_resultado_inferencia
            ON {_TABLA} (id_resultado_inferencia);

        COMMENT ON TABLE {_TABLA} IS
            'RF-72 (INC-M04-229-G070): excepción justificada a la ventana de retroalimentación '
            'para un resultado de inferencia. Solo inserción; la auditoría va en RF-73.';

        ALTER TABLE {_TABLA} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {_TABLA} FORCE ROW LEVEL SECURITY;

        CREATE POLICY pol_ampliacion_ventana_retroalimentacion_select ON {_TABLA}
            FOR SELECT
            USING (EXISTS (
                SELECT 1 FROM modulo4.resultados_inferencia ri
                WHERE ri.id_resultado_inferencia = ampliaciones_ventana_retroalimentacion.id_resultado_inferencia
            ));

        CREATE POLICY pol_ampliacion_ventana_retroalimentacion_insert ON {_TABLA}
            FOR INSERT
            WITH CHECK (
                (SELECT modulo1.fn_tiene_permiso('configuraciones_globales'::text, 'U'::text))
                AND id_usuario_autorizador = (SELECT modulo1.fn_id_usuario_actual())
                AND EXISTS (
                    SELECT 1 FROM modulo4.resultados_inferencia ri
                    WHERE ri.id_resultado_inferencia = ampliaciones_ventana_retroalimentacion.id_resultado_inferencia
                )
            );

        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT SELECT, INSERT ON {_TABLA} TO %I', r);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute(f"DROP TABLE {_TABLA};")
    # Postgres no permite quitar valores de un enum (mismo criterio que 67e33de11180).
