# | Fecha      | Nombre     | Que se hizo |
# |------------|------------|-------------|
# | 2026-11-07 | SamuelPR21 | RLS modulo6 RF-82..94: politicas pol_* por permiso, estado del periodo y usuario de servicio |
"""rls_modulo_06

Revision ID: 4fa0e24ea021
Revises: f7463281b461
Create Date: 2026-11-07

Aplica Row Level Security al esquema modulo6 (financiero NIC 41, RF-82 a RF-94 y RF-COT)
sobre sus 25 tablas. Hasta esta migracion ninguna tenia RLS. Va despues de
rls_modulo_05 (f7463281b461).

Contrato con la base (Paso 0, leido de modulo4/modulo9): mismo que rls_modulo_05.
Identidad con modulo1.fn_id_usuario_actual(), permisos con modulo1.fn_tiene_permiso(recurso,
accion), procesos de fondo como usuario de servicio. No se crean roles ni esquema
seguridad. Politicas sin TO <rol>.

Recursos RBAC (modulo1.recursos, ids 88-99 de c4d81e6f2a95; se usan por nombre):
  precios_mercado (88)  configuracion_contable (89)  reconocimiento_inicial (90)
  valoracion_activos (91)  costos_activos (92)  cierre_periodo (93)
  valoracion_por_costo (94)  cotizaciones (95)  trazabilidad_contable (96)
  revelaciones_nic41 (97)  estado_resultados (98)  auditoria_financiera (99)

Diferencias con el instructivo, por lo que existe en la base:
  - Nombres reales: deterioros_activos e informes_revelacion_nic41; existen ademas
    asignaciones_cuentas_contables, comprobantes_nic41, configuraciones_contables,
    lineas_asiento_nic41, parametros_contables_especies y procesamientos_eventos_m02.
  - Auditor: el rol de la base es Revisor Fiscal y los roles son dinamicos, asi que no se
    nombra. "Vision completa" (periodos abiertos y borradores) = quien ejecuta el cierre
    (cierre_periodo·E, Contador) o registra costos (costos_activos·C, Administrador).
    Quien solo tiene lectura (Revisor Fiscal, Productor) ve unicamente periodos CERRADOS
    y documentos APROBADOS. Es la constante VISION_COMPLETA, unico punto a cambiar.
  - Periodo: la regla "solo periodo ABIERTO" es la de los triggers tgr_m06_09*, incluida
    su excepcion: EN_CIERRE solo escribe si la transaccion declara app.cierre_periodo.
    Sin esa excepcion el propio cierre (RF-87) quedaria bloqueado. Se aplica tambien al
    usuario de servicio.
  - cotizaciones: no se aplica la regla de periodo al UPDATE del servicio; el
    vencimiento diario (RF-COT FA-7) debe poder actualizar el estado.
  - Escritura por permiso, no por rol: lo que el instructivo asigna a "Contador" o
    "Administrador" sale de la matriz modulo1.permisos (C/U/E/D por recurso).
  - periodos_contables se crean de forma perezosa (Contabilizador) desde varios flujos
    de usuario: INSERT para quien tenga algun permiso de escritura financiero.
  - reconocimientos_iniciales: confirmar = 90·C; revertir = 90·D.

Todas las funciones van dentro de (SELECT ...) para evaluarse una vez por sentencia.
FORCE RLS: sin app.current_user_id no se ve nada (falla cerrado).

Tabla de seguimiento
  Tipo:                     Migracion Alembic (RLS)
  Nombre:                   rls_modulo_06
  Responsable:              Samuel
  Version Alembic:          4fa0e24ea021 (down_revision: f7463281b461)
  Fecha:                    2026-11-07
  Estado:                   Pendiente de prueba en TEST (no aplicada)
  Descripcion:              Habilita y fuerza RLS en las 25 tablas de modulo6
  Justificacion:            Segunda linea de defensa del RBAC: por rol y por estado del
                            periodo contable, con registros inmutables sin DELETE
  Objetos Afectados:        25 tablas de modulo6 (ENABLE + FORCE RLS), politicas pol_*
  Requerimientos Funcionales: RF-82, RF-83, RF-84, RF-85, RF-86, RF-87, RF-88, RF-89,
                            RF-90, RF-91, RF-92, RF-93, RF-94, RF-COT
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4fa0e24ea021'
down_revision: Union[str, Sequence[str], None] = 'f7463281b461'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = 'modulo6'

# ── Contexto de sesion ────────────────────────────────────────────────
UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"
AUTENTICADO = f"{UID} IS NOT NULL"


def permiso(recurso: str, accion: str) -> str:
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


def alguno(*pares: tuple) -> str:
    """OR de permisos (recurso, accion)."""
    return "(" + " OR ".join(permiso(r, a) for r, a in pares) + ")"


# ── Recursos RBAC ─────────────────────────────────────────────────────
R_PRECIOS = 'precios_mercado'                # 88
R_CONFIG = 'configuracion_contable'          # 89
R_RECONOC = 'reconocimiento_inicial'         # 90
R_VALOR = 'valoracion_activos'               # 91
R_COSTOS = 'costos_activos'                  # 92
R_CIERRE = 'cierre_periodo'                  # 93
R_VCOSTO = 'valoracion_por_costo'            # 94
R_COTIZ = 'cotizaciones'                     # 95
R_TRAZA = 'trazabilidad_contable'            # 96
R_REVELA = 'revelaciones_nic41'              # 97
R_ESTADO = 'estado_resultados'               # 98
R_AUDIT = 'auditoria_financiera'             # 99

# Quien opera el modulo ve todo; el resto (lectores) solo lo cerrado/aprobado.
VISION_COMPLETA = alguno((R_CIERRE, 'E'), (R_COSTOS, 'C'))

# Quien escribe en el modulo financiero (para crear periodos de forma perezosa).
_ESCRIBE_M06 = alguno(
    (R_CIERRE, 'E'), (R_VALOR, 'E'), (R_COSTOS, 'C'), (R_RECONOC, 'C'),
    (R_COTIZ, 'C'), (R_ESTADO, 'C'), (R_PRECIOS, 'C'), (R_CONFIG, 'C'),
)


def periodo_cerrado(tabla: str) -> str:
    return (
        "EXISTS (SELECT 1 FROM modulo6.periodos_contables p "
        f"WHERE p.id_periodo_contable = {tabla}.id_periodo_contable AND p.estado::text = 'CERRADO')"
    )


def periodo_escribible(tabla: str) -> str:
    """ABIERTO, o EN_CIERRE con app.cierre_periodo = ese periodo (mismo criterio que tgr_m06_09)."""
    return (
        "EXISTS (SELECT 1 FROM modulo6.periodos_contables p "
        f"WHERE p.id_periodo_contable = {tabla}.id_periodo_contable "
        "AND (p.estado::text = 'ABIERTO' OR (p.estado::text = 'EN_CIERRE' "
        "AND current_setting('app.cierre_periodo', true) = p.id_periodo_contable::text)))"
    )


def ve_periodo(tabla: str) -> str:
    """Vision completa, o solo filas de un periodo CERRADO."""
    return f"({VISION_COMPLETA} OR {periodo_cerrado(tabla)})"


# ── Nombre singular de cada tabla (convencion: pol_<singular>_<criterio>) ──
SING = {
    'asignaciones_cuentas_contables': 'asignacion_cuenta_contable',
    'auditorias_financieras': 'auditoria_financiera',
    'cadenas_trazabilidad_contable': 'cadena_trazabilidad_contable',
    'calculos_valor_razonable': 'calculo_valor_razonable',
    'comprobantes_nic41': 'comprobante_nic41',
    'configuraciones_contables': 'configuracion_contable',
    'cotizaciones': 'cotizacion',
    'deterioros_activos': 'deterioro_activo',
    'ejecuciones_cierre_periodo': 'ejecucion_cierre_periodo',
    'estados_resultados_periodo': 'estado_resultados_periodo',
    'informes_revelacion_nic41': 'informe_revelacion_nic41',
    'lineas_asiento_nic41': 'linea_asiento_nic41',
    'mediciones_posteriores': 'medicion_posterior',
    'parametros_contables_especies': 'parametro_contable_especie',
    'parametros_costos_venta': 'parametro_costo_venta',
    'periodos_contables': 'periodo_contable',
    'precios_mercado': 'precio_mercado',
    'procesamientos_eventos_m02': 'procesamiento_evento_m02',
    'recepciones_provisiones_m05': 'recepcion_provision_m05',
    'reconocimientos_iniciales': 'reconocimiento_inicial',
    'reconocimientos_productos_agricolas': 'reconocimiento_producto_agricola',
    'registros_costos': 'registro_costo',
    'revisiones_reconocimiento': 'revision_reconocimiento',
    'valoraciones_por_costos': 'valoracion_por_costo',
    'variaciones_valor_razonable': 'variacion_valor_razonable',
}

# Registro declarativo: (tabla, criterio, comando, using, with_check, restrictiva).
POLITICAS: list = []


def _pol(tabla: str, criterio: str, cmd: str, using: str = None, check: str = None,
         restrictiva: bool = False) -> None:
    POLITICAS.append((tabla, criterio, cmd, using, check, restrictiva))


def _servicio(tabla: str, modo: str = 'all') -> None:
    """Usuario de servicio: 'all', 'append' (SELECT+INSERT) o 'select'."""
    if modo == 'all':
        _pol(tabla, 'servicio', 'ALL', SERVICIO, SERVICIO)
    elif modo == 'append':
        _pol(tabla, 'servicio_select', 'SELECT', SERVICIO)
        _pol(tabla, 'servicio_insert', 'INSERT', None, SERVICIO)


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

    # ── Configuracion contable (RF-109/M09, RF-84, RF-82): 89 ───────
    for t in ('asignaciones_cuentas_contables', 'configuraciones_contables',
              'parametros_contables_especies', 'parametros_costos_venta'):
        _politicas(
            t,
            select=permiso(R_CONFIG, 'R'),
            insert=permiso(R_CONFIG, 'C'),
            update=permiso(R_CONFIG, 'U'),
        )

    # ── RF-89: precios de mercado (append-only; UPDATE solo del estado) ──
    # El INSERT lo hace quien tiene C (Contador); confirmar un precio de M07 o
    # marcar el anterior como SUPERADO es un UPDATE del estado.
    _politicas(
        'precios_mercado',
        select=permiso(R_PRECIOS, 'R'),
        insert=permiso(R_PRECIOS, 'C'),
        update=permiso(R_PRECIOS, 'C'),
    )

    # ── RF-87: periodos y ejecuciones de cierre ─────────────────────
    # El periodo CERRADO es inmutable (triggers 21). Los periodos se crean de forma
    # perezosa desde varios flujos, y el cierre abre el siguiente.
    t = 'periodos_contables'
    _politicas(
        t,
        select=AUTENTICADO,  # contexto no sensible: lo necesitan todos los lectores
        insert=_ESCRIBE_M06,
        update=f"{t}.estado::text <> 'CERRADO' AND {permiso(R_CIERRE, 'E')}",
        update_check=permiso(R_CIERRE, 'E'),
    )
    _politicas(
        'ejecuciones_cierre_periodo',
        select=permiso(R_CIERRE, 'R'),
        insert=permiso(R_CIERRE, 'E'),
        update=permiso(R_CIERRE, 'E'),
    )

    # ── RF-82: reconocimiento inicial ───────────────────────────────
    # Propuesta: la crea el sistema al llegar ACTIVO_REGISTRADO. Confirmar = C;
    # revertir = D. Inmutable fuera de eso (trigger 01).
    t = 'reconocimientos_iniciales'
    _politicas(
        t,
        select=permiso(R_RECONOC, 'R'),
        insert=permiso(R_RECONOC, 'C'),
        update=(
            f"{t}.estado::text IN ('PENDIENTE_CONFIRMACION', 'CONFIRMADO') "
            f"AND {alguno((R_RECONOC, 'C'), (R_RECONOC, 'D'))}"
        ),
        update_check=alguno((R_RECONOC, 'C'), (R_RECONOC, 'D')),
    )
    _politicas(  # append-only: asiento de reversion
        'revisiones_reconocimiento',
        select=permiso(R_RECONOC, 'R'),
        insert=permiso(R_RECONOC, 'D'),
    )

    # ── RF-84/83/86: valoracion ─────────────────────────────────────
    _politicas(
        'calculos_valor_razonable',
        select=permiso(R_VALOR, 'R'),
        insert=permiso(R_VALOR, 'E'),
        update=permiso(R_VALOR, 'E'),  # validar REVISION_REQUERIDA
    )
    _politicas(
        'mediciones_posteriores',
        select=permiso(R_VALOR, 'R'),
        insert=alguno((R_VALOR, 'E'), (R_CIERRE, 'E')),
        update=alguno((R_VALOR, 'E'), (R_CIERRE, 'E')),  # resolver MEDICION_PENDIENTE
    )
    t = 'variaciones_valor_razonable'  # append-only; UPDATE solo estado_trazabilidad
    _politicas(
        t,
        select=f"{alguno((R_VALOR, 'R'), (R_TRAZA, 'R'))} AND {ve_periodo(t)}",
        insert=alguno((R_VALOR, 'E'), (R_CIERRE, 'E')),
        update=alguno((R_TRAZA, 'E'), (R_VALOR, 'E'), (R_CIERRE, 'E')),
    )

    # ── RF-85: productos agricolas (inmutable) ──────────────────────
    _politicas(
        'reconocimientos_productos_agricolas',
        select=permiso(R_VALOR, 'R'),
        insert=permiso(R_VALOR, 'E'),
    )

    # ── RF-90: costos ───────────────────────────────────────────────
    _politicas(
        'registros_costos',
        select=permiso(R_COSTOS, 'R'),
        insert=permiso(R_COSTOS, 'C'),
        update=permiso(R_COSTOS, 'U'),  # clasificar / capitalizar
    )

    # ── RF-COT: cotizaciones ────────────────────────────────────────
    # Contador/Administrador ven todas; el Productor solo las de sus activos.
    # Crear = C; modificar = U; anular = D. El servicio las vence cada dia.
    t = 'cotizaciones'
    _pol(t, 'select', 'SELECT',
         f"{permiso(R_COTIZ, 'R')} AND ({VISION_COMPLETA} OR {t}.activos_cotizados <@ "
         f"ARRAY(SELECT a.id_activo_biologico FROM modulo2.fn_activos_del_usuario({UID}) a))")
    _pol(t, 'insert', 'INSERT', None, permiso(R_COTIZ, 'C'))
    _pol(t, 'update', 'UPDATE', alguno((R_COTIZ, 'U'), (R_COTIZ, 'D')), alguno((R_COTIZ, 'U'), (R_COTIZ, 'D')))
    _servicio(t)

    # ── RF-88: valoracion por costo y deterioros ────────────────────
    _politicas(
        'valoraciones_por_costos',
        select=permiso(R_VCOSTO, 'R'),
        insert=alguno((R_VCOSTO, 'C'), (R_CIERRE, 'E')),
        update=alguno((R_VCOSTO, 'U'), (R_CIERRE, 'E')),  # depreciacion al cierre
    )
    _politicas(
        'deterioros_activos',
        select=permiso(R_VCOSTO, 'R'),
        insert=permiso(R_VCOSTO, 'C'),
    )

    # ── RF-91: trazabilidad contable ────────────────────────────────
    # No tiene id_periodo_contable: el periodo sale de su variacion (la propia
    # variacion ya filtra por periodo cerrado para quien solo lee).
    t = 'cadenas_trazabilidad_contable'
    _politicas(
        t,
        select=(
            f"{permiso(R_TRAZA, 'R')} AND ({VISION_COMPLETA} OR EXISTS ("
            "SELECT 1 FROM modulo6.variaciones_valor_razonable v "
            "JOIN modulo6.periodos_contables p ON p.id_periodo_contable = v.id_periodo_contable "
            f"WHERE v.id_variacion_valor_razonable = {t}.id_variacion_valor_razonable "
            "AND p.estado::text = 'CERRADO'))"
        ),
        insert=alguno((R_TRAZA, 'E'), (R_VALOR, 'E'), (R_CIERRE, 'E')),
        update=alguno((R_TRAZA, 'E'), (R_VALOR, 'E'), (R_CIERRE, 'E')),
    )

    # ── RF-86 v2.0 / RF-87 v1.1: lineas de asiento y comprobante NIC 41 ──
    t = 'lineas_asiento_nic41'
    _politicas(
        t,
        select=f"{alguno((R_VALOR, 'R'), (R_CIERRE, 'R'), (R_TRAZA, 'R'))} AND {ve_periodo(t)}",
        insert=alguno((R_VALOR, 'E'), (R_CIERRE, 'E'), (R_RECONOC, 'C'), (R_COSTOS, 'C')),
        # PENDIENTE_CUENTA al completar la matriz; asignar el comprobante al cerrar
        update=alguno((R_CIERRE, 'E'), (R_CONFIG, 'C'), (R_CONFIG, 'U')),
    )
    _politicas(  # inmutable (trigger): solo se inserta
        'comprobantes_nic41',
        select=permiso(R_CIERRE, 'R'),
        insert=permiso(R_CIERRE, 'E'),
    )

    # ── RF-92: informe de revelaciones NIC 41 ───────────────────────
    t = 'informes_revelacion_nic41'
    _politicas(
        t,
        select=(
            f"{permiso(R_REVELA, 'R')} AND ({VISION_COMPLETA} OR "
            f"{t}.estado::text IN ('APROBADO', 'ARCHIVADO'))"
        ),
        insert=alguno((R_REVELA, 'C'), (R_CIERRE, 'E')),
        update=alguno((R_REVELA, 'U'), (R_CIERRE, 'E')),  # aprobar, rechazar, archivar
    )

    # ── RF-93: estado de resultados ─────────────────────────────────
    t = 'estados_resultados_periodo'
    _politicas(
        t,
        select=f"{permiso(R_ESTADO, 'R')} AND ({VISION_COMPLETA} OR {t}.estado = 'APROBADO')",
        insert=alguno((R_ESTADO, 'C'), (R_CIERRE, 'E')),
        update=alguno((R_ESTADO, 'U'), (R_CIERRE, 'E')),  # aprobar
    )

    # ── RF-94: auditoria financiera (append-only) ───────────────────
    # SELECT: auditoria (99·R) o el propio autor (el repositorio inserta con
    # RETURNING). INSERT: cualquier autenticado o el servicio (emisores de RF-82..93).
    t = 'auditorias_financieras'
    _pol(t, 'select', 'SELECT', permiso(R_AUDIT, 'R'))
    _pol(t, 'select_propio', 'SELECT', f"{t}.id_usuario = {UID}")
    _pol(t, 'insert', 'INSERT', None, f"{SERVICIO} OR {AUTENTICADO}")
    _servicio(t, 'append')

    # ── Eventos de M02 y provisiones de M05 (los procesa el servicio, o el
    #    Contador con POST /eventos/procesar = valoracion_activos·E) ──
    _politicas(
        'procesamientos_eventos_m02',
        select=permiso(R_VALOR, 'E'),
        insert=permiso(R_VALOR, 'E'),
        update=permiso(R_VALOR, 'E'),
    )
    _politicas(
        'recepciones_provisiones_m05',
        select=alguno((R_COSTOS, 'R'), (R_VALOR, 'E')),
        insert=permiso(R_VALOR, 'E'),
        update=permiso(R_VALOR, 'E'),  # fecha_procesamiento / resultado_procesamiento
    )

    # ── Regla transversal: solo se escribe en un periodo ABIERTO ────
    # (RESTRICTIVE: se combina con AND con las politicas anteriores.) Aplica al
    # usuario y al servicio; es el mismo criterio que los triggers tgr_m06_09*.
    for t in ('calculos_valor_razonable', 'mediciones_posteriores', 'reconocimientos_iniciales',
              'reconocimientos_productos_agricolas', 'registros_costos', 'variaciones_valor_razonable'):
        _pol(t, 'periodo_abierto_insert', 'INSERT', None, periodo_escribible(t), True)
        _pol(t, 'periodo_abierto_update', 'UPDATE', periodo_escribible(t), periodo_escribible(t), True)
    # Cotizaciones: el vencimiento del servicio se hace sobre el periodo de emision, que
    # puede estar cerrado; solo se exige periodo abierto para crear o modificar por usuario.
    t = 'cotizaciones'
    _pol(t, 'periodo_abierto_insert', 'INSERT', None, periodo_escribible(t), True)
    _pol(t, 'periodo_abierto_update', 'UPDATE',
         f"{SERVICIO} OR {periodo_escribible(t)}", f"{SERVICIO} OR {periodo_escribible(t)}", True)


_definir()


def _nombre(tabla: str, criterio: str) -> str:
    return f"pol_{SING[tabla]}_{criterio}"


# =====================================================================
# UPGRADE
# =====================================================================
def upgrade() -> None:
    for tabla, criterio, cmd, using, check, restrictiva in POLITICAS:
        tipo = "AS RESTRICTIVE " if restrictiva else ""
        sql = f"CREATE POLICY {_nombre(tabla, criterio)} ON {SCHEMA}.{tabla} {tipo}FOR {cmd}"
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
    for tabla, criterio, *_ in reversed(POLITICAS):
        op.execute(f"DROP POLICY IF EXISTS {_nombre(tabla, criterio)} ON {SCHEMA}.{tabla}")

    for tabla in SING:
        op.execute(f"ALTER TABLE {SCHEMA}.{tabla} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {SCHEMA}.{tabla} DISABLE ROW LEVEL SECURITY")
