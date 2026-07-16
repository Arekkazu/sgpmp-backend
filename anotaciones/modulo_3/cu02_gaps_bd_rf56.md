# Gaps BD — M03 CU02: Procesar y enviar datos al motor de inferencia (RF-56)

## Contexto

CU02 cubre el flujo Dev de RF-56: consolidar el paquete multivariable a partir de
eventos Edge clasificados por AIOT (RF-55) y enviarlo al Motor de Inferencia M04.
Los pasos 1-6 (evaluación y clasificación en el nodo Edge) son responsabilidad del
equipo AIOT y no se implementan aquí.

Referencia de delimitación: `M03-SPLIT.md` §3 CU02.

---

## Gaps encontrados y DDL aplicado

### Gap 1 — `modulo3.paquetes_inferencia.severidad` usa enum incorrecto

**Problema:** La columna usaba `enum_bitacora_ingest_severidad` (INFO, EMERGENCY,
CRITICAL, WARNING), pero RF-56 recibe la severidad producida por RF-55 que es
LEVE/MODERADO/CRITICO (enum `enum_buffer_nivel_severidad`).

**Impacto:** Imposible almacenar los valores de severidad correctos de RF-55 sin
convertirlos, lo que haría la trazabilidad engañosa.

**Acción previa:** Se identificaron tres vistas que dependían de la columna
(`vw_m03_alerta_contextualizada`, `vw_m03_pipeline_inferencia`,
`vw_m03_02_buffer_sincronizacion`) y se dropearon con CASCADE. Las tres vistas
solo hacían `severidad::text`, por lo que su comportamiento no cambió tras recrearlas.

**Fix aplicado:**
```sql
DROP VIEW IF EXISTS modulo3.vw_m03_alerta_contextualizada CASCADE;
DROP VIEW IF EXISTS modulo3.vw_m03_pipeline_inferencia CASCADE;
DROP VIEW IF EXISTS modulo3.vw_m03_02_buffer_sincronizacion CASCADE;

ALTER TABLE modulo3.paquetes_inferencia
  ALTER COLUMN severidad TYPE modulo3.enum_buffer_nivel_severidad
  USING CASE severidad::text
    WHEN 'INFO'      THEN 'LEVE'::modulo3.enum_buffer_nivel_severidad
    WHEN 'WARNING'   THEN 'MODERADO'::modulo3.enum_buffer_nivel_severidad
    WHEN 'CRITICAL'  THEN 'CRITICO'::modulo3.enum_buffer_nivel_severidad
    WHEN 'EMERGENCY' THEN 'CRITICO'::modulo3.enum_buffer_nivel_severidad
    ELSE NULL
  END;

-- Recrear vistas (sin cambio de comportamiento; solo cast a text)
CREATE VIEW modulo3.vw_m03_02_buffer_sincronizacion AS ...;
CREATE VIEW modulo3.vw_m03_pipeline_inferencia AS ...;
CREATE VIEW modulo3.vw_m03_alerta_contextualizada AS ...;
```

La columna estaba vacía; la conversión fue trivial (sin pérdida de datos).

---

### Gap 2 — `modulo3.paquetes_inferencia.contexto_incomplento` typo (solo documentar)

**Problema:** El campo tiene un typo en BD: `contexto_incomplento` en lugar de
`contexto_incompleto`.

**Decisión:** No alterar el nombre en BD para no romper las vistas y consultas
existentes. El modelo ORM mapea la columna con el nombre exacto de BD. La entidad
de dominio usa el nombre correcto `contexto_incompleto` y el repository hace la
traducción explícita.

---

### Gap 3 — Campos `timestamp_captura` y `timestamp_procesamiento_edge` ausentes

**Problema:** RF-56 requiere trazabilidad de `timestamp_captura` y
`timestamp_procesamiento_edge` en el paquete, pero la tabla `paquetes_inferencia`
no tiene estas columnas.

**Decisión:** Almacenarlos en la columna `metadatos JSONB` ya existente.
El modelo ORM y el repository manejan esto transparentemente.

---

### Gap 4 — `modulo3.eventos_edge_computing.tipo_evento` enum no coincide con RF-55

**Problema:** La columna usa `enum_eventos_edge_computing_tipo_evento` con valores
de propósito general (ALERTA_GENERADA, DATOS_PROCESADOS, CALIBRACION, etc.), pero
RF-55 produce NORMAL/DESVIACION_SIMPLE/DESVIACION_COMPUESTA/ERROR_CONFIGURACION.

**Decisión:** Mapear en el repository sin modificar el enum de BD:
- NORMAL → DATOS_PROCESADOS
- DESVIACION_SIMPLE → ALERTA_GENERADA
- DESVIACION_COMPUESTA → ALERTA_GENERADA
- ERROR_CONFIGURACION → ERROR_PROCESAMIENTO

La clasificación RF-55 real se guarda en `metadatos['clasificacion_rf55']` y se
recupera en el `_a_entidad` del repository para preservar el valor exacto.

---

### Gap 5 — `modulo3.eventos_edge_computing.almacendado_buffer` typo

**Problema:** Typo en BD: `almacendado_buffer` en lugar de `almacenado_buffer`.

**Decisión:** No alterar. El modelo ORM usa el nombre exacto de BD con comentario.

---

### Gap 6 — Trigger `trg_rf55_01_crear_paquete_inferencia` usaba enum incorrecto

**Problema:** El trigger `modulo3.fn_crear_paquete_inferencia()` tenía una variable
`v_severidad_bitacora modulo3.enum_bitacora_ingest_severidad` y convertía severidad al
enum antiguo antes de insertar en `paquetes_inferencia.severidad`. Tras el fix del Gap 1
(la columna ahora es `enum_buffer_nivel_severidad`), el trigger fallaba con
`DatatypeMismatch` al dispararse.

**Causa secundaria:** El repository insertaba `enviado_backend=TRUE`, lo que activaba
el trigger en el INSERT y creaba una fila duplicada en `paquetes_inferencia` (el use case
`ConsolidarEnviarPaqueteUseCase` crea su propia fila con lógica de negocio completa).

**Fix aplicado:**
1. Redefinido `fn_crear_paquete_inferencia` para pasar `NEW.severidad` directamente
   (ambos lados usan ahora el mismo enum). Variable `v_severidad_bitacora` eliminada.
2. Repository cambia `enviado_backend=False` en el INSERT inicial. Semántica correcta:
   el evento llegó a M03 pero aún no fue enviado a M04. El trigger solo se activa si
   alguien hace UPDATE con `enviado_backend=TRUE` explícitamente.

---

### Gap 7 — RBAC

**El endpoint `POST /iot/eventos-edge` usa autenticación por dispositivo (`access_key`),
igual que CU01.** No se requiere JWT ni permisos en `modulo1.permisos`.
No se agregan recursos a `modulo1.recursos` en esta fase.
