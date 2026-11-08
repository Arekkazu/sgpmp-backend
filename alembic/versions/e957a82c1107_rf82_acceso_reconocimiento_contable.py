# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-07 | Leandro | INC-M06-273-G67-01 RF-82: conceder acceso al esquema y dependencias del reconocimiento inicial. |
"""RF-82: permisos de reconocimiento inicial para los roles existentes de la API.

Revision ID: e957a82c1107
Revises: b7e2d94c1a68

c4d81e6f2a95 crea las estructuras contables y concede permisos en sus tablas nuevas,
pero no concede USAGE sobre modulo6 ni ACL sobre las tablas heredadas del baseline
que utiliza el reconocimiento. Una base migrada desde cero falla bajo sgpmp_app.

Esta revisión agrega exclusivamente los permisos del flujo RF-82. No crea tablas,
roles, permisos de RBAC ni cuentas contables; tampoco concede CREATE o DELETE.
El despliegue en bases compartidas sigue el procedimiento autorizado de migraciones.
"""
from alembic import op

revision = 'e957a82c1107'
down_revision = 'b7e2d94c1a68'
branch_labels = None
depends_on = None

_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"
_TABLAS_LECTURA = ('precios_mercado', 'parametros_costos_venta')
_TABLAS_REGISTRO = (
    ('periodos_contables', 'id_periodo_contable'),
    ('calculos_valor_razonable', 'id_calculo_valor_razonable'),
    ('valoraciones_por_costos', 'id_valoracion_por_costo'),
    ('reconocimientos_iniciales', 'id_reconocimiento_inicial'),
    ('auditorias_financieras', 'id_auditoria_financiera'),
)


def upgrade() -> None:
    op.execute(f"""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT USAGE ON SCHEMA modulo6 TO %I', r.rolname);
            END LOOP;
        END $$;
    """)
    for tabla in _TABLAS_LECTURA:
        _conceder(tabla, 'SELECT')
    for tabla, pk in _TABLAS_REGISTRO:
        _conceder(tabla, 'SELECT, INSERT', pk)


def _conceder(tabla: str, permisos: str, pk: str | None = None) -> None:
    secuencia = '' if pk is None else f"""
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO %I',
                               pg_get_serial_sequence('modulo6.{tabla}', '{pk}'), r.rolname);
    """
    op.execute(f"""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT {permisos} ON modulo6.{tabla} TO %I', r.rolname);
                {secuencia}
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    # Igual que b7e2d94c1a68: no revocar ACL que podían existir previamente por ambiente.
    # La revisión solo agrega permisos; no cambia datos ni estructuras que revertir.
    pass
