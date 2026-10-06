"""RF-52: la bitácora de auditoría de M02 es append-only también en la base

Revision ID: 785d330f7541
Revises: 78f6f579b5ba
Create Date: 2026-10-06

INC-M02-64-G101 (#489). RF-52, restricción 1: "La bitácora es append-only. Esta
restricción debe estar implementada a nivel de base de datos, no solo a nivel de
lógica de negocio." `modulo2.bitacora_auditoria_m02` no tenía triggers y cualquier
conexión con privilegios sobre la tabla (incluida la de la aplicación) podía
modificar o borrar registros de auditoría.

Se bloquean UPDATE, DELETE y TRUNCATE con un trigger, igual que las demás
bitácoras inmutables del esquema (`trg_auditoria_activos_inmutable_*` de M02, RF-57
y RF-60 en M03), con el mismo SQLSTATE `P0252` IMMUTABLE_AUDIT que la auditoría de
activos de M02. El trigger aplica a todos los roles, también al dueño de la tabla.
La aplicación solo inserta en esta tabla (`SqlAlchemyBitacoraAuditoriaRepository.registrar`)
y ninguna función de la base la modifica, así que el flujo actual no cambia.

No se revocan privilegios: los grants de `sgpmp_app` y de los roles por equipo los
gestiona la fase de control de acceso por BD del DBA (F4), y el trigger ya cubre a
todos los roles sin depender de ellos.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '785d330f7541'
down_revision: Union[str, Sequence[str], None] = '78f6f579b5ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable() RETURNS trigger
            LANGUAGE plpgsql
            AS $$
        BEGIN
            RAISE EXCEPTION
                'IMMUTABLE_AUDIT: La bitácora de auditoría RF-52 (modulo2.bitacora_auditoria_m02) es append-only. Operación % bloqueada.',
                TG_OP
            USING ERRCODE = 'P0252';
        END;
        $$;

        COMMENT ON FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable() IS
            'RF-52 restricción 1 (INC-M02-64-G101): rechaza UPDATE, DELETE y TRUNCATE sobre la bitácora de M02.';

        CREATE TRIGGER trg_antes_actualizar_bitacora_auditoria_m02
            BEFORE UPDATE ON modulo2.bitacora_auditoria_m02
            FOR EACH ROW EXECUTE FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable();

        CREATE TRIGGER trg_antes_eliminar_bitacora_auditoria_m02
            BEFORE DELETE ON modulo2.bitacora_auditoria_m02
            FOR EACH ROW EXECUTE FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable();

        CREATE TRIGGER trg_antes_truncar_bitacora_auditoria_m02
            BEFORE TRUNCATE ON modulo2.bitacora_auditoria_m02
            FOR EACH STATEMENT EXECUTE FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER trg_antes_truncar_bitacora_auditoria_m02 ON modulo2.bitacora_auditoria_m02;
        DROP TRIGGER trg_antes_eliminar_bitacora_auditoria_m02 ON modulo2.bitacora_auditoria_m02;
        DROP TRIGGER trg_antes_actualizar_bitacora_auditoria_m02 ON modulo2.bitacora_auditoria_m02;
        DROP FUNCTION modulo2.fn_bitacora_auditoria_m02_inmutable();
        """
    )
