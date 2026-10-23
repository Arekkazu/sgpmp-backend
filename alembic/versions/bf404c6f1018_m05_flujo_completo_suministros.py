# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74..81: flujo completo sin atajos      |
"""M05 (RF-74 a RF-81): flujo completo de suministros sin atajos

Revision ID: bf404c6f1018
Revises: e5a3c9b17d42
Create Date: 2026-10-22

Por qué va por Alembic y no por SQL suelto vía MCP: es el patrón del repo
(cadena lineal + `migration-db.yml`), el DDL manual ya desincronizó `sgpmp` y
`pruebas` en M05 (recursos/permisos aplicados a mano en julio), CI solo
despliega lo que está en `alembic/versions/`, y el `rev_id` deja trazado el RF.

Qué hace:

1. RF-78 R7/R12/CA-8/RNF-09 — la CORRECCION es un ajuste que SUMA al acumulado
   (puede ser negativo). `fn_acumular_costo_ciclo` calculaba el delta contra el
   registro original (semántica de reemplazo): con dos correcciones sobre el
   mismo original el acumulado quedaba en `c1 + c2 - original`. Ahora el delta es
   siempre `NEW.costo_registro`, y Σ costo_registro del ledger == acumulado.
   Las filas existentes no se tocan (append-only); los ciclos con correcciones
   anteriores a esta migración quedan marcados como potencialmente incompletos
   al consolidar (RF-79 R11), que es el comportamiento que pide el RF ante una
   diferencia entre el ledger y el acumulado.
   Además, la deduplicación por contenido de R8 (índice único
   `uq_registro_suministro_dedup_contenido`) se aplicaba también a las filas que
   el trigger crea desde RF-75/RF-76, y dos raciones iguales del mismo alimento
   el mismo día a horas distintas (permitidas por RF-75 R12) chocaban en el
   ledger y el consumo se rechazaba con 409. Para ALIMENTO/MEDICAMENTO el
   duplicado lo deciden RF-75 R10 y RF-76 R13 (que incluyen la hora); el índice
   queda solo para los registros directos de RF-78.
2. RF-78 RNF-05 — el Gestor de Granja registra, consulta y corrige suministros
   directos; el Contador también registra. Permisos sobre el recurso
   `costeo_directo_suministros`, resueltos por nombre (no por id).
3. RF-77 (24 h) y RF-81 (72 h) — `modulo5.archivos_exportacion_suministros`
   guarda los archivos exportados (PDF/CSV/EXCEL) con su vencimiento. Al vencer
   se purga el contenido y la descarga responde 410.
4. RF-79 — `modulo5.outbox_provisiones_m06`: cola persistente (transactional
   outbox) de los eventos INCREMENTAL y CONSOLIDADO hacia M06, con reintentos
   0/5/15/30/60 s y estado PROVISION_PENDIENTE tras 5 fallos (E1/E7).
5. M06 provisional — `modulo6.recepciones_provisiones_m05`: bandeja de entrada
   de M06 con deduplicación por `id_evento_provision` (RF-79 R10/CA-10). Es lo
   mínimo para que la entrega tenga un ACK real mientras M06 no tenga backend;
   cuando lo tenga, consume desde esta tabla.
6. RF-80 — valores del catálogo que faltaban en
   `enum_auditoria_suministro_tipo_operacion`: PRECIO_MANUAL_INGRESADO,
   ACUMULADO_ACTUALIZADO, PROVISION_PENDIENTE y EXPORTACION_HISTORIAL_ELIMINADA
   (RF-81 RNF-06: la eliminación del archivo vencido queda en RF-80).
7. Notificaciones internas (RF-14) que pide M05: tipos de evento para reporte
   asíncrono listo/fallido (RF-77 E4/E5), resultado de historial listo (RF-81
   E3/E7), provisión pendiente (RF-79 E1/CA-9), conversión alimenticia crítica
   (RF-74 paso 8) y batch ICA interrumpido (RF-74).
8. RF-75/RF-76 — datos de entrada que la BD no admitía:
   - RF-75 pide `costo_unitario` como entrada obligatoria del consumo y
     `costo_total = cantidad × costo_unitario` (paso 8). El trigger
     `fn_trg_calcular_costo_total_consumo` usaba siempre el precio del catálogo;
     ahora usa el del registro y solo cae al catálogo si no viene.
   - RF-75 `observaciones` varchar(255): la columna era varchar(60) porque la
     vista `vw_m05_registro_alimentacion` la referencia. Se recrea la vista con
     su misma definición y sus mismos permisos.
   - RF-76 `observaciones` varchar(500): `registros_medicamentos` no tenía
     columna para guardarlas.
9. RF-77 RNF "Historial de reportes": se guardan todos los parámetros del
   reporte (tipo_periodo, categorías, especie...) en
   `reporte_gastos_acumulados.json_parametros` para regenerarlo y exportarlo.
10. Las filas de configuración de los motores de M05 (`configuracion_batch_ica`,
   `_historial_suministros`, `_reportes_gastos`) se sembraron a mano en dev y no
   están en el baseline: en una base construida con Alembic no existen y RF-74,
   RF-77 y RF-81 fallan. Se insertan si faltan (fila única con los valores por
   defecto de cada tabla). El downgrade no las borra.
   Parámetros que no coincidían con el RF: niveles de volumen de RF-81 R11
   (nivel 3 desde 50.001 y nivel 4 desde 200.001 registros) y reintentos de
   RF-77 E5 (3 intentos cada 5 minutos, límite de 50 generaciones simultáneas).

Downgrade: borra las tablas y tipos de evento nuevos y restaura la función y
los parámetros anteriores. Los valores de enum y los permisos de los roles no
se retiran (PostgreSQL no permite quitar valores de un enum; los permisos se
desactivan).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'bf404c6f1018'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"

_VALORES_ENUM_AUDITORIA = (
    "PRECIO_MANUAL_INGRESADO",
    "ACUMULADO_ACTUALIZADO",
    "PROVISION_PENDIENTE",
    "EXPORTACION_HISTORIAL_ELIMINADA",
)

# (nombre, accion varchar(50))
_TIPOS_EVENTO = (
    ("REPORTE_GASTOS_GENERADO", "Reporte de gastos asincrono disponible"),
    ("REPORTE_GASTOS_FALLIDO", "Fallo en la generacion del reporte de gastos"),
    ("HISTORIAL_SUMINISTROS_LISTO", "Resultado de historial de suministros listo"),
    ("PROVISION_M06_PENDIENTE", "Provision de costos pendiente de entrega a M06"),
    ("ALERTA_CONVERSION_ALIMENTICIA", "Conversion alimenticia critica"),
    ("BATCH_ICA_INTERRUMPIDO", "Batch de conversion alimenticia interrumpido"),
)

# (prefijo, nombre_rol, id_accion, verbo)
_PERMISOS_RF78 = (
    ("gestor", "Gestor de Granja", 1, "crear"),
    ("gestor", "Gestor de Granja", 2, "leer"),
    ("gestor", "Gestor de Granja", 3, "actualizar"),
    ("cont", "Contador", 1, "crear"),
)

_FN_ACUMULAR_ADITIVA = """
CREATE OR REPLACE FUNCTION modulo5.fn_acumular_costo_ciclo()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.id_gestion_fases IS NULL THEN
    RAISE WARNING 'registro_suministro %: sin id_gestion_fases; no se acumula.', NEW.id_registro_suministro;
    RETURN NEW;
  END IF;

  -- RF-78 R7/R12: el acumulado es la suma de costo_registro de todas las filas
  -- del ciclo; una CORRECCION suma su propio costo (negativo si compensa).
  -- UPDATE primero: el CHECK chk_acumulado_no_negativo se evalúa contra el
  -- valor final y no contra el VALUES de un INSERT .. ON CONFLICT.
  UPDATE modulo5.acumulado_ciclo SET
    acumulado_total_ciclo = acumulado_total_ciclo + NEW.costo_registro,
    acumulado_por_categoria = jsonb_set(
      COALESCE(acumulado_por_categoria, '{}'::jsonb),
      ARRAY[NEW.tipo_suministro],
      to_jsonb(COALESCE((acumulado_por_categoria ->> NEW.tipo_suministro)::numeric, 0) + NEW.costo_registro)
    ),
    version_acumulado = version_acumulado + 1,
    fecha_ultima_actualizacion = now()
  WHERE id_gestion_fases = NEW.id_gestion_fases;

  IF NOT FOUND THEN
    -- Solo un REGISTRO abre el acumulado (costo > 0): una CORRECCION siempre
    -- referencia un registro cuyo REGISTRO ya creó esta fila.
    INSERT INTO modulo5.acumulado_ciclo
      (id_activo_biologico, id_ciclo_productivo, id_gestion_fases, acumulado_total_ciclo,
       acumulado_por_categoria, version_acumulado)
    VALUES
      (NEW.id_activo_biologico, NEW.id_ciclo_productivo, NEW.id_gestion_fases, NEW.costo_registro,
       jsonb_build_object(NEW.tipo_suministro, NEW.costo_registro), 0)
    ON CONFLICT (id_gestion_fases) DO UPDATE SET
      acumulado_total_ciclo = modulo5.acumulado_ciclo.acumulado_total_ciclo + NEW.costo_registro,
      acumulado_por_categoria = jsonb_set(
        COALESCE(modulo5.acumulado_ciclo.acumulado_por_categoria, '{}'::jsonb),
        ARRAY[NEW.tipo_suministro],
        to_jsonb(COALESCE((modulo5.acumulado_ciclo.acumulado_por_categoria ->> NEW.tipo_suministro)::numeric, 0) + NEW.costo_registro)
      ),
      version_acumulado = modulo5.acumulado_ciclo.version_acumulado + 1,
      fecha_ultima_actualizacion = now();
  END IF;

  RETURN NEW;
END; $function$
"""

_FN_ACUMULAR_REEMPLAZO = """
CREATE OR REPLACE FUNCTION modulo5.fn_acumular_costo_ciclo()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_delta numeric;
  v_costo_original numeric;
BEGIN
  IF NEW.id_gestion_fases IS NULL THEN
    RAISE WARNING 'registro_suministro %: sin id_gestion_fases; no se acumula.', NEW.id_registro_suministro;
    RETURN NEW;
  END IF;

  IF NEW.tipo_operacion = 'CORRECCION' THEN
    SELECT costo_registro INTO v_costo_original
    FROM modulo5.registro_suministro WHERE id_registro_suministro = NEW.id_registro_original;
    v_delta := NEW.costo_registro - COALESCE(v_costo_original, 0);
  ELSE
    v_delta := NEW.costo_registro;
  END IF;

  UPDATE modulo5.acumulado_ciclo SET
    acumulado_total_ciclo = acumulado_total_ciclo + v_delta,
    acumulado_por_categoria = jsonb_set(
      COALESCE(acumulado_por_categoria, '{}'::jsonb),
      ARRAY[NEW.tipo_suministro],
      to_jsonb(COALESCE((acumulado_por_categoria ->> NEW.tipo_suministro)::numeric, 0) + v_delta)
    ),
    version_acumulado = version_acumulado + 1,
    fecha_ultima_actualizacion = now()
  WHERE id_gestion_fases = NEW.id_gestion_fases;

  IF NOT FOUND THEN
    INSERT INTO modulo5.acumulado_ciclo
      (id_activo_biologico, id_ciclo_productivo, id_gestion_fases, acumulado_total_ciclo,
       acumulado_por_categoria, version_acumulado)
    VALUES
      (NEW.id_activo_biologico, NEW.id_ciclo_productivo, NEW.id_gestion_fases, v_delta,
       jsonb_build_object(NEW.tipo_suministro, v_delta), 0)
    ON CONFLICT (id_gestion_fases) DO UPDATE SET
      acumulado_total_ciclo = modulo5.acumulado_ciclo.acumulado_total_ciclo + v_delta,
      acumulado_por_categoria = jsonb_set(
        COALESCE(modulo5.acumulado_ciclo.acumulado_por_categoria, '{}'::jsonb),
        ARRAY[NEW.tipo_suministro],
        to_jsonb(COALESCE((modulo5.acumulado_ciclo.acumulado_por_categoria ->> NEW.tipo_suministro)::numeric, 0) + v_delta)
      ),
      version_acumulado = modulo5.acumulado_ciclo.version_acumulado + 1,
      fecha_ultima_actualizacion = now();
  END IF;

  RETURN NEW;
END; $function$
"""


_INDICE_DEDUP = (
    "CREATE UNIQUE INDEX uq_registro_suministro_dedup_contenido ON modulo5.registro_suministro "
    "(id_activo_biologico, id_ciclo_productivo, tipo_suministro, fecha_aplicacion, cantidad, "
    "precio_unitario_resuelto) WHERE {condicion}"
)
_SOLO_REGISTRO = "(tipo_operacion)::text = 'REGISTRO'::text"
_SOLO_REGISTRO_DIRECTO = _SOLO_REGISTRO + " AND id_registro_rf75 IS NULL AND id_registro_rf76 IS NULL"


_FN_COSTO_CONSUMO = """
CREATE OR REPLACE FUNCTION modulo5.fn_trg_calcular_costo_total_consumo()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_costo_unitario modulo5.tipos_alimentos.costo_unitario%TYPE;
BEGIN
    IF NEW.cantidad_suministrada <= 0 THEN
        RAISE EXCEPTION
            'CANTIDAD_INVALIDA: La cantidad suministrada debe ser mayor a cero. '
            'Valor recibido: [%]. (RF-75 Restricción 1)',
            NEW.cantidad_suministrada
        USING ERRCODE = 'P0001';
    END IF;

    SELECT costo_unitario
    INTO v_costo_unitario
    FROM modulo5.tipos_alimentos
    WHERE id_tipo_elemento = NEW.id_tipo_alimento
      AND estado = 'ACTIVO';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'TIPO_ALIMENTO_INVALIDO: No se encontró el tipo de alimento con id [%] '
            'en estado ACTIVO. Verifique el catálogo antes de registrar el consumo. '
            '(RF-75 Proceso paso 2)',
            NEW.id_tipo_alimento
        USING ERRCODE = 'P0001';
    END IF;

    -- RF-75 paso 8: costo_total = cantidad × costo_unitario del registro.
    NEW.costo_unitario := COALESCE(NEW.costo_unitario, v_costo_unitario);
    NEW.costo_total := NEW.cantidad_suministrada * NEW.costo_unitario;

    RETURN NEW;
END;
$function$
"""

_FN_COSTO_CONSUMO_CATALOGO = _FN_COSTO_CONSUMO.replace(
    """    NEW.costo_unitario := COALESCE(NEW.costo_unitario, v_costo_unitario);
    NEW.costo_total := NEW.cantidad_suministrada * NEW.costo_unitario;""",
    "    NEW.costo_total := NEW.cantidad_suministrada * v_costo_unitario;",
)

# Recrea vw_m05_registro_alimentacion alrededor del cambio de tipo de la columna:
# misma definición y mismos permisos (no hay vistas que dependan de ella).
_CAMBIAR_OBSERVACION_CONSUMO = """
DO $$
DECLARE
    v_def text;
    v_acl aclitem[];
    r record;
BEGIN
    SELECT pg_get_viewdef(c.oid), c.relacl INTO v_def, v_acl
    FROM pg_class c WHERE c.oid = 'modulo5.vw_m05_registro_alimentacion'::regclass;
    DROP VIEW modulo5.vw_m05_registro_alimentacion;
    ALTER TABLE modulo5.registros_consumo_alimentos ALTER COLUMN observacion TYPE {tipo};
    EXECUTE 'CREATE VIEW modulo5.vw_m05_registro_alimentacion AS ' || v_def;
    IF v_acl IS NULL THEN
        RETURN;  -- sin permisos explícitos (BD recién construida)
    END IF;
    FOR r IN SELECT a.privilege_type, a.grantee FROM aclexplode(v_acl) a LOOP
        EXECUTE format(
            'GRANT %s ON modulo5.vw_m05_registro_alimentacion TO %s',
            r.privilege_type,
            CASE WHEN r.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(r.grantee)) END
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    # 1. Corrección aditiva (RF-78 R7/R12/CA-8/RNF-09) y dedup R8 solo para registros directos.
    op.execute(_FN_ACUMULAR_ADITIVA)
    op.execute("DROP INDEX modulo5.uq_registro_suministro_dedup_contenido")
    op.execute(_INDICE_DEDUP.format(condicion=_SOLO_REGISTRO_DIRECTO))

    # 2. Permisos RF-78 RNF-05 (bajo RLS de modulo1: identidad de Administrador).
    valores = ",\n".join(
        f"('{prefijo}', '{rol}', {accion}, '{verbo}')" for prefijo, rol, accion, verbo in _PERMISOS_RF78
    )
    op.execute(f"""
        DO $$
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            SELECT v.prefijo || '_' || v.verbo || '_costeo_directo_suministros',
                   'RF-78 RNF-05: ' || v.rol || ' gestiona los suministros directos del ciclo.',
                   ro.id_rol, re.id_recurso, v.accion, TRUE
            FROM (VALUES {valores}) AS v(prefijo, rol, accion, verbo)
            JOIN modulo1.roles ro ON ro.nombre_rol = v.rol
            JOIN modulo1.recursos re ON re.nombre_recurso = 'costeo_directo_suministros'
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE SET es_activo = TRUE;
        END $$;
    """)

    # 3. Archivos exportados de RF-77 (24 h) y RF-81 (72 h).
    op.execute("""
        CREATE TABLE modulo5.archivos_exportacion_suministros (
            id_archivo_exportacion_suministro UUID NOT NULL DEFAULT gen_random_uuid(),
            origen VARCHAR(10) NOT NULL,
            id_referencia INTEGER,
            formato VARCHAR(10) NOT NULL,
            nombre_archivo VARCHAR(255) NOT NULL,
            tipo_contenido VARCHAR(100) NOT NULL,
            contenido BYTEA,
            tamano_bytes BIGINT NOT NULL,
            total_registros INTEGER NOT NULL,
            id_usuario INTEGER NOT NULL,
            fecha_generacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            fecha_expiracion TIMESTAMPTZ NOT NULL,
            fecha_eliminacion TIMESTAMPTZ,
            CONSTRAINT archivos_exportacion_suministros_pkey PRIMARY KEY (id_archivo_exportacion_suministro),
            CONSTRAINT archivos_exportacion_suministros_id_usuario_fkey
                FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios (id_usuario)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_archivo_exportacion_suministro_origen CHECK (origen IN ('RF77', 'RF81')),
            CONSTRAINT ck_archivo_exportacion_suministro_formato CHECK (formato IN ('PDF', 'CSV', 'EXCEL')),
            CONSTRAINT ck_archivo_exportacion_suministro_vencimiento CHECK (fecha_expiracion > fecha_generacion)
        )
    """)
    op.execute("""
        CREATE INDEX idx_archivo_exportacion_suministro_fecha_expiracion
            ON modulo5.archivos_exportacion_suministros (fecha_expiracion)
            WHERE fecha_eliminacion IS NULL
    """)
    op.execute("""
        CREATE INDEX idx_archivo_exportacion_suministro_origen_id_referencia
            ON modulo5.archivos_exportacion_suministros (origen, id_referencia)
    """)
    op.execute("""
        COMMENT ON TABLE modulo5.archivos_exportacion_suministros IS
        'RF-77 (24 h) y RF-81 (72 h): archivos exportados. Al vencer se purga contenido y la descarga responde 410.'
    """)

    # 4. Cola persistente M05 -> M06 (RF-79).
    op.execute("""
        CREATE TABLE modulo5.outbox_provisiones_m06 (
            id_outbox_provision_m06 UUID NOT NULL DEFAULT gen_random_uuid(),
            modalidad modulo5.enum_tipo_provision NOT NULL,
            schema_version VARCHAR(10) NOT NULL,
            id_activo_biologico INTEGER NOT NULL,
            id_gestion_fases INTEGER,
            id_registro_suministro UUID,
            id_provision INTEGER,
            costo_registro NUMERIC(14,4),
            json_contenido JSONB NOT NULL,
            estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
            numero_intentos INTEGER NOT NULL DEFAULT 0,
            fecha_intentos TIMESTAMPTZ[] NOT NULL DEFAULT '{}',
            fecha_proximo_intento TIMESTAMPTZ NOT NULL DEFAULT now(),
            es_alerta_enviada BOOLEAN NOT NULL DEFAULT FALSE,
            fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
            fecha_entrega TIMESTAMPTZ,
            CONSTRAINT outbox_provisiones_m06_pkey PRIMARY KEY (id_outbox_provision_m06),
            CONSTRAINT outbox_provisiones_m06_id_gestion_fases_fkey
                FOREIGN KEY (id_gestion_fases) REFERENCES modulo2.gestiones_fases (id_gestion_fases)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT outbox_provisiones_m06_id_provision_fkey
                FOREIGN KEY (id_provision) REFERENCES modulo5.provision_nic41 (id_provision)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT ck_outbox_provision_m06_estado
                CHECK (estado IN ('PENDIENTE', 'ENTREGADO', 'PROVISION_PENDIENTE')),
            CONSTRAINT ck_outbox_provision_m06_numero_intentos CHECK (numero_intentos >= 0)
        )
    """)
    op.execute("""
        CREATE INDEX idx_outbox_provision_m06_fecha_proximo_intento
            ON modulo5.outbox_provisiones_m06 (fecha_proximo_intento)
            WHERE estado <> 'ENTREGADO'
    """)
    op.execute("""
        CREATE INDEX idx_outbox_provision_m06_id_gestion_fases
            ON modulo5.outbox_provisiones_m06 (id_gestion_fases)
    """)
    op.execute("""
        COMMENT ON TABLE modulo5.outbox_provisiones_m06 IS
        'RF-79: eventos INCREMENTAL/CONSOLIDADO hacia M06, escritos en la misma transacción del registro (outbox).'
    """)

    # 5. Bandeja de entrada provisional de M06.
    op.execute("""
        CREATE TABLE modulo6.recepciones_provisiones_m05 (
            id_recepcion_provision_m05 SERIAL,
            id_evento_provision UUID NOT NULL,
            modalidad VARCHAR(15) NOT NULL,
            schema_version VARCHAR(10) NOT NULL,
            id_activo_biologico INTEGER NOT NULL,
            id_gestion_fases INTEGER,
            json_contenido JSONB NOT NULL,
            fecha_recepcion TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT recepciones_provisiones_m05_pkey PRIMARY KEY (id_recepcion_provision_m05),
            CONSTRAINT uq_recepcion_provision_m05_id_evento_provision UNIQUE (id_evento_provision),
            CONSTRAINT ck_recepcion_provision_m05_modalidad CHECK (modalidad IN ('INCREMENTAL', 'CONSOLIDADO'))
        )
    """)
    op.execute("""
        CREATE INDEX idx_recepcion_provision_m05_id_activo_biologico
            ON modulo6.recepciones_provisiones_m05 (id_activo_biologico)
    """)
    op.execute("""
        COMMENT ON TABLE modulo6.recepciones_provisiones_m05 IS
        'M06 provisional: provisiones de costos recibidas de M05 (RF-79). Dedup por id_evento_provision.'
    """)

    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT INSERT, SELECT, UPDATE ON modulo5.archivos_exportacion_suministros TO %I', r);
                EXECUTE format('GRANT INSERT, SELECT, UPDATE ON modulo5.outbox_provisiones_m06 TO %I', r);
                EXECUTE format('GRANT INSERT, SELECT ON modulo6.recepciones_provisiones_m05 TO %I', r);
                EXECUTE format(
                    'GRANT USAGE, SELECT ON SEQUENCE modulo6.recepciones_provisiones_m05_id_recepcion_provision_m05_seq TO %I', r
                );
            END LOOP;
        END $$;
    """)

    # 6. Catálogo de eventos de RF-80.
    for valor in _VALORES_ENUM_AUDITORIA:
        op.execute(
            f"ALTER TYPE modulo5.enum_auditoria_suministro_tipo_operacion ADD VALUE IF NOT EXISTS '{valor}'"
        )

    # 7. Tipos de evento de las notificaciones internas de M05 (se resuelven por nombre).
    op.execute("""
        SELECT setval(
            'modulo1.tipos_evento_id_tipo_evento_seq',
            (SELECT max(id_tipo_evento) FROM modulo1.tipos_eventos)
        )
    """)
    for nombre, accion in _TIPOS_EVENTO:
        op.execute(f"""
            INSERT INTO modulo1.tipos_eventos (nombre, accion)
            SELECT '{nombre}', '{accion}'
            WHERE NOT EXISTS (SELECT 1 FROM modulo1.tipos_eventos WHERE nombre = '{nombre}')
        """)

    # 8. RF-75/RF-76: costo del registro, observaciones.
    op.execute(_FN_COSTO_CONSUMO)
    op.execute(_CAMBIAR_OBSERVACION_CONSUMO.format(tipo="VARCHAR(255)"))
    op.execute("ALTER TABLE modulo5.registros_medicamentos ADD COLUMN observaciones VARCHAR(500)")

    # 9. RF-77: parámetros completos del reporte.
    op.execute("ALTER TABLE modulo5.reporte_gastos_acumulados ADD COLUMN json_parametros JSONB")

    # 10. Filas de configuración faltantes y parámetros del RF.
    for tabla in ("configuracion_batch_ica", "configuracion_batch_historial_suministros",
                  "configuracion_batch_reportes_gastos"):
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM modulo5.{tabla}) THEN
                    INSERT INTO modulo5.{tabla} DEFAULT VALUES;
                END IF;
            END $$;
        """)
    op.execute("""
        UPDATE modulo5.configuracion_batch_historial_suministros
        SET umbral_nivel3 = 50000, umbral_nivel4 = 200000, actualizado_en = now()
    """)
    op.execute("""
        UPDATE modulo5.configuracion_batch_reportes_gastos
        SET max_reintentos = 3, backoff_minutos = '{5,5,5}', limite_concurrencia = 50, actualizado_en = now()
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE modulo5.reporte_gastos_acumulados DROP COLUMN json_parametros")
    op.execute("ALTER TABLE modulo5.registros_medicamentos DROP COLUMN observaciones")
    op.execute(_CAMBIAR_OBSERVACION_CONSUMO.format(tipo="VARCHAR(60) USING left(observacion, 60)"))
    op.execute(_FN_COSTO_CONSUMO_CATALOGO)
    op.execute("""
        UPDATE modulo5.configuracion_batch_reportes_gastos
        SET max_reintentos = 3, backoff_minutos = '{1,3,5}', limite_concurrencia = 5, actualizado_en = now()
    """)
    op.execute("""
        UPDATE modulo5.configuracion_batch_historial_suministros
        SET umbral_nivel3 = 10000, umbral_nivel4 = 50000, actualizado_en = now()
    """)
    nombres = ", ".join(f"'{nombre}'" for nombre, _ in _TIPOS_EVENTO)
    op.execute(f"""
        DELETE FROM modulo1.tipos_eventos t
        WHERE t.nombre IN ({nombres})
          AND NOT EXISTS (SELECT 1 FROM modulo1.eventos e WHERE e.tipo_evento = t.id_tipo_evento)
    """)
    op.execute("DROP TABLE modulo6.recepciones_provisiones_m05")
    op.execute("DROP TABLE modulo5.outbox_provisiones_m06")
    op.execute("DROP TABLE modulo5.archivos_exportacion_suministros")
    # Los permisos de Gestor/Contador se desactivan (no son de Administrador, se pueden tocar).
    op.execute("""
        DO $$
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            UPDATE modulo1.permisos SET es_activo = FALSE
            WHERE nombre IN ('gestor_crear_costeo_directo_suministros',
                             'gestor_leer_costeo_directo_suministros',
                             'gestor_actualizar_costeo_directo_suministros',
                             'cont_crear_costeo_directo_suministros');
        END $$;
    """)
    op.execute("DROP INDEX modulo5.uq_registro_suministro_dedup_contenido")
    op.execute(_INDICE_DEDUP.format(condicion=_SOLO_REGISTRO))
    op.execute(_FN_ACUMULAR_REEMPLAZO)
