"""Vistas nuevas de M01/M09: SELECT para sgpmp_app y sgpmp_owner

Revision ID: 7e1d4c2b9a30
Revises: a698c54d0f6c
Create Date: 2026-10-12 12:00:00.000000

Las migraciones de vistas (58c0b8b18f74, 32389a6e5686) crean vistas nuevas con
dueno `dba` y solo heredan el GRANT por defecto a `rol_app`. Ni `sgpmp_app` (la
app tras F5) ni `sgpmp_owner` (dueno de las vistas reemplazadas que ahora leen
de `vw_rf21_dispositivo_area_actual`) pueden leerlas: una vista se evalua con
los privilegios de su dueno, asi que la cadena se corta.

Sintoma en DEV: GET /configuracion/personalizacion/dashboard/datos responde 500
("permission denied for view vw_rf21_dispositivo_area_actual") para todo usuario
con widgets de dispositivos/fincas (RF-28), y lo mismo pasa con las
dependencias al desactivar fincas (RF-19) e infraestructuras (RF-20).

Solo concede SELECT; no cambia duenos ni definiciones.
"""
from alembic import op

revision = '7e1d4c2b9a30'
down_revision = 'a698c54d0f6c'
branch_labels = None
depends_on = None

# Creadas por las migraciones de vistas: sin SELECT para ninguno de los dos roles.
_VISTAS_NUEVAS = (
    'modulo1.vw_administradores_sistema',
    'modulo1.vw_auditoria_eventos_por_archivar',
    'modulo1.vw_auditoria_frecuencia_consultas',
    'modulo1.vw_matriz_permisos_rol',
    'modulo1.vw_notificaciones_bandeja_usuario',
    'modulo1.vw_roles_lista_permisos',
    'modulo1.vw_usuarios_elegibilidad_notificacion',
    'modulo9.vw_rf16_patologias_especie_nombre_normalizado',
    'modulo9.vw_rf17_umbrales_validacion',
    'modulo9.vw_rf21_dispositivo_area_actual',
)
# Ya legibles por sgpmp_app, pero no por sgpmp_owner.
_VISTAS_SIN_OWNER = (
    'modulo9.vw_rf19_fincas_nombre_normalizado',
    'modulo9.vw_rf19_fincas_productor_resumen',
    'modulo9.vw_rf20_fincas_activas_selector',
)


def _ejecutar(sentencia: str, rol: str, vistas: tuple[str, ...]) -> None:
    # Los roles no existen en una BD construida desde cero (CI, "pruebas").
    lista = ', '.join(f"'{v}'" for v in vistas)
    op.execute(f"""
        DO $$
        DECLARE v text;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rol}') THEN
                RETURN;
            END IF;
            FOREACH v IN ARRAY ARRAY[{lista}] LOOP
                IF to_regclass(v) IS NOT NULL THEN
                    EXECUTE format('{sentencia}', v);
                END IF;
            END LOOP;
        END $$;
    """)


def upgrade() -> None:
    _ejecutar('GRANT SELECT ON %s TO sgpmp_app', 'sgpmp_app', _VISTAS_NUEVAS)
    _ejecutar('GRANT SELECT ON %s TO sgpmp_owner', 'sgpmp_owner', _VISTAS_NUEVAS + _VISTAS_SIN_OWNER)


def downgrade() -> None:
    _ejecutar('REVOKE SELECT ON %s FROM sgpmp_owner', 'sgpmp_owner', _VISTAS_NUEVAS + _VISTAS_SIN_OWNER)
    _ejecutar('REVOKE SELECT ON %s FROM sgpmp_app', 'sgpmp_app', _VISTAS_NUEVAS)
