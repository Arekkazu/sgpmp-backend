"""RF-52 E5: tipo de evento de la alerta y permiso del registro correctivo (M02)

Revision ID: 094d4799c3ca
Revises: 6af637931784
Create Date: 2026-09-23

RF-52 E5 ("Inconsistencia entre RF-52 y RF-46") pide dos cosas que necesitan
catálogo en modulo1:

1. "Se genera una alerta CRITICAL al administrador": la reconciliación diaria
   avisa por la bandeja interna (RF-14), igual que la alerta de fallo de
   archivado de RF-10 (a3b7c1d95e40). Toda notificación cuelga de un evento de
   modulo1.eventos, así que hace falta el tipo INCONSISTENCIA_AUDITORIA_M02. El
   id se fija en 28 porque el código lo referencia por número (mismo patrón que
   5c844a858bde) y después se reposiciona la secuencia.

2. "El administrador puede crear un registro correctivo en RF-52": el endpoint
   POST /activos-biologicos/auditoria/registros-correctivos exige la acción
   C (crear) sobre el recurso 31 (bitacora_auditoria_m02), que hoy solo tiene
   permisos de lectura. Se otorga únicamente a Administrador: la restricción 6
   del RF prohíbe que los usuarios escriban en la bitácora, y E5 lo exceptúa
   solo para el administrador.

Sin cambios de esquema: dos filas de catálogo. El permiso de Administrador queda
inmutable una vez creado (triggers trg_fn_proteger_permisos_admin_update y
_delete): el insert es ON CONFLICT DO NOTHING, igual que c977eab2eb0d, y el
downgrade solo puede retirar el tipo de evento.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '094d4799c3ca'
down_revision: Union[str, Sequence[str], None] = '6af637931784'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID_TIPO_EVENTO = 28
NOMBRE_TIPO_EVENTO = "INCONSISTENCIA_AUDITORIA_M02"
ACCION_TIPO_EVENTO = "Inconsistencia de auditoria de activos biologicos"  # varchar(50)


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
        SELECT {ID_TIPO_EVENTO}, '{NOMBRE_TIPO_EVENTO}', '{ACCION_TIPO_EVENTO}'
        WHERE NOT EXISTS (
            SELECT 1 FROM modulo1.tipos_eventos
            WHERE id_tipo_evento = {ID_TIPO_EVENTO} OR nombre = '{NOMBRE_TIPO_EVENTO}'
        )
        """
    )
    op.execute(
        """
        SELECT setval(
            'modulo1.tipos_evento_id_tipo_evento_seq',
            (SELECT max(id_tipo_evento) FROM modulo1.tipos_eventos)
        )
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM modulo1.recursos
                WHERE id_recurso = 31
                  AND lower(btrim(nombre_recurso)) = 'bitacora_auditoria_m02'
            ) THEN
                RAISE EXCEPTION 'RF52: id_recurso=31 no corresponde a bitacora_auditoria_m02';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.acciones
                WHERE id_accion = 1 AND upper(btrim(codigo)) = 'C'
            ) THEN
                RAISE EXCEPTION 'RF52: id_accion=1 no corresponde a CREATE';
            END IF;

            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            )
            VALUES (
                'admin_crear_bitacora_auditoria_m02',
                'Permite al Administrador crear registros correctivos en la bitácora de M02 (RF-52 E5).',
                1, 31, 1, TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END
        $$;
        """
    )


def downgrade() -> None:
    # El permiso admin_crear_bitacora_auditoria_m02 no se revierte:
    # modulo1.trg_fn_proteger_permisos_admin_delete rechaza borrar cualquier
    # permiso 'admin_%' (ADMIN_PERM_NO_DELETE) y el de UPDATE impide desactivarlo.
    # Es la inmutabilidad deliberada de los permisos de Administrador, no un
    # olvido; sin el endpoint, el permiso no habilita nada.
    op.execute(
        f"""
        DELETE FROM modulo1.tipos_eventos
        WHERE id_tipo_evento = {ID_TIPO_EVENTO}
          AND NOT EXISTS (
              SELECT 1 FROM modulo1.eventos WHERE tipo_evento = {ID_TIPO_EVENTO}
          )
        """
    )
