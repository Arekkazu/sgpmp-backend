"""F5 para el modulo2

Revision ID: d28c1a5a66d2
Revises: 00c60ae92735
Create Date: 2026-10-09 10:03:40.647438


Clasifica la totalidad de las tablas de modulo2 en patrones de acceso:

  1. CATALOGO (sin RLS):        estados_activos_biologicos
  2. YA RESUELTO F4:            activos_biologicos (3 politicas vigentes)
  3. VIA SENSOR:                asociaciones_activos_sensores (id_sensor NOT NULL)
  4. VIA INFRAESTRUCTURA:       historial_infraestructura_activo, movimientos
  5. VIA ACTIVO:                detalles, eventos, gestiones, historial, indicadores
  6. VIA EVENTO (EXISTS):       sub-eventos sobre eventos_activos
  7. AUDITORIA POR CADENA:      auditoria_activos, auditoria_asociaciones
  8. BITACORA (RF-52):          id_activo nullable, recurso bitacora_auditoria_m02

Contrato con la app (anotaciones/convencion_nomenclatura_bd.md):
  - Identidad: modulo1.fn_id_usuario_actual() lee app.current_user_id.
  - Servicio: modulo1.fn_es_usuario_servicio() identifica servicio.sistema@sgpmp.local.
  - Todas las funciones van dentro de (SELECT ...) para evaluarse por sentencia.

Correcciones aplicadas segun revision de Arekkazu (#536):
  - ENABLE ROW LEVEL SECURITY antes de FORCE (sin ENABLE, FORCE no tiene efecto).
  - asociaciones_activos_sensores por id_sensor (NOT NULL), no id_infraestructura (nullable).
  - auditoria_activos_biologicos sin f_auth(): el trigger inserta con la identidad de
    quien modifica el activo; el servicio tiene acceso a todas las fincas.
  - bitacora_auditoria_m02: filas sin activo se insertan con cualquier identidad
    declarada y se leen con permiso sobre el recurso bitacora_auditoria_m02 (id 31).
  - Sub-eventos: EXISTS sobre eventos_activos (0.25 ms) en vez de
    fn_eventos_del_usuario (84.6 ms con 200k eventos).
  - down_revision encadenada detras de la F5 de modulo9.
  - Downgrade: politicas primero, funciones al final, DISABLE RLS.

NO SE TOCAN: activos_biologicos (F4 vigente), estados_activos_biologicos (catalogo).

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd28c1a5a66d2'
down_revision: Union[str, Sequence[str], None] = '00c60ae92735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"


def permiso(recurso: str, accion: str) -> str:
    """Nombres reales de modulo1.recursos."""
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


# ── Subconsultas reutilizables ────────────────────────────────────────
_ACTIVOS_SUBQ = (
    "SELECT a.id_activo_biologico"
    f" FROM modulo2.fn_activos_del_usuario({UID}) a"
)
_INFRA_SUBQ = (
    "SELECT i.id_infraestructura"
    f" FROM modulo9.fn_infraestructuras_del_usuario({UID}) i"
)
_SENSORES_SUBQ = (
    "SELECT s.id_sensores"
    f" FROM modulo9.fn_sensores_del_usuario({UID}) s"
)

# Tablas via activo con SELECT + INSERT + UPDATE
_VIA_ACTIVO_FULL = [
    'detalles_activos_biologicos_poblacionales',
    'detalles_activos_individuales',
    'gestiones_fases',
]

_VIA_ACTIVO_APPEND = [
    'eventos_activos',
    'historial_activos',
    'historicos_estados_activos',
]

_SUB_EVENTOS = [
    'eventos_bajas',
    'eventos_crecimeinto',
    'eventos_ingresos',
    'eventos_productivos',
    'eventos_sanitarios',
]


def _enable_force(tabla: str) -> None:
    """ENABLE + FORCE RLS en una tabla (sin ENABLE, FORCE no tiene efecto)."""
    op.execute(f"ALTER TABLE modulo2.{tabla} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE modulo2.{tabla} FORCE ROW LEVEL SECURITY;")


def upgrade() -> None:

    # ================================================================
    # 0. FUNCION HELPER: activos accesibles por el usuario
    #    (no se crea fn_eventos_del_usuario: reemplazada por EXISTS)
    # ================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo2.fn_activos_del_usuario(p_usuario_id bigint)
        RETURNS TABLE (id_activo_biologico int)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo2, modulo9 AS
        $$ SELECT ab.id_activo_biologico
           FROM modulo2.activos_biologicos ab
           WHERE ab.id_infraestructura IN (
               SELECT i.id_infraestructura
               FROM modulo9.fn_infraestructuras_del_usuario(p_usuario_id) i); $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION modulo2.fn_activos_del_usuario(bigint) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION modulo2.fn_activos_del_usuario(bigint) TO sgpmp_app;")

    # ================================================================
    # 1. CATALOGO: sin RLS
    # ================================================================
    op.execute("ALTER TABLE modulo2.estados_activos_biologicos DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo2.estados_activos_biologicos NO FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 2. VIA SENSOR: asociaciones_activos_sensores
    #    id_infraestructura es NULLABLE (NULL en las 4 filas de DEV);
    #    id_sensor es NOT NULL → cadena por sensor.
    # ================================================================
    op.execute(f"""
        CREATE POLICY pol_asociaciones_select ON modulo2.asociaciones_activos_sensores
          FOR SELECT USING (id_sensor IN ({_SENSORES_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_asociaciones_insert ON modulo2.asociaciones_activos_sensores
          FOR INSERT WITH CHECK (id_sensor IN ({_SENSORES_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_asociaciones_update ON modulo2.asociaciones_activos_sensores
          FOR UPDATE USING (id_sensor IN ({_SENSORES_SUBQ}))
          WITH CHECK (id_sensor IN ({_SENSORES_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_asociaciones_servicio ON modulo2.asociaciones_activos_sensores
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('asociaciones_activos_sensores')

    # ================================================================
    # 3. VIA INFRAESTRUCTURA
    # ================================================================

    # historial_infraestructura_activo
    op.execute(f"""
        CREATE POLICY pol_hist_infra_select ON modulo2.historial_infraestructura_activo
          FOR SELECT USING (id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_hist_infra_insert ON modulo2.historial_infraestructura_activo
          FOR INSERT WITH CHECK (id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_hist_infra_update ON modulo2.historial_infraestructura_activo
          FOR UPDATE USING (id_infraestructura IN ({_INFRA_SUBQ}))
          WITH CHECK (id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_hist_infra_servicio ON modulo2.historial_infraestructura_activo
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('historial_infraestructura_activo')

    # movimientos: SELECT con OR (ambos lados ven), INSERT con AND.
    # NOTA: en DEV 3/13 movimientos son entre fincas distintas. Con AND,
    # un usuario con acceso solo a la finca origen no puede mover a otra
    # finca. Pendiente de decision con RF-48.
    op.execute(f"""
        CREATE POLICY pol_movimientos_select ON modulo2.movimientos
          FOR SELECT USING (
            id_infraestructura_origen IN ({_INFRA_SUBQ})
            OR id_infraestructura_destino IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_movimientos_insert ON modulo2.movimientos
          FOR INSERT WITH CHECK (
            id_infraestructura_origen IN ({_INFRA_SUBQ})
            AND id_infraestructura_destino IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_movimientos_servicio ON modulo2.movimientos
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('movimientos')

    # ================================================================
    # 4. VIA ACTIVO BIOLOGICO (3 saltos)
    # ================================================================

    # SELECT + INSERT + UPDATE
    for t in _VIA_ACTIVO_FULL:
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo2.{t}
              FOR SELECT USING (id_activo_biologico IN ({_ACTIVOS_SUBQ}));
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_insert ON modulo2.{t}
              FOR INSERT WITH CHECK (id_activo_biologico IN ({_ACTIVOS_SUBQ}));
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_update ON modulo2.{t}
              FOR UPDATE USING (id_activo_biologico IN ({_ACTIVOS_SUBQ}))
              WITH CHECK (id_activo_biologico IN ({_ACTIVOS_SUBQ}));
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_servicio ON modulo2.{t}
              FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
        """)
        _enable_force(t)

    # Append-only: SELECT + INSERT
    for t in _VIA_ACTIVO_APPEND:
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo2.{t}
              FOR SELECT USING (id_activo_biologico IN ({_ACTIVOS_SUBQ}));
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_insert ON modulo2.{t}
              FOR INSERT WITH CHECK (id_activo_biologico IN ({_ACTIVOS_SUBQ}));
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_servicio ON modulo2.{t}
              FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
        """)
        _enable_force(t)

    # indicadores_zootecnicos: SELECT usuarios, INSERT solo servicio
    op.execute(f"""
        CREATE POLICY pol_indicadores_zootecnicos_select ON modulo2.indicadores_zootecnicos
          FOR SELECT USING (id_activo_biologico IN ({_ACTIVOS_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_indicadores_zootecnicos_servicio ON modulo2.indicadores_zootecnicos
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('indicadores_zootecnicos')

    # bitacora_auditoria_m02 (RF-52): id_activo_biologico NULLABLE
    # Con activo → cadena. Sin activo → permiso recurso 31 (SELECT)
    # o cualquier identidad declarada (INSERT, buffer del sistema).
    op.execute(f"""
        CREATE POLICY pol_bitacora_select ON modulo2.bitacora_auditoria_m02
          FOR SELECT USING (
            {SERVICIO}
            OR (id_activo_biologico IS NOT NULL
                AND id_activo_biologico IN ({_ACTIVOS_SUBQ}))
            OR (id_activo_biologico IS NULL
                AND {permiso('bitacora_auditoria_m02', 'R')}));
    """)
    op.execute(f"""
        CREATE POLICY pol_bitacora_insert ON modulo2.bitacora_auditoria_m02
          FOR INSERT WITH CHECK (
            {SERVICIO}
            OR (id_activo_biologico IS NOT NULL
                AND id_activo_biologico IN ({_ACTIVOS_SUBQ}))
            OR (id_activo_biologico IS NULL
                AND {UID} IS NOT NULL));
    """)
    _enable_force('bitacora_auditoria_m02')

    # ================================================================
    # 5. SUB-EVENTOS: EXISTS sobre eventos_activos
    #    eventos_activos ya filtra por su propia politica RLS.
    #    EXISTS evalua solo la fila buscada: 0.25 ms vs 84.6 ms.
    # ================================================================
    for t in _SUB_EVENTOS:
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo2.{t}
              FOR SELECT USING (
                EXISTS (SELECT 1 FROM modulo2.eventos_activos ea
                        WHERE ea.id_eventos = {t}.id_evento));
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_insert ON modulo2.{t}
              FOR INSERT WITH CHECK (
                EXISTS (SELECT 1 FROM modulo2.eventos_activos ea
                        WHERE ea.id_eventos = {t}.id_evento));
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_servicio ON modulo2.{t}
              FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
        """)
        _enable_force(t)

    # eventos_reproductivos: PK = id_evento_reproductivo (FK a eventos_activos)
    op.execute("""
        CREATE POLICY pol_eventos_reproductivos_select ON modulo2.eventos_reproductivos
          FOR SELECT USING (
            EXISTS (SELECT 1 FROM modulo2.eventos_activos ea
                    WHERE ea.id_eventos = eventos_reproductivos.id_evento_reproductivo));
    """)
    op.execute("""
        CREATE POLICY pol_eventos_reproductivos_insert ON modulo2.eventos_reproductivos
          FOR INSERT WITH CHECK (
            EXISTS (SELECT 1 FROM modulo2.eventos_activos ea
                    WHERE ea.id_eventos = eventos_reproductivos.id_evento_reproductivo));
    """)
    op.execute(f"""
        CREATE POLICY pol_eventos_reproductivos_servicio ON modulo2.eventos_reproductivos
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('eventos_reproductivos')

    # ================================================================
    # 6. AUDITORIA POR CADENA
    # ================================================================

    # auditoria_activos_biologicos: cadena por activo, SIN f_auth().
    # El trigger trg_auditar_activo_biologico inserta con la identidad de
    # quien modifica el activo. El usuario de servicio tiene acceso a todas
    # las fincas via usuarios_fincas, asi que la cadena lo cubre.
    op.execute(f"""
        CREATE POLICY pol_auditoria_activos_select ON modulo2.auditoria_activos_biologicos
          FOR SELECT USING (id_activo_biologico IN ({_ACTIVOS_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditoria_activos_insert ON modulo2.auditoria_activos_biologicos
          FOR INSERT WITH CHECK (id_activo_biologico IN ({_ACTIVOS_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditoria_activos_servicio ON modulo2.auditoria_activos_biologicos
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('auditoria_activos_biologicos')

    # auditorias_asociaciones_sensor_activo: EXISTS sobre asociaciones
    # (que ya tiene RLS por sensor).
    op.execute("""
        CREATE POLICY pol_audit_asociaciones_select ON modulo2.auditorias_asociaciones_sensor_activo
          FOR SELECT USING (
            EXISTS (SELECT 1 FROM modulo2.asociaciones_activos_sensores asa
                    WHERE asa.id_asociacion_activo_sensor
                        = auditorias_asociaciones_sensor_activo.id_asociacion_activo_sensor));
    """)
    op.execute("""
        CREATE POLICY pol_audit_asociaciones_insert ON modulo2.auditorias_asociaciones_sensor_activo
          FOR INSERT WITH CHECK (
            EXISTS (SELECT 1 FROM modulo2.asociaciones_activos_sensores asa
                    WHERE asa.id_asociacion_activo_sensor
                        = auditorias_asociaciones_sensor_activo.id_asociacion_activo_sensor));
    """)
    op.execute(f"""
        CREATE POLICY pol_audit_asociaciones_servicio ON modulo2.auditorias_asociaciones_sensor_activo
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('auditorias_asociaciones_sensor_activo')

    # ================================================================
    # 7. ESTADISTICAS
    # ================================================================
    op.execute("ANALYZE modulo2.activos_biologicos;")
    op.execute("ANALYZE modulo2.eventos_activos;")
    op.execute("ANALYZE modulo2.historial_activos;")
    op.execute("ANALYZE modulo2.historicos_estados_activos;")
    op.execute("ANALYZE modulo2.gestiones_fases;")


def downgrade() -> None:

    # 1. Borrar politicas PRIMERO (antes que las funciones que usan)
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN
            SELECT policyname, tablename FROM pg_policies
            WHERE schemaname = 'modulo2'
              AND tablename != 'activos_biologicos'
          LOOP
            EXECUTE format('DROP POLICY %I ON modulo2.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)

    # 2. Quitar FORCE RLS
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo2'
              AND tablename != 'activos_biologicos'
          LOOP
            EXECUTE format('ALTER TABLE modulo2.%I NO FORCE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)

    # 3. DISABLE RLS (estas tablas no tenian RLS antes de esta migracion)
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo2'
              AND tablename NOT IN ('activos_biologicos', 'estados_activos_biologicos')
          LOOP
            EXECUTE format('ALTER TABLE modulo2.%I DISABLE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)

    # 4. Borrar funciones helper AL FINAL (sin dependencias pendientes)
    op.execute("DROP FUNCTION IF EXISTS modulo2.fn_activos_del_usuario(bigint);")

    # 5. Restaurar estado de activos_biologicos (F4)
    op.execute("ALTER TABLE modulo2.activos_biologicos ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo2.activos_biologicos FORCE ROW LEVEL SECURITY;")