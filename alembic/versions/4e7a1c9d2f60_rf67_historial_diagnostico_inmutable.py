# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M04-145-G012 RF-67: resultados de inferencia e historial diagnóstico inmutables en la BD |
# | 2026-10-25 | Arekkazu | INC-M04-145-G012 RF-67: encadenada tras 8c4e2a6f1b93 (un solo head en la integración) |
"""RF-67: resultados de inferencia e historial diagnóstico de solo escritura en la base

Revision ID: 4e7a1c9d2f60
Revises: 8c4e2a6f1b93
Create Date: 2026-10-25

Por qué va por Alembic: es el patrón del repo y CI solo despliega lo que está
en `alembic/versions/`.

INC-M04-145-G012 (#700). RF-67, restricción de inmutabilidad: "Bajo ninguna
circunstancia se permite la edición o borrado de un resultado de inferencia una
vez persistido" (también RF-66 regla 5). La API ya rechazaba PUT/PATCH/DELETE,
pero en la base un UPDATE sobre `modulo4.resultados_inferencia` y un UPDATE o
DELETE sobre `modulo4.historial_diagnostico_eventos` pasaban sin bloqueo.

Se bloquean UPDATE, DELETE y TRUNCATE con triggers, igual que la bitácora de M02
(`785d330f7541`). El SQLSTATE es `P0403`, el mismo IMMUTABLE de
`modulo4.alertas_patologicas`. Aplica a todos los roles, también al dueño de la
tabla. Ningún código de la aplicación ni función de la base modifica estas
tablas: el historial solo inserta (materialización idempotente).
"""
from typing import Sequence, Union

from alembic import op


revision: str = '4e7a1c9d2f60'
down_revision: Union[str, Sequence[str], None] = '8c4e2a6f1b93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS = (
    ('resultados_inferencia', 'resultado_inferencia'),
    ('historial_diagnostico_eventos', 'historial_diagnostico_evento'),
)


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION modulo4.fn_historial_diagnostico_inmutable() RETURNS trigger
            LANGUAGE plpgsql
            AS $$
        BEGIN
            RAISE EXCEPTION
                'IMMUTABLE_HISTORY: % es de solo escritura (RF-67). Operación % bloqueada.',
                TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME, TG_OP
            USING ERRCODE = 'P0403';
        END;
        $$;

        COMMENT ON FUNCTION modulo4.fn_historial_diagnostico_inmutable() IS
            'RF-67 (INC-M04-145-G012): rechaza UPDATE, DELETE y TRUNCATE sobre resultados de inferencia e historial diagnóstico.';
        """
    )
    for tabla, singular in _TABLAS:
        op.execute(
            f"""
            CREATE TRIGGER trg_antes_actualizar_{singular}
                BEFORE UPDATE ON modulo4.{tabla}
                FOR EACH ROW EXECUTE FUNCTION modulo4.fn_historial_diagnostico_inmutable();

            CREATE TRIGGER trg_antes_eliminar_{singular}
                BEFORE DELETE ON modulo4.{tabla}
                FOR EACH ROW EXECUTE FUNCTION modulo4.fn_historial_diagnostico_inmutable();

            CREATE TRIGGER trg_antes_truncar_{singular}
                BEFORE TRUNCATE ON modulo4.{tabla}
                FOR EACH STATEMENT EXECUTE FUNCTION modulo4.fn_historial_diagnostico_inmutable();
            """
        )


def downgrade() -> None:
    for tabla, singular in _TABLAS:
        op.execute(
            f"""
            DROP TRIGGER trg_antes_truncar_{singular} ON modulo4.{tabla};
            DROP TRIGGER trg_antes_eliminar_{singular} ON modulo4.{tabla};
            DROP TRIGGER trg_antes_actualizar_{singular} ON modulo4.{tabla};
            """
        )
    op.execute("DROP FUNCTION modulo4.fn_historial_diagnostico_inmutable();")
