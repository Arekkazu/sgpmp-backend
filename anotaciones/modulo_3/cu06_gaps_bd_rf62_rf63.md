# CU06 — Gaps de BD y RBAC (RF-62, RF-63)

## Estado de tablas modulo3

| Tabla | Estado |
|---|---|
| `telemetrias` (columnas `apto_para_ia`, `apto_para_nic41`) | ⚠️ Faltan 2 columnas → agregadas |
| `telemetria_calidad` | ⚠️ No existía → creada |
| `bitacora_auditoria_iot` | ⚠️ No existía → creada |

## DDL aplicado

Fecha: 2026-07-07

```sql
-- Columnas de aptitud en telemetrias
ALTER TABLE modulo3.telemetrias ADD COLUMN apto_para_ia    BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE modulo3.telemetrias ADD COLUMN apto_para_nic41 BOOLEAN NOT NULL DEFAULT false;

-- Tabla de calidad RF-62
CREATE TABLE modulo3.telemetria_calidad (
    id_evaluacion              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_telemetria              INTEGER NOT NULL REFERENCES modulo3.telemetrias(id_telemetria),
    id_sensor                  INTEGER NOT NULL,
    timestamp_evaluacion       TIMESTAMPTZ NOT NULL DEFAULT now(),
    indice_calidad             SMALLINT,
    clasificacion_calidad      VARCHAR(20) NOT NULL,
    apto_para_ia               BOOLEAN NOT NULL DEFAULT false,
    apto_para_nic41            BOOLEAN NOT NULL DEFAULT false,
    flags_detectados           JSONB NOT NULL DEFAULT '{}',
    version_limites_fisicos_aplicada VARCHAR(50),
    parametros_aplicados       JSONB NOT NULL DEFAULT '{}',
    parametros_calibracion_aplicados JSONB,
    estado_evaluacion          VARCHAR(10) NOT NULL DEFAULT 'VIGENTE',
    motivo_reevaluacion        TEXT,
    id_evaluacion_superada     UUID REFERENCES modulo3.telemetria_calidad(id_evaluacion),
    version_evaluacion         VARCHAR(100),
    fecha_creacion             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_telem_calidad_lectura ON modulo3.telemetria_calidad(id_telemetria);
CREATE INDEX idx_telem_calidad_sensor  ON modulo3.telemetria_calidad(id_sensor);
CREATE INDEX idx_telem_calidad_clasif  ON modulo3.telemetria_calidad(clasificacion_calidad);

-- Tabla de auditoría IoT RF-63
CREATE TABLE modulo3.bitacora_auditoria_iot (
    id_evento             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_usuario            INTEGER,
    nombre_usuario        VARCHAR(255),
    tipo_evento           VARCHAR(80) NOT NULL,
    modulo                VARCHAR(10) NOT NULL DEFAULT 'M03',
    descripcion           VARCHAR(500),
    resultado             VARCHAR(20) NOT NULL,
    direccion_ip          VARCHAR(45),
    user_agent            VARCHAR(500),
    id_sesion             UUID,
    fecha_hora            TIMESTAMPTZ NOT NULL,
    accion_detallada      JSONB,
    entidad_afectada_tipo VARCHAR(30),
    entidad_afectada_id   VARCHAR(100),
    severidad_log         VARCHAR(10) NOT NULL DEFAULT 'INFO',
    hash_integridad       VARCHAR(64) NOT NULL,
    clasificacion_registro VARCHAR(10) NOT NULL DEFAULT 'TECNICO',
    retencion_aplicable   SMALLINT NOT NULL DEFAULT 1,
    registro_incompleto   BOOLEAN NOT NULL DEFAULT false,
    componente_origen     VARCHAR(10),
    timestamp_registro    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_bitacora_iot_fecha      ON modulo3.bitacora_auditoria_iot(fecha_hora);
CREATE INDEX idx_bitacora_iot_componente ON modulo3.bitacora_auditoria_iot(componente_origen);
CREATE INDEX idx_bitacora_iot_tipo       ON modulo3.bitacora_auditoria_iot(tipo_evento);
CREATE INDEX idx_bitacora_iot_entidad    ON modulo3.bitacora_auditoria_iot(entidad_afectada_id);
CREATE INDEX idx_bitacora_iot_severidad  ON modulo3.bitacora_auditoria_iot(severidad_log);
```

## RBAC aplicado

```sql
INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial) VALUES
  (38, 'calidad_telemetria',    'Evaluación de calidad estadística de datos telemétricos (RF-62)', false),
  (39, 'bitacora_auditoria_iot','Bitácora de auditoría IoT con hash SHA-256 (RF-63)', false);

-- recurso 38: R todos; E solo admin+ing
INSERT INTO modulo1.permisos (nombre, id_rol, id_recurso, id_accion) VALUES
  ('admin_leer_calidad_telemetria',     1, 38, 2),
  ('admin_ejecutar_calidad_telemetria', 1, 38, 5),
  ('prod_leer_calidad_telemetria',      2, 38, 2),
  ('vet_leer_calidad_telemetria',       3, 38, 2),
  ('ing_leer_calidad_telemetria',       4, 38, 2),
  ('ing_ejecutar_calidad_telemetria',   4, 38, 5),
  ('cont_leer_calidad_telemetria',      5, 38, 2);

-- recurso 39: R admin+ing+cont; E admin+cont
INSERT INTO modulo1.permisos (nombre, id_rol, id_recurso, id_accion) VALUES
  ('admin_leer_bitacora_auditoria_iot',     1, 39, 2),
  ('admin_ejecutar_bitacora_auditoria_iot', 1, 39, 5),
  ('ing_leer_bitacora_auditoria_iot',       4, 39, 2),
  ('cont_leer_bitacora_auditoria_iot',      5, 39, 2),
  ('cont_ejecutar_bitacora_auditoria_iot',  5, 39, 5);
```

## Nota de diseño

- `bitacora_auditoria_iot` unifica el esquema base de RF-10 con la extensión IoT de RF-63 en una sola tabla del módulo M03.
- `componente_origen` (RF53–RF62) es campo interno: no se expone en respuestas ni exportaciones al usuario.
- Las evaluaciones en `telemetria_calidad` son inmutables: se marca `estado_evaluacion = SUPERADA` en lugar de eliminar o modificar (FA-08).
- FA-10 (buffer edge de auditoría offline) es responsabilidad de AIOT — no implementado en Dev.
