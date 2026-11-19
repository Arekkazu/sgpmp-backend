# | Fecha      | Nombre   | Que se hizo                                                                        |
# |------------|----------|------------------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104..107: reportes, preferencias de notificación, catálogo de errores, RBAC |
"""m08: reportes (RF-104), preferencias de notificación (RF-105), historial predictivo (RF-106) y catálogo de errores (RF-107)

Revision ID: a7c3e91f5b20
Revises: c8e1a7f30b52
Create Date: 2026-11-18

Estructura:
- ``modulo8.solicitudes_reportes``: cada reporte pedido, con su estado (EN_PROCESO, GENERADO, FALLIDO, CANCELADO,
  EXPIRADO), filtros, checksum, reintentos del proceso en segundo plano y vencimiento a las 48 h.
- ``modulo8.archivos_reportes``: el archivo en partes de hasta 50 MB (``bytea``, como los archivos de exportación de
  M05). Al vencer se borra el contenido y queda la fila como rastro.
- ``modulo9.preferencias_notificaciones``: canal PUSH o EMAIL por nivel y usuario (RF-105 R6). Sin fila rigen los
  valores por defecto del RF; la bandeja interna no se configura (R9: es la fuente canónica).
- ``modulo9.catalogo_mensajes_error``: texto en lenguaje natural, botón y ruta por clave de error e idioma (RF-107
  RNF-03), editable por el Administrador.

Las tablas viejas de ``modulo8`` del dump inicial (``reportes_regulatorios``, ``auditorias_reportes``…) no se tocan.

Datos:
- Parámetros en ``modulo4.parametros_mlops`` (el almacén que ya expone M09): ventana de agrupación de notificaciones,
  ventana de correspondencia del historial predictivo y umbral de la tasa de validación clínica.
- Tipos de evento 43–46 (reporte listo, reporte fallido, degradación del modelo, auditoría de notificaciones).
- 20 recursos RBAC: uno por tipo de reporte (acción Ejecutar), el historial predictivo (Leer) y el catálogo de errores
  (Crear, Actualizar, Eliminar). «Gerencia» no es un rol: sus reportes van al Productor (dueño de la finca).

Roles y recursos se resuelven por nombre. ``downgrade()`` deja recursos y permisos: el permiso del Administrador no se
puede borrar (``trg_proteger_permisos_admin_delete``) y sin uso no afecta nada.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a7c3e91f5b20'
down_revision: Union[str, Sequence[str], None] = 'c8e1a7f30b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS_FORCE = ('modulo1.recursos', 'modulo1.permisos', 'modulo1.roles')
_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"

ADMIN, PROD, VET, ING, CONT = 'Administrador', 'Productor', 'Veterinario', 'Ingeniero de Campo', 'Contador'
_PREFIJO = {ADMIN: 'admin', PROD: 'prod', VET: 'vet', ING: 'ing', CONT: 'cont'}

# tipo de reporte → (descripción del recurso, roles que lo generan)
_REPORTES = {
    'REPORTE_INVENTARIO_BIOLOGICO': ('Reporte de inventario biológico', (ADMIN, PROD, CONT)),
    'REPORTE_COSTOS_SUMINISTROS': ('Reporte de costos de suministros', (ADMIN, PROD, CONT)),
    'REPORTE_PRODUCTIVIDAD': ('Reporte de productividad', (ADMIN, PROD)),
    'REPORTE_BAJAS_Y_SALIDAS': ('Reporte de bajas y salidas', (ADMIN, PROD, CONT)),
    'REPORTE_VALORACION_NIC41': ('Reporte de valoración NIC 41', (ADMIN, CONT)),
    'REPORTE_ESTADO_EXPORTACIONES': ('Reporte de estado de las exportaciones contables', (ADMIN, CONT)),
    'REPORTE_VARIACION_PERIODOS': ('Reporte de variación entre períodos', (ADMIN, CONT)),
    'REPORTE_HISTORICO_SANITARIO': ('Reporte histórico sanitario', (ADMIN, VET, PROD)),
    'REPORTE_FICHA_ANIMAL': ('Ficha completa de un animal', (ADMIN, VET, PROD)),
    'REPORTE_VACUNACION_MEDICAMENTOS': ('Reporte de vacunación y medicamentos', (ADMIN, VET, PROD)),
    'REPORTE_RIESGO_SANITARIO': ('Reporte de riesgo sanitario', (ADMIN, VET)),
    'REPORTE_TELEMETRIA': ('Reporte de telemetría', (ADMIN, ING)),
    'REPORTE_ESTADO_DISPOSITIVOS': ('Reporte de estado de dispositivos', (ADMIN, ING)),
    'REPORTE_CALIBRACION_SENSORES': ('Reporte de calibración de sensores', (ADMIN, ING)),
    'REPORTE_ALERTAS_SENSORES': ('Reporte de alertas de sensores', (ADMIN, ING)),
    'REPORTE_EJECUTIVO_CONSOLIDADO': ('Reporte ejecutivo consolidado', (ADMIN, PROD)),
    'REPORTE_RENTABILIDAD_FINCA': ('Reporte de rentabilidad por finca', (ADMIN, PROD)),
    'REPORTE_COMPARATIVO_PERIODOS': ('Reporte comparativo de períodos', (ADMIN, PROD, CONT)),
}

# recurso → (descripción, [(rol, código de acción)])
_OTROS_RECURSOS = {
    'historial_clinico_predictivo': (
        'Historial clínico predictivo por animal (RF-106)', [(ADMIN, 'R'), (VET, 'R')]),
    'catalogo_mensajes_error': (
        'Catálogo de mensajes de error en lenguaje natural (RF-107)',
        [(ADMIN, 'C'), (ADMIN, 'U'), (ADMIN, 'D')]),
}
_VERBO = {'C': 'crear', 'R': 'leer', 'U': 'actualizar', 'D': 'desactivar', 'E': 'ejecutar'}

_TIPOS_EVENTO = (
    (43, 'REPORTE_GENERADO', 'Reporte generado y disponible para descarga'),
    (44, 'REPORTE_FALLIDO', 'Fallo en la generacion de un reporte'),
    (45, 'DEGRADACION_MODELO_PREDICTIVO', 'Tasa de validacion clinica bajo el umbral'),
    (46, 'AUDITORIA_NOTIFICACION', 'Creacion o cambio de estado de una notificacion'),
)

# (nombre, valor, descripción, mínimo, máximo)
_PARAMETROS = (
    ('ventana_agrupacion_notificaciones_min', 5,
     'Minutos en que avisos iguales sobre el mismo animal se agrupan en una sola notificación (RF-105)', 1, 60),
    ('ventana_correspondencia_horas', 12,
     'Horas entre una predicción y un evento sanitario para mostrarlos relacionados en el historial (RF-106)', 1, 48),
    ('umbral_tvco_degradacion', 60,
     'Porcentaje de validación clínica bajo el cual se avisa al Administrador de la degradación del modelo (RF-106)',
     0, 100),
)

# (clave, idioma, mensaje, texto del botón, ruta)
_MENSAJES = (
    ('ERROR_NO_CATALOGADO', 'es-CO', 'Ocurrió un problema técnico. Intenta nuevamente o contacta al administrador.',
     None, None),
    ('ERROR_NO_CATALOGADO', 'en-US', 'A technical problem occurred. Try again or contact the administrator.',
     None, None),
    ('SIN_CONEXION', 'es-CO', 'Sin conexión. La operación se reintentará automáticamente cuando vuelva la conexión.',
     None, None),
    ('SIN_CONEXION', 'en-US', 'No connection. The operation will retry automatically when the connection is back.',
     None, None),
    ('OPERACION_INTERRUMPIDA', 'es-CO', 'La operación no pudo completarse. Intenta nuevamente.', None, None),
    ('OPERACION_INTERRUMPIDA', 'en-US', 'The operation could not be completed. Try again.', None, None),
    ('OPERACION_DUPLICADA', 'es-CO', 'Esta operación ya está en curso o fue ejecutada recientemente.', None, None),
    ('OPERACION_DUPLICADA', 'en-US', 'This operation is already in progress or was run recently.', None, None),
    ('PERIODO_NO_CERRADO', 'es-CO', 'Este reporte solo se genera sobre períodos contables cerrados.',
     'Ir al cierre de período', 'finanzas'),
    ('PERIODO_NO_CERRADO', 'en-US', 'This report can only be generated for closed accounting periods.',
     'Go to period closing', 'finanzas'),
)


def _rls(force: bool) -> None:
    for tabla in _TABLAS_FORCE:
        op.execute(sa.text(f"ALTER TABLE {tabla} {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def _actor() -> None:
    # Los triggers de M01 (auditoría DML, protección de permisos) piden un actor en la sesión.
    op.execute(sa.text("SELECT set_config('app.current_role', 'Administrador', true), "
                       "set_config('app.current_user_id', '1', true)"))


def _ddl_reportes() -> None:
    tipos = ", ".join(f"'{t}'" for t in _REPORTES)
    op.execute(f"CREATE TYPE modulo8.enum_solicitud_reporte_tipo_reporte AS ENUM ({tipos})")
    op.execute("CREATE TYPE modulo8.enum_solicitud_reporte_formato AS ENUM ('PDF', 'EXCEL')")
    op.execute("CREATE TYPE modulo8.enum_solicitud_reporte_estado AS ENUM "
               "('EN_PROCESO', 'GENERADO', 'FALLIDO', 'CANCELADO', 'EXPIRADO')")
    op.execute("""
        CREATE TABLE modulo8.solicitudes_reportes (
            id_solicitud_reporte uuid NOT NULL DEFAULT gen_random_uuid()
                CONSTRAINT solicitudes_reportes_pkey PRIMARY KEY,
            id_usuario integer NOT NULL
                CONSTRAINT solicitudes_reportes_id_usuario_fkey REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE CASCADE ON UPDATE CASCADE,
            tipo_reporte modulo8.enum_solicitud_reporte_tipo_reporte NOT NULL,
            formato modulo8.enum_solicitud_reporte_formato NOT NULL,
            estado modulo8.enum_solicitud_reporte_estado NOT NULL DEFAULT 'EN_PROCESO',
            json_filtros jsonb NOT NULL DEFAULT '{}'::jsonb,
            zona_horaria varchar(64) NOT NULL DEFAULT 'UTC',
            numero_registros integer,
            numero_partes smallint NOT NULL DEFAULT 0,
            tamano_archivo_kb integer,
            checksum_sha256 varchar(64),
            intentos smallint NOT NULL DEFAULT 0,
            mensaje_error varchar(500),
            fecha_solicitud timestamptz NOT NULL DEFAULT now(),
            fecha_snapshot timestamptz,
            fecha_generacion timestamptz,
            fecha_proximo_intento timestamptz,
            fecha_expiracion timestamptz,
            fecha_eliminacion timestamptz,
            CONSTRAINT ck_solicitud_reporte_intentos CHECK (intentos BETWEEN 0 AND 3),
            CONSTRAINT ck_solicitud_reporte_registros CHECK (numero_registros IS NULL OR numero_registros >= 0),
            CONSTRAINT ck_solicitud_reporte_generado_completo CHECK (
                estado NOT IN ('GENERADO', 'EXPIRADO')
                OR (fecha_generacion IS NOT NULL AND fecha_expiracion IS NOT NULL
                    AND checksum_sha256 IS NOT NULL AND numero_partes >= 1))
        )
    """)
    op.execute("CREATE INDEX idx_solicitud_reporte_id_usuario_fecha_solicitud "
               "ON modulo8.solicitudes_reportes (id_usuario, fecha_solicitud DESC)")
    op.execute("CREATE INDEX idx_solicitud_reporte_fecha_proximo_intento "
               "ON modulo8.solicitudes_reportes (fecha_proximo_intento) WHERE estado = 'EN_PROCESO'")
    op.execute("CREATE INDEX idx_solicitud_reporte_fecha_expiracion "
               "ON modulo8.solicitudes_reportes (fecha_expiracion) WHERE estado = 'GENERADO'")
    op.execute("""
        CREATE TABLE modulo8.archivos_reportes (
            id_archivo_reporte bigint GENERATED ALWAYS AS IDENTITY CONSTRAINT archivos_reportes_pkey PRIMARY KEY,
            id_solicitud_reporte uuid NOT NULL
                CONSTRAINT archivos_reportes_id_solicitud_reporte_fkey
                REFERENCES modulo8.solicitudes_reportes (id_solicitud_reporte) ON DELETE CASCADE ON UPDATE CASCADE,
            numero_parte smallint NOT NULL,
            nombre_archivo varchar(200) NOT NULL,
            tipo_contenido varchar(100) NOT NULL,
            contenido bytea,
            tamano_bytes bigint NOT NULL,
            checksum_sha256 varchar(64) NOT NULL,
            CONSTRAINT uq_archivo_reporte_id_solicitud_reporte_numero_parte UNIQUE (id_solicitud_reporte, numero_parte),
            CONSTRAINT ck_archivo_reporte_tamano CHECK (tamano_bytes BETWEEN 0 AND 52428800),
            CONSTRAINT ck_archivo_reporte_numero_parte CHECK (numero_parte >= 1)
        )
    """)
    for tabla in ('solicitudes_reportes', 'archivos_reportes'):
        op.execute(f"ALTER TABLE modulo8.{tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE modulo8.{tabla} FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY pol_solicitud_reporte_propia ON modulo8.solicitudes_reportes
          USING (id_usuario = (SELECT modulo1.fn_id_usuario_actual()) OR (SELECT modulo1.fn_es_usuario_servicio()))
          WITH CHECK (id_usuario = (SELECT modulo1.fn_id_usuario_actual())
                      OR (SELECT modulo1.fn_es_usuario_servicio()))
    """)
    # Las partes se ven si se ve su solicitud (la RLS de solicitudes aplica dentro de la subconsulta).
    op.execute("""
        CREATE POLICY pol_archivo_reporte_de_solicitud_propia ON modulo8.archivos_reportes
          USING (EXISTS (SELECT 1 FROM modulo8.solicitudes_reportes s
                         WHERE s.id_solicitud_reporte = archivos_reportes.id_solicitud_reporte))
          WITH CHECK (EXISTS (SELECT 1 FROM modulo8.solicitudes_reportes s
                              WHERE s.id_solicitud_reporte = archivos_reportes.id_solicitud_reporte))
    """)
    op.execute("COMMENT ON TABLE modulo8.solicitudes_reportes IS "
               "'Reportes pedidos (RF-104): estado, filtros, checksum y vencimiento a las 48 h.'")
    op.execute("COMMENT ON COLUMN modulo8.archivos_reportes.contenido IS "
               "'Parte del archivo (hasta 50 MB). NULL cuando el reporte venció.'")


def _ddl_preferencias_y_catalogo() -> None:
    op.execute("CREATE TYPE modulo9.enum_preferencia_notificacion_canal AS ENUM ('PUSH', 'EMAIL')")
    op.execute("""
        CREATE TABLE modulo9.preferencias_notificaciones (
            id_preferencia_notificacion integer GENERATED ALWAYS AS IDENTITY
                CONSTRAINT preferencias_notificaciones_pkey PRIMARY KEY,
            id_usuario integer NOT NULL
                CONSTRAINT preferencias_notificaciones_id_usuario_fkey REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE CASCADE ON UPDATE CASCADE,
            nivel modulo1.enum_notificacion_nivel NOT NULL,
            canal modulo9.enum_preferencia_notificacion_canal NOT NULL,
            es_habilitado boolean NOT NULL,
            fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_preferencia_notificacion_id_usuario_nivel_canal UNIQUE (id_usuario, nivel, canal)
        )
    """)
    op.execute("""
        CREATE TABLE modulo9.catalogo_mensajes_error (
            id_catalogo_mensaje_error integer GENERATED ALWAYS AS IDENTITY
                CONSTRAINT catalogo_mensajes_error_pkey PRIMARY KEY,
            clave varchar(80) NOT NULL,
            idioma varchar(10) NOT NULL DEFAULT 'es-CO',
            mensaje varchar(500) NOT NULL,
            texto_accion varchar(80),
            ruta_accion varchar(200),
            es_activo boolean NOT NULL DEFAULT TRUE,
            id_usuario integer
                CONSTRAINT catalogo_mensajes_error_id_usuario_fkey REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE SET NULL ON UPDATE CASCADE,
            fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_catalogo_mensaje_error_clave_idioma UNIQUE (clave, idioma),
            CONSTRAINT ck_catalogo_mensaje_error_clave CHECK (clave ~ '^[A-Z0-9_]{2,80}$'),
            CONSTRAINT ck_catalogo_mensaje_error_mensaje CHECK (char_length(btrim(mensaje)) >= 5),
            CONSTRAINT ck_catalogo_mensaje_error_accion CHECK ((texto_accion IS NULL) = (ruta_accion IS NULL))
        )
    """)
    for tabla in ('preferencias_notificaciones', 'catalogo_mensajes_error'):
        op.execute(f"ALTER TABLE modulo9.{tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE modulo9.{tabla} FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY pol_preferencia_notificacion_propia ON modulo9.preferencias_notificaciones
          USING (id_usuario = (SELECT modulo1.fn_id_usuario_actual()) OR (SELECT modulo1.fn_es_usuario_servicio()))
          WITH CHECK (id_usuario = (SELECT modulo1.fn_id_usuario_actual()))
    """)
    op.execute("CREATE POLICY pol_catalogo_mensaje_error_select ON modulo9.catalogo_mensajes_error "
               "FOR SELECT USING (true)")
    for accion, comando in (('C', 'INSERT'), ('U', 'UPDATE'), ('D', 'DELETE')):
        permiso = f"((SELECT modulo1.fn_tiene_permiso('catalogo_mensajes_error', '{accion}')))"
        clausulas = {'INSERT': f"WITH CHECK {permiso}", 'UPDATE': f"USING {permiso} WITH CHECK {permiso}",
                     'DELETE': f"USING {permiso}"}[comando]
        op.execute(f"CREATE POLICY pol_catalogo_mensaje_error_{comando.lower()} "
                   f"ON modulo9.catalogo_mensajes_error FOR {comando} {clausulas}")
    for clave, idioma, mensaje, texto, ruta in _MENSAJES:
        op.execute(sa.text("""
            INSERT INTO modulo9.catalogo_mensajes_error (clave, idioma, mensaje, texto_accion, ruta_accion)
            VALUES (:clave, :idioma, :mensaje, :texto, :ruta)
            ON CONFLICT (clave, idioma) DO NOTHING
        """).bindparams(clave=clave, idioma=idioma, mensaje=mensaje, texto=texto, ruta=ruta))


def _grants() -> None:
    op.execute(f"""
        DO $$
        DECLARE r text; t text;
        BEGIN
            -- Una BD construida desde cero no da USAGE sobre modulo8 (DEV ya lo tiene del dump inicial).
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT USAGE ON SCHEMA modulo8 TO %I', r);
            END LOOP;
            FOREACH t IN ARRAY ARRAY['modulo8.solicitudes_reportes', 'modulo8.archivos_reportes',
                                     'modulo9.preferencias_notificaciones', 'modulo9.catalogo_mensajes_error'] LOOP
                FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %s TO %I', t, r);
                END LOOP;
            END LOOP;
        END $$;
    """)


def _tipos_evento() -> None:
    for id_tipo, nombre, accion in _TIPOS_EVENTO:
        op.execute(f"""
            DO $$
            BEGIN
                LOCK TABLE modulo1.tipos_eventos IN SHARE ROW EXCLUSIVE MODE;
                IF EXISTS (SELECT 1 FROM modulo1.tipos_eventos
                            WHERE (id_tipo_evento = {id_tipo} AND nombre <> '{nombre}')
                               OR (nombre = '{nombre}' AND id_tipo_evento <> {id_tipo})) THEN
                    RAISE EXCEPTION 'M08: conflicto de identidad del tipo {nombre} ({id_tipo})';
                END IF;
                INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
                VALUES ({id_tipo}, '{nombre}', '{accion}') ON CONFLICT (id_tipo_evento) DO NOTHING;
            END $$;
        """)
    op.execute("""
        SELECT setval('modulo1.tipos_evento_id_tipo_evento_seq',
                      GREATEST((SELECT max(id_tipo_evento) FROM modulo1.tipos_eventos),
                               (SELECT last_value FROM modulo1.tipos_evento_id_tipo_evento_seq)), true)
    """)


def _parametros() -> None:
    for nombre, valor, descripcion, minimo, maximo in _PARAMETROS:
        op.execute(sa.text("""
            INSERT INTO modulo4.parametros_mlops
                (nombre_parametro, valor_actual, valor_por_defecto, descripcion, rango_minimo, rango_maximo)
            SELECT :nombre, to_jsonb(CAST(:valor AS integer)), to_jsonb(CAST(:valor AS integer)), :descripcion,
                   :minimo, :maximo
            WHERE NOT EXISTS (SELECT 1 FROM modulo4.parametros_mlops WHERE nombre_parametro = :nombre)
        """).bindparams(nombre=nombre, valor=valor, descripcion=descripcion, minimo=minimo, maximo=maximo))


def _recurso(nombre: str, descripcion: str, permisos: list[tuple[str, str]]) -> None:
    op.execute(sa.text("""
        INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
        SELECT (SELECT max(id_recurso) + 1 FROM modulo1.recursos), :nombre, :descripcion
        WHERE NOT EXISTS (SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = :nombre)
    """).bindparams(nombre=nombre, descripcion=descripcion))
    for rol, codigo in permisos:
        op.execute(sa.text("""
            INSERT INTO modulo1.permisos (nombre, descripcion, es_activo, id_recurso, id_accion, id_rol)
            SELECT :permiso, :texto, TRUE, rec.id_recurso, a.id_accion, r.id_rol
            FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
            WHERE r.nombre_rol = :rol AND rec.nombre_recurso = :recurso AND a.codigo = :codigo
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE SET es_activo = TRUE, fecha_actualizacion = now()
        """).bindparams(permiso=f"{_PREFIJO[rol]}_{_VERBO[codigo]}_{nombre}"[:100],
                        texto=f"{rol}: {descripcion.lower()} ({_VERBO[codigo]}).", rol=rol, recurso=nombre,
                        codigo=codigo))


def _rbac() -> None:
    for tipo, (descripcion, roles) in _REPORTES.items():
        _recurso(tipo.lower(), f"{descripcion} (RF-104)", [(rol, 'E') for rol in roles])
    for nombre, (descripcion, permisos) in _OTROS_RECURSOS.items():
        _recurso(nombre, descripcion, permisos)


def upgrade() -> None:
    _rls(False)
    try:
        _actor()
        _ddl_reportes()
        _ddl_preferencias_y_catalogo()
        _grants()
        _tipos_evento()
        _parametros()
        _rbac()
    finally:
        _rls(True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS modulo8.archivos_reportes")
    op.execute("DROP TABLE IF EXISTS modulo8.solicitudes_reportes")
    op.execute("DROP TYPE IF EXISTS modulo8.enum_solicitud_reporte_estado")
    op.execute("DROP TYPE IF EXISTS modulo8.enum_solicitud_reporte_formato")
    op.execute("DROP TYPE IF EXISTS modulo8.enum_solicitud_reporte_tipo_reporte")
    op.execute("DROP TABLE IF EXISTS modulo9.catalogo_mensajes_error")
    op.execute("DROP TABLE IF EXISTS modulo9.preferencias_notificaciones")
    op.execute("DROP TYPE IF EXISTS modulo9.enum_preferencia_notificacion_canal")
    op.execute(sa.text("DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro IN :nombres")
               .bindparams(sa.bindparam('nombres', value=tuple(p[0] for p in _PARAMETROS), expanding=True)))
    for id_tipo, nombre, _ in _TIPOS_EVENTO:
        op.execute(f"""
            DELETE FROM modulo1.tipos_eventos t WHERE t.id_tipo_evento = {id_tipo} AND t.nombre = '{nombre}'
               AND NOT EXISTS (SELECT 1 FROM modulo1.eventos e WHERE e.tipo_evento = t.id_tipo_evento)
        """)
