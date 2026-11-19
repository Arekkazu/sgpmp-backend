"""rls_modulo7

Revision ID: 3076315fb9c7
Revises: c8e1a7f30b52
Create Date: 2026-11-18 18:54:06.920190

Clasifica la totalidad de las 16 tablas de modulo7 en patrones de acceso:

  1. CATALOGO (sin RLS):          catalogo_errores_de_integracion,
                                  tipos_documentos_aaef, permisos_api
  2. CONFIGURACION GLOBAL (RBAC): clientes_externos, canales_clientes_externos,
                                  identificadores_apis, permisos_clientes,
                                  mapeos_anexos_aaef, reglas_mapeo_aaef,
                                  versiones_contrato_aaef
  3. OPERACION / LOGS (Sistema):  integraciones_solicitudes, eventos_integracion,
                                  auditoria_peticiones, registros_ejecucion_mapeador,
                                  notificaciones_weebhook, documentos_generados_aaef,
                                  metadatos_respuesta_aaef

Recursos RBAC utilizados (modulo1.recursos):
  - integracion_aaef (pendiente de crear en seed, se asume permiso sobre
    configuracion_motor_ia (41) para admin y auditoria_m04 (46) para auditores)
  - El rol Externo AgroFusion (id_rol=9) consume el Gateway via API Key
    y solo puede consultar el endpoint de salud; no accede a tablas internas.

Reutiliza funciones de modulo1 (F5):
  - fn_id_usuario_actual()
  - fn_es_usuario_servicio()
  - fn_tiene_permiso()

Tabla de Seguimiento (Obligatoria CLAUDE.md):
+------------+--------------+----------------------------------------------+
| Fecha      | Autor        | Descripcion                                  |
+------------+--------------+----------------------------------------------+
| 2026-11-19 | SamuelPR21   | Creacion inicial politicas RLS modulo7       |      
+------------+--------------+----------------------------------------------+

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3076315fb9c7'
down_revision: Union[str, Sequence[str], None] = 'c8e1a7f30b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"
ADM = "(SELECT modulo1.fn_tiene_permiso('configuracion_motor_ia', 'R'))"  # Admin (recurso 41)
VET = "(SELECT modulo1.fn_tiene_permiso('configuracion_motor_ia', 'U'))"  # Vet aprueba anexos
AUDITORES = "(SELECT modulo1.fn_tiene_permiso('auditoria_m04', 'R'))"    # CON, RF, Admin


def _enable_force(tabla: str) -> None:
    op.execute(f"ALTER TABLE modulo7.{tabla} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE modulo7.{tabla} FORCE ROW LEVEL SECURITY;")


def upgrade() -> None:

    # ================================================================
    # 1. CATALOGOS (sin RLS): lectura publica dentro del sistema
    # ================================================================
    for t in ('catalogo_errores_de_integracion',
              'tipos_documentos_aaef',
              'permisos_api'):
        op.execute(f"ALTER TABLE modulo7.{t} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE modulo7.{t} NO FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 2. CONFIGURACION GLOBAL (RBAC puro, sin aislamiento por finca)
    #    RF-95/RF-98: el Administrador gestiona clientes y contratos.
    #    El Veterinario aprueba los anexos de mapeo (RF-AE02).
    # ================================================================

    # --- clientes_externos + canales + identificadores_apis + permisos_clientes
    for t in ('clientes_externos', 'canales_clientes_externos',
              'identificadores_apis', 'permisos_clientes'):
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo7.{t}
              FOR SELECT USING ({ADM});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_write ON modulo7.{t}
              FOR ALL USING ({ADM}) WITH CHECK ({ADM});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_servicio ON modulo7.{t}
              FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
        """)
        _enable_force(t)

    # --- mapeos_anexos_aaef: admin + veterinario (aprobacion clinica)
    op.execute("""
        CREATE POLICY pol_mapeos_anexos_aaef_select ON modulo7.mapeos_anexos_aaef
          FOR SELECT USING (""" + ADM + " OR " + VET + """);
    """)
    op.execute("""
        CREATE POLICY pol_mapeos_anexos_aaef_insert ON modulo7.mapeos_anexos_aaef
          FOR INSERT WITH CHECK (""" + ADM + """);
    """)
    op.execute("""
        CREATE POLICY pol_mapeos_anexos_aaef_update ON modulo7.mapeos_anexos_aaef
          FOR UPDATE USING (""" + ADM + " OR " + VET + """)
          WITH CHECK (""" + ADM + " OR " + VET + """);
    """)
    op.execute(f"""
        CREATE POLICY pol_mapeos_anexos_aaef_servicio ON modulo7.mapeos_anexos_aaef
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('mapeos_anexos_aaef')

    # --- reglas_mapeo_aaef: admin gestiona, vet lee
    op.execute("""
        CREATE POLICY pol_reglas_mapeo_aaef_select ON modulo7.reglas_mapeo_aaef
          FOR SELECT USING (""" + ADM + " OR " + VET + """);
    """)
    op.execute("""
        CREATE POLICY pol_reglas_mapeo_aaef_write ON modulo7.reglas_mapeo_aaef
          FOR ALL USING (""" + ADM + """) WITH CHECK (""" + ADM + """);
    """)
    op.execute(f"""
        CREATE POLICY pol_reglas_mapeo_aaef_servicio ON modulo7.reglas_mapeo_aaef
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('reglas_mapeo_aaef')

    # --- versiones_contrato_aaef: admin gestiona ciclo de vida
    op.execute(f"""
        CREATE POLICY pol_versiones_contrato_aaef_select ON modulo7.versiones_contrato_aaef
          FOR SELECT USING ({ADM} OR {SERVICIO});
    """)
    op.execute(f"""
        CREATE POLICY pol_versiones_contrato_aaef_write ON modulo7.versiones_contrato_aaef
          FOR ALL USING ({ADM}) WITH CHECK ({ADM});
    """)
    op.execute(f"""
        CREATE POLICY pol_versiones_contrato_aaef_servicio ON modulo7.versiones_contrato_aaef
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('versiones_contrato_aaef')

    # ================================================================
    # 3. OPERACION Y LOGS (Append-only, escribe solo sistema)
    #    RF-102: un registro por evento, hash SHA-256, inmutable.
    #    SELECT: auditores (Admin + Contador + Revisor Fiscal).
    # ================================================================

    _TABLAS_LOG = (
        'integraciones_solicitudes',
        'eventos_integracion',
        'auditoria_peticiones',
        'registros_ejecucion_mapeador',
        'notificaciones_weebhook',
        'documentos_generados_aaef',
        'metadatos_respuesta_aaef',
    )

    for t in _TABLAS_LOG:
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo7.{t}
              FOR SELECT USING ({AUDITORES});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_insert ON modulo7.{t}
              FOR INSERT WITH CHECK ({SERVICIO});
        """)
        # UPDATE solo para que el sistema marque estados (EXITOSO/FALLIDO)
        op.execute(f"""
            CREATE POLICY pol_{t}_update ON modulo7.{t}
              FOR UPDATE USING ({SERVICIO}) WITH CHECK ({SERVICIO});
        """)
        _enable_force(t)


def downgrade() -> None:

    # 1. Borrar politicas PRIMERO
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN
            SELECT policyname, tablename FROM pg_policies
            WHERE schemaname = 'modulo7'
          LOOP
            EXECUTE format('DROP POLICY %I ON modulo7.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)

    # 2. Quitar FORCE + DISABLE RLS
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo7'
          LOOP
            EXECUTE format('ALTER TABLE modulo7.%I NO FORCE ROW LEVEL SECURITY', t);
            EXECUTE format('ALTER TABLE modulo7.%I DISABLE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)