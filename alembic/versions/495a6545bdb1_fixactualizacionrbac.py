"""FixActualizacionRBAC

Revision ID: 495a6545bdb1
Revises: e5a3c9b17d42
Create Date: 2026-10-20 16:36:05.519350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import logging
import re


# revision identifiers, used by Alembic.
revision: str = '495a6545bdb1'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



log = logging.getLogger("alembic.runtime.migration")

ROL_VETERINARIO = "Veterinario"
ROL_PRODUCTOR = "Productor"  # antiguo id_rol = 2 (prefijo prod_ en el CSV)
# ASUNCION: 'variables_ambientales' no existe en recursos; el recurso RF-17 es umbrales_ambientales (antiguo id 20)
REC_VARIABLES = "umbrales_ambientales"
# ASUNCION: 'alertas' no existe en recursos; el recurso es alertas_operativas
REC_ALERTAS = "alertas_operativas"
REC_AUDITORIA = "auditoria_m04"
REC_DASHBOARD = "datos_tecnicos_dashboard"

# letra -> (verbo usado en el nombre del permiso, valores posibles en modulo1.acciones)
ACCIONES = {
    "R": ("leer", ("r", "leer", "read", "select", "consultar", "lectura")),
    "U": ("actualizar", ("u", "actualizar", "update", "editar", "modificar")),
    "D": ("eliminar", ("d", "eliminar", "delete", "borrar", "desactivar")),
}


def _exigir_transaccion() -> None:
    if not op.get_context().impl.transactional_ddl:
        raise RuntimeError("Esta migración exige DDL transaccional (se desactiva FORCE RLS temporalmente).")


def _rls(force: bool) -> None:
    # permisos tiene FORCE RLS: sin contexto de usuario el DELETE/INSERT afectaría 0 filas o fallaría.
    modo = "FORCE" if force else "NO FORCE"
    op.execute(sa.text(f"ALTER TABLE modulo1.permisos {modo} ROW LEVEL SECURITY"))


def _verificar_force() -> None:
    ok = op.get_bind().execute(sa.text(
        "SELECT relforcerowsecurity FROM pg_class WHERE oid = to_regclass('modulo1.permisos')"
    )).scalar()
    if not ok:
        raise RuntimeError("FORCE ROW LEVEL SECURITY no quedó activo en modulo1.permisos")


def _uno(sql: str, descripcion: str) -> None:
    n = op.get_bind().execute(sa.text(f"SELECT count(*) FROM ({sql}) s")).scalar()
    if n != 1:
        raise RuntimeError(f"RBAC: se esperaba exactamente 1 {descripcion}, hay {n}")


def _validar_rol(nombre: str) -> None:
    _uno(f"SELECT 1 FROM modulo1.roles WHERE nombre_rol = '{nombre}'", f"rol '{nombre}'")


def _validar_recurso(nombre: str) -> None:
    _uno(f"SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = '{nombre}'", f"recurso '{nombre}'")


def _sub_accion(letra: str) -> str:
    """Subconsulta que resuelve el id_accion sin números: descubre la columna de modulo1.acciones
    (código o nombre) que identifica la acción de forma única."""
    bind = op.get_bind()
    cols = [r[0] for r in bind.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'modulo1' AND table_name = 'acciones' "
        "AND data_type IN ('character varying', 'character', 'text') ORDER BY ordinal_position"
    ))]
    valores = ", ".join(f"'{v}'" for v in ACCIONES[letra][1])
    for col in cols:
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", col):
            continue
        sub = f"SELECT id_accion FROM modulo1.acciones WHERE lower(btrim({col}::text)) = ANY (ARRAY[{valores}])"
        if bind.execute(sa.text(f"SELECT count(*) FROM ({sub}) s")).scalar() == 1:
            return sub
    raise RuntimeError(f"No se pudo resolver la acción '{letra}' en modulo1.acciones (columnas: {cols})")


def _sincronizar_secuencias() -> None:
    # Los IDs quemados dejaron las secuencias por detrás del MAX(id): evita colisiones de PK en los INSERT.
    op.execute(sa.text("""
        SELECT setval('modulo1.recursos_id_recurso_seq',
            GREATEST((SELECT COALESCE(MAX(id_recurso), 0) + 1 FROM modulo1.recursos),
                     (SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END
                      FROM modulo1.recursos_id_recurso_seq)), false)
    """))
    op.execute(sa.text("""
        SELECT setval('modulo1.permisos_id_permiso_seq',
            GREATEST((SELECT COALESCE(MAX(id_permiso), 0) + 1 FROM modulo1.permisos),
                     (SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END
                      FROM modulo1.permisos_id_permiso_seq)), false)
    """))


def _revocar(rol: str, recurso: str, letras: tuple[str, ...]) -> None:
    _validar_rol(rol)
    _validar_recurso(recurso)
    acciones = " UNION ".join(_sub_accion(letra) for letra in letras)
    op.execute(sa.text(f"""
        DELETE FROM modulo1.permisos p
        USING modulo1.roles r, modulo1.recursos rec
        WHERE p.id_rol = r.id_rol
          AND p.id_recurso = rec.id_recurso
          AND r.nombre_rol = '{rol}'
          AND rec.nombre_recurso = '{recurso}'
          AND p.id_accion IN ({acciones})
    """))


def _otorgar(rol: str, recurso: str, letra: str, descripcion: str) -> None:
    _validar_rol(rol)
    _validar_recurso(recurso)
    verbo = ACCIONES[letra][0]
    op.execute(sa.text(f"""
        INSERT INTO modulo1.permisos (nombre, descripcion, es_activo, id_rol, id_recurso, id_accion)
        SELECT lower(r.nombre_rol || '_{verbo}_' || rec.nombre_recurso),
               '{descripcion}', TRUE, r.id_rol, rec.id_recurso, a.id_accion
        FROM modulo1.roles r
        CROSS JOIN modulo1.recursos rec
        CROSS JOIN ({_sub_accion(letra)}) a
        WHERE r.nombre_rol = '{rol}'
          AND rec.nombre_recurso = '{recurso}'
        ON CONFLICT ON CONSTRAINT uq_permiso_unico
        DO UPDATE SET es_activo = TRUE, fecha_actualizacion = now()
    """))


def upgrade() -> None:
    _exigir_transaccion()
    _rls(False)
    _sincronizar_secuencias()

    # Tarea 1: Veterinario pierde edicion sobre variables ambientales
    _revocar(ROL_VETERINARIO, REC_VARIABLES, ("U",))

    # Tarea 2: Productor pierde D/U sobre alertas
    _revocar(ROL_PRODUCTOR, REC_ALERTAS, ("D", "U"))

    # Tarea 3: Veterinario gana lectura sobre auditoria_m04
    _otorgar(ROL_VETERINARIO, REC_AUDITORIA, "R", "Lectura de la auditoria del modulo de prediccion")

    # Tarea 4: nuevo recurso del dashboard y permiso para Productor
    op.execute(sa.text(f"""
        INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial)
        VALUES ('{REC_DASHBOARD}', 'Datos tecnicos del dashboard', FALSE)
        ON CONFLICT (nombre_recurso) DO NOTHING
    """))
    _otorgar(ROL_PRODUCTOR, REC_DASHBOARD, "R", "Lectura de los datos tecnicos del dashboard")

    _rls(True)
    _verificar_force()


def downgrade() -> None:
    _exigir_transaccion()
    _rls(False)
    _sincronizar_secuencias()

    # Revierte tarea 4
    op.execute(sa.text(f"""
        DELETE FROM modulo1.permisos p
        USING modulo1.recursos rec
        WHERE p.id_recurso = rec.id_recurso
          AND rec.nombre_recurso = '{REC_DASHBOARD}'
    """))
    op.execute(sa.text(f"DELETE FROM modulo1.recursos WHERE nombre_recurso = '{REC_DASHBOARD}'"))

    # Revierte tarea 3
    _revocar(ROL_VETERINARIO, REC_AUDITORIA, ("R",))

    # Revierte tarea 2: solo U existia en alertas_operativas para Productor; reinsertar D crearia un privilegio nuevo
    _otorgar(ROL_PRODUCTOR, REC_ALERTAS, "U", "Actualizacion de alertas operativas")

    # Revierte tarea 1
    _otorgar(ROL_VETERINARIO, REC_VARIABLES, "U", "Actualizacion de umbrales ambientales")

    _rls(True)
    _verificar_force()
