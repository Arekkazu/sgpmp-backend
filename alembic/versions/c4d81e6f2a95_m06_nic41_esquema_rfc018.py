# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94 + RFC-018: esquema modulo6 listo para NIC 41 (líneas de asiento, matriz, comprobante, titular) |
"""m06 nic41: modulo6 alineado a RFC-018 y listo para el backend

Revision ID: c4d81e6f2a95
Revises: eab9814cd751
Create Date: 2026-11-04

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

``modulo6`` vino en el baseline con un diseño anterior a RFC-018 y sin uso (0 filas, sin
código). Esta migración lo deja operable sin borrar vistas ni objetos de otros módulos:

1. RFC-018: líneas de asiento NIC 41 (RF-86 v2.0), matriz contable (RF-109), comprobante del
   período (RF-87 v1.1) y titular tributario de la finca (RF-19 v1.1). Los campos AAEF que
   RFC-018 retiró de ``registros_costos`` y ``cotizaciones`` dejan de ser obligatorios (no se
   borran: vistas de modulo6 los leen).
2. Restricciones que bloqueaban el RF: ``UNIQUE(id_activo_biologico)`` del reconocimiento
   (impedía reconocer de nuevo tras una reversión, RF-82 CA-14) pasa a único solo entre
   CONFIRMADOS; el período deja de ser único por rango y lo es por titular; el precio deja de
   ser único por fecha (la corrección de RF-89 FA-6 usa la misma fecha de vigencia).
3. Triggers: el cierre (RF-87) escribe con el período EN_CIERRE si la transacción declara
   ``app.cierre_periodo``; la reversión (RF-82), la aprobación del estado de resultados
   (RF-93) y el archivado del informe (RF-92) eran imposibles con los triggers de inmutabilidad
   anteriores y ahora solo permiten esa transición.
4. Nombres que rompían la convención: la PK ``"id_ medicion_posterior"`` (con espacio) y la
   tabla ``deterorios_activos``.
5. RBAC: 12 recursos de M06 (ids fijos 88-99, resueltos por nombre) y sus permisos.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4d81e6f2a95'
down_revision: Union[str, Sequence[str], None] = 'eab9814cd751'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"

_TIPOS_HECHO = (
    'RECONOCIMIENTO_NACIMIENTO', 'RECONOCIMIENTO_DIFERENCIA', 'VARIACION_VR_TB', 'VARIACION_VR_PM',
    'PRODUCTO_AGRICOLA', 'CONSUMO_INSUMO', 'MANO_OBRA_PROPIA', 'BAJA_ACTIVO', 'AJUSTE_PERIODO_ANTERIOR',
    'DEPRECIACION_ACTIVO_COSTO', 'DETERIORO_ACTIVO_COSTO',
)
_SENTIDOS = ('GANANCIA', 'PERDIDA', 'UNICO', 'TRASLADO', 'CAPITALIZACION')
_TIPOS_EVENTO_AUDITORIA = (
    'RECONOCIMIENTO_INICIAL', 'RECONOCIMIENTO_REVERTIDO', 'RECONOCIMIENTO_BLOQUEADO_SIN_VALOR', 'REVERSION_BLOQUEADA',
    'CALCULO_VALOR_RAZONABLE', 'AJUSTE_MANUAL_COSTOS_VENTA', 'MEDICION_POSTERIOR', 'MEDICION_CON_ESTIMACION',
    'MEDICION_SIN_VARIACION', 'MEDICION_PENDIENTE', 'VARIACION_REGISTRADA', 'LINEA_ASIENTO_PENDIENTE_CUENTA',
    'LINEA_ASIENTO_REGISTRADA', 'PRODUCTO_AGRICOLA_RECONOCIDO', 'RECONOCIMIENTO_PRODUCTO_PENDIENTE',
    'BAJA_ACTIVO_REGISTRADA', 'COSTO_REGISTRADO', 'COSTO_CLASIFICADO', 'PRECIO_REGISTRADO',
    'PRECIO_MARCADO_REEMPLAZADO', 'PRECIO_REFERENCIA_VENCIDO', 'PARAMETRO_COSTOS_VENTA_ACTUALIZADO',
    'MATRIZ_CONTABLE_ACTUALIZADA', 'CONFIGURACION_CONTABLE_ACTUALIZADA', 'ACTIVO_MARCADO_SIN_MERCADO',
    'METODO_VALORACION_CAMBIADO', 'DEPRECIACION_REGISTRADA', 'DETERIORO_REGISTRADO', 'COTIZACION_REGISTRADA',
    'COTIZACION_MODIFICADA', 'COTIZACION_ANULADA', 'COTIZACION_VENCIDA', 'CIERRE_PERIODO_INICIADO',
    'CIERRE_PERIODO_COMPLETADO', 'CIERRE_PERIODO_FALLIDO', 'EXCLUSION_CIERRE_AUTORIZADA', 'COMPROBANTE_GENERADO',
    'CADENA_TRAZABILIDAD_VERIFICADA', 'INFORME_REVELACIONES_GENERADO', 'INFORME_REVELACIONES_APROBADO',
    'INFORME_REVELACIONES_RECHAZADO', 'ERROR_CONSISTENCIA', 'ESTADO_RESULTADOS_GENERADO',
    'ESTADO_RESULTADOS_APROBADO', 'ERROR_CONCILIACION', 'ERROR_TECNICO',
)

# (id fijo, nombre, descripción); el id solo se usa si el nombre no existe todavía.
_RECURSOS = (
    (88, 'precios_mercado', 'Repositorio de precios de mercado de referencia NIC 41 (RF-89)'),
    (89, 'configuracion_contable', 'Costos de venta, matriz contable, parámetros por especie y periodicidad (RF-84, RF-109)'),
    (90, 'reconocimiento_inicial', 'Reconocimiento inicial de activos biológicos y su reversión (RF-82)'),
    (91, 'valoracion_activos', 'Valor razonable, mediciones posteriores, variaciones y productos agrícolas (RF-83 a RF-86)'),
    (92, 'costos_activos', 'Costos de mantenimiento, inversión y venta del activo biológico (RF-90)'),
    (93, 'cierre_periodo', 'Períodos contables, cierre y comprobante NIC 41 (RF-87)'),
    (94, 'valoracion_por_costo', 'Valoración por costo y deterioros (RF-88)'),
    (95, 'cotizaciones', 'Cotizaciones de venta de activos biológicos (RF-COT)'),
    (96, 'trazabilidad_contable', 'Cadena de trazabilidad desde la telemetría hasta el asiento (RF-91)'),
    (97, 'revelaciones_nic41', 'Informe de revelaciones NIC 41 (RF-92)'),
    (98, 'estado_resultados', 'Estado de resultados del período agropecuario (RF-93)'),
    (99, 'auditoria_financiera', 'Auditoría del módulo financiero (RF-94)'),
)

_ROLES = {1: ('admin', 'Administrador'), 2: ('prod', 'Productor'), 5: ('cont', 'Contador'), 8: ('revfis', 'Revisor Fiscal')}
_ACCIONES = {1: ('crear', 'registra'), 2: ('leer', 'consulta'), 3: ('actualizar', 'actualiza'),
             4: ('desactivar', 'anula o revierte'), 5: ('ejecutar', 'ejecuta')}
# recurso -> {id_rol: (acciones)}
_MATRIZ_PERMISOS = {
    'precios_mercado': {5: (1, 2), 1: (2,), 8: (2,)},
    'configuracion_contable': {5: (1, 2, 3), 1: (1, 2, 3), 8: (2,)},
    'reconocimiento_inicial': {5: (1, 2, 4), 1: (2,), 8: (2,)},
    'valoracion_activos': {5: (2, 5), 1: (2,), 8: (2,)},
    'costos_activos': {5: (1, 2, 3), 1: (1, 2), 8: (2,)},
    'cierre_periodo': {5: (2, 5), 1: (2,), 8: (2,)},
    'valoracion_por_costo': {5: (1, 2, 3), 8: (2,)},
    'cotizaciones': {5: (1, 2, 3, 4), 1: (1, 2, 4), 2: (2,)},
    'trazabilidad_contable': {5: (2, 5), 1: (2,), 8: (2,)},
    'revelaciones_nic41': {5: (1, 2, 3), 2: (2,), 8: (2,)},
    'estado_resultados': {5: (1, 2, 3), 1: (2,), 2: (2,), 8: (2,)},
    'auditoria_financiera': {5: (2,), 1: (2,), 8: (2,)},
}


def _enum(nombre: str, valores: tuple) -> str:
    lista = ", ".join(f"'{v}'" for v in valores)
    return f"CREATE TYPE modulo6.{nombre} AS ENUM ({lista})"


def _conceder(tabla: str, pk: str) -> None:
    """DML a los roles de la app sobre la tabla y su secuencia (el nombre largo lo trunca Postgres)."""
    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT SELECT, INSERT, UPDATE ON modulo6.{tabla} TO %I', r);
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO %I',
                               pg_get_serial_sequence('modulo6.{tabla}', '{pk}'), r);
            END LOOP;
        END $$;
    """)


def upgrade() -> None:
    # Un valor nuevo de enum no se puede usar en la misma transacción que lo crea.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE modulo6.enum_auditorias_financieras_severidad ADD VALUE IF NOT EXISTS 'CRITICAL'")
        op.execute("ALTER TYPE modulo6.enum_precio_mercado_categoria ADD VALUE IF NOT EXISTS 'PRODUCTO'")

    op.execute(_enum('enum_linea_asiento_nic41_tipo_hecho', _TIPOS_HECHO))
    op.execute(_enum('enum_linea_asiento_nic41_sentido', _SENTIDOS))
    op.execute(_enum('enum_linea_asiento_nic41_estado', ('PENDIENTE_CUENTA', 'REGISTRADA')))
    op.execute(_enum('enum_registro_costo_origen_costo',
                     ('CONSUMO_INVENTARIO', 'MANO_OBRA_PROPIA', 'COMPRA_PROVEEDOR', 'SERVICIO_TERCERO')))
    op.execute(_enum('enum_registro_costo_vehiculo_contable', ('FACTURA_COMPRA', 'ASIENTO_NIC41', 'NINGUNO')))
    op.execute(_enum('enum_registro_costo_metodo_reparto', ('POR_CABEZAS', 'POR_BIOMASA')))
    op.execute(_enum('enum_auditoria_financiera_tipo_evento', _TIPOS_EVENTO_AUDITORIA))

    # --- Titular tributario de la finca (RF-19 v1.1, RFC-018 D-18.6) -------------------------
    op.execute("""
        ALTER TABLE modulo9.fincas
            ADD COLUMN tipo_id_tributaria varchar(3),
            ADD COLUMN numero_id_tributaria varchar(15),
            ADD COLUMN dv varchar(1),
            ADD COLUMN razon_social varchar(120),
            ADD CONSTRAINT ck_finca_tipo_id_tributaria CHECK (tipo_id_tributaria IN ('NIT', 'CC', 'CE')),
            ADD CONSTRAINT ck_finca_numero_id_tributaria CHECK (numero_id_tributaria ~ '^[0-9]{6,15}$'),
            ADD CONSTRAINT ck_finca_dv CHECK (dv ~ '^[0-9]$'),
            ADD CONSTRAINT ck_finca_titular_completo CHECK (
                num_nulls(tipo_id_tributaria, numero_id_tributaria, razon_social) IN (0, 3)
                AND (tipo_id_tributaria IS DISTINCT FROM 'NIT' OR dv IS NOT NULL))
    """)

    # --- Configuración contable y parámetros por especie (RF-109, RF-84, RF-88) --------------
    op.execute("""
        CREATE TABLE modulo6.configuraciones_contables (
            id_configuracion_contable smallint NOT NULL DEFAULT 1,
            tipo_cierre modulo6.enum_periodos_contables_tipo_cierre NOT NULL DEFAULT 'MENSUAL',
            pct_umbral_desviacion_precio numeric(5,2) NOT NULL DEFAULT 50,
            dias_alerta_vencimiento_precio smallint NOT NULL DEFAULT 30,
            fecha_inicio_operacion date NOT NULL DEFAULT CURRENT_DATE,
            id_usuario integer,
            fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT configuraciones_contables_pkey PRIMARY KEY (id_configuracion_contable),
            CONSTRAINT ck_configuracion_contable_fila_unica CHECK (id_configuracion_contable = 1),
            CONSTRAINT ck_configuracion_contable_umbral CHECK (pct_umbral_desviacion_precio > 0),
            CONSTRAINT ck_configuracion_contable_dias_alerta CHECK (dias_alerta_vencimiento_precio IN (7, 15, 30)),
            CONSTRAINT configuraciones_contables_id_usuario_fkey FOREIGN KEY (id_usuario)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE SET NULL ON UPDATE CASCADE
        )
    """)
    op.execute("INSERT INTO modulo6.configuraciones_contables (id_configuracion_contable) VALUES (1)")
    op.execute("""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {roles} LOOP
                EXECUTE format('GRANT SELECT, UPDATE ON modulo6.configuraciones_contables TO %I', r);
            END LOOP;
        END $$;
    """.replace('{roles}', _ROLES_APP))

    op.execute("""
        CREATE TABLE modulo6.parametros_contables_especies (
            id_parametro_contable_especie serial NOT NULL,
            id_especie integer NOT NULL,
            clasificacion modulo6.enum_reconocimientos_iniciales_clasificacion NOT NULL,
            categoria_precio modulo6.enum_precio_mercado_categoria NOT NULL DEFAULT 'PESO_KG',
            vida_util_meses integer,
            id_usuario integer,
            fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT parametros_contables_especies_pkey PRIMARY KEY (id_parametro_contable_especie),
            CONSTRAINT uq_parametro_contable_especie_id_especie UNIQUE (id_especie),
            CONSTRAINT ck_parametro_contable_especie_categoria CHECK (categoria_precio <> 'PRODUCTO'),
            CONSTRAINT ck_parametro_contable_especie_vida_util CHECK (vida_util_meses IS NULL OR vida_util_meses > 0),
            CONSTRAINT parametros_contables_especies_id_especie_fkey FOREIGN KEY (id_especie)
                REFERENCES modulo9.especies (id_especie) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT parametros_contables_especies_id_usuario_fkey FOREIGN KEY (id_usuario)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE SET NULL ON UPDATE CASCADE
        )
    """)
    _conceder('parametros_contables_especies', 'id_parametro_contable_especie')

    op.execute("""
        CREATE TABLE modulo6.asignaciones_cuentas_contables (
            id_asignacion_cuenta_contable serial NOT NULL,
            tipo_hecho modulo6.enum_linea_asiento_nic41_tipo_hecho NOT NULL,
            sentido modulo6.enum_linea_asiento_nic41_sentido NOT NULL,
            id_especie integer,
            subtipo_costo modulo6.enum_registros_costos_subtipo_costo,
            cuenta_debito varchar(20) NOT NULL,
            cuenta_credito varchar(20) NOT NULL,
            es_activo boolean NOT NULL DEFAULT true,
            id_usuario integer,
            fecha_creacion timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT asignaciones_cuentas_contables_pkey PRIMARY KEY (id_asignacion_cuenta_contable),
            CONSTRAINT ck_asignacion_cuenta_contable_cuentas CHECK (
                cuenta_debito ~ '^[0-9]{1,20}$' AND cuenta_credito ~ '^[0-9]{1,20}$' AND cuenta_debito <> cuenta_credito),
            CONSTRAINT asignaciones_cuentas_contables_id_especie_fkey FOREIGN KEY (id_especie)
                REFERENCES modulo9.especies (id_especie) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT asignaciones_cuentas_contables_id_usuario_fkey FOREIGN KEY (id_usuario)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE SET NULL ON UPDATE CASCADE
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_asignacion_cuenta_contable_vigente ON modulo6.asignaciones_cuentas_contables
            (tipo_hecho, sentido, id_especie, subtipo_costo) NULLS NOT DISTINCT WHERE es_activo
    """)
    _conceder('asignaciones_cuentas_contables', 'id_asignacion_cuenta_contable')

    # --- Período por titular (RF-87 v1.1, RFC-017 D-17.5) ------------------------------------
    op.execute('ALTER TABLE modulo6.periodos_contables DROP CONSTRAINT IF EXISTS "uq_periodo_rango "')
    op.execute("ALTER TABLE modulo6.periodos_contables ADD COLUMN numero_id_tributaria varchar(15)")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM modulo6.periodos_contables) THEN
                ALTER TABLE modulo6.periodos_contables ALTER COLUMN numero_id_tributaria SET NOT NULL;
            END IF;
        END $$;
    """)
    # El cierre abre el período siguiente aunque aún no haya empezado (RF-87 v1.1).
    op.execute("ALTER TABLE modulo6.periodos_contables DROP CONSTRAINT IF EXISTS chk_periodo_inicio_no_futuro")
    op.execute("""
        CREATE UNIQUE INDEX uq_periodo_contable_numero_id_tributaria_fecha_inicio
            ON modulo6.periodos_contables (numero_id_tributaria, fecha_inicio)
    """)

    # --- Auditoría (RF-94): tipo de evento real, eventos sin activo, actor sistema -----------
    op.execute("""
        ALTER TABLE modulo6.auditorias_financieras
            ADD COLUMN tipo_evento modulo6.enum_auditoria_financiera_tipo_evento NOT NULL DEFAULT 'ERROR_TECNICO',
            ADD COLUMN id_referencia bigint,
            ADD COLUMN id_sistema varchar(60),
            ADD COLUMN es_payload_truncado boolean NOT NULL DEFAULT false,
            ALTER COLUMN id_activo_biologico DROP NOT NULL,
            ALTER COLUMN fecha_registro SET DEFAULT now()
    """)
    op.execute("ALTER TABLE modulo6.auditorias_financieras ALTER COLUMN tipo_evento DROP DEFAULT")
    op.execute("""
        COMMENT ON COLUMN modulo6.auditorias_financieras.tipo IS
        'Columna del diseño previo tipada con la severidad; la app guarda la misma severidad. El tipo de evento real es tipo_evento.'
    """)
    op.execute("CREATE INDEX idx_auditoria_financiera_tipo_evento ON modulo6.auditorias_financieras (tipo_evento, fecha_registro)")
    op.execute("CREATE INDEX idx_auditoria_financiera_id_activo_biologico ON modulo6.auditorias_financieras (id_activo_biologico)")
    op.execute("CREATE INDEX idx_auditoria_financiera_id_periodo_contable ON modulo6.auditorias_financieras (id_periodo_contable)")

    # --- Precios (RF-89) ----------------------------------------------------------------------
    op.execute("ALTER TABLE modulo6.precios_mercado RENAME COLUMN id_precio_coregido TO id_precio_corregido")
    op.execute("ALTER TABLE modulo6.precios_mercado DROP CONSTRAINT IF EXISTS uq_precio_especie_cat_fuente_vigencia")
    op.execute("ALTER TABLE modulo6.precios_mercado DROP CONSTRAINT IF EXISTS chk_vigencia_no_retroactiva")
    op.execute("""
        ALTER TABLE modulo6.precios_mercado
            ADD COLUMN id_metrica_produccion integer,
            ALTER COLUMN fecha_registro SET DEFAULT now(),
            ALTER COLUMN version_precio SET DEFAULT 1,
            ADD CONSTRAINT precios_mercado_id_metrica_produccion_fkey FOREIGN KEY (id_metrica_produccion)
                REFERENCES modulo9.metricas_produccion (id_metrica_produccion) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT ck_precio_mercado_categoria_unica CHECK (array_length(categoria, 1) = 1),
            ADD CONSTRAINT ck_precio_mercado_producto_metrica CHECK (
                ('PRODUCTO' = ANY (categoria)) = (id_metrica_produccion IS NOT NULL))
    """)
    op.execute("""
        CREATE INDEX idx_precio_mercado_id_especie_fecha_vigencia
            ON modulo6.precios_mercado (id_especie, fecha_vigencia DESC, id_precio_mercado DESC)
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_08_validacion_fechas_precio()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.fecha_vigencia < (modulo1.fn_hoy_usuario() - 365) THEN
                RAISE EXCEPTION '[TGR-M06-08] fecha_vigencia=% es anterior en más de 365 días a hoy (%). RF-89.',
                    NEW.fecha_vigencia, modulo1.fn_hoy_usuario() USING ERRCODE = 'P0001';
            END IF;
            IF NEW.fecha_vencimiento IS NOT NULL AND NEW.fecha_vencimiento <= NEW.fecha_vigencia THEN
                RAISE EXCEPTION '[TGR-M06-08] fecha_vencimiento=% debe ser posterior a fecha_vigencia=%. RF-89.',
                    NEW.fecha_vencimiento, NEW.fecha_vigencia USING ERRCODE = 'P0001';
            END IF;
            IF NEW.precio_unitario <= 0 THEN
                RAISE EXCEPTION '[TGR-M06-08] precio_unitario=% debe ser mayor a cero. RF-89 CA-3.',
                    NEW.precio_unitario USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    # --- Parámetros de costos de venta (RF-84): historial, uno vigente por especie y región ---
    op.execute('ALTER TABLE modulo6.parametros_costos_venta DROP CONSTRAINT IF EXISTS "uq_param_especie_region "')
    op.execute("""
        ALTER TABLE modulo6.parametros_costos_venta
            ALTER COLUMN es_activo SET DEFAULT true,
            ALTER COLUMN fecha_creacion SET DEFAULT now()
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_parametro_costo_venta_id_especie_region_vigente
            ON modulo6.parametros_costos_venta (id_especie, region) WHERE es_activo
    """)

    # --- Reconocimiento inicial (RF-82) --------------------------------------------------------
    op.execute("ALTER TABLE modulo6.reconocimientos_iniciales DROP CONSTRAINT IF EXISTS uq_reconocimientos_iniciales_id_activo_biologico")
    op.execute("""
        ALTER TABLE modulo6.reconocimientos_iniciales
            ALTER COLUMN id_precio_mercado DROP NOT NULL,
            ALTER COLUMN cuenta_debito DROP NOT NULL,
            ALTER COLUMN cuenta_credito DROP NOT NULL,
            ALTER COLUMN fecha_creacion SET DEFAULT now(),
            ADD COLUMN costo_adquisicion numeric(18,4),
            ADD COLUMN origen_financiero modulo2.enum_activo_biologico_origen_financiero,
            ADD COLUMN id_calculo_valor_razonable integer,
            ADD COLUMN id_valoracion_por_costo integer,
            ADD COLUMN es_apertura boolean NOT NULL DEFAULT false,
            ADD COLUMN id_usuario_reversion integer,
            ADD COLUMN fecha_reversion timestamptz,
            ADD CONSTRAINT reconocimientos_iniciales_id_calculo_valor_razonable_fkey FOREIGN KEY (id_calculo_valor_razonable)
                REFERENCES modulo6.calculos_valor_razonable (id_calculo_valor_razonable) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT reconocimientos_iniciales_id_valoracion_por_costo_fkey FOREIGN KEY (id_valoracion_por_costo)
                REFERENCES modulo6.valoraciones_por_costos (id_valoracion_por_costo) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT reconocimientos_iniciales_id_usuario_reversion_fkey FOREIGN KEY (id_usuario_reversion)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT ck_reconocimiento_inicial_fuente_valor CHECK (
                num_nonnulls(id_calculo_valor_razonable, id_valoracion_por_costo) = 1)
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_reconocimiento_inicial_id_activo_biologico_confirmado
            ON modulo6.reconocimientos_iniciales (id_activo_biologico) WHERE estado = 'CONFIRMADO'
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_01_inmutabilidad_reconocimiento()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_mutables text[] := ARRAY['estado', 'justificacion_reversion', 'id_usuario_reversion', 'fecha_reversion'];
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION '[TGR-M06-01] El reconocimiento inicial id=% no puede eliminarse. RF-82 R2.',
                    OLD.id_reconocimiento_inicial USING ERRCODE = 'P0001';
            END IF;
            -- Única transición permitida: la reversión auditada (RF-82 R2).
            IF OLD.estado = 'CONFIRMADO' AND NEW.estado = 'REVERTIDO'
               AND (to_jsonb(NEW) - v_mutables) = (to_jsonb(OLD) - v_mutables) THEN
                RETURN NEW;
            END IF;
            IF OLD.estado IN ('CONFIRMADO', 'REVERTIDO') THEN
                RAISE EXCEPTION '[TGR-M06-01] El reconocimiento inicial id=% tiene estado % y es inmutable. RF-82 R2.',
                    OLD.id_reconocimiento_inicial, OLD.estado USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    # --- Cálculo de valor razonable (RF-84): magnitud física y supuestos (RF-92 ¶47) -----------
    op.execute("""
        ALTER TABLE modulo6.calculos_valor_razonable
            ALTER COLUMN fecha_calculo SET DEFAULT now(),
            ADD COLUMN magnitud numeric(18,4),
            ADD COLUMN unidad_magnitud varchar(20),
            ADD COLUMN precio_unitario numeric(18,4),
            ADD COLUMN id_evento_magnitud integer,
            ADD COLUMN tiene_valor_estimado boolean NOT NULL DEFAULT false,
            ADD COLUMN json_metodo_costo jsonb,
            ADD CONSTRAINT calculos_valor_razonable_id_evento_magnitud_fkey FOREIGN KEY (id_evento_magnitud)
                REFERENCES modulo2.eventos_activos (id_eventos) ON DELETE RESTRICT ON UPDATE CASCADE
    """)
    op.execute("CREATE INDEX idx_calculo_valor_razonable_id_activo_biologico ON modulo6.calculos_valor_razonable (id_activo_biologico, fecha_calculo DESC)")

    # --- Mediciones posteriores (RF-83): PK sin espacio ----------------------------------------
    op.execute('ALTER TABLE modulo6.mediciones_posteriores RENAME COLUMN "id_ medicion_posterior" TO id_medicion_posterior')
    op.execute('ALTER SEQUENCE IF EXISTS modulo6."mediciones_posteriores_id_ medicion_posterior_seq" '
               'RENAME TO mediciones_posteriores_id_medicion_posterior_seq')
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_05_inmutabilidad_medicion()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION '[TGR-M06-05] La medición posterior id=% no puede eliminarse. RF-83 RNF-83-04.',
                    OLD.id_medicion_posterior USING ERRCODE = 'P0001';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD.estado = 'COMPLETADO' THEN
                RAISE EXCEPTION '[TGR-M06-05] La medición posterior id=% está COMPLETADA y es inmutable. RF-83 RNF-83-04.',
                    OLD.id_medicion_posterior USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("CREATE INDEX idx_medicion_posterior_id_activo_biologico ON modulo6.mediciones_posteriores (id_activo_biologico, fecha_medicion DESC)")

    # --- Variaciones (RF-86): origen por evento, precio o cierre --------------------------------
    op.execute("""
        ALTER TABLE modulo6.variaciones_valor_razonable
            ALTER COLUMN id_evento DROP NOT NULL,
            ALTER COLUMN fecha_registro SET DEFAULT now(),
            ADD COLUMN id_precio_mercado integer,
            ADD COLUMN id_cierre integer,
            ADD CONSTRAINT variaciones_valor_razonable_id_precio_mercado_fkey FOREIGN KEY (id_precio_mercado)
                REFERENCES modulo6.precios_mercado (id_precio_mercado) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT variaciones_valor_razonable_id_cierre_fkey FOREIGN KEY (id_cierre)
                REFERENCES modulo6.ejecuciones_cierre_periodo (id_cierre) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT ck_variacion_valor_razonable_origen CHECK (num_nonnulls(id_evento, id_precio_mercado, id_cierre) >= 1)
    """)
    op.execute("CREATE INDEX idx_variacion_valor_razonable_id_periodo_contable ON modulo6.variaciones_valor_razonable (id_periodo_contable)")

    # --- El cierre escribe con el período EN_CIERRE si declara app.cierre_periodo (RF-87) ------
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_09_periodo_cerrado_bloqueo()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_estado modulo6.enum_periodo_contables_estado;
            v_id_periodo integer;
        BEGIN
            IF TG_OP = 'DELETE' THEN v_id_periodo := OLD.id_periodo_contable; ELSE v_id_periodo := NEW.id_periodo_contable; END IF;
            SELECT estado INTO v_estado FROM modulo6.periodos_contables WHERE id_periodo_contable = v_id_periodo;
            IF NOT FOUND THEN
                RAISE EXCEPTION '[TGR-M06-09] El período contable id=% no existe.', v_id_periodo USING ERRCODE = 'P0001';
            END IF;
            IF v_estado = 'CERRADO'
               OR (v_estado = 'EN_CIERRE' AND current_setting('app.cierre_periodo', true) IS DISTINCT FROM v_id_periodo::text) THEN
                RAISE EXCEPTION '[TGR-M06-09] PERIODO_CONTABLE_CERRADO: el período % está % (tabla %, operación %). RF-87.',
                    v_id_periodo, v_estado, TG_TABLE_NAME, TG_OP USING ERRCODE = 'P0001';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_validar_periodo_abierto_en_variacion()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            -- El bloqueo por período lo hace fn_tgr_m06_09 (mismo criterio, incluida la excepción del cierre).
            RETURN NEW;
        END;
        $$
    """)

    # --- Productos agrícolas (RF-85) -------------------------------------------------------------
    op.execute("ALTER TABLE modulo6.reconocimientos_productos_agricolas "
               "RENAME COLUMN id_reconocimiento_prodcutos_agricola TO id_reconocimiento_producto_agricola")
    op.execute("""
        ALTER TABLE modulo6.reconocimientos_productos_agricolas
            ALTER COLUMN cuenta_debito DROP NOT NULL,
            ALTER COLUMN cuenta_credito DROP NOT NULL,
            ALTER COLUMN fecha_registro SET DEFAULT now(),
            ADD COLUMN id_medicion_posterior integer,
            ADD CONSTRAINT reconocimientos_productos_agricolas_id_medicion_posterior_fkey FOREIGN KEY (id_medicion_posterior)
                REFERENCES modulo6.mediciones_posteriores (id_medicion_posterior) ON DELETE RESTRICT ON UPDATE CASCADE
    """)

    # --- Costos (RF-90 v2.0): origen, vehículo, factura, reparto ---------------------------------
    op.execute("DROP TRIGGER IF EXISTS tgr_m06_14a_accounting_costos ON modulo6.registros_costos")
    op.execute("ALTER TABLE modulo6.registros_costos DROP CONSTRAINT IF EXISTS chk_accounting_account_no_vacio")
    op.execute("""
        ALTER TABLE modulo6.registros_costos
            ALTER COLUMN accounting_account DROP NOT NULL,
            ALTER COLUMN line_type DROP NOT NULL,
            ALTER COLUMN exportable_aaef SET DEFAULT false,
            ALTER COLUMN naturaleza_costo DROP NOT NULL,
            ALTER COLUMN fecha_registro SET DEFAULT now(),
            ADD COLUMN origen_costo modulo6.enum_registro_costo_origen_costo NOT NULL DEFAULT 'MANO_OBRA_PROPIA',
            ADD COLUMN vehiculo_contable modulo6.enum_registro_costo_vehiculo_contable NOT NULL DEFAULT 'NINGUNO',
            ADD COLUMN fecha_costo date NOT NULL DEFAULT CURRENT_DATE,
            ADD COLUMN id_origen_m05 uuid,
            ADD COLUMN tercero_nit varchar(15),
            ADD COLUMN tercero_dv varchar(1),
            ADD COLUMN tercero_razon_social varchar(200),
            ADD COLUMN factura_prefijo varchar(10),
            ADD COLUMN factura_numero varchar(30),
            ADD COLUMN fecha_factura date,
            ADD COLUMN fecha_vencimiento_factura date,
            ADD COLUMN id_grupo_reparto uuid,
            ADD COLUMN metodo_reparto modulo6.enum_registro_costo_metodo_reparto,
            ADD COLUMN cuenta_debito varchar(20),
            ADD COLUMN cuenta_credito varchar(20),
            ADD COLUMN es_cuenta_manual boolean NOT NULL DEFAULT false,
            ADD COLUMN es_reverso boolean NOT NULL DEFAULT false,
            ADD COLUMN id_registro_costo_compensado integer,
            ADD CONSTRAINT uq_registro_costo_id_origen_m05 UNIQUE (id_origen_m05),
            ADD CONSTRAINT registros_costos_id_registro_costo_compensado_fkey FOREIGN KEY (id_registro_costo_compensado)
                REFERENCES modulo6.registros_costos (id_registro_costo) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT ck_registro_costo_naturaleza_clasificada CHECK (
                naturaleza_costo IS NOT NULL OR estado = 'PENDIENTE_CLASIFICACION'),
            ADD CONSTRAINT ck_registro_costo_datos_proveedor CHECK (
                origen_costo NOT IN ('COMPRA_PROVEEDOR', 'SERVICIO_TERCERO')
                OR (tercero_nit ~ '^[0-9]{6,15}$' AND tercero_dv ~ '^[0-9]$' AND tercero_razon_social IS NOT NULL
                    AND factura_numero IS NOT NULL AND fecha_factura IS NOT NULL
                    AND fecha_vencimiento_factura >= fecha_factura))
    """)
    op.execute("ALTER TABLE modulo6.registros_costos ALTER COLUMN origen_costo DROP DEFAULT, "
               "ALTER COLUMN vehiculo_contable DROP DEFAULT, ALTER COLUMN fecha_costo DROP DEFAULT")
    op.execute("""
        CREATE UNIQUE INDEX uq_registro_costo_factura_id_activo_biologico ON modulo6.registros_costos
            (tercero_nit, factura_prefijo, factura_numero, id_activo_biologico) NULLS NOT DISTINCT WHERE factura_numero IS NOT NULL
    """)
    op.execute("CREATE INDEX idx_registro_costo_id_periodo_contable ON modulo6.registros_costos (id_periodo_contable)")
    op.execute("CREATE INDEX idx_registro_costo_id_activo_biologico ON modulo6.registros_costos (id_activo_biologico)")

    op.execute("""
        ALTER TABLE modulo6.recepciones_provisiones_m05
            ADD COLUMN fecha_procesamiento timestamptz,
            ADD COLUMN resultado_procesamiento varchar(40)
    """)

    # --- Cotizaciones (RF-COT v1.1): sin campos AAEF ----------------------------------------------
    op.execute("DROP TRIGGER IF EXISTS tgr_m06_14b_accounting_cotizaciones ON modulo6.cotizaciones")
    op.execute("""
        ALTER TABLE modulo6.cotizaciones
            ALTER COLUMN accounting_account DROP NOT NULL,
            ALTER COLUMN line_type DROP NOT NULL,
            ALTER COLUMN type_code DROP NOT NULL,
            ALTER COLUMN fecha_registro SET DEFAULT now(),
            ALTER COLUMN estado SET DEFAULT 'COTIZADO',
            ADD COLUMN estado_al_cierre modulo6.enum_cotizaciones_estado_cotizacion,
            ADD COLUMN valor_razonable_referencia numeric(18,4),
            ADD COLUMN version integer NOT NULL DEFAULT 1,
            ADD COLUMN fecha_actualizacion timestamptz
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_19_campos_inmutables_cotizacion()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.fecha_emision <> OLD.fecha_emision OR NEW.id_periodo_contable <> OLD.id_periodo_contable
               OR NEW.activos_cotizados <> OLD.activos_cotizados THEN
                RAISE EXCEPTION '[TGR-M06-19] CAMPO_NO_MODIFICABLE: la cotización id=% solo admite cambios en valor propuesto, condiciones y vencimiento. RF-COT 5.4.',
                    OLD.id_cotizacion USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    # --- Valoración por costo y deterioros (RF-88) -----------------------------------------------
    op.execute("ALTER TABLE modulo6.valoraciones_por_costos ADD COLUMN vida_util_meses integer, "
               "ALTER COLUMN fecha_marcacion SET DEFAULT now()")
    op.execute("ALTER TABLE modulo6.deterorios_activos RENAME TO deterioros_activos")
    op.execute("ALTER TABLE modulo6.deterioros_activos RENAME COLUMN id_deterorio_activo TO id_deterioro_activo")
    op.execute("ALTER TABLE modulo6.deterioros_activos RENAME COLUMN id_valoracio_costo TO id_valoracion_por_costo")
    op.execute("ALTER TABLE modulo6.deterioros_activos ALTER COLUMN fecha_registro SET DEFAULT now()")
    op.execute("ALTER SEQUENCE IF EXISTS modulo6.deterorios_activos_id_deterorio_activo_seq "
               "RENAME TO deterioros_activos_id_deterioro_activo_seq")

    # --- Cierre, estado de resultados e informe (RF-87, RF-93, RF-92) ---------------------------
    op.execute("""
        ALTER TABLE modulo6.ejecuciones_cierre_periodo
            ADD COLUMN json_precios_congelados jsonb,
            ADD COLUMN es_incluir_activos_sin_precio boolean NOT NULL DEFAULT false
    """)
    op.execute("""
        ALTER TABLE modulo6.estados_resultados_periodo
            ADD COLUMN total_ingresos numeric(18,4),
            ADD COLUMN total_gastos numeric(18,4),
            ADD COLUMN json_componentes jsonb,
            ADD COLUMN json_filtros jsonb,
            ADD COLUMN version integer NOT NULL DEFAULT 1,
            ADD COLUMN id_usuario integer,
            ADD COLUMN id_usuario_aprobador integer,
            ADD COLUMN fecha_aprobacion timestamptz,
            ADD CONSTRAINT estados_resultados_periodo_id_usuario_fkey FOREIGN KEY (id_usuario)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT estados_resultados_periodo_id_usuario_aprobador_fkey FOREIGN KEY (id_usuario_aprobador)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_23_inmutabilidad_estado_resultados()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_mutables text[] := ARRAY['estado', 'id_usuario_aprobador', 'fecha_aprobacion'];
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION '[TGR-M06-23] El estado de resultados id=% no puede eliminarse. RF-93 R5.',
                    OLD.id_estado USING ERRCODE = 'P0001';
            END IF;
            IF OLD.estado = 'GENERADO' AND NEW.estado = 'APROBADO'
               AND (to_jsonb(NEW) - v_mutables) = (to_jsonb(OLD) - v_mutables) THEN
                RETURN NEW;
            END IF;
            IF OLD.estado IN ('GENERADO', 'APROBADO') THEN
                RAISE EXCEPTION '[TGR-M06-23] El estado de resultados id=% tiene estado % y es inmutable. RF-93 R5.',
                    OLD.id_estado, OLD.estado USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_24_consistencia_resultado_neto()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_calculado numeric(18,4);
        BEGIN
            IF NEW.total_ingresos IS NOT NULL AND NEW.total_gastos IS NOT NULL THEN
                v_calculado := NEW.total_ingresos - NEW.total_gastos;
            ELSE
                v_calculado := COALESCE(NEW.total_ingresos_transformacion, 0) + COALESCE(NEW.total_ingresos_precio_mercado, 0)
                    + COALESCE(NEW.total_ingresos_cosecha, 0) - COALESCE(NEW.total_gastos_mantenimiento, 0)
                    - COALESCE(NEW.total_bajas_deterioro, 0);
            END IF;
            IF abs(NEW.resultado_neto - v_calculado) > 0.01 THEN
                RAISE EXCEPTION '[TGR-M06-24] ERROR_CONCILIACION: resultado_neto=% no coincide con ingresos - gastos = %. RF-93 R2.',
                    NEW.resultado_neto, v_calculado USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        ALTER TABLE modulo6.informes_revelacion_nic41
            ADD COLUMN razon_rechazo text,
            ADD COLUMN id_usuario_solicitante integer,
            ADD COLUMN fecha_generacion timestamptz NOT NULL DEFAULT now(),
            ADD CONSTRAINT informes_revelacion_nic41_id_usuario_solicitante_fkey FOREIGN KEY (id_usuario_solicitante)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT uq_informe_revelacion_nic41_periodo_version
                UNIQUE (id_periodo_contable, version_informe)
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_25_inmutabilidad_informe_revelacion()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION '[TGR-M06-25] El informe de revelaciones id=% no puede eliminarse. RF-92 R5.',
                    OLD.id_informe USING ERRCODE = 'P0001';
            END IF;
            -- Al aprobar una versión la anterior pasa a ARCHIVADO (RF-92 R4): única transición permitida.
            IF OLD.estado = 'APROBADO' AND NEW.estado = 'ARCHIVADO'
               AND (to_jsonb(NEW) - 'estado') = (to_jsonb(OLD) - 'estado') THEN
                RETURN NEW;
            END IF;
            IF OLD.estado IN ('APROBADO', 'ARCHIVADO', 'RECHAZADO') THEN
                RAISE EXCEPTION '[TGR-M06-25] El informe de revelaciones id=% tiene estado % y es inmutable. RF-92 R5.',
                    OLD.id_informe, OLD.estado USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    # --- Líneas de asiento NIC 41 (RF-86 v2.0) y comprobante (RF-87 v1.1) -----------------------
    op.execute("""
        CREATE TABLE modulo6.comprobantes_nic41 (
            id_comprobante_nic41 serial NOT NULL,
            codigo varchar(80) NOT NULL,
            id_periodo_contable integer NOT NULL,
            id_cierre integer NOT NULL,
            numero_id_tributaria varchar(15) NOT NULL,
            tipo_hecho modulo6.enum_linea_asiento_nic41_tipo_hecho NOT NULL,
            id_especie integer NOT NULL,
            fecha_comprobante date NOT NULL,
            json_lineas jsonb NOT NULL,
            valor_total numeric(18,2) NOT NULL,
            hash_integridad varchar(64) NOT NULL,
            fecha_creacion timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT comprobantes_nic41_pkey PRIMARY KEY (id_comprobante_nic41),
            CONSTRAINT uq_comprobante_nic41_codigo UNIQUE (codigo),
            CONSTRAINT comprobantes_nic41_id_periodo_contable_fkey FOREIGN KEY (id_periodo_contable)
                REFERENCES modulo6.periodos_contables (id_periodo_contable) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT comprobantes_nic41_id_cierre_fkey FOREIGN KEY (id_cierre)
                REFERENCES modulo6.ejecuciones_cierre_periodo (id_cierre) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT comprobantes_nic41_id_especie_fkey FOREIGN KEY (id_especie)
                REFERENCES modulo9.especies (id_especie) ON DELETE RESTRICT ON UPDATE CASCADE
        )
    """)
    _conceder('comprobantes_nic41', 'id_comprobante_nic41')
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_bloquear_modificacion_comprobante_nic41()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'El comprobante NIC 41 id=% es inmutable (RF-87 v1.1).', OLD.id_comprobante_nic41
                USING ERRCODE = 'P0001';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_antes_modificar_comprobante_nic41 BEFORE UPDATE OR DELETE ON modulo6.comprobantes_nic41
            FOR EACH ROW EXECUTE FUNCTION modulo6.fn_bloquear_modificacion_comprobante_nic41()
    """)

    op.execute("""
        CREATE TABLE modulo6.lineas_asiento_nic41 (
            id_linea_asiento_nic41 serial NOT NULL,
            tipo_hecho modulo6.enum_linea_asiento_nic41_tipo_hecho NOT NULL,
            sentido modulo6.enum_linea_asiento_nic41_sentido NOT NULL,
            estado modulo6.enum_linea_asiento_nic41_estado NOT NULL DEFAULT 'PENDIENTE_CUENTA',
            estado_trazabilidad modulo6.enum_variaciones_valor_razonable_estado_trazabilidad NOT NULL DEFAULT 'VERIFICACION_PENDIENTE',
            tipo_evidencia varchar(30) NOT NULL,
            fecha_hecho date NOT NULL,
            id_periodo_contable integer NOT NULL,
            id_activo_biologico integer NOT NULL,
            id_especie integer NOT NULL,
            id_finca integer NOT NULL,
            numero_id_tributaria varchar(15) NOT NULL,
            subtipo_costo modulo6.enum_registros_costos_subtipo_costo,
            cuenta_debito varchar(20),
            cuenta_credito varchar(20),
            valor numeric(18,2) NOT NULL,
            tabla_origen varchar(60) NOT NULL,
            id_origen integer NOT NULL,
            es_estimacion boolean NOT NULL DEFAULT false,
            es_reverso boolean NOT NULL DEFAULT false,
            tipo_hecho_corregido modulo6.enum_linea_asiento_nic41_tipo_hecho,
            id_linea_corregida integer,
            id_comprobante_nic41 integer,
            justificacion text,
            id_usuario integer,
            fecha_creacion timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT lineas_asiento_nic41_pkey PRIMARY KEY (id_linea_asiento_nic41),
            CONSTRAINT ck_linea_asiento_nic41_valor_positivo CHECK (valor > 0),
            CONSTRAINT ck_linea_asiento_nic41_tipo_evidencia CHECK (tipo_evidencia IN
                ('IOT_DIRECTO', 'REGISTRO_MANUAL', 'VARIACION_PRECIO', 'EVENTO_SANITARIO', 'CIERRE_PERIODO')),
            CONSTRAINT ck_linea_asiento_nic41_ajuste CHECK (
                (tipo_hecho = 'AJUSTE_PERIODO_ANTERIOR') = (tipo_hecho_corregido IS NOT NULL)),
            CONSTRAINT ck_linea_asiento_nic41_cuentas CHECK (estado = 'PENDIENTE_CUENTA'
                OR (cuenta_debito IS NOT NULL AND cuenta_credito IS NOT NULL AND cuenta_debito <> cuenta_credito)),
            CONSTRAINT lineas_asiento_nic41_id_periodo_contable_fkey FOREIGN KEY (id_periodo_contable)
                REFERENCES modulo6.periodos_contables (id_periodo_contable) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT lineas_asiento_nic41_id_activo_biologico_fkey FOREIGN KEY (id_activo_biologico)
                REFERENCES modulo2.activos_biologicos (id_activo_biologico) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT lineas_asiento_nic41_id_especie_fkey FOREIGN KEY (id_especie)
                REFERENCES modulo9.especies (id_especie) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT lineas_asiento_nic41_id_finca_fkey FOREIGN KEY (id_finca)
                REFERENCES modulo9.fincas (id_finca) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT lineas_asiento_nic41_id_linea_corregida_fkey FOREIGN KEY (id_linea_corregida)
                REFERENCES modulo6.lineas_asiento_nic41 (id_linea_asiento_nic41) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT lineas_asiento_nic41_id_comprobante_nic41_fkey FOREIGN KEY (id_comprobante_nic41)
                REFERENCES modulo6.comprobantes_nic41 (id_comprobante_nic41) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT lineas_asiento_nic41_id_usuario_fkey FOREIGN KEY (id_usuario)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
        )
    """)
    op.execute("CREATE INDEX idx_linea_asiento_nic41_id_periodo_contable ON modulo6.lineas_asiento_nic41 (id_periodo_contable, estado)")
    op.execute("CREATE INDEX idx_linea_asiento_nic41_id_activo_biologico ON modulo6.lineas_asiento_nic41 (id_activo_biologico)")
    op.execute("CREATE INDEX idx_linea_asiento_nic41_origen ON modulo6.lineas_asiento_nic41 (tabla_origen, id_origen)")
    _conceder('lineas_asiento_nic41', 'id_linea_asiento_nic41')
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_proteger_linea_asiento_nic41()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_mutables text[] := ARRAY['estado', 'cuenta_debito', 'cuenta_credito', 'estado_trazabilidad',
                                       'id_comprobante_nic41', 'id_periodo_contable'];
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'La línea de asiento NIC 41 id=% no puede eliminarse (RF-86 v2.0).', OLD.id_linea_asiento_nic41
                    USING ERRCODE = 'P0001';
            END IF;
            IF (to_jsonb(NEW) - v_mutables) <> (to_jsonb(OLD) - v_mutables)
               OR (OLD.estado = 'REGISTRADA' AND (NEW.estado <> OLD.estado OR NEW.cuenta_debito <> OLD.cuenta_debito
                                                  OR NEW.cuenta_credito <> OLD.cuenta_credito))
               OR (OLD.id_comprobante_nic41 IS NOT NULL AND NEW.id_comprobante_nic41 IS DISTINCT FROM OLD.id_comprobante_nic41) THEN
                RAISE EXCEPTION 'La línea de asiento NIC 41 id=% es inmutable; corrija con una línea correctiva (RF-86 v2.0).',
                    OLD.id_linea_asiento_nic41 USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_antes_modificar_linea_asiento_nic41 BEFORE UPDATE OR DELETE ON modulo6.lineas_asiento_nic41
            FOR EACH ROW EXECUTE FUNCTION modulo6.fn_proteger_linea_asiento_nic41()
    """)
    op.execute("""
        CREATE TRIGGER trg_antes_escribir_linea_asiento_nic41_periodo BEFORE INSERT OR UPDATE ON modulo6.lineas_asiento_nic41
            FOR EACH ROW EXECUTE FUNCTION modulo6.fn_tgr_m06_09_periodo_cerrado_bloqueo()
    """)

    # --- Trazabilidad (RF-91): una verificación por línea ---------------------------------------
    op.execute("""
        ALTER TABLE modulo6.cadenas_trazabilidad_contable
            ADD COLUMN id_linea_asiento_nic41 integer,
            ADD COLUMN tipo_evidencia_origen varchar(30),
            ADD COLUMN json_eslabones jsonb,
            ADD CONSTRAINT cadenas_trazabilidad_contable_id_linea_asiento_nic41_fkey FOREIGN KEY (id_linea_asiento_nic41)
                REFERENCES modulo6.lineas_asiento_nic41 (id_linea_asiento_nic41) ON DELETE RESTRICT ON UPDATE CASCADE
    """)
    op.execute("CREATE INDEX idx_cadena_trazabilidad_contable_id_linea_asiento_nic41 "
               "ON modulo6.cadenas_trazabilidad_contable (id_linea_asiento_nic41)")

    # --- Procesamiento de eventos de M02 (RF-83/RF-85/baja), idempotente y con cola del cierre ---
    op.execute("""
        CREATE TABLE modulo6.procesamientos_eventos_m02 (
            id_procesamiento_evento_m02 serial NOT NULL,
            id_evento integer NOT NULL,
            resultado varchar(30) NOT NULL,
            detalle text,
            intentos integer NOT NULL DEFAULT 1,
            fecha_procesamiento timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT procesamientos_eventos_m02_pkey PRIMARY KEY (id_procesamiento_evento_m02),
            CONSTRAINT uq_procesamiento_evento_m02_id_evento UNIQUE (id_evento),
            CONSTRAINT ck_procesamiento_evento_m02_resultado CHECK (resultado IN
                ('PROCESADO', 'SIN_EFECTO', 'MEDICION_PENDIENTE', 'ENCOLADO_CIERRE', 'ERROR')),
            CONSTRAINT procesamientos_eventos_m02_id_evento_fkey FOREIGN KEY (id_evento)
                REFERENCES modulo2.eventos_activos (id_eventos) ON DELETE RESTRICT ON UPDATE CASCADE
        )
    """)
    _conceder('procesamientos_eventos_m02', 'id_procesamiento_evento_m02')

    # Tipos de evento de M01 para las notificaciones de M06 (RF-14), resueltos por nombre.
    op.execute("""
        INSERT INTO modulo1.tipos_eventos (nombre, accion)
        SELECT v.nombre, v.accion FROM (VALUES
            ('CIERRE_PERIODO_CONTABLE', 'Período contable cerrado (M06)'),
            ('ALERTA_FINANCIERA_NIC41', 'Alerta financiera NIC 41 (M06)')
        ) AS v(nombre, accion)
        WHERE NOT EXISTS (SELECT 1 FROM modulo1.tipos_eventos t WHERE t.nombre = v.nombre)
    """)

    _sembrar_rbac()


def _sembrar_rbac() -> None:
    filas = []
    for recurso, roles in _MATRIZ_PERMISOS.items():
        for id_rol, acciones in roles.items():
            prefijo, nombre_rol = _ROLES[id_rol]
            for id_accion in acciones:
                accion, verbo = _ACCIONES[id_accion]
                filas.append((recurso, f"{prefijo}_{accion}_{recurso}", f"{nombre_rol} {verbo} {recurso.replace('_', ' ')} (M06).",
                              id_rol, id_accion))
    recursos = "\n".join(
        f"""
            SELECT id_recurso INTO v_id FROM modulo1.recursos WHERE nombre_recurso = '{nombre}';
            IF v_id IS NULL THEN
                IF EXISTS (SELECT 1 FROM modulo1.recursos WHERE id_recurso = {id_fijo}) THEN
                    RAISE EXCEPTION 'M06: id_recurso={id_fijo} ya está en uso; reasignar el id fijo de {nombre}.';
                END IF;
                INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion) VALUES ({id_fijo}, '{nombre}', '{descripcion}');
            END IF;
            v_id := NULL;"""
        for id_fijo, nombre, descripcion in _RECURSOS
    )
    permisos = ",\n".join(
        f"('{nombre}', '{descripcion}', {id_rol}, (SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso = '{recurso}'), {id_accion}, TRUE)"
        for recurso, nombre, descripcion, id_rol, id_accion in filas
    )
    op.execute(f"""
        DO $$
        DECLARE
            v_id integer;
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            {recursos}
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            SELECT v.nombre, v.descripcion, v.id_rol, v.id_recurso, v.id_accion, v.es_activo
            FROM (VALUES {permisos}) AS v(nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            WHERE EXISTS (SELECT 1 FROM modulo1.roles r WHERE r.id_rol = v.id_rol)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END
        $$;
    """)


def downgrade() -> None:
    """Retira lo agregado. Los permisos ``admin_*`` y sus recursos quedan (los protege un trigger de M01);
    los valores nuevos de enum tampoco se pueden quitar en PostgreSQL."""
    nombres = ", ".join(f"'{n}'" for _, n, _ in _RECURSOS)
    op.execute(f"""
        DO $$
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            DELETE FROM modulo1.permisos p USING modulo1.recursos r
             WHERE p.id_recurso = r.id_recurso AND r.nombre_recurso IN ({nombres}) AND p.nombre NOT LIKE 'admin\\_%';
        END $$;
    """)
    op.execute("""
        DELETE FROM modulo1.tipos_eventos t WHERE t.nombre IN ('CIERRE_PERIODO_CONTABLE', 'ALERTA_FINANCIERA_NIC41')
           AND NOT EXISTS (SELECT 1 FROM modulo1.eventos e WHERE e.tipo_evento = t.id_tipo_evento)
    """)
    op.execute("DROP TABLE modulo6.procesamientos_eventos_m02")
    op.execute("ALTER TABLE modulo6.cadenas_trazabilidad_contable DROP COLUMN id_linea_asiento_nic41, "
               "DROP COLUMN tipo_evidencia_origen, DROP COLUMN json_eslabones")
    op.execute("DROP TABLE modulo6.lineas_asiento_nic41")
    op.execute("DROP FUNCTION modulo6.fn_proteger_linea_asiento_nic41()")
    op.execute("DROP TABLE modulo6.comprobantes_nic41")
    op.execute("DROP FUNCTION modulo6.fn_bloquear_modificacion_comprobante_nic41()")
    op.execute("ALTER TABLE modulo6.informes_revelacion_nic41 DROP COLUMN razon_rechazo, DROP COLUMN id_usuario_solicitante, "
               "DROP COLUMN fecha_generacion, DROP CONSTRAINT uq_informe_revelacion_nic41_periodo_version")
    op.execute("ALTER TABLE modulo6.estados_resultados_periodo DROP COLUMN total_ingresos, DROP COLUMN total_gastos, "
               "DROP COLUMN json_componentes, DROP COLUMN json_filtros, DROP COLUMN version, DROP COLUMN id_usuario, "
               "DROP COLUMN id_usuario_aprobador, DROP COLUMN fecha_aprobacion")
    op.execute("ALTER TABLE modulo6.ejecuciones_cierre_periodo DROP COLUMN json_precios_congelados, "
               "DROP COLUMN es_incluir_activos_sin_precio")
    op.execute("ALTER SEQUENCE IF EXISTS modulo6.deterioros_activos_id_deterioro_activo_seq "
               "RENAME TO deterorios_activos_id_deterorio_activo_seq")
    op.execute("ALTER TABLE modulo6.deterioros_activos RENAME COLUMN id_valoracion_por_costo TO id_valoracio_costo")
    op.execute("ALTER TABLE modulo6.deterioros_activos RENAME COLUMN id_deterioro_activo TO id_deterorio_activo")
    op.execute("ALTER TABLE modulo6.deterioros_activos RENAME TO deterorios_activos")
    op.execute("ALTER TABLE modulo6.valoraciones_por_costos DROP COLUMN vida_util_meses")
    op.execute("ALTER TABLE modulo6.cotizaciones DROP COLUMN estado_al_cierre, DROP COLUMN valor_razonable_referencia, "
               "DROP COLUMN version, DROP COLUMN fecha_actualizacion")
    op.execute("ALTER TABLE modulo6.recepciones_provisiones_m05 DROP COLUMN fecha_procesamiento, DROP COLUMN resultado_procesamiento")
    op.execute("DROP INDEX modulo6.uq_registro_costo_factura_id_activo_biologico")
    op.execute("DROP INDEX modulo6.idx_registro_costo_id_periodo_contable")
    op.execute("DROP INDEX modulo6.idx_registro_costo_id_activo_biologico")
    op.execute("""
        ALTER TABLE modulo6.registros_costos
            DROP CONSTRAINT ck_registro_costo_datos_proveedor, DROP CONSTRAINT ck_registro_costo_naturaleza_clasificada,
            DROP COLUMN origen_costo, DROP COLUMN vehiculo_contable, DROP COLUMN fecha_costo, DROP COLUMN id_origen_m05,
            DROP COLUMN tercero_nit, DROP COLUMN tercero_dv, DROP COLUMN tercero_razon_social, DROP COLUMN factura_prefijo,
            DROP COLUMN factura_numero, DROP COLUMN fecha_factura, DROP COLUMN fecha_vencimiento_factura,
            DROP COLUMN id_grupo_reparto, DROP COLUMN metodo_reparto, DROP COLUMN cuenta_debito, DROP COLUMN cuenta_credito,
            DROP COLUMN es_cuenta_manual, DROP COLUMN es_reverso, DROP COLUMN id_registro_costo_compensado
    """)
    op.execute("ALTER TABLE modulo6.reconocimientos_productos_agricolas DROP COLUMN id_medicion_posterior")
    op.execute("ALTER TABLE modulo6.reconocimientos_productos_agricolas "
               "RENAME COLUMN id_reconocimiento_producto_agricola TO id_reconocimiento_prodcutos_agricola")
    op.execute("ALTER TABLE modulo6.variaciones_valor_razonable DROP CONSTRAINT ck_variacion_valor_razonable_origen, "
               "DROP COLUMN id_precio_mercado, DROP COLUMN id_cierre")
    op.execute("DROP INDEX modulo6.idx_variacion_valor_razonable_id_periodo_contable")
    op.execute("DROP INDEX modulo6.idx_medicion_posterior_id_activo_biologico")
    op.execute("ALTER SEQUENCE IF EXISTS modulo6.mediciones_posteriores_id_medicion_posterior_seq "
               'RENAME TO "mediciones_posteriores_id_ medicion_posterior_seq"')
    op.execute('ALTER TABLE modulo6.mediciones_posteriores RENAME COLUMN id_medicion_posterior TO "id_ medicion_posterior"')
    op.execute("DROP INDEX modulo6.idx_calculo_valor_razonable_id_activo_biologico")
    op.execute("ALTER TABLE modulo6.calculos_valor_razonable DROP COLUMN magnitud, DROP COLUMN unidad_magnitud, "
               "DROP COLUMN precio_unitario, DROP COLUMN id_evento_magnitud, DROP COLUMN tiene_valor_estimado, "
               "DROP COLUMN json_metodo_costo")
    op.execute("DROP INDEX modulo6.uq_reconocimiento_inicial_id_activo_biologico_confirmado")
    op.execute("ALTER TABLE modulo6.reconocimientos_iniciales DROP CONSTRAINT ck_reconocimiento_inicial_fuente_valor, "
               "DROP COLUMN costo_adquisicion, DROP COLUMN origen_financiero, DROP COLUMN id_calculo_valor_razonable, "
               "DROP COLUMN id_valoracion_por_costo, DROP COLUMN es_apertura, DROP COLUMN id_usuario_reversion, "
               "DROP COLUMN fecha_reversion")
    op.execute("DROP INDEX modulo6.uq_parametro_costo_venta_id_especie_region_vigente")
    op.execute("DROP INDEX modulo6.idx_precio_mercado_id_especie_fecha_vigencia")
    op.execute("ALTER TABLE modulo6.precios_mercado DROP CONSTRAINT ck_precio_mercado_producto_metrica, "
               "DROP CONSTRAINT ck_precio_mercado_categoria_unica, DROP COLUMN id_metrica_produccion")
    op.execute("ALTER TABLE modulo6.precios_mercado RENAME COLUMN id_precio_corregido TO id_precio_coregido")
    op.execute("DROP INDEX modulo6.idx_auditoria_financiera_tipo_evento")
    op.execute("DROP INDEX modulo6.idx_auditoria_financiera_id_activo_biologico")
    op.execute("DROP INDEX modulo6.idx_auditoria_financiera_id_periodo_contable")
    op.execute("ALTER TABLE modulo6.auditorias_financieras DROP COLUMN tipo_evento, DROP COLUMN id_referencia, "
               "DROP COLUMN id_sistema, DROP COLUMN es_payload_truncado")
    op.execute("DROP INDEX modulo6.uq_periodo_contable_numero_id_tributaria_fecha_inicio")
    op.execute("ALTER TABLE modulo6.periodos_contables DROP COLUMN numero_id_tributaria")
    op.execute("DROP TABLE modulo6.asignaciones_cuentas_contables")
    op.execute("DROP TABLE modulo6.parametros_contables_especies")
    op.execute("DROP TABLE modulo6.configuraciones_contables")
    op.execute("""
        ALTER TABLE modulo9.fincas
            DROP CONSTRAINT ck_finca_titular_completo, DROP CONSTRAINT ck_finca_dv,
            DROP CONSTRAINT ck_finca_numero_id_tributaria, DROP CONSTRAINT ck_finca_tipo_id_tributaria,
            DROP COLUMN tipo_id_tributaria, DROP COLUMN numero_id_tributaria, DROP COLUMN dv, DROP COLUMN razon_social
    """)
    for tipo in ('enum_auditoria_financiera_tipo_evento', 'enum_registro_costo_metodo_reparto',
                 'enum_registro_costo_vehiculo_contable', 'enum_registro_costo_origen_costo',
                 'enum_linea_asiento_nic41_estado', 'enum_linea_asiento_nic41_sentido', 'enum_linea_asiento_nic41_tipo_hecho'):
        op.execute(f"DROP TYPE modulo6.{tipo}")
    # Las funciones de trigger reemplazadas (01, 05, 08, 09, 19, 23, 24, 25 y la de variación) quedan
    # con la versión nueva: son compatibles con el esquema anterior salvo 05 (PK renombrada), que se
    # restaura aquí.
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo6.fn_tgr_m06_05_inmutabilidad_medicion()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND OLD.estado = 'COMPLETADO') THEN
                RAISE EXCEPTION '[TGR-M06-05] La medición posterior id=% es inmutable.', OLD."id_ medicion_posterior"
                    USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
