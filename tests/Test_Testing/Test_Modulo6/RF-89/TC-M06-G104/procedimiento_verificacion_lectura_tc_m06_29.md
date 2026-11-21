# Verificación de lectura de TC-M06-29 (RF-89 v1.2 — alcance delimitado)

Este procedimiento solo lee. No ejecuta el job diario, no genera notificaciones y no altera TEST.

Base: `https://api.inmero.co/api-sgpmp-test`. Cabeceras: `Authorization`, `Accept: application/json`, `X-Zona-Horaria: America/Bogota`.

**Criterios:** `criterios_tc_m06_29_rf89_v1_2.md`  
**Estado oficial:** `resultados/estado_oficial_G104.json` · `resultados/tercera_evaluacion/DICTAMEN_DEFINITIVO_TC_M06_29.md`

## Alcance de cierre (pasos 1–4)

### 1. Precios especie 544
`GET /finanzas/precios?id_especie=544` → precio **492** `VENCIDO`, venc. `2026-11-10`, sin otro aplicado.

### 2. Activo 1644
`GET /finanzas/activos/1644` → ACTIVO, especie 544; reconocimiento 533 a VR con precio 492.

### 3. Período 266 (contexto)
`GET /finanzas/periodos?numero_id_tributaria=900000104` → 266 `ABIERTO` si el catálogo no cambió.

### 4. Simulación (exclusión del precio vencido)
`GET /finanzas/activos/1644/simulacion` → `motivo=SIN_PRECIO`, `es_valido=false`, `precio`/`calculo` nulos.  
No exigir `SIN_PRECIO_VIGENTE`, `PRECIO_REFERENCIA_VENCIDO` ni RF-88 por vencimiento.

**Resultado esperado del alcance de cierre:** APROBADO si 1, 2 y 4 cumplen (evidencia ya existente en `resultados/tercera_evaluacion/`).

## Validación complementaria (no determina el cierre de TC-29)

### 5. Bandeja Contador (CA-8 / FA-5)
`GET /notificaciones` (sesión Contador, todas las páginas).  
Buscar aviso «venció sin reemplazo» / precio 492.  
**Estado actual:** pendiente — ver `resultados/tercera_evaluacion/VALIDACION_COMPLEMENTARIA_CA8_AVISO_DIARIO_PENDIENTE.md`.  
No ejecutar el job ni marcar leídas.
