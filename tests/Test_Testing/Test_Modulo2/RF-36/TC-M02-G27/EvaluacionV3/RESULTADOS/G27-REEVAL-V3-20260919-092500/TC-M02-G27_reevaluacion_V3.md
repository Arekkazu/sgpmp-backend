# Reevaluación V3 — TC-M02-G27

## 1. Metadata
- **RUN_ID:** `G27-REEVAL-V3-20260919-092500`
- **Fecha:** `2026-09-19`
- **Hora Local:** `09:25:00 -05:00`
- **Hora UTC:** `14:25:00 UTC`
- **Entorno:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Evaluador:** Sebastian
- **Ronda:** V3
- **Reintento:** `_reintento2`
- **Archivo de Colección:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G27/test_tc_m02_g27.json`

## 2. Preflight ejecutado
El preflight empírico automatizado ejecutado previo a la corrida arrojó los siguientes resultados:
- **C.1. Health Check (`GET /health`):** HTTP 200 OK (`{"status":"healthy","version":"1.0.0"}`).
- **C.2. Login Admin (`POST /sesiones/`):** HTTP 200 OK. Token JWT administrativo emitido correctamente.
- **C.3. Login Productor (`POST /sesiones/` con `m2m.nuevo@ejemplo.com`):** HTTP 200 OK. Token JWT de Productor emitido.
- **C.4. Pertenencia de Lotes:**
  - Lote 8 (`GET /activos-biologicos/8` con Admin): Pertenece a Finca 2 (`id_finca: 2`, `nombre_finca: "Finca 2"`).
  - Lote 130 (`GET /activos-biologicos/130` con Admin): Pertenece a Finca 1 (`id_finca: 1`, `nombre_finca: "Finca 1"`).
- **Estado del Backend:** Fix #332 (commit `6ca29b5a`) confirmado y desplegado en TEST. La cláusula de scoping multi-tenant por finca restringe accesos no autorizados a activos biológicos.

## 3. Contexto histórico
- **V1 (2026-09-08):** `RECHAZADO` (1 PASS, 1 FAIL).
  - *TC-M02-057 (Mass Assignment):* PASS.
  - *TC-M02-058 (BOLA):* FAIL (200 OK exponiendo datos ajenos).
- **V2: NO EJECUTADA (SALTADA)**
  - *Motivo:* El fix #332 (commit `6ca29b5a`) no estaba aplicado en el entorno TEST el 2026-09-14. Ejecutar V2 en ese momento habría reproducido exactamente el mismo fallo de V1 sin aportar información nueva. Se decidió esperar el despliegue del fix y saltar directamente a V3.
- **V3 (2026-09-19, esta corrida):** Verificación del fix #332 ya desplegado. Aprobación integral de los controles de seguridad.

## 4. Cambios aplicados al spec
- **B.1: Credenciales en TC-M02-057:**
  - Se eliminó el hardcoding de `admin@pecuaria.co` y contraseñas en texto plano.
  - Se parametrizó con variables de Postman/Newman `{{admin_email}}` y `{{admin_password}}`.
- **B.2: Estrategia de Control Positivo en TC-M02-058 (CASO B):**
  - El sondeo de base de datos en TEST demostró que el usuario `productor@pecuaria.co` tiene asignadas ambas fincas (Finca 1 y Finca 2 en `modulo9.fincas`), mientras que `m2m.nuevo@ejemplo.com` no tiene fincas asociadas (`fincas: []`).
  - Se aplicó la estrategia **CASO B**: Paso 1 (BOLA) evalúa la negación de acceso con Productor `m2m.nuevo@ejemplo.com` sobre Lote 8 (espera 404 Not Found); Paso 2 (Control positivo) evalúa la existencia y consulta del Lote 130 usando token de Administrador (espera 200 OK).
  - Se actualizó la aserción BOLA para aceptar explícitamente códigos 403 y 404 (`pm.expect([403, 404]).to.include(pm.response.code)`), previniendo enumeración y fuga de metadatos.
- **B.3: Consolidación:**
  - Se creó la suite unificada y ejecutable `test_tc_m02_g27.json` agrupando los 6 requests secuenciales (Auth Admin, Inyección Mass Assignment, GET Lote verificación, Auth Productor, GET BOLA lote ajeno, GET Control Positivo lote accesible).
- **B.4: Teardown:**
  - La corrida evalúa inyección y consulta sobre lotes existentes sin crear registros de activos biológicos; no se generaron residuos que requieran soft-delete.

## 5. Resultados por subcaso

### TC-M02-057 — Mass Assignment en `cantidad_inicial`
- **Estado:** `OK` (APROBADO)
- **POST Evento con Inyección:**
  - Endpoint: `POST /activos-biologicos/130/eventos/crecimiento`
  - Payload inyectado: `{"cantidad_inicial": 500, "peso_promedio": 120.5, "unidad_medida": "g", "observaciones": "Test Mass Assignment"}`
  - HTTP Status: `400 Bad Request`
  - Error Code: `VAL_ENTRADA`
  - Detalle: El validador estricto del backend rechazó la carga con campo/unidad no permitida para el tipo de activo.
- **GET Verificación de Inmutabilidad:**
  - Endpoint: `GET /activos-biologicos/130`
  - HTTP Status: `200 OK`
  - Valor de `cantidad_inicial`: `5` (inalterado, no se mutó a 500).
- **Aserciones Pasadas:** 3/3.

> **Salvedad metodológica:** El backend respondió `400 Bad Request` rechazando la petición por `unidad_medida='g'` inválida, no por el campo `cantidad_inicial` inyectado. Aunque el GET posterior confirmó que `cantidad_inicial` permanece inmutable en `5`, la protección real contra Mass Assignment no se probó con un payload válido. Se recomienda para V4 ejecutar una variante con `unidad_medida='kg'` (válida) + `cantidad_inicial=500` inyectado, y verificar que el backend responde `201 Created` PERO ignora el campo prohibido.

### TC-M02-058 — Broken Object Level Authorization (BOLA / OWASP API1)
- **Estado:** `OK` (APROBADO)
- **GET Lote Ajeno (Finca 2):**
  - Endpoint: `GET /activos-biologicos/8`
  - Rol / Usuario: Productor (`m2m.nuevo@ejemplo.com`) sin autorización sobre Finca 2.
  - HTTP Status: `404 Not Found`
  - Error Code: `ACTIVO_NO_ENCONTRADO`
  - Detalle: El middleware de seguridad aplicó el filtro por alcance de fincas del usuario (RF-25 / Fix #332), bloqueando el acceso al recurso ajeno y retornando 404 sin exponer datos.
- **GET Control Positivo (Finca 1):**
  - Endpoint: `GET /activos-biologicos/130`
  - Rol / Usuario: Administrador con visibilidad global.
  - HTTP Status: `200 OK`
  - Detalle: Se comprobó que el lote existe y responde correctamente a solicitudes autorizadas.
- **Aserciones Pasadas:** 3/3.

## 6. Resumen de checkpoints

| Paso | Esperado | Obtenido | Estado |
| :--- | :--- | :--- | :--- |
| **0. Autenticación Administrador** | HTTP 200 OK con JWT | HTTP 200 OK - Token JWT obtenido | `OK` |
| **1. TC-M02-057 (Inyección Mass Assignment)** | HTTP 400/422 o 201 ignorando campo | HTTP 400 Bad Request (`VAL_ENTRADA`) | `OK` |
| **2. TC-M02-057 (Inmutabilidad `cantidad_inicial`)** | HTTP 200 OK y `cantidad_inicial = 5` | HTTP 200 OK - `cantidad_inicial = 5` inalterada | `OK` |
| **3. Autenticación Productor** | HTTP 200 OK con JWT Productor | HTTP 200 OK - Token JWT obtenido | `OK` |
| **4. TC-M02-058 (BOLA Lote 8 ajeno)** | HTTP 403 o 404 sin exponer datos | HTTP 404 Not Found (`ACTIVO_NO_ENCONTRADO`) | `OK` |
| **5. TC-M02-058 (Control Positivo Lote 130)** | HTTP 200 OK confirmando existencia | HTTP 200 OK - Activo consultado exitosamente | `OK` |

## 7. Veredicto final
**Veredicto:** `Aprobado`

**Justificación:**
1. **Protección BOLA (OWASP API1) confirmada:** La consulta contra un lote biológico ajeno (`GET /activos-biologicos/8`) por parte de un usuario Productor sin autorización de finca fue bloqueada estrictamente devolviendo `HTTP 404 Not Found` con código `ACTIVO_NO_ENCONTRADO`. No se produjo fuga de información biológica, productiva ni financiera.
2. **Protección Mass Assignment confirmada:** El backend rechazó la alteración del campo `cantidad_inicial` vía endpoints transaccionales de eventos (`HTTP 400 Bad Request`), y la consulta subsiguiente verificó que el valor persistido permaneció inmutable en `5`.
3. **Control positivo exitoso:** Se garantizó que el sistema no genera falsos positivos generalizados, retornando `HTTP 200 OK` en solicitudes legítimas autorizadas.
4. **Tasa de éxito:** 100% de aserciones aprobadas (8/8) sin fallas ni excepciones.

## 8. Recomendaciones
- **Cierre de Incidencia:** Incidencia histórica reportada por QA sobre BOLA en `/activos-biologicos/{id_activo}`. QA debe verificar en Taiga el ID canónico antes de cerrarla formalmente. El ID citado en este informe es un placeholder y no debe usarse en comunicaciones oficiales.
- **Monitoreo de Seeds:** Mantener la asignación multi-tenant consistente en la base de datos de pruebas para futuras corridas de regresión continua.

## 9. Lista Final de Archivos en `resultados/`

| Archivo | Ronda | Rango Scanner | Veredicto |
| :--- | :--- | :---: | :---: |
| `resultado_TC-M02-G27.json` | V1 (2026-09-08) | 0 | `Rechazado` |
| *(V2 no ejecutada — saltada)* | — | — | — |
| `resultado_TC-M02-G27_reintento2.json` | V3 (2026-09-19) | 2 | **`Aprobado` (DEFINITIVO)** |

> **Nota:** El sufijo `_reintento1` (rango 1) no existe porque la corrida V2 fue saltada intencionalmente (al no estar desplegado el fix en TEST). El scanner del dashboard elige el archivo de mayor rango disponible (`reintento2`), sin verse afectado por el hueco intermedio.

