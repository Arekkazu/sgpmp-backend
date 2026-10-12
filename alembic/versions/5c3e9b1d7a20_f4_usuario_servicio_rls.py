"""F4 control de acceso: usuario de servicio para tareas de fondo e ingesta IoT

Revision ID: 5c3e9b1d7a20
Revises: bc82ffbdf797
Create Date: 2026-10-06 00:00:00.000000

Decisión D1 del plan de control de acceso por BD, cerrada por el DBA en el PR
#485: los procesos sin usuario autenticado (las tareas de fondo de `main.py` y
la ingesta IoT de D4) corren como un usuario de servicio en
`modulo1.usuarios`, con filas explícitas en `modulo9.usuarios_fincas`; ninguno
se salta RLS con BYPASSRLS. Sin esta identidad, la política de
`modulo2.activos_biologicos` (`bc82ffbdf797`) les devuelve cero filas y los
batch dejan de procesar sin avisar.

- Usuario `servicio.sistema@sgpmp.local` con el rol Administrador (las
  políticas de `modulo1` solo reconocen ese rol por nombre, y es la identidad
  que ya declaraban las tareas de fondo). La contraseña es aleatoria y nadie la
  conoce, y su cuenta queda Inactiva: no puede iniciar sesión, y como el rol
  es protegido, tampoco se puede reactivar desde la API.
- Acceso a todas las fincas existentes.
- `trg_despues_insertar_finca`: le da acceso a cada finca nueva al confirmar
  la transacción. Es diferido para que su fila quede después de la del
  propietario, que la API muestra como `id_usuario` de la finca.

Va por Alembic y no por SQL suelto: el usuario tiene que existir igual en dev,
pruebas y producción, el código lo busca por correo, y el `downgrade()` deja
todo como estaba.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '5c3e9b1d7a20'
down_revision: Union[str, Sequence[str], None] = 'bc82ffbdf797'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CORREO = 'servicio.sistema@sgpmp.local'


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            v_id_rol     INT;
            v_id_usuario INT;
        BEGIN
            SELECT id_rol INTO v_id_rol FROM modulo1.roles WHERE nombre_rol = 'Administrador';
            IF v_id_rol IS NULL THEN
                RAISE EXCEPTION 'F4: no existe el rol Administrador';
            END IF;

            -- Idempotente: si ya existe (ej. creado a mano por el DBA), no se toca.
            SELECT id_usuario INTO v_id_usuario
              FROM modulo1.usuarios WHERE correo_electronico = '{_CORREO}';
            IF v_id_usuario IS NULL THEN
                INSERT INTO modulo1.usuarios (nombre, apellidos, correo_electronico, contrasena_cifrada, id_rol)
                VALUES (
                    'Servicio', 'Sistema SGPMP', '{_CORREO}',
                    crypt(gen_random_uuid()::text || gen_random_uuid()::text, gen_salt('bf', 12)),
                    v_id_rol
                )
                RETURNING id_usuario INTO v_id_usuario;

                INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado)
                SELECT v_id_usuario, id_estado_cuenta, FALSE
                  FROM modulo1.estados_cuentas WHERE nombre = 'Inactivo';
            END IF;

            INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca)
            SELECT v_id_usuario, id_finca FROM modulo9.fincas
            ON CONFLICT (id_usuario, id_finca) DO NOTHING;
        END
        $$;
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION modulo9.fn_asignar_finca_usuario_servicio()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, modulo1, modulo9
        AS $$
        BEGIN
            INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca)
            SELECT id_usuario, NEW.id_finca
              FROM modulo1.usuarios WHERE correo_electronico = '{_CORREO}'
            ON CONFLICT (id_usuario, id_finca) DO NOTHING;
            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION modulo9.fn_asignar_finca_usuario_servicio() FROM PUBLIC;")
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_despues_insertar_finca
            AFTER INSERT ON modulo9.fincas
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION modulo9.fn_asignar_finca_usuario_servicio();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_despues_insertar_finca ON modulo9.fincas;")
    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_asignar_finca_usuario_servicio();")
    op.execute(
        f"""
        DELETE FROM modulo9.usuarios_fincas
         WHERE id_usuario IN (SELECT id_usuario FROM modulo1.usuarios WHERE correo_electronico = '{_CORREO}');
        """
    )
    # Si el usuario ya firmó registros (auditoría, eventos), las FK impiden
    # borrarlo; en ese caso se conserva, Inactivo y sin fincas.
    op.execute(
        f"""
        DO $$
        BEGIN
            DELETE FROM modulo1.cuentas_usuarios
             WHERE id_usuario IN (SELECT id_usuario FROM modulo1.usuarios WHERE correo_electronico = '{_CORREO}');
            DELETE FROM modulo1.usuarios WHERE correo_electronico = '{_CORREO}';
        EXCEPTION WHEN foreign_key_violation THEN
            RAISE NOTICE 'F4: el usuario de servicio tiene registros asociados; se conserva.';
        END
        $$;
        """
    )
