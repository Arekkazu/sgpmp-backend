# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DB-08: permisos segun la tarea (variables_ambientales_criticas, D en alertas, dashboard tecnico) |
"""FixActualizacionRBAC

Revision ID: 495a6545bdb1
Revises: 032b0b6db060
Create Date: 2026-10-20 16:36:05.519350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import logging
import re


# revision identifiers, used by Alembic.
revision: str = '495a6545bdb1'
down_revision: Union[str, Sequence[str], None] = '032b0b6db060'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



log = logging.getLogger("alembic.runtime.migration")

ROL_ADMINISTRADOR = "Administrador"
ROL_VETERINARIO = "Veterinario"
ROL_INGENIERO = "Ingeniero de Campo"
# El Veterinario conserva U sobre umbrales_ambientales (RF-17: editan umbrales
# "Administrador o Veterinario"). Solo marcar una variable como crítica (es_critica,
# RFC-016) es del Administrador: va en un recurso propio.
REC_VARIABLES_CRITICAS = "variables_ambientales_criticas"
# Recurso de RF-57 (id 32). Atender (U) sigue para Productor y Veterinario;
# descartar (D) solo Administrador y Veterinario.
REC_ALERTAS = "alertas_operativas"
REC_AUDITORIA = "auditoria_m04"
# RF-58: datos técnicos del dashboard (batería, RSSI). Lo tienen los roles técnicos;
# el Productor no, y así se reemplaza el id_rol = 2 quemado en el backend (DEV-39).
REC_DASHBOARD = "datos_tecnicos_dashboard"

# Prefijo del rol en el nombre del permiso (CLAUDE.md: {rol}_{accion}_{recurso}).
PREFIJO_ROL = {"Administrador": "admin", "Veterinario": "vet", "Ingeniero de Campo": "ing"}

# letra -> (verbo usado en el nombre del permiso, valores posibles en modulo1.acciones)
ACCIONES = {
    "R": ("leer", ("r", "leer", "read", "select", "consultar", "lectura")),
    "U": ("actualizar", ("u", "actualizar", "update", "editar", "modificar")),
    "D": ("desactivar", ("d", "eliminar", "delete", "borrar", "desactivar")),
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
        SELECT '{PREFIJO_ROL[rol]}_{verbo}_' || rec.nombre_recurso,
               '{descripcion}', TRUE, r.id_rol, rec.id_recurso, a.id_accion
        FROM modulo1.roles r
        CROSS JOIN modulo1.recursos rec
        CROSS JOIN ({_sub_accion(letra)}) a
        WHERE r.nombre_rol = '{rol}'
          AND rec.nombre_recurso = '{recurso}'
        ON CONFLICT ON CONSTRAINT uq_permiso_unico
        DO UPDATE SET es_activo = TRUE, fecha_actualizacion = now()
    """))


def _crear_recurso(nombre: str, descripcion: str) -> None:
    op.execute(sa.text(f"""
        INSERT INTO modulo1.recursos (nombre_recurso, descripcion, es_proceso_especial)
        VALUES ('{nombre}', '{descripcion}', FALSE)
        ON CONFLICT (nombre_recurso) DO NOTHING
    """))


def upgrade() -> None:
    _exigir_transaccion()
    _rls(False)
    _sincronizar_secuencias()

    # 1. es_critica (RF-17 / RFC-016): solo el Administrador
    _crear_recurso(REC_VARIABLES_CRITICAS, "Marcar variables ambientales como criticas (RFC-016)")
    _otorgar(ROL_ADMINISTRADOR, REC_VARIABLES_CRITICAS, "U", "Marcar variables ambientales como criticas")

    # 2. Descartar alertas (RF-57 E11): Administrador y Veterinario
    _otorgar(ROL_ADMINISTRADOR, REC_ALERTAS, "D", "Descartar alertas operativas")
    _otorgar(ROL_VETERINARIO, REC_ALERTAS, "D", "Descartar alertas operativas")

    # 3. Auditoría de M04 (RF-73): también el Veterinario
    _otorgar(ROL_VETERINARIO, REC_AUDITORIA, "R", "Lectura de la auditoria del modulo de prediccion")

    # 4. Datos técnicos del dashboard (RF-58): roles técnicos, no el Productor
    _crear_recurso(REC_DASHBOARD, "Datos tecnicos del dashboard (bateria, RSSI)")
    for rol in (ROL_ADMINISTRADOR, ROL_VETERINARIO, ROL_INGENIERO):
        _otorgar(rol, REC_DASHBOARD, "R", "Lectura de los datos tecnicos del dashboard")

    _rls(True)
    _verificar_force()


def downgrade() -> None:
    # Los permisos del Administrador son permanentes (trigger ADMIN_PERM_NO_DELETE):
    # se conservan junto con sus recursos. Se retiran los de los demás roles.
    _exigir_transaccion()
    _rls(False)

    for rol in (ROL_VETERINARIO, ROL_INGENIERO):
        _revocar(rol, REC_DASHBOARD, ("R",))
    _revocar(ROL_VETERINARIO, REC_AUDITORIA, ("R",))
    _revocar(ROL_VETERINARIO, REC_ALERTAS, ("D",))

    _rls(True)
    _verificar_force()
