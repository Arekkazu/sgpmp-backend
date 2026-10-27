"""rls_modulo_04

Revision ID: 4a4b067e7a24
Revises: ebbb160365e5
Create Date: 2026-10-27 10:35:45.634755

Aplica Row Level Security al esquema modulo4 (RF-64 a RF-73).
Tablas auditables (historial_*, eventos_auditoria_m04, auditorias_predicciones,
configuracion_ia_log) son append-only: solo políticas SELECT e INSERT.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a4b067e7a24'
down_revision: Union[str, Sequence[str], None] = 'ebbb160365e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EXISTS_POLICY = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'modulo4' AND tablename = '{tabla}' AND policyname = '{policy}'
    ) THEN
        {stmt};
    END IF;
END$$;
"""


def _pol(tabla: str, policy: str, stmt: str) -> str:
    return _EXISTS_POLICY.format(tabla=tabla, policy=policy, stmt=stmt)


# ---------- Grupos de tablas por estrategia RLS ----------

# A) Catálogos globales (sin finca, sin usuario): lectura a roles operativos
#    escritura solo a admin/veterinario según catálogo.
CATALOGOS_GLOBALES = [
    'signos_clinicos',
    'patologias_signos',
    'patologias_variables_sensoricas',
    'parametros_mlops',
    'datasets',
    'metricas_drift',
]

# B) Versionado de modelos / ciclos MLOps: lectura amplia, escritura admin
#    (RF-69: RF-71 es el único emisor; el humano solo revisa/activa).
MLOPS_GLOBALES = [
    'versiones_modelos',
    'historial_estados_modelos',
    'historial_catalogo_patologias',
    'ciclos_entrenamientos',
    'configuracion_ia_log',       # append-only log de RF-65
    'distribuciones_ota',
]

# C) Motor de inferencia: configuración global por tipo_modelo (RF-65).
#    SELECT a roles técnicos; INSERT/UPDATE solo admin y veterinario.
MOTOR_IA = ['configuraciones_motor_ia']

# D) Tablas con id_finca directo: política por usuarios_fincas (RF-25/RF-46).
CON_ID_FINCA = ['alertas_patologicas']

# E) Tablas vinculadas a activo biológico (JOIN a modulo2.activos_biologicos
#    y de ahí a modulo9.infraestructuras -> modulo9.fincas -> usuarios_fincas).
#    Algunas además tienen id_usuario para "dueño del registro".
VIA_ACTIVO_BIOLOGICO = [
    'resultados_inferencia',         # RF-66 (inmutable)
    'resultados_riesgo_contagio',    # RF-68
    'observaciones_clinicas',        # RF-66/67
    'retroalimentaciones_clinicas',  # RF-72 (append-only por usuario)
    'historial_diagnostico_eventos', # RF-67 (append-only)
    'predicciones',
    'detalles_signos',
    'auditorias_predicciones',       # append-only
]

# F) Tablas vinculadas a dispositivo IoT (JOIN a modulo9.dispositivos_iot
#    -> modulo9.infraestructuras -> modulo9.fincas -> usuarios_fincas).
VIA_DISPOSITIVO_IOT = [
    'despliegues_ota',               # RF-70
    'sincronizacion_nodos_edge',     # RF-65
    'metricas_fallback_motor',       # RF-65
]

# G) Auditoría del módulo (RF-73): append-only, lectura restringida
#    a admin / contador / revisor fiscal / veterinario (limitado).
AUDITORIA_M04 = ['eventos_auditoria_m04']


# ---------- SQL fragments reutilizables ----------

# Rol IDs (según seed provisto):
# 1=Admin, 2=Productor, 3=Veterinario, 4=Ing.Campo, 5=Contador,
# 6=Supervisor, 7=Gestor, 8=RevisorFiscal, 11=USUARIOS,
# 21=IntegracionM04, 22=IntegracionM06

ROLES_LECTURA_OPERATIVA = "(1,2,3,4,5,6,7,8,21,22)"
ROLES_CLINICOS          = "(1,3)"              # Admin + Veterinario
ROLES_ADMIN             = "(1,)"
ROLES_AUDITORIA         = "(1,5,8)"            # Admin, Contador, Revisor Fiscal
ROLES_IOT               = "(1,4,21)"           # Admin, Ing.Campo, Integración M04
ROLES_SISTEMA           = "(21,22)"            # Integraciones M04/M06

# Expresión que resuelve la finca del usuario actual vía usuarios_fincas.
# Asume setting 'app.usuario_id' seteado por el backend en cada request.
FINCA_DEL_USUARIO = """
    EXISTS (
        SELECT 1 FROM modulo9.usuarios_fincas uf
        WHERE uf.id_usuario = current_setting('app.usuario_id')::integer
          AND uf.es_activo = true
          AND uf.id_finca = {col_finca}
    )
"""

# JOIN activo -> infraestructura -> finca -> usuarios_fincas
# Requiere que la tabla tenga id_activo_biologico.
FINCA_VIA_ACTIVO = """
    EXISTS (
        SELECT 1
        FROM modulo2.activos_biologicos ab
        JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
        JOIN modulo9.usuarios_fincas uf
             ON uf.id_finca = i.id_finca
            AND uf.id_usuario = current_setting('app.usuario_id')::integer
            AND uf.es_activo = true
        WHERE ab.id_activo_biologico = {col_activo}
    )
"""

# JOIN dispositivo_iot -> infraestructura -> finca -> usuarios_fincas
FINCA_VIA_IOT = """
    EXISTS (
        SELECT 1
        FROM modulo9.dispositivos_iot d
        JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
        JOIN modulo9.usuarios_fincas uf
             ON uf.id_finca = i.id_finca
            AND uf.id_usuario = current_setting('app.usuario_id')::integer
            AND uf.es_activo = true
        WHERE d.id_dispositivo_iot = {col_iot}
    )
"""

# Chequeo de rol
ES_ROL = "current_setting('app.rol_id')::integer = ANY({roles}::int[])"


# =====================================================================
# UPGRADE
# =====================================================================
def upgrade() -> None:
    # ------------------------------------------------------------------
    # A) CATÁLOGOS GLOBALES
    #    SELECT: todos los roles operativos.
    #    INSERT/UPDATE/DELETE: admin + veterinario (RF-64 permite a vet
    #    ampliar catálogo; admin lo gobierna).
    # ------------------------------------------------------------------
    for t in CATALOGOS_GLOBALES:
        op.execute(f"ALTER TABLE modulo4.{t} ENABLE ROW LEVEL SECURITY;")
        op.execute(_pol(t, f"{t}_select",
            f"CREATE POLICY {t}_select ON modulo4.{t} "
            f"FOR SELECT TO authenticated "
            f"USING ({ES_ROL.format(roles=ROLES_LECTURA_OPERATIVA)})"))
        op.execute(_pol(t, f"{t}_insert",
            f"CREATE POLICY {t}_insert ON modulo4.{t} "
            f"FOR INSERT TO authenticated "
            f"WITH CHECK ({ES_ROL.format(roles=ROLES_CLINICOS)})"))
        op.execute(_pol(t, f"{t}_update",
            f"CREATE POLICY {t}_update ON modulo4.{t} "
            f"FOR UPDATE TO authenticated "
            f"USING ({ES_ROL.format(roles=ROLES_CLINICOS)}) "
            f"WITH CHECK ({ES_ROL.format(roles=ROLES_CLINICOS)})"))
        op.execute(_pol(t, f"{t}_delete",
            f"CREATE POLICY {t}_delete ON modulo4.{t} "
            f"FOR DELETE TO authenticated "
            f"USING ({ES_ROL.format(roles=ROLES_ADMIN)})"))

    # ------------------------------------------------------------------
    # B) MLOPS GLOBALES (versiones_modelos, ciclos_entrenamientos, etc.)
    #    SELECT: roles operativos + integraciones.
    #    INSERT: solo sistema (RF-71) o admin (distribuciones_ota).
    #    UPDATE: admin (p.ej. activar versión APROBADO -> ACTIVO en RF-69).
    #    DELETE: nadie (append-only en historiales).
    # ------------------------------------------------------------------
    for t in MLOPS_GLOBALES:
        op.execute(f"ALTER TABLE modulo4.{t} ENABLE ROW LEVEL SECURITY;")
        op.execute(_pol(t, f"{t}_select",
            f"CREATE POLICY {t}_select ON modulo4.{t} "
            f"FOR SELECT TO authenticated "
            f"USING ({ES_ROL.format(roles=ROLES_LECTURA_OPERATIVA)})"))

    # version_modelo: el veterinario agrega notas_validacion (RF-69 Fase 4)
    op.execute(_pol('versiones_modelos', 'versiones_modelos_update',
        "CREATE POLICY versiones_modelos_update ON modulo4.versiones_modelos "
        "FOR UPDATE TO authenticated "
        f"USING ({ES_ROL.format(roles=ROLES_CLINICOS)}) "
        f"WITH CHECK ({ES_ROL.format(roles=ROLES_CLINICOS)})"))

    # distribuciones_ota: el admin/ingeniero lanza OTA (RF-70)
    op.execute(_pol('distribuciones_ota', 'distribuciones_ota_write',
        "CREATE POLICY distribuciones_ota_write ON modulo4.distribuciones_ota "
        "FOR INSERT TO authenticated "
        f"WITH CHECK ({ES_ROL.format(roles=ROLES_IOT)})"))
    op.execute(_pol('distribuciones_ota', 'distribuciones_ota_update',
        "CREATE POLICY distribuciones_ota_update ON modulo4.distribuciones_ota "
        "FOR UPDATE TO authenticated "
        f"USING ({ES_ROL.format(roles=ROLES_IOT)}) "
        f"WITH CHECK ({ES_ROL.format(roles=ROLES_IOT)})"))

    # Append-only: historial_estados_modelos, historial_catalogo_patologias,
    # ciclos_entrenamientos, configuracion_ia_log, metricas_drift, datasets
    for t in ['historial_estados_modelos', 'historial_catalogo_patologias',
              'ciclos_entrenamientos', 'configuracion_ia_log',
              'metricas_drift', 'datasets']:
        op.execute(_pol(t, f"{t}_insert",
            f"CREATE POLICY {t}_insert ON modulo4.{t} "
            f"FOR INSERT TO authenticated "
            f"WITH CHECK ({ES_ROL.format(roles='(1,21)')})"))  # admin + sistema M04

    # ------------------------------------------------------------------
    # C) MOTOR IA (configuraciones_motor_ia) - RF-65
    #    SELECT: roles técnicos. UPDATE/INSERT: admin + veterinario.
    # ------------------------------------------------------------------
    for t in MOTOR_IA:
        op.execute(f"ALTER TABLE modulo4.{t} ENABLE ROW LEVEL SECURITY;")
        op.execute(_pol(t, f"{t}_select",
            f"CREATE POLICY {t}_select ON modulo4.{t} "
            f"FOR SELECT TO authenticated "
            f"USING ({ES_ROL.format(roles='(1,3,4,5,21,22)')})"))
        op.execute(_pol(t, f"{t}_insert",
            f"CREATE POLICY {t}_insert ON modulo4.{t} "
            f"FOR INSERT TO authenticated "
            f"WITH CHECK ({ES_ROL.format(roles=ROLES_CLINICOS)})"))
        op.execute(_pol(t, f"{t}_update",
            f"CREATE POLICY {t}_update ON modulo4.{t} "
            f"FOR UPDATE TO authenticated "
            f"USING ({ES_ROL.format(roles=ROLES_CLINICOS)}) "
            f"WITH CHECK ({ES_ROL.format(roles=ROLES_CLINICOS)})"))
        op.execute(_pol(t, f"{t}_delete",
            f"CREATE POLICY {t}_delete ON modulo4.{t} "
            f"FOR DELETE TO authenticated "
            f"USING ({ES_ROL.format(roles=ROLES_ADMIN)})"))

    # ------------------------------------------------------------------
    # D) CON_ID_FINCA: alertas_patologicas (RF-66 / RF-68)
    #    Tiene id_finca directo + id_usuario + id_activo_biologico.
    #    SELECT por finca; INSERT solo sistema M04; UPDATE limitado.
    #    Inmutable según RF-66 (no UPDATE real, solo diagnóstico_confirmado).
    # ------------------------------------------------------------------
    t = 'alertas_patologicas'
    op.execute(f"ALTER TABLE modulo4.{t} ENABLE ROW LEVEL SECURITY;")
    op.execute(_pol(t, f"{t}_select",
        f"CREATE POLICY {t}_select ON modulo4.{t} "
        f"FOR SELECT TO authenticated "
        f"USING ("
        f"  {FINCA_DEL_USUARIO.format(col_finca='id_finca')} "
        f"  OR {ES_ROL.format(roles='(21,22)')} "  # sistemas M04/M06 ven todo
        f")"))
    op.execute(_pol(t, f"{t}_insert",
        f"CREATE POLICY {t}_insert ON modulo4.{t} "
        f"FOR INSERT TO authenticated "
        f"WITH CHECK ({ES_ROL.format(roles='(1,21)')})"))  # motor M04
    # UPDATE solo para que el veterinario confirme diagnóstico (RF-67)
    op.execute(_pol(t, f"{t}_update",
        f"CREATE POLICY {t}_update ON modulo4.{t} "
        f"FOR UPDATE TO authenticated "
        f"USING ("
        f"  {FINCA_DEL_USUARIO.format(col_finca='id_finca')} "
        f"  AND {ES_ROL.format(roles=ROLES_CLINICOS)}"
        f") "
        f"WITH CHECK ("
        f"  {FINCA_DEL_USUARIO.format(col_finca='id_finca')} "
        f"  AND {ES_ROL.format(roles=ROLES_CLINICOS)}"
        f")"))

    # ------------------------------------------------------------------
    # E) VÍA ACTIVO BIOLÓGICO
    #    Tablas que cuelgan de un activo: requieren JOIN a M02+M09 para
    #    resolver la finca. Algunas son append-only (RF-67/RF-72).
    # ------------------------------------------------------------------
    for t in VIA_ACTIVO_BIOLOGICO:
        op.execute(f"ALTER TABLE modulo4.{t} ENABLE ROW LEVEL SECURITY;")

        # SELECT: usuarios con acceso a la finca del activo + sistemas M04/M06
        op.execute(_pol(t, f"{t}_select",
            f"CREATE POLICY {t}_select ON modulo4.{t} "
            f"FOR SELECT TO authenticated "
            f"USING ("
            f"  {FINCA_VIA_ACTIVO.format(col_activo='id_activo_biologico')} "
            f"  OR {ES_ROL.format(roles=ROLES_SISTEMA)} "
            f"  OR {ES_ROL.format(roles=ROLES_ADMIN)}"
            f")"))

    # Inserts específicos por tabla (según RF):
    # - resultados_inferencia / resultados_riesgo_contagio: solo M04 (21)
    for t in ['resultados_inferencia', 'resultados_riesgo_contagio']:
        op.execute(_pol(t, f"{t}_insert",
            f"CREATE POLICY {t}_insert ON modulo4.{t} "
            f"FOR INSERT TO authenticated "
            f"WITH CHECK ({ES_ROL.format(roles='(1,21)')})"))

    # - observaciones_clinicas: veterinario + productor de la finca
    op.execute(_pol('observaciones_clinicas', 'observaciones_clinicas_insert',
        "CREATE POLICY observaciones_clinicas_insert ON modulo4.observaciones_clinicas "
        "FOR INSERT TO authenticated "
        f"WITH CHECK ("
        f"  {FINCA_VIA_ACTIVO.format(col_activo='id_activo_biologico')} "
        f"  AND {ES_ROL.format(roles='(1,2,3,4)')}"
        f")"))

    # - predicciones: solo sistema M04
    op.execute(_pol('predicciones', 'predicciones_insert',
        "CREATE POLICY predicciones_insert ON modulo4.predicciones "
        "FOR INSERT TO authenticated "
        f"WITH CHECK ({ES_ROL.format(roles='(1,21)')})"))

    # - detalles_signos: veterinario de la finca
    op.execute(_pol('detalles_signos', 'detalles_signos_insert',
        "CREATE POLICY detalles_signos_insert ON modulo4.detalles_signos "
        "FOR INSERT TO authenticated "
        "WITH CHECK ("
        "  EXISTS ("
        "    SELECT 1 FROM modulo4.observaciones_clinicas oc"
        "    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = oc.id_activo_biologico"
        "    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura"
        "    JOIN modulo9.usuarios_fincas uf"
        "         ON uf.id_finca = i.id_finca"
        "        AND uf.id_usuario = current_setting('app.usuario_id')::integer"
        "        AND uf.es_activo = true"
        "    WHERE oc.id_observacion_clinica = id_observaciones"
        "  )"
        f"  AND {ES_ROL.format(roles=ROLES_CLINICOS)}"
        ")"))

    # - retroalimentaciones_clinicas (RF-72): solo veterinario, sobre
    #   resultados de inferencia de su finca. UNIQUE por (resultado, usuario).
    op.execute(_pol('retroalimentaciones_clinicas', 'retroalimentaciones_clinicas_insert',
        "CREATE POLICY retroalimentaciones_clinicas_insert "
        "ON modulo4.retroalimentaciones_clinicas "
        "FOR INSERT TO authenticated "
        "WITH CHECK ("
        f"  {ES_ROL.format(roles=ROLES_CLINICOS)}"
        "  AND EXISTS ("
        "    SELECT 1 FROM modulo4.resultados_inferencia ri"
        "    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ri.id_activo_biologico"
        "    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura"
        "    JOIN modulo9.usuarios_fincas uf"
        "         ON uf.id_finca = i.id_finca"
        "        AND uf.id_usuario = current_setting('app.usuario_id')::integer"
        "        AND uf.es_activo = true"
        "    WHERE ri.id_resultado_inferencia = id_resultado_inferencia"
        "  )"
        "  AND id_usuario_veterinario = current_setting('app.usuario_id')::integer"
        ")"))
    # Append-only: sin UPDATE ni DELETE sobre retroalimentaciones (RF-72 restricción)

    # - Append-only: historial_diagnostico_eventos, auditorias_predicciones
    #   INSERT solo sistema; SELECT ya creado arriba.
    op.execute(_pol('historial_diagnostico_eventos', 'historial_diagnostico_eventos_insert',
        "CREATE POLICY historial_diagnostico_eventos_insert "
        "ON modulo4.historial_diagnostico_eventos "
        "FOR INSERT TO authenticated "
        f"WITH CHECK ({ES_ROL.format(roles='(1,21)')})"))
    op.execute(_pol('auditorias_predicciones', 'auditorias_predicciones_insert',
        "CREATE POLICY auditorias_predicciones_insert "
        "ON modulo4.auditorias_predicciones "
        "FOR INSERT TO authenticated "
        f"WITH CHECK ({ES_ROL.format(roles='(1,21)')})"))

    # ------------------------------------------------------------------
    # F) VÍA DISPOSITIVO IOT (RF-65 / RF-70)
    #    Tablas que cuelgan de un dispositivo: JOIN a M09 para finca.
    # ------------------------------------------------------------------
    for t in VIA_DISPOSITIVO_IOT:
        op.execute(f"ALTER TABLE modulo4.{t} ENABLE ROW LEVEL SECURITY;")
        op.execute(_pol(t, f"{t}_select",
            f"CREATE POLICY {t}_select ON modulo4.{t} "
            f"FOR SELECT TO authenticated "
            f"USING ("
            f"  {FINCA_VIA_IOT.format(col_iot='id_dispositivo_iot')} "
            f"  OR {ES_ROL.format(roles='(1,21)')}"
            f")"))
        op.execute(_pol(t, f"{t}_insert",
            f"CREATE POLICY {t}_insert ON modulo4.{t} "
            f"FOR INSERT TO authenticated "
            f"WITH CHECK ("
            f"  {FINCA_VIA_IOT.format(col_iot='id_dispositivo_iot')} "
            f"  AND {ES_ROL.format(roles=ROLES_IOT)}"
            f")"))
        op.execute(_pol(t, f"{t}_update",
            f"CREATE POLICY {t}_update ON modulo4.{t} "
            f"FOR UPDATE TO authenticated "
            f"USING ("
            f"  {FINCA_VIA_IOT.format(col_iot='id_dispositivo_iot')} "
            f"  AND {ES_ROL.format(roles=ROLES_IOT)}"
            f") "
            f"WITH CHECK ("
            f"  {FINCA_VIA_IOT.format(col_iot='id_dispositivo_iot')} "
            f"  AND {ES_ROL.format(roles=ROLES_IOT)}"
            f")"))

    # ------------------------------------------------------------------
    # G) AUDITORÍA M04 (RF-73) - eventos_auditoria_m04
    #    Append-only estricto: INSERT por sistema, SELECT por auditores.
    #    FORCE RLS para que ni el owner se salte la política.
    # ------------------------------------------------------------------
    t = 'eventos_auditoria_m04'
    op.execute(f"ALTER TABLE modulo4.{t} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE modulo4.{t} FORCE ROW LEVEL SECURITY;")
    op.execute(_pol(t, f"{t}_select",
        f"CREATE POLICY {t}_select ON modulo4.{t} "
        f"FOR SELECT TO authenticated "
        f"USING ({ES_ROL.format(roles='(1,5,8)')})"))  # admin, contador, revisor
    op.execute(_pol(t, f"{t}_select_vet",
        f"CREATE POLICY {t}_select_vet ON modulo4.{t} "
        f"FOR SELECT TO authenticated "
        f"USING ("
        f"  {ES_ROL.format(roles='(3,)')} "  # veterinario
        f"  AND tipo_evento = ANY(ARRAY["
        f"    'RETROALIMENTACION_REGISTRADA'::modulo4.enum_tipo_evento_auditoria_m04,"
        f"    'VERSION_APROBADA'::modulo4.enum_tipo_evento_auditoria_m04,"
        f"    'VERSION_RECHAZADA'::modulo4.enum_tipo_evento_auditoria_m04,"
        f"    'REENTRENAMIENTO_COMPLETADO'::modulo4.enum_tipo_evento_auditoria_m04"
        f"  ]::modulo4.enum_tipo_evento_auditoria_m04[])"
        f")"))
    op.execute(_pol(t, f"{t}_insert",
        f"CREATE POLICY {t}_insert ON modulo4.{t} "
        f"FOR INSERT TO authenticated "
        f"WITH CHECK ({ES_ROL.format(roles='(1,21)')})"))  # sistema M04
    # Sin UPDATE ni DELETE: apéndice estricto (RF-73 RNF-03)


# =====================================================================
# DOWNGRADE
# =====================================================================
def downgrade() -> None:
    todas = (
        CATALOGOS_GLOBALES + MLOPS_GLOBALES + MOTOR_IA + CON_ID_FINCA
        + VIA_ACTIVO_BIOLOGICO + VIA_DISPOSITIVO_IOT + AUDITORIA_M04
    )
    for t in todas:
        op.execute(f"DROP POLICY IF EXISTS {t}_select ON modulo4.{t};")
        op.execute(f"DROP POLICY IF EXISTS {t}_select_vet ON modulo4.{t};")
        op.execute(f"DROP POLICY IF EXISTS {t}_insert ON modulo4.{t};")
        op.execute(f"DROP POLICY IF EXISTS {t}_update ON modulo4.{t};")
        op.execute(f"DROP POLICY IF EXISTS {t}_delete ON modulo4.{t};")
        # Políticas con nombres específicos
        for suf in ('update', 'write', 'insert'):
            op.execute(f"DROP POLICY IF EXISTS {t}_{suf} ON modulo4.{t};")
        op.execute(f"ALTER TABLE modulo4.{t} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE modulo4.{t} NO FORCE ROW LEVEL SECURITY;")