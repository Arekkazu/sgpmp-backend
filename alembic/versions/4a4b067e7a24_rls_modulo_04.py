# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-27 | SamuelPR21 | RLS modulo4 RF-64..73: politicas pol_* por permiso y alcance |
# | 2026-10-29 | Arekkazu | RLS modulo4 RF-64..73: recursos reales, predicciones por padre, escrituras de usuario y cadena tras 440ee187dab5 |
"""rls_modulo_04

Revision ID: 4a4b067e7a24
Revises: 440ee187dab5
Create Date: 2026-10-27 10:35:45.634755

Aplica Row Level Security al esquema modulo4 (RF-64 a RF-73) sobre sus 26 tablas.

Patrones de acceso:
  1. CATALOGO CLINICO (RF-64):  signos_clinicos, patologias_signos,
                                patologias_variables_sensoricas,
                                historial_catalogo_patologias
  2. MLOPS / MODELOS (RF-69-71): parametros_mlops, versiones_modelos,
                                historial_estados_modelos, datasets,
                                metricas_drift, ciclos_entrenamientos,
                                distribuciones_ota
  3. MOTOR IA (RF-65):          configuraciones_motor_ia, configuracion_ia_log
  4. FINCA DIRECTA:             alertas_patologicas
  5. VIA ACTIVO BIOLOGICO:      resultados_inferencia, resultados_riesgo_contagio,
                                observaciones_clinicas, historial_diagnostico_eventos,
                                predicciones, auditorias_predicciones;
                                EXISTS sobre padre: detalles_signos (-> observaciones),
                                retroalimentaciones_clinicas (-> resultados)
  6. VIA DISPOSITIVO IOT:       despliegues_ota, sincronizacion_nodos_edge,
                                metricas_fallback_motor
  7. AUDITORIA (RF-73):         eventos_auditoria_m04

Append-only (solo SELECT/INSERT, tambien para el usuario de servicio):
  historial_estados_modelos, historial_catalogo_patologias,
  historial_diagnostico_eventos, configuracion_ia_log, eventos_auditoria_m04,
  auditorias_predicciones, resultados_inferencia, retroalimentaciones_clinicas

Recursos RBAC (modulo1.recursos), los mismos que exige cada router de src/prediction:
  patologias                 (18) RF-64  C/R/U/D
  configuracion_motor_ia     (41) RF-65  C/R; RF-68 riesgo de contagio E
  historial_diagnostico      (42) RF-66/67 R
  version_modelo             (43) RF-69/71 R/U/E
  ota_status                 (44) RF-70  R/E
  retroalimentacion_clinica  (45) RF-72  C/R
  auditoria_m04              (46) RF-73  R/E

Reutiliza funciones de modulo9 (F5):
  - fn_fincas_del_usuario()
  - fn_infraestructuras_del_usuario()
  - fn_dispositivos_del_usuario()

Contrato con la app:
  - Identidad: modulo1.fn_id_usuario_actual() lee app.current_user_id
  - Servicio: modulo1.fn_es_usuario_servicio() identifica servicio.sistema@sgpmp.local
  - Permisos: modulo1.fn_tiene_permiso(recurso, accion); no hay IDs de rol quemados
  - Todas las funciones van dentro de (SELECT ...) para evaluarse por sentencia
  - FORCE RLS: el motor de inferencia, el reentrenamiento y los procesos de fondo
    de M04 DEBEN declarar el usuario de servicio en app.current_user_id; de lo
    contrario sus INSERT/UPDATE quedan bloqueados (ver pol_*_servicio).

Tabla de seguimiento
  Tipo:                     Migracion Alembic (RLS)
  Nombre:                   rls_modulo_04
  Responsable:              Samuel
  Version:                  <X.Y.Z segun semantic-release>
  Version Alembic:          4a4b067e7a24 (down_revision: 440ee187dab5)
  Fecha:                    2026-10-28
  Estado:                   En correccion (PR pendiente de autorizacion)
  Repositorio:              Arekkazu/sgpmp-backend
  Commit:                   <hash tras reescribir commits>
  Descripcion:              Habilita y fuerza RLS en las 26 tablas de modulo4
                            (select/insert/update + politica de servicio)
  Justificacion:            Aislar predicciones, diagnosticos, MLOps y auditoria
                            del motor de IA por finca/activo/dispositivo/permiso
  Objetos Afectados:        26 tablas de modulo4 (ENABLE + FORCE RLS), politicas pol_*
  Requerimientos Funcionales: RF-64, RF-65, RF-66, RF-67, RF-68, RF-69, RF-70,
                            RF-71, RF-72, RF-73
  Evaluador:                <evaluador>
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a4b067e7a24'
down_revision: Union[str, Sequence[str], None] = '440ee187dab5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Contexto de sesion (mismo contrato que modulo3) ───────────────────
UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"


def permiso(recurso: str, accion: str) -> str:
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


# ── Recursos RBAC: los mismos que exige cada router (src/prediction) ───
R_CATALOGO = 'patologias'                   # RF-64, patologia_m04_router (18)
R_MOTOR = 'configuracion_motor_ia'          # RF-65/68, motor_ia y riesgo_contagio (41)
R_HIST_DIAG = 'historial_diagnostico'       # RF-66/67, historial_diagnostico_router (42)
R_MODELOS = 'version_modelo'                # RF-69/71, version_modelo_router (43)
R_OTA = 'ota_status'                        # RF-70, ota_router (44)
R_RETRO = 'retroalimentacion_clinica'       # RF-72, retroalimentacion_clinica_router (45)
R_AUDITORIA = 'auditoria_m04'               # RF-73, auditoria_m04_router (46)

# El catálogo se crea (C), edita (U) y desactiva (D) desde patologia_m04_router.
_CATALOGO_ESCRITURA = (
    f"({permiso(R_CATALOGO, 'C')} OR {permiso(R_CATALOGO, 'U')} OR {permiso(R_CATALOGO, 'D')})"
)

# ── Subconsultas de alcance (modulo9) ─────────────────────────────────
_INFRA_SUBQ = (
    "SELECT i.id_infraestructura"
    f" FROM modulo9.fn_infraestructuras_del_usuario({UID}) i"
)
_DISP_SUBQ = (
    "SELECT d.id_dispositivo_iot"
    f" FROM modulo9.fn_dispositivos_del_usuario({UID}) d"
)
_FINCA_SUBQ = (
    "SELECT f.id_finca"
    f" FROM modulo9.fn_fincas_del_usuario({UID}) f"
)


def _activo_visible(tabla: str) -> str:
    """El activo biologico de la fila pertenece a una infraestructura del usuario."""
    return (
        "EXISTS (SELECT 1 FROM modulo2.activos_biologicos ab "
        f"WHERE ab.id_activo_biologico = {tabla}.id_activo_biologico "
        f"AND ab.id_infraestructura IN ({_INFRA_SUBQ}))"
    )


def _dispositivo_visible(tabla: str) -> str:
    return f"{tabla}.id_dispositivo_iot IN ({_DISP_SUBQ})"


# ── Nombre singular de cada tabla (convencion: pol_<singular>_<criterio>) ──
SING = {
    'signos_clinicos': 'signo_clinico',
    'patologias_signos': 'patologia_signo',
    'patologias_variables_sensoricas': 'patologia_variable_sensorica',
    'historial_catalogo_patologias': 'historial_catalogo_patologia',
    'parametros_mlops': 'parametro_mlops',
    'versiones_modelos': 'version_modelo',
    'historial_estados_modelos': 'historial_estado_modelo',
    'datasets': 'dataset',
    'metricas_drift': 'metrica_drift',
    'ciclos_entrenamientos': 'ciclo_entrenamiento',
    'distribuciones_ota': 'distribucion_ota',
    'configuraciones_motor_ia': 'configuracion_motor_ia',
    'configuracion_ia_log': 'configuracion_ia_log',
    'alertas_patologicas': 'alerta_patologica',
    'resultados_inferencia': 'resultado_inferencia',
    'resultados_riesgo_contagio': 'resultado_riesgo_contagio',
    'observaciones_clinicas': 'observacion_clinica',
    'retroalimentaciones_clinicas': 'retroalimentacion_clinica',
    'historial_diagnostico_eventos': 'historial_diagnostico_evento',
    'predicciones': 'prediccion',
    'detalles_signos': 'detalle_signo',
    'auditorias_predicciones': 'auditoria_prediccion',
    'despliegues_ota': 'despliegue_ota',
    'sincronizacion_nodos_edge': 'sincronizacion_nodo_edge',
    'metricas_fallback_motor': 'metrica_fallback_motor',
    'eventos_auditoria_m04': 'evento_auditoria_m04',
}


# ── Helpers ───────────────────────────────────────────────────────────
def _pol(tabla: str, criterio: str, cmd: str, using: str = None, check: str = None) -> None:
    nombre = f"pol_{SING[tabla]}_{criterio}"
    sql = f"CREATE POLICY {nombre} ON modulo4.{tabla} FOR {cmd}"
    if using:
        sql += f" USING ({using})"
    if check:
        sql += f" WITH CHECK ({check})"
    op.execute(sql + ";")


def _servicio(tabla: str, append_only: bool = False) -> None:
    """Usuario de servicio: ALL, o solo SELECT+INSERT en tablas append-only."""
    if append_only:
        _pol(tabla, 'servicio_select', 'SELECT', using=SERVICIO)
        _pol(tabla, 'servicio_insert', 'INSERT', check=SERVICIO)
    else:
        _pol(tabla, 'servicio', 'ALL', using=SERVICIO, check=SERVICIO)


def _enable_force(tabla: str) -> None:
    op.execute(f"ALTER TABLE modulo4.{tabla} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE modulo4.{tabla} FORCE ROW LEVEL SECURITY;")


def _politicas(tabla: str, select: str, insert: str = None, update: str = None,
               append_only: bool = False) -> None:
    _pol(tabla, 'select', 'SELECT', using=select)
    if insert:
        _pol(tabla, 'insert', 'INSERT', check=insert)
    if update:
        _pol(tabla, 'update', 'UPDATE', using=update, check=update)
    _servicio(tabla, append_only=append_only)
    _enable_force(tabla)


# =====================================================================
# UPGRADE
# =====================================================================
def upgrade() -> None:

    # ================================================================
    # 1. CATALOGO CLINICO (RF-64): global, sin finca
    #    SELECT: cualquier usuario autenticado (nombres de patologias/signos
    #    se muestran en RF-66/67). Escritura: permiso U sobre el catalogo.
    # ================================================================
    for t in ('signos_clinicos', 'patologias_signos', 'patologias_variables_sensoricas'):
        _politicas(
            t,
            select=f"{UID} IS NOT NULL",
            insert=_CATALOGO_ESCRITURA,
            update=_CATALOGO_ESCRITURA,
        )

    # historial del catalogo: append-only; lo escribe un trigger como invoker
    _politicas(
        'historial_catalogo_patologias',
        select=permiso(R_CATALOGO, 'R'),
        insert=_CATALOGO_ESCRITURA,
        append_only=True,
    )

    # ================================================================
    # 2. MLOPS / MODELOS (RF-69/70/71): global
    # ================================================================
    _politicas(
        'parametros_mlops',
        select=permiso(R_MODELOS, 'R'),
        insert=permiso(R_MODELOS, 'U'),
        update=permiso(R_MODELOS, 'U'),
    )
    # INSERT de versiones: solo sistema (RF-71). UPDATE humano: validacion (RF-69)
    _politicas(
        'versiones_modelos',
        select=permiso(R_MODELOS, 'R'),
        update=permiso(R_MODELOS, 'U'),
    )
    _politicas(
        'historial_estados_modelos',
        select=permiso(R_MODELOS, 'R'),
        insert=permiso(R_MODELOS, 'U'),
        append_only=True,
    )
    # datasets y metricas_drift: los escribe solo el sistema
    _politicas('datasets', select=permiso(R_MODELOS, 'R'))
    _politicas('metricas_drift', select=permiso(R_MODELOS, 'R'))
    # ciclos: ejecucion manual (E) o automatica (servicio)
    _politicas(
        'ciclos_entrenamientos',
        select=permiso(R_MODELOS, 'R'),
        insert=permiso(R_MODELOS, 'E'),
    )
    # OTA global: lanzar y actualizar requiere permiso E (RF-70)
    _politicas(
        'distribuciones_ota',
        select=permiso(R_OTA, 'R'),
        insert=permiso(R_OTA, 'E'),
        update=permiso(R_OTA, 'E'),
    )

    # ================================================================
    # 3. MOTOR IA (RF-65): configuracion global por tipo_modelo
    # ================================================================
    _politicas(
        'configuraciones_motor_ia',
        select=permiso(R_MOTOR, 'R'),
        insert=permiso(R_MOTOR, 'C'),
        update=permiso(R_MOTOR, 'C'),
    )
    _politicas(
        'configuracion_ia_log',
        select=permiso(R_MOTOR, 'R'),
        insert=permiso(R_MOTOR, 'C'),
        append_only=True,
    )

    # ================================================================
    # 4. FINCA DIRECTA: alertas_patologicas (RF-66/68)
    #    INSERT: solo sistema. UPDATE: confirmar diagnostico (RF-67).
    # ================================================================
    _politicas(
        'alertas_patologicas',
        select=f"alertas_patologicas.id_finca IN ({_FINCA_SUBQ})",
        update=(
            f"{permiso(R_HIST_DIAG, 'U')} "
            f"AND alertas_patologicas.id_finca IN ({_FINCA_SUBQ})"
        ),
    )

    # ================================================================
    # 5. VIA ACTIVO BIOLOGICO (2 saltos: activo -> infraestructura)
    #    Sin excepcion para Administrador: ve solo sus fincas.
    # ================================================================
    # RF-66 (inmutable): solo sistema inserta
    _politicas(
        'resultados_inferencia',
        select=_activo_visible('resultados_inferencia'),
        append_only=True,
    )
    # RF-68: el cálculo manual (41·E) y el sistema insertan; asociar_alerta actualiza
    _politicas(
        'resultados_riesgo_contagio',
        select=_activo_visible('resultados_riesgo_contagio'),
        insert=f"{permiso(R_MOTOR, 'E')} AND {_activo_visible('resultados_riesgo_contagio')}",
        update=f"{permiso(R_MOTOR, 'E')} AND {_activo_visible('resultados_riesgo_contagio')}",
    )
    # RF-66/67: hoy ningún endpoint registra observaciones; las escribe el sistema
    _politicas(
        'observaciones_clinicas',
        select=_activo_visible('observaciones_clinicas'),
    )
    # RF-67 (append-only): solo sistema inserta
    _politicas(
        'historial_diagnostico_eventos',
        select=_activo_visible('historial_diagnostico_eventos'),
        append_only=True,
    )
    # predicciones no tiene id_activo_biologico: hereda la visibilidad de su observación
    _politicas('predicciones', select=(
        "EXISTS (SELECT 1 FROM modulo4.observaciones_clinicas oc "
        "WHERE oc.id_observacion_clinica = predicciones.id_observacion)"))
    # y la auditoría hereda la de su predicción
    _politicas(
        'auditorias_predicciones',
        select=(
            "EXISTS (SELECT 1 FROM modulo4.predicciones p "
            "WHERE p.id_prediccion = auditorias_predicciones.id_prediccion)"
        ),
        append_only=True,
    )

    # EXISTS sobre padre: heredan la visibilidad de observaciones_clinicas
    _obs_visible = (
        "EXISTS (SELECT 1 FROM modulo4.observaciones_clinicas oc "
        "WHERE oc.id_observacion_clinica = detalles_signos.id_observaciones)"
    )
    _politicas('detalles_signos', select=_obs_visible)

    # RF-72 (append-only): veterinario con permiso, sobre resultados visibles
    # y firmando con su propio id. Columnas calificadas con el nombre de tabla.
    _res_visible = (
        "EXISTS (SELECT 1 FROM modulo4.resultados_inferencia ri "
        "WHERE ri.id_resultado_inferencia = "
        "retroalimentaciones_clinicas.id_resultado_inferencia)"
    )
    _politicas(
        'retroalimentaciones_clinicas',
        select=_res_visible,
        insert=(
            f"{permiso(R_RETRO, 'C')} "
            f"AND {_res_visible} "
            f"AND retroalimentaciones_clinicas.id_usuario_veterinario = {UID}"
        ),
        append_only=True,
    )

    # ================================================================
    # 6. VIA DISPOSITIVO IOT (3 saltos): RF-65 / RF-70
    # ================================================================
    # OTA por dispositivo: lanzar/actualizar con permiso E sobre el recurso OTA
    _politicas(
        'despliegues_ota',
        select=_dispositivo_visible('despliegues_ota'),
        insert=(
            f"{permiso(R_OTA, 'E')} "
            f"AND {_dispositivo_visible('despliegues_ota')}"
        ),
        update=(
            f"{permiso(R_OTA, 'E')} "
            f"AND {_dispositivo_visible('despliegues_ota')}"
        ),
    )
    # POST /motor-ia (41·C) registra el intento de sincronización; los nodos, por el servicio
    _politicas(
        'sincronizacion_nodos_edge',
        select=_dispositivo_visible('sincronizacion_nodos_edge'),
        insert=f"{permiso(R_MOTOR, 'C')} AND {_dispositivo_visible('sincronizacion_nodos_edge')}",
        update=f"{permiso(R_MOTOR, 'C')} AND {_dispositivo_visible('sincronizacion_nodos_edge')}",
    )
    _politicas(
        'metricas_fallback_motor',
        select=_dispositivo_visible('metricas_fallback_motor'),
    )

    # ================================================================
    # 7. AUDITORIA M04 (RF-73): append-only estricto
    #    SELECT: auditores (R_AUDITORIA) o veterinario con permiso de
    #    retroalimentacion limitado a 4 tipos de evento.
    #    INSERT: cualquier usuario autenticado puede dejar rastro (los eventos
    #    se generan desde funciones/triggers como invoker) o el servicio.
    # ================================================================
    t = 'eventos_auditoria_m04'
    _pol(t, 'select', 'SELECT', using=permiso(R_AUDITORIA, 'R'))
    _pol(t, 'select_vet', 'SELECT', using=(
        f"{permiso(R_RETRO, 'R')} "
        "AND eventos_auditoria_m04.tipo_evento::text IN ("
        "'RETROALIMENTACION_REGISTRADA', 'VERSION_APROBADA', "
        "'VERSION_RECHAZADA', 'REENTRENAMIENTO_COMPLETADO')"))
    # El repositorio inserta con RETURNING: quien deja el evento tiene que poder leerlo,
    # aunque no tenga permiso de consulta de auditoría (mismo caso de #556).
    _pol(t, 'select_propio', 'SELECT', using=f"eventos_auditoria_m04.id_usuario = {UID}")
    _pol(t, 'insert', 'INSERT', check=f"{SERVICIO} OR {UID} IS NOT NULL")
    _servicio(t, append_only=True)
    _enable_force(t)


# =====================================================================
# DOWNGRADE
# =====================================================================
def downgrade() -> None:

    # 1. Borrar politicas PRIMERO
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN
            SELECT policyname, tablename FROM pg_policies
            WHERE schemaname = 'modulo4'
          LOOP
            EXECUTE format('DROP POLICY %I ON modulo4.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)

    # 2. Quitar FORCE RLS y 3. DISABLE RLS (estado original: sin RLS)
    for tabla in SING:
        op.execute(f"ALTER TABLE modulo4.{tabla} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE modulo4.{tabla} DISABLE ROW LEVEL SECURITY;")