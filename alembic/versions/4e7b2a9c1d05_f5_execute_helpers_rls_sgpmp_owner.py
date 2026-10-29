"""F5: permitir a sgpmp_owner ejecutar los helpers de RLS

Revision ID: 4e7b2a9c1d05
Revises: d28c1a5a66d2
Create Date: 2026-10-09 20:30:00.000000

Las F5 (98389cebef99, bd9cea80dea6, d28c1a5a66d2) revocan EXECUTE de PUBLIC
en los helpers que usan las politicas RLS y solo lo conceden a sgpmp_app.
Pero las funciones SECURITY DEFINER cuyo dueno es sgpmp_owner (por ejemplo
modulo2.trg_fn_fase_activo_estado_valido) corren como sgpmp_owner y leen
tablas con RLS FORCE: al evaluar la politica, Postgres invoca el helper con
ese rol y falla con "permission denied for function fn_es_usuario_servicio".

Sintoma en TEST: POST /activos-biologicos/{id}/fases (RF-37) responde 500 a
cualquier usuario, lo que bloquea crecimiento, cierre de ciclo e indicadores.

Solo concede EXECUTE; no cambia duenos, politicas ni cuerpos de funcion.
"""
from alembic import op

revision = '4e7b2a9c1d05'
down_revision = 'd28c1a5a66d2'
branch_labels = None
depends_on = None

# Helpers referenciados por politicas RLS que sgpmp_owner no podia ejecutar.
_HELPERS = (
    'modulo1.fn_es_usuario_servicio()',
    'modulo1.fn_id_cuenta_actual()',
    'modulo1.fn_id_rol_actual()',
    'modulo1.fn_rol_protegido(integer)',
    'modulo1.fn_tiene_permiso(text, text)',
    'modulo2.fn_activos_del_usuario(bigint)',
    'modulo9.fn_fincas_del_usuario(bigint)',
    'modulo9.fn_infraestructuras_del_usuario(bigint)',
    'modulo9.fn_dispositivos_del_usuario(bigint)',
    'modulo9.fn_sensores_del_usuario(bigint)',
)


def _para_cada_helper(sentencia: str) -> None:
    # sgpmp_owner no existe en una BD construida desde cero (CI, "pruebas").
    lista = ', '.join(f"'{h}'" for h in _HELPERS)
    op.execute(f"""
        DO $$
        DECLARE h text;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sgpmp_owner') THEN
                RETURN;
            END IF;
            FOREACH h IN ARRAY ARRAY[{lista}] LOOP
                EXECUTE format('{sentencia}', h);
            END LOOP;
        END $$;
    """)


def upgrade() -> None:
    _para_cada_helper('GRANT EXECUTE ON FUNCTION %s TO sgpmp_owner')


def downgrade() -> None:
    _para_cada_helper('REVOKE EXECUTE ON FUNCTION %s FROM sgpmp_owner')
