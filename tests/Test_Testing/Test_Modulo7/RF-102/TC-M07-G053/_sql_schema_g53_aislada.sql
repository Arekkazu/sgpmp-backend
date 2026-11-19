-- Esquema mínimo aislado TC-M07-G053 (integridad + inmutabilidad).
-- DDL derivado de 94b14a6931d6_m07_integracion_aaef_rfc017.py (RF-102).
-- Incluye triggers UPDATE/DELETE/TRUNCATE. No es Alembic completo.

CREATE SCHEMA IF NOT EXISTS modulo1;
CREATE SCHEMA IF NOT EXISTS modulo7;

CREATE TABLE IF NOT EXISTS modulo1.usuarios (id_usuario integer PRIMARY KEY);
CREATE TABLE IF NOT EXISTS modulo7.clientes_externos (id_cliente_externo integer PRIMARY KEY);

DO $$ BEGIN
    CREATE TYPE modulo7.enum_evento_integracion_tipo_evento AS ENUM (
        'PAQUETE_AAEF_CONSULTADO', 'SOLICITUD_RECHAZADA', 'CREDENCIALES_EN_URL', 'RATE_LIMIT_EXCEDIDO',
        'VISTA_AAEF_GENERADA', 'PREPARACION_AAEF_FALLIDA',
        'TOKEN_CANAL_EMITIDO', 'TOKEN_CANAL_RECHAZADO', 'USUARIO_CREADO_M2M', 'USUARIO_ACTUALIZADO_M2M',
        'ESTADO_USUARIO_CAMBIADO_M2M',
        'CLIENTE_REGISTRADO', 'CLIENTE_EDITADO', 'CLIENTE_SUSPENDIDO', 'CLIENTE_REACTIVADO', 'CLIENTE_REVOCADO',
        'SECRETO_ROTADO',
        'CONTRATO_REGISTRADO', 'CONTRATO_ACTIVADO', 'CONTRATO_DEPRECADO', 'CONTRATO_INACTIVADO',
        'CONTRATO_ACTIVACION_BLOQUEADA', 'ANEXO_REGISTRADO', 'ANEXO_EN_REVISION', 'ANEXO_APROBADO',
        'ANEXO_VALIDACION_FALLIDA',
        'INTENTO_MODIFICACION_AUDITORIA', 'ACCESO_AUDITORIA_DENEGADO', 'REGISTRO_AUDITORIA_CORRUPTO'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE modulo7.enum_evento_integracion_severidad AS ENUM ('INFO', 'WARNING', 'ERROR', 'CRITICAL');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE modulo7.enum_evento_integracion_tipo_actor AS ENUM ('SISTEMA', 'CLIENTE_EXTERNO', 'USUARIO');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS modulo7.eventos_integracion (
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
);

CREATE OR REPLACE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '[TGR-M07-14] La auditoria de integracion es inmutable (RF-102 4.4).' USING ERRCODE = 'P0001';
END;
$$;

DROP TRIGGER IF EXISTS trg_antes_modificar_evento_integracion ON modulo7.eventos_integracion;
CREATE TRIGGER trg_antes_modificar_evento_integracion
    BEFORE UPDATE OR DELETE ON modulo7.eventos_integracion
    FOR EACH ROW EXECUTE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion();

DROP TRIGGER IF EXISTS trg_antes_truncar_evento_integracion ON modulo7.eventos_integracion;
CREATE TRIGGER trg_antes_truncar_evento_integracion
    BEFORE TRUNCATE ON modulo7.eventos_integracion
    FOR EACH STATEMENT EXECUTE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion();
