"""F5 para el modulo2

Revision ID: d28c1a5a66d2
Revises: 00c60ae92735
Create Date: 2026-10-09 10:03:40.647438


Clasifica la totalidad de las tablas de modulo2 en patrones de acceso:

  1. CATALOGO (sin RLS):        estados_activos_biologicos
  2. YA RESUELTO F4:            activos_biologicos (3 politicas vigentes)
  3. FINCA POR CADENA (via infra): asociaciones, historial_infra, movimientos
  4. FINCA POR CADENA (via activo): detalles, eventos, gestiones, historial, indicadores, bitacora
  5. FINCA POR CADENA (via evento): sub-eventos (bajas, crecimiento, ingresos, productivos, reproductivos, sanitarios)
  6. AUDITORIA POR CADENA:      auditoria_activos, auditoria_asociaciones

Funciones helper creadas:
  - modulo2.fn_activos_del_usuario(p_usuario_id): 1 salto activo → infra
  - modulo2.fn_eventos_del_usuario(p_usuario_id): 2 saltos evento → activo → infra

NO SE TOCAN: activos_biologicos (F4 vigente), estados_activos_biologicos (catálogo)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd28c1a5a66d2'
down_revision: Union[str, Sequence[str], None] = '00c60ae92735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Tablas sin RLS ────────────────────────────────────────────────────
_CATALOGOS = ['estados_activos_biologicos']

# ── Tablas vía infraestructura (2 saltos) ─────────────────────────────
_VIA_INFRA = ['asociaciones_activos_sensores', 'historial_infraestructura_activo']

# ── Tablas vía activo (3 saltos) ──────────────────────────────────────
_VIA_ACTIVO = [
    'detalles_activos_biologicos_poblacionales',
    'detalles_activos_individuales',
    'eventos_activos',
    'gestiones_fases',
    'historial_activos',
    'historicos_estados_activos',
    'indicadores_zootecnicos',
]

# ── Sub-eventos vía eventos_activos (4 saltos) ────────────────────────
_SUB_EVENTOS = [
    'eventos_bajas',
    'eventos_crecimeinto',
    'eventos_ingresos',
    'eventos_productivos',
    'eventos_reproductivos',
    'eventos_sanitarios',
]

# ── Auditoría por cadena ──────────────────────────────────────────────
_AUDITORIA = ['auditoria_activos_biologicos']


def upgrade() -> None:

    # ================================================================
    # 0. FUNCIONES HELPER
    # ================================================================

    # Helper 1: activos accesibles por el usuario (activo → infra → finca)
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

    # Helper 2: eventos accesibles por el usuario (evento → activo → infra → finca)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo2.fn_eventos_del_usuario(p_usuario_id bigint)
        RETURNS TABLE (id_evento int)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo2 AS
        $$ SELECT ea.id_eventos
           FROM modulo2.eventos_activos ea
           WHERE ea.id_activo_biologico IN (
               SELECT a.id_activo_biologico
               FROM modulo2.fn_activos_del_usuario(p_usuario_id) a); $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION modulo2.fn_eventos_del_usuario(bigint) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION modulo2.fn_eventos_del_usuario(bigint) TO sgpmp_app;")

    # ================================================================
    # 1. CATÁLOGOS: sin RLS
    # ================================================================
    for t in _CATALOGOS:
        op.execute(f"ALTER TABLE modulo2.{t} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE modulo2.{t} NO FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 2. VÍA INFRAESTRUCTURA (2 saltos, id_infraestructura directo)
    # ================================================================

    # asociaciones_activos_sensores: SELECT, INSERT, UPDATE, sistema
    op.execute("""
        CREATE POLICY asoc_sel ON modulo2.asociaciones_activos_sensores
          FOR SELECT USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY asoc_ins ON modulo2.asociaciones_activos_sensores
          FOR INSERT WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY asoc_upd ON modulo2.asociaciones_activos_sensores
          FOR UPDATE USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i))
          WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY asoc_sis ON modulo2.asociaciones_activos_sensores
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.asociaciones_activos_sensores FORCE ROW LEVEL SECURITY;")

    # historial_infraestructura_activo: SELECT, INSERT, UPDATE (cerrar asociaciones)
    op.execute("""
        CREATE POLICY hist_infra_sel ON modulo2.historial_infraestructura_activo
          FOR SELECT USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY hist_infra_ins ON modulo2.historial_infraestructura_activo
          FOR INSERT WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY hist_infra_upd ON modulo2.historial_infraestructura_activo
          FOR UPDATE USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i))
          WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY hist_infra_sis ON modulo2.historial_infraestructura_activo
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.historial_infraestructura_activo FORCE ROW LEVEL SECURITY;")

    # movimientos: origen O destino accesible
    op.execute("""
        CREATE POLICY mov_sel ON modulo2.movimientos
          FOR SELECT USING (
            id_infraestructura_origen IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i)
            OR id_infraestructura_destino IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY mov_ins ON modulo2.movimientos
          FOR INSERT WITH CHECK (
            id_infraestructura_origen IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i)
            AND id_infraestructura_destino IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY mov_sis ON modulo2.movimientos
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.movimientos FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 3. VÍA ACTIVO BIOLÓGICO (3 saltos)
    # ================================================================

    # --- detalles_activos_biologicos_poblacionales (SELECT, INSERT, UPDATE)
    op.execute("""
        CREATE POLICY det_pob_sel ON modulo2.detalles_activos_biologicos_poblacionales
          FOR SELECT USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY det_pob_ins ON modulo2.detalles_activos_biologicos_poblacionales
          FOR INSERT WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY det_pob_upd ON modulo2.detalles_activos_biologicos_poblacionales
          FOR UPDATE USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a))
          WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY det_pob_sis ON modulo2.detalles_activos_biologicos_poblacionales
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.detalles_activos_biologicos_poblacionales FORCE ROW LEVEL SECURITY;")

    # --- detalles_activos_individuales (SELECT, INSERT, UPDATE)
    op.execute("""
        CREATE POLICY det_ind_sel ON modulo2.detalles_activos_individuales
          FOR SELECT USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY det_ind_ins ON modulo2.detalles_activos_individuales
          FOR INSERT WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY det_ind_upd ON modulo2.detalles_activos_individuales
          FOR UPDATE USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a))
          WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY det_ind_sis ON modulo2.detalles_activos_individuales
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.detalles_activos_individuales FORCE ROW LEVEL SECURITY;")

    # --- eventos_activos (SELECT, INSERT — append-only en la práctica)
    op.execute("""
        CREATE POLICY ev_act_sel ON modulo2.eventos_activos
          FOR SELECT USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY ev_act_ins ON modulo2.eventos_activos
          FOR INSERT WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY ev_act_sis ON modulo2.eventos_activos
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.eventos_activos FORCE ROW LEVEL SECURITY;")

    # --- gestiones_fases (SELECT, INSERT, UPDATE para cerrar fases)
    op.execute("""
        CREATE POLICY gest_fases_sel ON modulo2.gestiones_fases
          FOR SELECT USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY gest_fases_ins ON modulo2.gestiones_fases
          FOR INSERT WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY gest_fases_upd ON modulo2.gestiones_fases
          FOR UPDATE USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a))
          WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY gest_fases_sis ON modulo2.gestiones_fases
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.gestiones_fases FORCE ROW LEVEL SECURITY;")

    # --- historial_activos (append-only: SELECT, INSERT)
    op.execute("""
        CREATE POLICY hist_act_sel ON modulo2.historial_activos
          FOR SELECT USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY hist_act_ins ON modulo2.historial_activos
          FOR INSERT WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY hist_act_sis ON modulo2.historial_activos
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.historial_activos FORCE ROW LEVEL SECURITY;")

    # --- historicos_estados_activos (append-only: SELECT, INSERT)
    op.execute("""
        CREATE POLICY hist_est_sel ON modulo2.historicos_estados_activos
          FOR SELECT USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY hist_est_ins ON modulo2.historicos_estados_activos
          FOR INSERT WITH CHECK (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY hist_est_sis ON modulo2.historicos_estados_activos
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.historicos_estados_activos FORCE ROW LEVEL SECURITY;")

    # --- indicadores_zootecnicos (SELECT, INSERT por sistema)
    op.execute("""
        CREATE POLICY ind_zoot_sel ON modulo2.indicadores_zootecnicos
          FOR SELECT USING (
            id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY ind_zoot_sis ON modulo2.indicadores_zootecnicos
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.indicadores_zootecnicos FORCE ROW LEVEL SECURITY;")

    # --- bitacora_auditoria_m02 (RF-52): id_activo nullable
    op.execute("""
        CREATE POLICY bitacora_sel ON modulo2.bitacora_auditoria_m02
          FOR SELECT USING (
            modulo1.f_sistema()
            OR (id_activo_biologico IS NOT NULL
                AND id_activo_biologico IN (
                  SELECT a.id_activo_biologico
                  FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a))
            OR (id_activo_biologico IS NULL AND modulo1.f_auth()));
    """)
    op.execute("""
        CREATE POLICY bitacora_ins ON modulo2.bitacora_auditoria_m02
          FOR INSERT WITH CHECK (
            modulo1.f_sistema()
            OR (id_activo_biologico IS NOT NULL
                AND id_activo_biologico IN (
                  SELECT a.id_activo_biologico
                  FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a))
            OR (id_activo_biologico IS NULL AND modulo1.f_auth()));
    """)
    op.execute("ALTER TABLE modulo2.bitacora_auditoria_m02 FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 4. SUB-EVENTOS (4 saltos: vía eventos_activos)
    #    PK = FK a eventos_activos.id_eventos
    # ================================================================

    # Tablas con id_evento como PK y FK a eventos_activos
    for t in ['eventos_bajas', 'eventos_crecimeinto', 'eventos_ingresos',
              'eventos_productivos', 'eventos_sanitarios']:
        op.execute(f"""
            CREATE POLICY {t}_sel ON modulo2.{t}
              FOR SELECT USING (
                id_evento IN (
                  SELECT e.id_evento
                  FROM modulo2.fn_eventos_del_usuario(modulo1.f_uid()) e));
        """)
        op.execute(f"""
            CREATE POLICY {t}_ins ON modulo2.{t}
              FOR INSERT WITH CHECK (
                id_evento IN (
                  SELECT e.id_evento
                  FROM modulo2.fn_eventos_del_usuario(modulo1.f_uid()) e));
        """)
        op.execute(f"""
            CREATE POLICY {t}_sis ON modulo2.{t}
              FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
        """)
        op.execute(f"ALTER TABLE modulo2.{t} FORCE ROW LEVEL SECURITY;")

    # eventos_reproductivos: PK = id_evento_reproductivo (FK a eventos_activos.id_eventos)
    op.execute("""
        CREATE POLICY ev_rep_sel ON modulo2.eventos_reproductivos
          FOR SELECT USING (
            id_evento_reproductivo IN (
              SELECT e.id_evento
              FROM modulo2.fn_eventos_del_usuario(modulo1.f_uid()) e));
    """)
    op.execute("""
        CREATE POLICY ev_rep_ins ON modulo2.eventos_reproductivos
          FOR INSERT WITH CHECK (
            id_evento_reproductivo IN (
              SELECT e.id_evento
              FROM modulo2.fn_eventos_del_usuario(modulo1.f_uid()) e));
    """)
    op.execute("""
        CREATE POLICY ev_rep_sis ON modulo2.eventos_reproductivos
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo2.eventos_reproductivos FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 5. AUDITORÍA POR CADENA (read + insert)
    # ================================================================

    # auditoria_activos_biologicos: vía activos (3 saltos)
    op.execute("""
        CREATE POLICY audit_ab_sel ON modulo2.auditoria_activos_biologicos
          FOR SELECT USING (
            modulo1.f_sistema()
            OR id_activo_biologico IN (
              SELECT a.id_activo_biologico
              FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a));
    """)
    op.execute("""
        CREATE POLICY audit_ab_ins ON modulo2.auditoria_activos_biologicos
          FOR INSERT WITH CHECK (
            modulo1.f_sistema()
            OR (modulo1.f_auth()
                AND id_activo_biologico IN (
                  SELECT a.id_activo_biologico
                  FROM modulo2.fn_activos_del_usuario(modulo1.f_uid()) a)));
    """)
    op.execute("ALTER TABLE modulo2.auditoria_activos_biologicos FORCE ROW LEVEL SECURITY;")

    # auditorias_asociaciones_sensor_activo: vía asociaciones → infra (3 saltos)
    op.execute("""
        CREATE POLICY audit_asa_sel ON modulo2.auditorias_asociaciones_sensor_activo
          FOR SELECT USING (
            modulo1.f_sistema()
            OR id_asociacion_activo_sensor IN (
              SELECT asa.id_asociacion_activo_sensor
              FROM modulo2.asociaciones_activos_sensores asa
              WHERE asa.id_infraestructura IN (
                SELECT i.id_infraestructura
                FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i)));
    """)
    op.execute("""
        CREATE POLICY audit_asa_ins ON modulo2.auditorias_asociaciones_sensor_activo
          FOR INSERT WITH CHECK (
            modulo1.f_sistema()
            OR (modulo1.f_auth()
                AND id_asociacion_activo_sensor IN (
                  SELECT asa.id_asociacion_activo_sensor
                  FROM modulo2.asociaciones_activos_sensores asa
                  WHERE asa.id_infraestructura IN (
                    SELECT i.id_infraestructura
                    FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i))));
    """)
    op.execute("ALTER TABLE modulo2.auditorias_asociaciones_sensor_activo FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 6. ESTADÍSTICAS
    # ================================================================
    op.execute("ANALYZE modulo2.activos_biologicos;")
    op.execute("ANALYZE modulo2.eventos_activos;")
    op.execute("ANALYZE modulo2.historial_activos;")
    op.execute("ANALYZE modulo2.historicos_estados_activos;")
    op.execute("ANALYZE modulo2.gestiones_fases;")


def downgrade() -> None:

    # 1. Borrar funciones helper
    op.execute("DROP FUNCTION IF EXISTS modulo2.fn_eventos_del_usuario(bigint);")
    op.execute("DROP FUNCTION IF EXISTS modulo2.fn_activos_del_usuario(bigint);")

    # 2. Borrar todas las políticas creadas en modulo2
    #    (excepto las de activos_biologicos que son de F4)
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

    # 3. Quitar FORCE RLS de las tablas que lo recibieron
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo2'
              AND tablename != 'activos_biologicos'
          LOOP
            EXECUTE format('ALTER TABLE modulo2.%I NO FORCE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)

    # 4. Restaurar estado original: solo activos_biologicos tiene RLS + FORCE
    op.execute("ALTER TABLE modulo2.activos_biologicos ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo2.activos_biologicos FORCE ROW LEVEL SECURITY;")
