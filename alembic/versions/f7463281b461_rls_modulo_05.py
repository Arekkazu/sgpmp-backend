# | Fecha      | Nombre     | Que se hizo |
# |------------|------------|-------------|
# | 2026-11-07 | SamuelPR21 | RLS modulo5 RF-74..81: politicas pol_* por permiso, alcance por activo y usuario de servicio |
"""rls_modulo_05

Revision ID: f7463281b461
Revises: b7e2d94c1a68
Create Date: 2026-11-07

Aplica Row Level Security al esquema modulo5 (suministros y costos, RF-74 a RF-81)
sobre sus 27 tablas. Hasta esta migracion ninguna tenia RLS.

Contrato con la base (Paso 0 de las instrucciones, leido de las RLS que ya existen:
modulo4, modulo9). Donde el instructivo propone otro nombre, gana el de la base:

  - Usuario de la peticion:  modulo1.fn_id_usuario_actual()  (app.current_user_id)
  - Permisos (RBAC en BD):   modulo1.fn_tiene_permiso(recurso, accion). No hay nombres
                             de rol quemados: los roles son dinamicos (CRUD de roles).
  - Alcance por finca:       modulo2.fn_activos_del_usuario(uid). Devuelve todos los
                             activos si el rol es protegido (Administrador).
  - Procesos de fondo:       usuario de servicio (modulo1.fn_es_usuario_servicio()),
                             que main.py abre con sesion_sistema(). No se crea un rol
                             de BD sgpmp_worker ni seguridad_lector: no existen.
  - Politicas sin TO <rol>:  aplican a PUBLIC, igual que modulo4. La API conecta como
                             sgpmp_app o rol_app segun el ambiente.
  - Nombres:                 pol_<singular>_<criterio>.

Recursos RBAC (modulo1.recursos) que usan los routers de src/supplies:
  consumo_alimentos (47) C/R/D        medicamentos (48) C/R/D
  eficiencia_alimenticia (49) E/R     administracion_batch_ica (50) E/R
  reporte_gastos_suministros (51)     historial_suministros (52)
  administracion_batch_reportes_gastos (53)  administracion_batch_historial_suministros (54)
  costeo_directo_suministros (55) C/R/U      provision_nic41 (56) E/R
  bitacora_auditoria_suministros (57) E/R

Alcance de lectura (RF-75..81):
  - Productor / Veterinario / Gestor de Granja: solo activos de sus fincas
    (modulo9.usuarios_fincas).
  - Contador, Revisor Fiscal y Administrador: todas las fincas. En BD se expresa como
    el permiso de lectura de la bitacora de suministros (57), que tienen exactamente
    esos tres roles (constante ALCANCE_GLOBAL; si el DBA prefiere otro criterio,
    es el unico punto a cambiar).

Valores reales verificados en la base (no los del instructivo):
  - acumulado_ciclo.estado: ACTIVO -> CONSOLIDADO (no CERRADO).
  - registros_*.estado_registro: VALIDADO / ANULADO.

Efectos en cascada que las politicas deben dejar pasar (triggers invoker, no
SECURITY DEFINER): INSERT en consumo/medicamentos -> INSERT en registro_suministro ->
INSERT/UPDATE en acumulado_ciclo; triggers de auditoria -> INSERT en
auditorias_suministros. Por eso estas escrituras se autorizan por permiso del
recurso de origen y no solo por el del destino.

Append-only (sin politica de DELETE; sin UPDATE salvo lo indicado): registro_suministro,
auditorias_suministros, costos_productivos, historial_suministros_activos,
reporte_gastos_acumulados. Consumo y medicamentos solo admiten el UPDATE de anulacion
(VALIDADO -> ANULADO); los triggers *_inmutable_validado ya protegen el resto de
columnas, por eso no se revoca ni concede UPDATE por columna.

Todas las funciones van dentro de (SELECT ...) para evaluarse una vez por sentencia.
FORCE RLS: sin app.current_user_id no se ve nada (falla cerrado). Toda ruta nueva de
M05 debe pasar por get_current_user / sesion_sistema.

Tabla de seguimiento
  Tipo:                     Migracion Alembic (RLS)
  Nombre:                   rls_modulo_05
  Responsable:              Samuel
  Version Alembic:          f7463281b461 (down_revision: b7e2d94c1a68)
  Fecha:                    2026-11-07
  Estado:                   Pendiente de prueba en TEST (no aplicada)
  Descripcion:              Habilita y fuerza RLS en las 27 tablas de modulo5
  Justificacion:            Segunda linea de defensa del RBAC: una finca no ve datos de
                            otra y los registros inmutables no se editan ni borran
  Objetos Afectados:        27 tablas de modulo5 (ENABLE + FORCE RLS), politicas pol_*
  Requerimientos Funcionales: RF-74, RF-75, RF-76, RF-77, RF-78, RF-79, RF-80, RF-81
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f7463281b461'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'modulo5'

# ── Contexto de sesion (mismo contrato que modulo3/modulo4) ───────────
UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"
AUTENTICADO = f"{UID} IS NOT NULL"


def permiso(recurso: str, accion: str) -> str:
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


def alguno(*pares: tuple) -> str:
    """OR de permisos (recurso, accion)."""
    return "(" + " OR ".join(permiso(r, a) for r, a in pares) + ")"


# ── Recursos RBAC (los de cada router de src/supplies) ────────────────
R_CONSUMO = 'consumo_alimentos'                         # 47
R_MEDICAMENTO = 'medicamentos'                          # 48
R_ICA = 'eficiencia_alimenticia'                        # 49
R_BATCH_ICA = 'administracion_batch_ica'                # 50
R_REPORTE = 'reporte_gastos_suministros'                # 51
R_HISTORIAL = 'historial_suministros'                   # 52
R_BATCH_REPORTE = 'administracion_batch_reportes_gastos'        # 53
R_BATCH_HISTORIAL = 'administracion_batch_historial_suministros'  # 54
R_COSTEO = 'costeo_directo_suministros'                 # 55
R_PROVISION = 'provision_nic41'                         # 56
R_AUDITORIA = 'bitacora_auditoria_suministros'          # 57

# Quien lee todas las fincas (Contador, Revisor Fiscal, Administrador): ver docstring.
ALCANCE_GLOBAL = permiso(R_AUDITORIA, 'R')

# Quien puede registrar suministros: dispara los triggers que escriben
# registro_suministro y acumulado_ciclo como invoker.
_ESCRIBE_SUMINISTRO = alguno((R_COSTEO, 'C'), (R_CONSUMO, 'C'), (R_MEDICAMENTO, 'C'))
_LEE_SUMINISTRO = alguno(
    (R_COSTEO, 'R'), (R_HISTORIAL, 'R'), (R_REPORTE, 'R'), (R_CONSUMO, 'R'), (R_MEDICAMENTO, 'R'),
)


def alcance(tabla: str) -> str:
    """El activo de la fila esta en una finca del usuario (o el usuario tiene alcance global)."""
    return (
        f"({ALCANCE_GLOBAL} OR {tabla}.id_activo_biologico IN "
        f"(SELECT a.id_activo_biologico FROM modulo2.fn_activos_del_usuario({UID}) a))"
    )


# ── Nombre singular de cada tabla (convencion: pol_<singular>_<criterio>) ──
SING = {
    'acumulado_ciclo': 'acumulado_ciclo',
    'archivos_exportacion_suministros': 'archivo_exportacion_suministro',
    'auditorias_suministros': 'auditoria_suministro',
    'cola_calculo_ica': 'cola_calculo_ica',
    'cola_generacion_reportes_gastos': 'cola_generacion_reporte_gasto',
    'cola_trabajos_historial_suministros': 'cola_trabajo_historial_suministro',
    'configuracion_batch_historial_suministros': 'configuracion_batch_historial_suministro',
    'configuracion_batch_ica': 'configuracion_batch_ica',
    'configuracion_batch_reportes_gastos': 'configuracion_batch_reporte_gasto',
    'costos_productivos': 'costo_productivo',
    'ejecuciones_batch_ica': 'ejecucion_batch_ica',
    'ejecuciones_generacion_reportes_gastos': 'ejecucion_generacion_reporte_gasto',
    'ejecuciones_trabajos_historial_suministros': 'ejecucion_trabajo_historial_suministro',
    'fallos_calculo_ica': 'fallo_calculo_ica',
    'fallos_generacion_reportes_gastos': 'fallo_generacion_reporte_gasto',
    'fallos_trabajos_historial_suministros': 'fallo_trabajo_historial_suministro',
    'historial_suministros_activos': 'historial_suministro_activo',
    'mediciones_incrementales': 'medicion_incremental',
    'mediciones_inventarios': 'medicion_inventario',
    'outbox_provisiones_m06': 'outbox_provision_m06',
    'provision_nic41': 'provision_nic41',
    'registro_suministro': 'registro_suministro',
    'registros_consumo_alimentos': 'registro_consumo_alimento',
    'registros_medicamentos': 'registro_medicamento',
    'reporte_gastos_acumulados': 'reporte_gasto_acumulado',
    'resultado_ica': 'resultado_ica',
    'tipos_alimentos': 'tipo_alimento',
}

# Registro declarativo: (tabla, criterio, comando, using, with_check).
# Se lee como la matriz de acceso, y el downgrade borra exactamente lo mismo.
POLITICAS: list = []


def _pol(tabla: str, criterio: str, cmd: str, using: str = None, check: str = None) -> None:
    POLITICAS.append((tabla, criterio, cmd, using, check))


def _servicio(tabla: str, modo: str = 'all') -> None:
    """Usuario de servicio: 'all', 'append' (SELECT+INSERT) o 'select'."""
    if modo == 'all':
        _pol(tabla, 'servicio', 'ALL', SERVICIO, SERVICIO)
    elif modo == 'append':
        _pol(tabla, 'servicio_select', 'SELECT', SERVICIO)
        _pol(tabla, 'servicio_insert', 'INSERT', None, SERVICIO)
    elif modo == 'select':
        _pol(tabla, 'servicio_select', 'SELECT', SERVICIO)


def _politicas(tabla: str, select: str, insert: str = None, update: str = None,
               update_check: str = None, servicio: str = 'all') -> None:
    _pol(tabla, 'select', 'SELECT', select)
    if insert:
        _pol(tabla, 'insert', 'INSERT', None, insert)
    if update:
        _pol(tabla, 'update', 'UPDATE', update, update_check or update)
    _servicio(tabla, servicio)


# =====================================================================
# MATRIZ DE ACCESO
# =====================================================================
def _definir() -> None:
    POLITICAS.clear()

    # ── RF-75: consumo de alimentos ─────────────────────────────────
    # Registra quien tiene C; anula (VALIDADO -> ANULADO) quien tiene D (Veterinario,
    # Administrador). El servicio solo lee e inserta (append-only).
    t = 'registros_consumo_alimentos'
    _politicas(
        t,
        select=f"{permiso(R_CONSUMO, 'R')} AND {alcance(t)}",
        insert=f"{permiso(R_CONSUMO, 'C')} AND {alcance(t)}",
        update=f"{t}.estado_registro = 'VALIDADO' AND {permiso(R_CONSUMO, 'D')} AND {alcance(t)}",
        update_check=f"{t}.estado_registro = 'ANULADO' AND {permiso(R_CONSUMO, 'D')} AND {alcance(t)}",
        servicio='append',
    )

    # ── RF-76: aplicacion de medicamentos ───────────────────────────
    t = 'registros_medicamentos'
    _politicas(
        t,
        select=f"{permiso(R_MEDICAMENTO, 'R')} AND {alcance(t)}",
        insert=f"{permiso(R_MEDICAMENTO, 'C')} AND {alcance(t)}",
        update=f"{t}.estado_registro = 'VALIDADO' AND {permiso(R_MEDICAMENTO, 'D')} AND {alcance(t)}",
        update_check=f"{t}.estado_registro = 'ANULADO' AND {permiso(R_MEDICAMENTO, 'D')} AND {alcance(t)}",
        servicio='append',
    )

    # ── RF-78: registro de suministro (append-only; las correcciones son filas nuevas) ──
    t = 'registro_suministro'
    _politicas(
        t,
        select=f"{_LEE_SUMINISTRO} AND {alcance(t)}",
        insert=f"{_ESCRIBE_SUMINISTRO} AND {alcance(t)}",
        servicio='append',
    )

    # ── RF-78: acumulado del ciclo ──────────────────────────────────
    # Lo actualiza un trigger como invoker al registrar un suministro. Una vez
    # CONSOLIDADO (RF-78 R2) nadie lo toca. SELECT amplio porque el UPDATE del
    # trigger necesita ver la fila para aplicar su WHERE.
    t = 'acumulado_ciclo'
    _escritura = f"({_ESCRIBE_SUMINISTRO} OR {permiso(R_PROVISION, 'E')}) AND {alcance(t)}"
    _lee_acumulado = alguno(
        (R_COSTEO, 'R'), (R_HISTORIAL, 'R'), (R_REPORTE, 'R'), (R_PROVISION, 'R'),
        (R_CONSUMO, 'R'), (R_MEDICAMENTO, 'R'),
    )
    _politicas(
        t,
        select=f"{_lee_acumulado} AND {alcance(t)}",
        insert=_escritura,
        update=f"{t}.estado IS DISTINCT FROM 'CONSOLIDADO' AND {_escritura}",
        update_check=_escritura,
    )

    # ── RF-79: outbox hacia M06 ─────────────────────────────────────
    # Se encola en la misma transaccion del suministro (usuario); el despachador
    # (servicio) lo actualiza.
    t = 'outbox_provisiones_m06'
    _outbox = f"({_ESCRIBE_SUMINISTRO} OR {permiso(R_PROVISION, 'E')}) AND {alcance(t)}"
    _politicas(t, select=_outbox, insert=_outbox)

    # ── RF-79: provision NIC 41 (una correccion es una version nueva; la anterior pasa a SUPERADO) ──
    t = 'provision_nic41'
    _politicas(
        t,
        select=f"{permiso(R_PROVISION, 'R')} AND {alcance(t)}",
        insert=f"{permiso(R_PROVISION, 'E')} AND {alcance(t)}",
        update=f"{permiso(R_PROVISION, 'E')} AND {alcance(t)}",
    )

    # ── RF-74: resultado del ICA y su cola ──────────────────────────
    t = 'resultado_ica'
    _politicas(
        t,
        select=f"{permiso(R_ICA, 'R')} AND {alcance(t)}",
        insert=f"{permiso(R_ICA, 'E')} AND {alcance(t)}",
        update=f"{permiso(R_ICA, 'E')} AND {alcance(t)}",  # es_vigente del resultado anterior
    )
    t = 'cola_calculo_ica'
    _politicas(
        t,
        select=f"{alguno((R_ICA, 'R'), (R_BATCH_ICA, 'R'))} AND {alcance(t)}",
        insert=f"{alguno((R_ICA, 'E'), (R_BATCH_ICA, 'E'))} AND {alcance(t)}",
        update=f"{permiso(R_BATCH_ICA, 'E')} AND {alcance(t)}",
    )

    # ── RF-74/78: costos y mediciones que calcula el sistema ────────
    t = 'costos_productivos'  # triggers no_update / no_delete
    _politicas(
        t,
        select=f"{alguno((R_COSTEO, 'R'), (R_REPORTE, 'R'), (R_HISTORIAL, 'R'))} AND {alcance(t)}",
        insert=f"{permiso(R_COSTEO, 'C')} AND {alcance(t)}",
        servicio='append',
    )
    for t in ('mediciones_incrementales', 'mediciones_inventarios'):
        _politicas(
            t,
            select=f"{alguno((R_ICA, 'R'), (R_COSTEO, 'R'), (R_REPORTE, 'R'))} AND {alcance(t)}",
        )

    # ── RF-80: auditoria de suministros (append-only) ───────────────
    # SELECT: control (57·R) o el propio autor (el repositorio inserta con RETURNING:
    # quien deja el evento debe poder leerlo, aunque no consulte la bitacora).
    # INSERT: cualquier usuario autenticado, porque los triggers de auditoria
    # de consumo/medicamento/ICA/costos corren como invoker.
    t = 'auditorias_suministros'
    _pol(t, 'select', 'SELECT', permiso(R_AUDITORIA, 'R'))
    _pol(t, 'select_propio', 'SELECT', f"{t}.id_usuario = {UID}")
    _pol(t, 'insert', 'INSERT', None, f"{SERVICIO} OR {AUTENTICADO}")
    _servicio(t, 'append')

    # ── RF-77/81: consultas, reportes, colas y archivos del propio usuario ──
    t = 'historial_suministros_activos'
    _politicas(
        t,
        select=f"{t}.id_usuario = {UID} OR ({permiso(R_HISTORIAL, 'R')} AND {ALCANCE_GLOBAL})",
        insert=f"{t}.id_usuario = {UID}",
    )
    t = 'reporte_gastos_acumulados'
    _politicas(
        t,
        select=f"{t}.id_usuario = {UID} OR ({permiso(R_REPORTE, 'R')} AND {ALCANCE_GLOBAL})",
        insert=f"{t}.id_usuario = {UID}",
    )
    t = 'archivos_exportacion_suministros'
    _politicas(t, select=f"{t}.id_usuario = {UID}", insert=f"{t}.id_usuario = {UID}")

    for t, recurso in (
        ('cola_generacion_reportes_gastos', R_BATCH_REPORTE),
        ('cola_trabajos_historial_suministros', R_BATCH_HISTORIAL),
    ):
        _politicas(
            t,
            select=f"{t}.id_usuario_solicitante = {UID} OR {permiso(recurso, 'R')}",
            insert=f"{t}.id_usuario_solicitante = {UID}",
        )

    # ── Procesos batch: ejecuciones y fallos (los escribe el servicio; el
    #    administrador consulta y reactiva con E) ────────────────────
    for t, recurso in (
        ('ejecuciones_batch_ica', R_BATCH_ICA),
        ('fallos_calculo_ica', R_BATCH_ICA),
        ('ejecuciones_generacion_reportes_gastos', R_BATCH_REPORTE),
        ('fallos_generacion_reportes_gastos', R_BATCH_REPORTE),
        ('ejecuciones_trabajos_historial_suministros', R_BATCH_HISTORIAL),
        ('fallos_trabajos_historial_suministros', R_BATCH_HISTORIAL),
    ):
        _politicas(
            t,
            select=permiso(recurso, 'R'),
            insert=permiso(recurso, 'E'),
            update=permiso(recurso, 'E'),
        )

    # ── Configuracion de los batch: viene por seed; solo se edita ───
    for t, recurso in (
        ('configuracion_batch_ica', R_BATCH_ICA),
        ('configuracion_batch_reportes_gastos', R_BATCH_REPORTE),
        ('configuracion_batch_historial_suministros', R_BATCH_HISTORIAL),
    ):
        _politicas(t, select=permiso(recurso, 'R'), update=permiso(recurso, 'E'))

    # ── Catalogo de alimentos (RF-75): lo lee cualquier autenticado ─
    # (el trigger de consumo lo consulta como invoker). Ningun endpoint lo escribe.
    _politicas('tipos_alimentos', select=AUTENTICADO)


_definir()


def _nombre(tabla: str, criterio: str) -> str:
    return f"pol_{SING[tabla]}_{criterio}"


# =====================================================================
# UPGRADE
# =====================================================================
def upgrade() -> None:
    # Las politicas se crean en la misma transaccion que activa la RLS: no hay
    # ventana en la que una tabla con RLS quede sin politicas.
    for tabla, criterio, cmd, using, check in POLITICAS:
        sql = f"CREATE POLICY {_nombre(tabla, criterio)} ON {SCHEMA}.{tabla} FOR {cmd}"
        if using:
            sql += f" USING ({using})"
        if check:
            sql += f" WITH CHECK ({check})"
        op.execute(sql)

    for tabla in SING:
        op.execute(f"ALTER TABLE {SCHEMA}.{tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {SCHEMA}.{tabla} FORCE ROW LEVEL SECURITY")


# =====================================================================
# DOWNGRADE
# =====================================================================
def downgrade() -> None:
    # Politicas PRIMERO, luego FORCE y ENABLE (estado original: sin RLS).
    for tabla, criterio, *_ in reversed(POLITICAS):
        op.execute(f"DROP POLICY IF EXISTS {_nombre(tabla, criterio)} ON {SCHEMA}.{tabla}")

    for tabla in SING:
        op.execute(f"ALTER TABLE {SCHEMA}.{tabla} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {SCHEMA}.{tabla} DISABLE ROW LEVEL SECURITY")
