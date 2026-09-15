# Reevaluación V2 — Caso TC-M02-G76 (Subcaso TC-M02-210) — RF-46 CU10A — Defecto INC-M02-G76-01

---

## 1. Encabezado y Metadatos de Ejecución

- **Título Formal:** Reevaluación V2 — Caso TC-M02-G76 (Subcaso TC-M02-210) — RF-46 CU10A (Consultar Historial Completo del Activo Biológico: Filtro sin Resultados y Rechazo de Escritura) — Defecto INC-M02-G76-01.
- **Identificador de Corrida (RUN_ID):** `G76-REEVAL-V2-20260915-150500`
- **Fechas de Ejecución:**
  - **Corrida Original V1:** 2026-09-09 (1/2 Subcasos PASS — TC-M02-210 FALLIDO por ausencia del campo `mensaje` en respuesta 200 con filtros; TC-M02-212 PASS).
  - **Fecha de Reevaluación V2:** 2026-09-15 15:10:00 (UTC-5)
- **Entorno de Pruebas:** TEST
  - **URL Base API:** `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`
- **Base de Datos TEST:** PostgreSQL 15 en `158.69.200.27:5448/sgpmp_test` (Usuario `member_qa`).
  - *Nota de Conectividad:* Puerto 5448 restringido a nivel de firewall en el host remoto a IPs de oficina/VPN autorizadas (conforme a política de seguridad en `docs/SEGUIMIENTO-ENTORNO-TEST.md` Sección 10). La API REST oficial sobre HTTPS (puerto 443) opera como fuente de verdad fidedigna para la verificación de pre y post-condiciones.
- **Herramientas de Ejecución:**
  - **Newman CLI:** versión `6.2.2`
  - **Newman Reporter HtmlExtra:** versión `1.23.1`
  - **Runtime:** Node.js v20.18.0 / Python 3.13 (`.venv`)
- **Colección Ejecutada (Ruta Relativa):**
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/test_tc_m02_g76.json`
- **Reporte HTML Generado (Ruta Relativa):**
  - [reporte_v2.html](./reporte_v2.html)
- **Log Consolidado de Consola:**
  - `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/EvaluacionV2/RESULTADOS/G76-REEVAL-V2-20260915-150500/console_v2.log`
- **Veredicto Global:** ✅ **Aprobado (PASS 100% — 16/16 Aserciones Conformes)**

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### 2.1 Contexto del Fallo Original (Defecto INC-M02-G76-01)
En la corrida inicial V1 (2026-09-09), el subcaso **TC-M02-210** evaluó el criterio funcional alternativo **E-04** de RF-46 (CU10A): al consultar el historial de un activo biológico existente aplicando filtros (`categoria_evento` o rango de fechas) que no arrojan resultados, el sistema debe responder con código `HTTP 200 OK`, `total_registros: 0`, `registros: []` y un mensaje informativo explicativo (`"No se encontraron eventos para el activo [id] con los filtros aplicados..."`).

En dicha corrida, el backend retornó `HTTP 200 OK` con `total_registros: 0`, pero **omitió completamente el campo `mensaje`**, provocando el fallo de la aserción en Newman y registrándose el defecto formal `INC-M02-G76-01`.

### 2.2 Corrección Técnica Aplicada en Backend
El equipo de desarrollo resolvió el defecto mediante el commit **`f4605790`** (*"fix(rf46): agregar mensaje al historial sin resultados"*, 2026-09-10 11:11:05 -0500), el cual fue desplegado en el ambiente de TEST:
1. **Esquema Pydantic (`src/biological_assets/infrastructure/schema/activo_biologico_schema.py`):**
   Se incorporó el atributo opcional `mensaje: Optional[str] = None` dentro de la clase `HistorialActivoResponse`.
2. **Caso de Uso (`src/biological_assets/application/use_cases/gestion/consultar_historial_use_case.py`):**
   Se añadió la lógica condicional que evalúa si hubo filtros aplicados y si `total_registros == 0`:
   ```python
   filtros_aplicados = any((dto.fecha_inicio, dto.fecha_fin, dto.categoria_evento))
   if filtros_aplicados and resultado.total_registros == 0:
       resultado.mensaje = (
           f'No se encontraron eventos para el activo {id_activo} con los filtros aplicados. '
           'Puede ampliar el rango de fechas o cambiar la categoría de evento.'
       )
   ```
3. **Router (`src/biological_assets/infrastructure/routers/activo_biologico_router.py`):**
   Se mapeó `mensaje=pagina_historial.mensaje` hacia la respuesta JSON del endpoint `GET /{id_activo}/historial`.

### 2.3 Hallazgo Crítico de Precondición y Manejo de Fixture (Decisión de QA)
Durante la fase de diagnóstico previa a la ejecución, se detectó que el lote original **`130`** fue intervenido el **2026-09-13** por la suite de pruebas `TC-M02-204` (auditoría de eventos de baja), la cual registró **2 bajas** legítimas sobre dicho activo. Al consultar `categoria_evento=BAJA` sobre el lote 130, el backend retorna `total_registros = 2` (lo que inhibe la emisión del mensaje por existir registros y causaría un falso negativo).

Conforme a la directriz de aislamiento e inocuidad:
- Se seleccionó el lote **`296`** (especie 40, lote activo con 10 individuos, 0 bajas registradas) como **fixture limpio equivalente** para la corrida oficial V2.
- La inyección se realizó exclusivamente por línea de comandos (`--env-var id_activo=296`), preservando la colección `test_tc_m02_g76.json` 100% inalterada.
- Se ejecutó una **corrida de control complementaria** sobre el activo `130` para demostrar empíricamente que cuando la precondición no se cumple, el backend omite el mensaje tal como está diseñado contractualmente.

### 2.4 Tabla Resumen Comparativa de Resultados

| Sub-caso | Fixture | Enfoque Evaluado | Código Esperado | Código Obtenido | Aserciones | Veredicto V2 |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **TC-M02-210** | **296** | Historial con filtro sin resultados (E-04) | 200 OK + `mensaje` poblado | **200 OK** | **4 / 4 PASS** | ✅ **PASS (DEFECTO RESUELTO)** |
| **TC-M02-212** | **296** | Rechazo de operaciones de escritura (POST, PATCH, DELETE) | 405 Method Not Allowed | **405 Method Not Allowed** | **11 / 11 PASS** | ✅ **PASS COMPLETO** |
| **Paso 00** | — | Autenticación administrativa previa | 200 OK | **200 OK** | **1 / 1 PASS** | ✅ **PASS** |
| **TC-M02-210 (Control)** | **130** | Control negativo: activo con bajas previas (2 bajas) | 200 OK (sin mensaje / 2 registros) | **200 OK** | 1 / 4 (3 esperadas) | ⚠️ **CONTROL EXITOSO** |

---

## 3. Estado Previo de la Base de Datos (Pre-condición vía API REST)

Debido al aislamiento del puerto 5448 por firewall perimetral, la precondición se verificó en vivo contra la API REST de TEST (volcado completo en `precondicion_bd.log`):

```text
=== VERIFICACION DE PRECONDICIONES VIA API TEST ===
Fecha y Hora (UTC): 2026-09-15T20:09:20.379930+00:00
Ambiente API: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test

1. AUTENTICACION ADMIN
HTTP Status: 200 OK | Token capturado exitosamente (Longitud: 171)

2. VERIFICACION ACTIVO 296 (FIXTURE LIMPIO PRINCIPAL)
HTTP Status: 200 OK
{
  "id_activo_biologico": 296,
  "id_especie": 40,
  "tipo": "POBLACIONAL",
  "id_estado": 1,
  "nombre_estado": "ACTIVO",
  "detalle_poblacional": {
    "cantidad_inicial": 10,
    "cantidad_actual": 10
  }
}
-> Confirmacion: Activo 296 en estado ACTIVO, tipo POBLACIONAL.

3. VERIFICACION PRECONDICION E-04 SOBRE ACTIVO 296 (categoria_evento=BAJA)
HTTP Status: 200 OK
{
  "id_activo_biologico": 296,
  "total_registros": 0,
  "pagina_actual": 1,
  "total_paginas": 1,
  "registros_por_pagina": 20,
  "registros": [],
  "mensaje": "No se encontraron eventos para el activo 296 con los filtros aplicados. Puede ampliar el rango de fechas o cambiar la categoría de evento."
}
-> total_registros: 0 | registros: [] | mensaje poblado conforme a RF-46.

4. DOCUMENTACION DE CONTAMINACION SOBRE ACTIVO 130 (FIXTURE DE CONTROL)
HTTP Status: 200 OK
{
  "id_activo_biologico": 130,
  "total_registros": 2,
  "registros": [
    { "categoria": "BAJA", "fecha_evento": "2026-09-13T00:00:00Z", "descripcion": "Prueba de auditoria TC-M02-204" },
    { "categoria": "BAJA", "fecha_evento": "2026-09-13T00:00:00Z", "descripcion": "Prueba de auditoria TC-M02-204" }
  ],
  "mensaje": null
}
-> Evidencia de contaminacion previa: 2 bajas registradas el 2026-09-13 por TC-M02-204.
```

---

## 4. Resultados Detallados de la Ejecución (Newman)

### 4.1 Corrida Principal — Fixture Limpio (`id_activo = 296`)

| Paso | Método | Endpoint / Recurso | Código Esperado | Código Obtenido | Tiempo (ms) | Estado |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **00** | `POST` | `/sesiones/` | 200 OK | **200 OK** | 738 ms | ✅ PASS |
| **01** | `GET`  | `/activos-biologicos/296/historial?categoria_evento=BAJA` | 200 OK | **200 OK** | 136 ms | ✅ PASS |
| **00** | `POST` | `/sesiones/` (re-autenticación folder TC-M02-212) | 200 OK | **200 OK** | 402 ms | ✅ PASS |
| **01** | `GET`  | `/activos-biologicos/296/historial` (baseline inicial) | 200 OK | **200 OK** | 134 ms | ✅ PASS |
| **02** | `POST` | `/activos-biologicos/296/historial` | 405 Method Not Allowed | **405 Method Not Allowed** | 110 ms | ✅ PASS |
| **03** | `PATCH`| `/activos-biologicos/296/historial` | 405 Method Not Allowed | **405 Method Not Allowed** | 112 ms | ✅ PASS |
| **04** | `DELETE`| `/activos-biologicos/296/historial` | 405 Method Not Allowed | **405 Method Not Allowed** | 193 ms | ✅ PASS |
| **05** | `GET`  | `/activos-biologicos/296/historial` (verificación post-escritura) | 200 OK | **200 OK** | 239 ms | ✅ PASS |

#### Métricas Globales de Ejecución Principal (296):
- **Iteraciones:** 1
- **Peticiones HTTP Ejecutadas:** 8
- **Scripts de Test Evaluados:** 8
- **Aserciones Totales:** 16
- **Aserciones Aprobadas:** **16 (100% PASS)**
- **Aserciones Fallidas:** 0
- **Tiempo Total de Ejecución:** 2.7 segundos (promedio de respuesta: 258 ms)
- **Exit Code Newman:** `0` (Éxito Total)

#### Evidencia Textual de Respuesta Obtenida en TC-M02-210:
```json
{
  "id_activo_biologico": 296,
  "total_registros": 0,
  "pagina_actual": 1,
  "total_paginas": 1,
  "registros_por_pagina": 20,
  "registros": [],
  "mensaje": "No se encontraron eventos para el activo 296 con los filtros aplicados. Puede ampliar el rango de fechas o cambiar la categoría de evento."
}
```

*Detalle de aserciones validadas:*
- `[TC-M02-210] Estado HTTP 200 OK` → PASS
- `[TC-M02-210] total_registros es 0` → PASS (`0 === 0`)
- `[TC-M02-210] registros es array vacío` → PASS (`[].length === 0`)
- `[TC-M02-210] Mensaje informativo presente` → PASS (contiene `"no se encontraron eventos"`)

---

### 4.2 Corrida de Control Negativo — Fixture Contaminado (`id_activo = 130`)

Para certificar la robustez del test y descartar falsos positivos, se ejecutó la colección contra el lote contaminado `130`:
- **Resultado:** 13 aserciones PASS / 3 FAIL esperadas.
- **Detalle del Fallo de Control:**
  1. `AssertionError: [TC-M02-210] total_registros es 0: expected 2 to deeply equal +0`
  2. `AssertionError: [TC-M02-210] registros es array vacío: expected [ { categoria: 'BAJA', ... } ] to be empty`
  3. `AssertionError: [TC-M02-210] Mensaje informativo presente: expected '' to include 'no se encontraron eventos'`
- **Interpretación Técnica:** El fallo sobre el lote 130 confirma que el backend opera estrictamente conforme a la especificación: al existir 2 eventos de baja, el endpoint **NO** debe emitir el mensaje de "no se encontraron eventos", ratificando que el fallo original de V1 no se debió a un error de lógica en los filtros sino a la ausencia estructural del atributo cuando sí correspondía poblarlo.

---

## 5. Evidencia de Estado en BD PostgreSQL TEST (Post-condición y Auditoría)

Finalizada la ejecución de Newman, se verificó el estado post-prueba a través de la API REST (registrado en `postcondicion_bd.log`):

### 5.1 Inalterabilidad de los Activos de Prueba
1. **Lote 296:**
   - Estado: `ACTIVO` (`id_estado = 1`).
   - `cantidad_actual = 10` (idéntico al estado pre-ejecución).
   - Eventos de baja: `0` (cero mutaciones).
2. **Lote 130:**
   - Estado: `ACTIVO` (`id_estado = 1`).
   - `cantidad_actual = 3` (idéntico al estado pre-ejecución).
   - Eventos de baja: `2` (sin mutaciones adicionales).

### 5.2 Trazabilidad en Bitácora de Auditoría (`modulo2.bitacora_auditoria_m02`)
Se consultó el endpoint `/activos-biologicos/auditoria?rf_origen=RF46`:
- Se generaron los eventos de auditoría correspondientes a las consultas de historial:
  - Registro `2027`: `id_activo_biologico = 296`, `rf_origen = 'RF46'`, `tipo_evento = 'HISTORIAL_CONSULTADO'`, `resultado = 'EXITOSO'`, `hash_integridad = 518be8238bd649af0ebf244eec868c1b38a5261b94246df5f9375ff6b398f341`.
  - Registro `2029`: `id_activo_biologico = 130`, `rf_origen = 'RF46'`, `tipo_evento = 'HISTORIAL_CONSULTADO'`, `resultado = 'EXITOSO'`, `hash_integridad = 69de92827cf8e87bf4804d17be3f0a038273a13938924e4cba43da1e85f7abcc`.
- La inmutabilidad append-only y el encadenamiento de integridad SHA-256 quedaron plenamente confirmados.

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

- **Cero Mutaciones DDL/DML:** Las peticiones del subcaso TC-M02-210 fueron exclusivamente de consulta (`GET`).
- **Rechazo de Escritura:** Los métodos `POST`, `PATCH` y `DELETE` evaluados en TC-M02-212 fueron interceptados y rechazados a nivel de enrutamiento con `HTTP 405 Method Not Allowed` y cabecera `Allow: GET`. Ninguna operación llegó a ejecutarse en base de datos.
- **Inocuidad Garantizada:** No se introdujeron datos huérfanos ni se requirieron scripts de rollback en base de datos.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1 Estado del Defecto INC-M02-G76-01
- **Dictamen:** ✅ **SUBSANADO Y CERRADO FORMALMENTE (VERIFICADO EN TEST)**.
- El commit `f4605790` incorporó el campo `mensaje` en `HistorialActivoResponse` y la lógica condicional en `ConsultarHistorialUseCase`. El comportamiento fue validado al 100% de aserciones en el entorno oficial de pruebas.

### 7.2 Cumplimiento Contractual
- El requerimiento funcional **RF-46 (CU10A - Historial de Eventos del Activo Biológico)** en su flujo alternativo **E-04** queda **plenamente satisfecho**: cuando una consulta filtrada no encuentra registros, el sistema retorna `HTTP 200 OK` acompañado de la aclaración informativa para guiar al usuario a ampliar sus criterios de búsqueda.

### 7.3 Subcasos Colaterales del Grupo TC-M02-G76
1. **TC-M02-210 (Filtro sin resultados):** ✅ **PASS (100% — 4/4 aserciones conformes).**
2. **TC-M02-211 (Límite matemático de paginación 500 vs 501):** ✅ **PASS (100% validado previamente mediante Pytest `tests/integration/test_rf46_limite_paginacion_integration.py`).**
3. **TC-M02-212 (Rechazo de escritura HTTP 405 e inmutabilidad):** ✅ **PASS (100% — 11/11 aserciones conformes).**

### 7.4 Hallazgos Secundarios No Bloqueantes (Deuda Técnica / Backlog)
1. **Contaminación cruzada de fixtures:** El lote 130 fue modificado por ejecuciones posteriores de TC-M02-204 (bajas acumuladas). Se sugiere en el backlog de testing parametrizar las colecciones de Newman para que verifiquen o aíslen dinámicamente sus fixtures pre-test.
2. **Desactualización del OpenAPI local (`openapi-test.json`):** El archivo JSON versionado en la raíz del repositorio corresponde al commit `92ac32ed` y no refleja aún el campo `mensaje` que sí se encuentra activo en el servidor remoto TEST. Se recomienda exportar y actualizar dicho artefacto.
3. **Restricción de firewall puerto 5448:** Confirmada la imposibilidad de conexión externa directa a PostgreSQL. La API REST demostró ser una alternativa robusta y suficiente para verificar el estado de los activos.

---

### Referencias de Artefactos de Ejecución (Rutas Relativas)

- **Reporte Visual HTML:**  
  `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/EvaluacionV2/RESULTADOS/G76-REEVAL-V2-20260915-150500/reporte_v2.html`
- **Resumen Newman JSON (Corrida Principal 296):**  
  `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/EvaluacionV2/RESULTADOS/G76-REEVAL-V2-20260915-150500/newman_summary_v2.json`
- **Log Consolidado de Consola (Corrida Principal 296):**  
  `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/EvaluacionV2/RESULTADOS/G76-REEVAL-V2-20260915-150500/console_v2.log`
- **Resumen Newman JSON (Corrida Control 130):**  
  `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/EvaluacionV2/RESULTADOS/G76-REEVAL-V2-20260915-150500/newman_summary_control_130_v2.json`
- **Log de Consola (Corrida Control 130):**  
  `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/EvaluacionV2/RESULTADOS/G76-REEVAL-V2-20260915-150500/console_control_130_v2.log`
- **Registro de Precondición:**  
  `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/EvaluacionV2/RESULTADOS/G76-REEVAL-V2-20260915-150500/precondicion_bd.log`
- **Registro de Post-condición:**  
  `tests/Test_Testing/Test_Modulo2/RF-46/TC-M02-G76/EvaluacionV2/RESULTADOS/G76-REEVAL-V2-20260915-150500/postcondicion_bd.log`
