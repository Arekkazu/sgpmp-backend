# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-95..102 + RFC-017/019: modulo7 listo para la consulta AAEF de AgroFusion |
"""m07 aaef: modulo7 alineado a RFC-017/RFC-019 para la integración contable con AgroFusion

Revision ID: 94b14a6931d6
Revises: c4d81e6f2a95
Create Date: 2026-11-06

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

``modulo7`` vino en el baseline con el diseño previo a RFC-017 (API Key por consulta, envelope
persistido, webhooks) y sin uso (0 filas, sin código). Esta migración reutiliza lo que encaja y no
borra tablas, vistas ni triggers que ya no aplican (``documentos_generados_aaef``,
``metadatos_respuesta_aaef``, ``notificaciones_weebhook``...: quedan sin uso):

1. RF-101 v2.0: ``clientes_externos`` gana el identificador público (``client_id``) y la vigencia del
   token de canal; ``identificadores_apis`` pasa a guardar el hash del ``client_secret`` (su trigger
   ya garantiza una sola credencial activa, lo que da la rotación con historial); los canales
   habilitados y su límite por minuto van en ``canales_clientes_externos``.
2. RF-98 v1.1: los estados del contrato pasan a PENDIENTE → ACTIVO → DEPRECADO → INACTIVO (se
   renombran los valores del enum, así las vistas siguen compilando) y se agregan tipo de cambio,
   anexo, mappers, período de gracia y fechas de transición. Los triggers 03/04/05 se reescriben.
3. RF-AE02 v3.0: el anexo se aprueba antes de registrar el contrato (la FK obligatoria al contrato
   se vuelve opcional) y guarda la evidencia de la prueba de interoperabilidad.
4. RF-102 v1.1: ``eventos_integracion``, append-only con hash por registro. ``auditoria_peticiones``
   no sirve (FKs obligatorias a tablas sin uso) y queda quieta: la referencia ``modulo8``.
5. RBAC: 5 recursos de M07 (por nombre) y sus permisos; tipo de evento de M01 para las alertas.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '94b14a6931d6'
down_revision: Union[str, Sequence[str], None] = 'c4d81e6f2a95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')"

_ESTADOS_CONTRATO = (('BORRADOR', 'PENDIENTE'), ('EN_REVISION', 'ACTIVO'), ('APROBADO', 'DEPRECADO'),
                     ('OBSOLETO', 'INACTIVO'))

_TIPOS_EVENTO = (
    # Consulta contable (RF-95, RF-97, RF-AE01)
    'PAQUETE_AAEF_CONSULTADO', 'SOLICITUD_RECHAZADA', 'CREDENCIALES_EN_URL', 'RATE_LIMIT_EXCEDIDO',
    'VISTA_AAEF_GENERADA', 'PREPARACION_AAEF_FALLIDA',
    # Canal de identidad (RF-SSO02)
    'TOKEN_CANAL_EMITIDO', 'TOKEN_CANAL_RECHAZADO', 'USUARIO_CREADO_M2M', 'USUARIO_ACTUALIZADO_M2M',
    'ESTADO_USUARIO_CAMBIADO_M2M',
    # Clientes externos (RF-101)
    'CLIENTE_REGISTRADO', 'CLIENTE_EDITADO', 'CLIENTE_SUSPENDIDO', 'CLIENTE_REACTIVADO', 'CLIENTE_REVOCADO',
    'SECRETO_ROTADO',
    # Contratos y anexo (RF-98, RF-AE02)
    'CONTRATO_REGISTRADO', 'CONTRATO_ACTIVADO', 'CONTRATO_DEPRECADO', 'CONTRATO_INACTIVADO',
    'CONTRATO_ACTIVACION_BLOQUEADA', 'ANEXO_REGISTRADO', 'ANEXO_EN_REVISION', 'ANEXO_APROBADO',
    'ANEXO_VALIDACION_FALLIDA',
    # Seguridad de la propia auditoría (RF-102 FA-2, FA-3, FA-6)
    'INTENTO_MODIFICACION_AUDITORIA', 'ACCESO_AUDITORIA_DENEGADO', 'REGISTRO_AUDITORIA_CORRUPTO',
)

_RECURSOS = (
    ('exportacion_contable', 'Consulta contable AAEF de AgroFusion por titular (RF-95, RF-AE01)'),
    ('clientes_externos', 'Clientes externos de la integración y sus credenciales (RF-101)'),
    ('contratos_aaef', 'Versiones del contrato AAEF y anexo de mapeo (RF-98, RF-AE02)'),
    ('auditoria_integracion', 'Historial completo de la auditoría de integración (RF-102)'),
    ('auditoria_integracion_cierres', 'Auditoría de integración de períodos cerrados para el auditor externo (RF-102)'),
)

_ROLES = {1: ('admin', 'Administrador'), 5: ('cont', 'Contador'), 8: ('revfis', 'Revisor Fiscal')}
_ACCIONES = {1: ('crear', 'registra'), 2: ('leer', 'consulta'), 3: ('actualizar', 'actualiza'),
             4: ('desactivar', 'revoca'), 5: ('ejecutar', 'ejecuta')}
# recurso -> {id_rol: (acciones)}. En contratos_aaef, E es la aprobación interna del anexo (RF-AE02 5.9);
# en auditoria_integracion, E es la exportación (RF-102 CA-17).
_MATRIZ_PERMISOS = {
    'exportacion_contable': {5: (2,), 1: (2,)},
    'clientes_externos': {1: (1, 2, 3, 4)},
    'contratos_aaef': {1: (1, 2, 3), 5: (2, 5)},
    'auditoria_integracion': {1: (2, 5)},
    'auditoria_integracion_cierres': {8: (2,)},
}


def _por_rol(sentencia: str) -> None:
    """Ejecuta ``sentencia`` (con ``%I`` para el rol) por cada rol de la app que exista."""
    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                {sentencia}
            END LOOP;
        END $$;
    """)


def upgrade() -> None:
    op.execute("ALTER TYPE modulo7.enum_cliente_externo_tipo RENAME VALUE 'SISTEMA_INTERMEDIARIOS' TO 'SISTEMA_INTERMEDIARIO'")
    for anterior, nuevo in _ESTADOS_CONTRATO:
        op.execute(f"ALTER TYPE modulo7.enum_versiones_contrato_aaef_estado RENAME VALUE '{anterior}' TO '{nuevo}'")
    op.execute("CREATE TYPE modulo7.enum_canal_cliente_externo_canal AS ENUM ('IDENTIDAD_M2M', 'CONSULTA_AAEF')")
    op.execute("CREATE TYPE modulo7.enum_version_contrato_aaef_tipo_cambio AS ENUM ('MAJOR', 'MINOR')")
    tipos = ", ".join(f"'{t}'" for t in _TIPOS_EVENTO)
    op.execute(f"CREATE TYPE modulo7.enum_evento_integracion_tipo_evento AS ENUM ({tipos})")
    op.execute("CREATE TYPE modulo7.enum_evento_integracion_severidad AS ENUM ('INFO', 'WARNING', 'ERROR', 'CRITICAL')")
    op.execute("CREATE TYPE modulo7.enum_evento_integracion_tipo_actor AS ENUM ('SISTEMA', 'CLIENTE_EXTERNO', 'USUARIO')")

    # --- Clientes externos y credenciales (RF-101 v2.0) ---------------------------------------
    op.execute("UPDATE modulo7.clientes_externos SET tipo = 'SISTEMA_INTERMEDIARIO' WHERE tipo IS NULL")
    op.execute("UPDATE modulo7.clientes_externos SET estado = 'ACTIVO' WHERE estado IS NULL")
    op.execute("""
        ALTER TABLE modulo7.clientes_externos
            ALTER COLUMN tipo SET NOT NULL,
            ALTER COLUMN estado SET NOT NULL,
            ALTER COLUMN estado SET DEFAULT 'ACTIVO',
            ADD COLUMN identificador_publico varchar(64),
            ADD COLUMN ttl_token_canal_minutos smallint NOT NULL DEFAULT 15,
            ADD COLUMN fecha_actualizacion timestamptz NOT NULL DEFAULT now(),
            ADD CONSTRAINT uq_cliente_externo_identificador_publico UNIQUE (identificador_publico),
            ADD CONSTRAINT ck_cliente_externo_ttl_token_canal_minutos CHECK (ttl_token_canal_minutos BETWEEN 5 AND 60)
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM modulo7.clientes_externos) THEN
                ALTER TABLE modulo7.clientes_externos ALTER COLUMN identificador_publico SET NOT NULL;
            END IF;
        END $$;
    """)
    op.execute("COMMENT ON COLUMN modulo7.clientes_externos.identificador_publico IS "
               "'client_id que el cliente presenta en el endpoint de token del canal (RF-101 v2.0). Público.'")
    op.execute("COMMENT ON COLUMN modulo7.clientes_externos.ip_permitida IS "
               "'IP o red (CIDR) desde la que se acepta al cliente; NULL = sin restricción (RF-101 5.8).'")
    op.execute("ALTER TABLE modulo7.identificadores_apis RENAME COLUMN api_llave_encriptada TO hash_secreto")
    op.execute("COMMENT ON COLUMN modulo7.identificadores_apis.hash_secreto IS "
               "'Hash bcrypt (con sal) del client_secret. El secreto nunca se guarda (RF-101 5.1).'")

    op.execute("""
        CREATE TABLE modulo7.canales_clientes_externos (
            id_canal_cliente_externo serial NOT NULL,
            id_cliente_externo integer NOT NULL,
            canal modulo7.enum_canal_cliente_externo_canal NOT NULL,
            limite_por_minuto integer NOT NULL DEFAULT 60,
            fecha_creacion timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT canales_clientes_externos_pkey PRIMARY KEY (id_canal_cliente_externo),
            CONSTRAINT uq_canal_cliente_externo_id_cliente_externo_canal UNIQUE (id_cliente_externo, canal),
            CONSTRAINT ck_canal_cliente_externo_limite_por_minuto CHECK (limite_por_minuto > 0),
            CONSTRAINT canales_clientes_externos_id_cliente_externo_fkey FOREIGN KEY (id_cliente_externo)
                REFERENCES modulo7.clientes_externos (id_cliente_externo) ON DELETE CASCADE ON UPDATE CASCADE
        )
    """)
    op.execute("COMMENT ON TABLE modulo7.canales_clientes_externos IS "
               "'Canales habilitados por cliente externo y su límite de solicitudes por minuto (RF-101 v2.0).'")

    # --- Contratos AAEF (RF-98 v1.1) ------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS modulo7.uix_version_contrato_aprobado_activa")
    # La vigencia puede ser futura: el contrato se registra PENDIENTE y se activa al llegar la fecha (RF-98 Fase 2).
    op.execute("ALTER TABLE modulo7.versiones_contrato_aaef DROP CONSTRAINT chk_version_contrato_fecha_no_futura")
    op.execute("ALTER TABLE modulo7.versiones_contrato_aaef RENAME COLUMN fecha_comienzo TO fecha_vigencia")
    op.execute("""
        ALTER TABLE modulo7.versiones_contrato_aaef
            ALTER COLUMN estado SET DEFAULT 'PENDIENTE',
            ADD COLUMN tipo_cambio modulo7.enum_version_contrato_aaef_tipo_cambio NOT NULL DEFAULT 'MINOR',
            ADD COLUMN endpoint_asociado varchar(255) NOT NULL DEFAULT '/integracion/aaef/productores/{nit}',
            ADD COLUMN id_mapeo_anexo_aaef integer,
            ADD COLUMN json_mapeadores jsonb NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN periodo_gracia_dias smallint,
            ADD COLUMN fecha_activacion timestamptz,
            ADD COLUMN fecha_deprecacion timestamptz,
            ADD COLUMN fecha_inactivacion timestamptz,
            ADD CONSTRAINT versiones_contrato_aaef_id_mapeo_anexo_aaef_fkey FOREIGN KEY (id_mapeo_anexo_aaef)
                REFERENCES modulo7.mapeos_anexos_aaef (id_mapeo_anexo_aaef) ON DELETE RESTRICT ON UPDATE CASCADE,
            ADD CONSTRAINT ck_version_contrato_aaef_json_mapeadores CHECK (jsonb_typeof(json_mapeadores) = 'array'),
            ADD CONSTRAINT ck_version_contrato_aaef_periodo_gracia CHECK (
                periodo_gracia_dias >= 30 OR (tipo_cambio = 'MINOR' AND periodo_gracia_dias IS NULL))
    """)
    op.execute("ALTER TABLE modulo7.versiones_contrato_aaef ALTER COLUMN tipo_cambio DROP DEFAULT")
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo7.fn_tgr_m07_03_versiones_contrato_transicion_estado()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.estado = NEW.estado THEN
                RETURN NEW;
            END IF;
            -- Única secuencia válida: PENDIENTE → ACTIVO → DEPRECADO → INACTIVO (RF-98 5.1).
            IF (OLD.estado, NEW.estado) NOT IN (('PENDIENTE', 'ACTIVO'), ('ACTIVO', 'DEPRECADO'), ('DEPRECADO', 'INACTIVO')) THEN
                RAISE EXCEPTION '[TGR-M07-03] Transición no permitida del contrato %: % -> %. RF-98 5.1.',
                    OLD.contrato_version, OLD.estado, NEW.estado USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo7.fn_tgr_m07_04_versiones_contrato_limite_activas()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_count integer;
        BEGIN
            IF NOT (OLD.estado = 'PENDIENTE' AND NEW.estado = 'ACTIVO') THEN
                RETURN NEW;
            END IF;
            SELECT count(*) INTO v_count FROM modulo7.versiones_contrato_aaef
             WHERE estado IN ('ACTIVO', 'DEPRECADO') AND id_version_contrato_aaef <> NEW.id_version_contrato_aaef;
            IF v_count >= 2 THEN
                RAISE EXCEPTION '[TGR-M07-04] LIMITE_VERSIONES_EXCEDIDO: ya hay % versiones activas o deprecadas. RF-98 5.3.',
                    v_count USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo7.fn_tgr_m07_05_versiones_contrato_inmutable_activo()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_mutables text[] := ARRAY['estado', 'fecha_activacion', 'fecha_deprecacion', 'fecha_inactivacion'];
        BEGIN
            -- Fuera de PENDIENTE solo cambian el estado y sus fechas (RF-98 5.12).
            IF OLD.estado <> 'PENDIENTE' AND (to_jsonb(NEW) - v_mutables) <> (to_jsonb(OLD) - v_mutables) THEN
                RAISE EXCEPTION '[TGR-M07-05] MODIFICACION_NO_PERMITIDA: el contrato % está % y es inmutable. RF-98 5.12.',
                    OLD.contrato_version, OLD.estado USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)

    # --- Anexo de mapeo (RF-AE02 v3.0) ---------------------------------------------------------
    op.execute("""
        ALTER TABLE modulo7.mapeos_anexos_aaef
            ALTER COLUMN id_version_contrato_aaef DROP NOT NULL,
            ALTER COLUMN estado SET DEFAULT 'BORRADOR',
            ADD COLUMN json_evidencia jsonb
    """)
    op.execute("COMMENT ON COLUMN modulo7.mapeos_anexos_aaef.id_version_contrato_aaef IS "
               "'Diseño previo a RFC-017, sin uso: desde RF-98 v1.1 el contrato referencia al anexo.'")
    op.execute("COMMENT ON COLUMN modulo7.mapeos_anexos_aaef.json_evidencia IS "
               "'Evidencia de la prueba de interoperabilidad (ExchangeId, ACK de SIGCON, observaciones). RF-AE02 5.11.'")

    # --- Auditoría de integración (RF-102 v1.1) -------------------------------------------------
    op.execute("""
        CREATE TABLE modulo7.eventos_integracion (
            id_evento_integracion uuid NOT NULL,
            tipo_evento modulo7.enum_evento_integracion_tipo_evento NOT NULL,
            severidad modulo7.enum_evento_integracion_severidad NOT NULL,
            tipo_actor modulo7.enum_evento_integracion_tipo_actor NOT NULL,
            modulo varchar(10) NOT NULL DEFAULT 'M07',
            fecha_evento timestamptz NOT NULL,
            fecha_registro timestamptz NOT NULL,
            id_cliente_externo integer,
            id_usuario integer,
            id_solicitud uuid,
            endpoint varchar(255),
            metodo_http varchar(10),
            codigo_http smallint,
            codigo_resultado varchar(60),
            latencia_ms integer,
            ip_origen varchar(45),
            numero_id_tributaria varchar(15),
            fecha_desde date,
            fecha_hasta date,
            version_contrato varchar(20),
            hash_contenido varchar(64),
            id_intercambio varchar(80),
            tamano_payload_bytes bigint,
            json_detalle jsonb,
            hash_integridad varchar(64) NOT NULL,
            CONSTRAINT eventos_integracion_pkey PRIMARY KEY (id_evento_integracion),
            CONSTRAINT ck_evento_integracion_hash_integridad CHECK (hash_integridad ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_evento_integracion_hash_contenido CHECK (hash_contenido IS NULL OR hash_contenido ~ '^[0-9a-f]{64}$'),
            CONSTRAINT eventos_integracion_id_cliente_externo_fkey FOREIGN KEY (id_cliente_externo)
                REFERENCES modulo7.clientes_externos (id_cliente_externo) ON DELETE RESTRICT ON UPDATE CASCADE,
            CONSTRAINT eventos_integracion_id_usuario_fkey FOREIGN KEY (id_usuario)
                REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
        )
    """)
    op.execute("COMMENT ON TABLE modulo7.eventos_integracion IS "
               "'Auditoría append-only de M07 (RF-102): un registro por evento, hash SHA-256 por registro. "
               "Nunca guarda secretos, tokens ni el envelope (solo su hash y tamaño).'")
    op.execute("CREATE INDEX idx_evento_integracion_fecha_evento ON modulo7.eventos_integracion (fecha_evento DESC)")
    op.execute("CREATE INDEX idx_evento_integracion_tipo_evento ON modulo7.eventos_integracion (tipo_evento, fecha_evento DESC)")
    op.execute("CREATE INDEX idx_evento_integracion_id_cliente_externo ON modulo7.eventos_integracion (id_cliente_externo, fecha_evento DESC)")
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '[TGR-M07-14] La auditoría de integración es inmutable (RF-102 4.4).' USING ERRCODE = 'P0001';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_antes_modificar_evento_integracion BEFORE UPDATE OR DELETE ON modulo7.eventos_integracion
            FOR EACH ROW EXECUTE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion()
    """)
    op.execute("""
        CREATE TRIGGER trg_antes_truncar_evento_integracion BEFORE TRUNCATE ON modulo7.eventos_integracion
            FOR EACH STATEMENT EXECUTE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion()
    """)

    # --- Privilegios de la app -----------------------------------------------------------------
    _por_rol("EXECUTE format('GRANT USAGE ON SCHEMA modulo7 TO %I', r);")
    for tabla, secuencia in (
        ('clientes_externos', 'clientes_externos_id_cliente_externo_seq'),
        ('identificadores_apis', 'identificadores_apis_id_identificador_api_seq'),
        ('canales_clientes_externos', 'canales_clientes_externos_id_canal_cliente_externo_seq'),
        ('versiones_contrato_aaef', 'versiones_contrato_aaef_id_version_contrato_aaef_seq'),
        ('mapeos_anexos_aaef', 'mapeos_anexos_aaef_id_mapeo_anexo_aaef_seq'),
    ):
        _por_rol(f"EXECUTE format('GRANT SELECT, INSERT, UPDATE ON modulo7.{tabla} TO %I', r);"
                 f"EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE modulo7.{secuencia} TO %I', r);")
    _por_rol("EXECUTE format('GRANT DELETE ON modulo7.canales_clientes_externos TO %I', r);")
    _por_rol("EXECUTE format('GRANT SELECT, INSERT ON modulo7.eventos_integracion TO %I', r);")

    # Tipo de evento de M01 para las alertas al Administrador (RF-14), resuelto por nombre.
    op.execute("""
        INSERT INTO modulo1.tipos_eventos (nombre, accion)
        SELECT 'ALERTA_INTEGRACION_CONTABLE', 'Alerta de la integración contable (M07)'
        WHERE NOT EXISTS (SELECT 1 FROM modulo1.tipos_eventos WHERE nombre = 'ALERTA_INTEGRACION_CONTABLE')
    """)
    _sembrar_rbac()


def _sembrar_rbac() -> None:
    """Recursos por nombre (el id sale de max+1: la secuencia de recursos va atrasada respecto a los
    ids fijos de migraciones anteriores) y permisos ``{rol}_{accion}_{recurso}``."""
    recursos = "\n".join(
        f"""
            IF NOT EXISTS (SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = '{nombre}') THEN
                INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
                SELECT COALESCE(max(id_recurso), 0) + 1, '{nombre}', '{descripcion}' FROM modulo1.recursos;
            END IF;"""
        for nombre, descripcion in _RECURSOS
    )
    filas = []
    for recurso, roles in _MATRIZ_PERMISOS.items():
        for id_rol, acciones in roles.items():
            prefijo, nombre_rol = _ROLES[id_rol]
            for id_accion in acciones:
                accion, verbo = _ACCIONES[id_accion]
                filas.append(f"('{prefijo}_{accion}_{recurso}', '{nombre_rol} {verbo} {recurso.replace('_', ' ')} (M07).', "
                             f"{id_rol}, (SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso = '{recurso}'), "
                             f"{id_accion}, TRUE)")
    op.execute(f"""
        DO $$
        BEGIN
            PERFORM set_config('app.current_role', 'Administrador', true);
            PERFORM set_config('app.current_user_id', '1', true);
            {recursos}
            PERFORM setval('modulo1.recursos_id_recurso_seq', (SELECT max(id_recurso) FROM modulo1.recursos));
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            SELECT v.nombre, v.descripcion, v.id_rol, v.id_recurso, v.id_accion, v.es_activo
            FROM (VALUES {", ".join(filas)}) AS v(nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            WHERE EXISTS (SELECT 1 FROM modulo1.roles r WHERE r.id_rol = v.id_rol)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END
        $$;
    """)


def downgrade() -> None:
    """Retira lo agregado. Los permisos ``admin_*`` y sus recursos quedan (los protege un trigger de M01)."""
    nombres = ", ".join(f"'{n}'" for n, _ in _RECURSOS)
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
        DELETE FROM modulo1.tipos_eventos t WHERE t.nombre = 'ALERTA_INTEGRACION_CONTABLE'
           AND NOT EXISTS (SELECT 1 FROM modulo1.eventos e WHERE e.tipo_evento = t.id_tipo_evento)
    """)
    op.execute("DROP TABLE modulo7.eventos_integracion")
    op.execute("DROP FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion()")
    op.execute("ALTER TABLE modulo7.mapeos_anexos_aaef DROP COLUMN json_evidencia, ALTER COLUMN estado DROP DEFAULT")
    op.execute("""
        ALTER TABLE modulo7.versiones_contrato_aaef
            DROP CONSTRAINT ck_version_contrato_aaef_periodo_gracia, DROP CONSTRAINT ck_version_contrato_aaef_json_mapeadores,
            DROP CONSTRAINT versiones_contrato_aaef_id_mapeo_anexo_aaef_fkey,
            DROP COLUMN tipo_cambio, DROP COLUMN endpoint_asociado, DROP COLUMN id_mapeo_anexo_aaef,
            DROP COLUMN json_mapeadores, DROP COLUMN periodo_gracia_dias, DROP COLUMN fecha_activacion,
            DROP COLUMN fecha_deprecacion, DROP COLUMN fecha_inactivacion,
            ALTER COLUMN estado DROP DEFAULT
    """)
    op.execute("ALTER TABLE modulo7.versiones_contrato_aaef RENAME COLUMN fecha_vigencia TO fecha_comienzo")
    op.execute("ALTER TABLE modulo7.versiones_contrato_aaef ADD CONSTRAINT chk_version_contrato_fecha_no_futura "
               "CHECK (fecha_comienzo <= CURRENT_DATE) NOT VALID")
    op.execute("DROP TABLE modulo7.canales_clientes_externos")
    op.execute("ALTER TABLE modulo7.identificadores_apis RENAME COLUMN hash_secreto TO api_llave_encriptada")
    op.execute("""
        ALTER TABLE modulo7.clientes_externos
            DROP CONSTRAINT ck_cliente_externo_ttl_token_canal_minutos, DROP CONSTRAINT uq_cliente_externo_identificador_publico,
            DROP COLUMN identificador_publico, DROP COLUMN ttl_token_canal_minutos, DROP COLUMN fecha_actualizacion,
            ALTER COLUMN tipo DROP NOT NULL, ALTER COLUMN estado DROP NOT NULL, ALTER COLUMN estado DROP DEFAULT
    """)
    for tipo in ('enum_evento_integracion_tipo_actor', 'enum_evento_integracion_severidad',
                 'enum_evento_integracion_tipo_evento', 'enum_version_contrato_aaef_tipo_cambio',
                 'enum_canal_cliente_externo_canal'):
        op.execute(f"DROP TYPE modulo7.{tipo}")
    for anterior, nuevo in _ESTADOS_CONTRATO:
        op.execute(f"ALTER TYPE modulo7.enum_versiones_contrato_aaef_estado RENAME VALUE '{nuevo}' TO '{anterior}'")
    op.execute("ALTER TYPE modulo7.enum_cliente_externo_tipo RENAME VALUE 'SISTEMA_INTERMEDIARIO' TO 'SISTEMA_INTERMEDIARIOS'")
    # Triggers 03/04/05 con la semántica del baseline (los textos originales no se reproducen).
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo7.fn_tgr_m07_03_versiones_contrato_transicion_estado()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_orden text[] := ARRAY['BORRADOR', 'EN_REVISION', 'APROBADO', 'OBSOLETO'];
        BEGIN
            IF OLD.estado = NEW.estado THEN RETURN NEW; END IF;
            IF array_position(v_orden, NEW.estado::text) <> array_position(v_orden, OLD.estado::text) + 1 THEN
                RAISE EXCEPTION '[TGR-M07-03] Transición no permitida: % -> %.', OLD.estado, NEW.estado USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo7.fn_tgr_m07_04_versiones_contrato_limite_activas()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.estado::text IN ('APROBADO', 'OBSOLETO') AND OLD.estado::text NOT IN ('APROBADO', 'OBSOLETO')
               AND (SELECT count(*) FROM modulo7.versiones_contrato_aaef WHERE estado::text IN ('APROBADO', 'OBSOLETO')
                     AND id_version_contrato_aaef <> NEW.id_version_contrato_aaef) >= 2 THEN
                RAISE EXCEPTION '[TGR-M07-04] Límite de versiones simultáneas excedido.' USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo7.fn_tgr_m07_05_versiones_contrato_inmutable_activo()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.estado::text IN ('APROBADO', 'OBSOLETO') AND (NEW.contrato_version <> OLD.contrato_version
               OR NEW.fecha_comienzo <> OLD.fecha_comienzo OR NEW.descripcion IS DISTINCT FROM OLD.descripcion) THEN
                RAISE EXCEPTION '[TGR-M07-05] El contrato % es inmutable en estado %.', OLD.contrato_version, OLD.estado
                    USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE UNIQUE INDEX uix_version_contrato_aprobado_activa ON modulo7.versiones_contrato_aaef (estado)
            WHERE estado = 'APROBADO'::modulo7.enum_versiones_contrato_aaef_estado
    """)
