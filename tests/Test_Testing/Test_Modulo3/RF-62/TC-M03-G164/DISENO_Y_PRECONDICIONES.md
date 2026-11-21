# DISEÑO Y PRECONDICIONES — TC-M03-G164 (RF-62)

## 1. RESUMEN TÉCNICO Y ARQUITECTURA DEL CASO

* **Módulo:** Módulo 3 — Telemetría IoT
* **Requerimiento:** RF-62 (Evaluación de Calidad de Datos Telemétricos)
* **Caso de Prueba:** TC-M03-G164 (Consulta y filtrado de evaluaciones de calidad)
* **Endpoints:** `GET /iot/calidad`, `GET /iot/calidad/{id_telemetria}`
* **Colección Newman:** `test_tc_m03_g164.json`
* **Estándar de Salida:** Directorio `tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G164/` con reporte computable obligatorio en `resultados/resultado_TC-M03-G164.html`.

---

## 2. (a) MATRIZ DE SUBCASOS: EXPECTATIVA VS RF-62 VS EXPECTATIVA EFECTIVA

| Subcaso | Expectativa del Caso Original | Respaldo en RF-62 (Cita / Norma) | Expectativa Efectiva del Script |
| :--- | :--- | :--- | :--- |
| **TC-M03-301** | Listar evaluaciones sin filtros, validar paginación `{total, pagina, por_pagina, items[]}` y orden DESC por timestamp_evaluacion. Total coincide con DB y solo evaluaciones del tenant. | **RF-62 CA-15:** "La consulta de evaluaciones de calidad devuelve la lista paginada de evaluaciones ordenadas cronológicamente en forma descendente." | Status 200. Valida estructura paginada, defaults (1, 50), longitud igual a `min(50, total)`, orden no creciente por `timestamp_evaluacion` normalizado (M13). Total validado contra oráculo independiente de base de datos (`/test-control/query` y descarga de dataset completo). Todos los campos de CalidadEvaluacion presentes. Sonda tenant informativa (M12). |
| **TC-M03-302** | Consultar por `id_telemetria` y validar todos los campos de `CalidadEvaluacion` coherentes con clasificación. | **RF-62 Fase 6 & CA-15 / RNF-07:** "Cada evaluación almacena flags_detectados, versión de límites físicos, parámetros zootécnicos/estadísticos aplicados y parámetros de calibración." | Status 200. Aserciones C4 separadas de existencia de claves y valores no nulos referenciadas a RNF-07/CA-15 (M6). Coherencia estricta de aptitud (IA / NIC-41) e índice según clasificación. `id_evaluacion` e `id_telemetria` validados contra el oráculo del preflight. |
| **TC-M03-304** | Filtrar por `id_sensor` y validar aislamiento respecto a otros sensores; combinar con paginación. | **RF-62 CA-15:** "Permite filtrar por sensor evaluado." | Status 200 con sensor candidato descubierto en runtime (`sensor_candidato`). Valida que el 100% de items pertenecen al sensor, total igual al conteo del sensor en el oráculo, y no aparecen al consultar un segundo sensor distinto. Paginación combinada (`por_pagina=3`): pág 1 y 2 con longitudes correctas y total idéntico. Aserción de no repetidos por `id_evaluacion` condicionada por empates de timestamps (L5 / M12). |
| **TC-M03-305** | Filtrar por `clasificacion_calidad` (4 valores enum) y validar 422 ante valor inválido. | **RF-62 Fase 6:** "Clasificaciones permitidas: APTO, APTO_CON_RESERVA, NO_APTO, INDETERMINADA." | Status 200 para los 4 valores (`?clasificacion={val}`). Si el oráculo tiene $\ge 1$ item, exige longitud $\ge 1$ y total igual al oráculo; si tiene 0, exige array vacío, total 0 y registra omisión parcial (M10). Para valor inválido (`const_valor_invalido_enum`): aserción dual (4xx y 422). Sonda clasificacion informativa sin pm.test (M9). |
| **TC-M03-306** | Filtrar por rango `fecha_desde`/`fecha_hasta`, frontera `desde==hasta` y rechazo `desde>hasta`. | **RF-62 CA-15:** "Filtro temporal por rango de fechas de evaluación." | Status 200 con ventana de timestamps reales usando `compareTimestamps` (M13). Total de ventana y frontera exactas validados contra conteo de oráculo (M10). Caso con offset -05:00 equivalente. Para `desde>hasta`: aserción dual (4xx y 422). |
| **TC-M03-307** | Filtrar por `estado_evaluacion` (VIGENTE / SUPERADA). | **RF-62 Restricción 9 & Decisión D7 (RESUELTO):** "Las evaluaciones anteriores pasan a estado SUPERADA conservando su inmutabilidad." Literal oficial: `VIGENTE` (descartado `ACTIVA`). | Status 200 con `?estado_evaluacion=SUPERADA` (M2) y `?estado_evaluacion=VIGENTE`. Valida que motivo_reevaluacion no sea nulo ni vacío en items SUPERADA. Emite log `OBS-307: id_evaluacion_superada=<n> de <m> items SUPERADA`. Complemento estricto: `total(VIGENTE) + total(SUPERADA) == total_general` (M9). Sonda o prueba 422 con valor inválido (ej. `ACTIVA` como ejemplo inválido tras ser descartado). |
| **TC-M03-308** | Límite `por_pagina=200`, frontera `201` -> 422 y `pagina=0` -> 422 (OWASP API4). | **OWASP API4:2023 & RF-62 CA-15:** Protección de recursos; rechazo estricto previo al cómputo. | Status 200 con `por_pagina=200` con gating `total > 200` (omisión parcial si total $\le 200$). Rechazo dual de `201`, `pagina=0` y `por_pagina=0` (M10). Página mayor a la última retorna items vacíos y total intacto igual al oráculo (M10). Frontera mínima válida `por_pagina=1` verificada. |

---

## 3. (b) CORRECCIONES DE CRITERIO APLICADAS (C1 A C6)

* **C1 (Nomenclatura de Estado Vigente - Decisión D7 RESUELTO 2026-10-19):** El literal oficial confirmado por análisis es `VIGENTE` y el catálogo oficial es `{"VIGENTE", "SUPERADA"}` (RFC de aclaración de RF-62 en trámite). `ACTIVA` queda formalmente descartado. Se valida el estado `SUPERADA`, el estado `VIGENTE` y se comprueba contractualmente que `total(VIGENTE) + total(SUPERADA) == total_general`.
* **C2 (Rechazos 422 vs 400 y Aserciones Duales):** El código 422 proviene del caso y no de la implementación (que emite 400 `VAL_ENTRADA` vía `error_handlers.py`). Para no enmascarar errores de validación sin romper la suite, se emplean dos aserciones separadas: (a) status es 4xx (`within(400, 499)`), y (b) status == `status_validacion_esperado` (422).
* **C3 (Aislamiento por Tenant):** El RF-62 no exige aislamiento territorial por finca ni usuario en calidad telemétrica, y el router no lo implementa. Se ejecuta la consulta idéntica con Administrador, Productor e Ingeniero de Campo, y se registra el resultado comparativo en consola como `OBS-TENANT: admin=<a> productor=<b> ingeniero=<c>` sin aserción de falla.
* **C4 (RNF-07 y CA-15 en Metadatos):** Se crean aserciones diferenciadas para presencia de claves y valores no nulos en `version_evaluacion`, `version_limites_fisicos_aplicada`, `parametros_aplicados` y `parametros_calibracion_aplicados`. `indice_calidad == null` solo se acepta si `clasificacion_calidad == 'INDETERMINADA'`.
* **C5 (Alcance Estricto):** No se inventan pruebas para ID inexistente (404) ni IDs no numéricos, delegados a otros casos como TC-M03-303.
* **C6 (Observación Documental ID):** La especificación menciona `id_lectura` (UUID conceptual), mientras que el esquema PostgreSQL y OpenAPI implementan `id_telemetria` (entero secuencial).

---

## 4. (c) PRONÓSTICO DE RESULTADOS CON EL CÓDIGO ACTUAL

Para contrastar durante la ejecución efectiva en TEST:
1. **TC-M03-301, TC-M03-302:** **PASS (100%)**. La infraestructura y datos existentes en TEST satisfacen plenamente las precondiciones y esquemas.
2. **TC-M03-304 (Filtrado por Sensor y Paginación):** **PASS**. Si en el conjunto paginado existen timestamps idénticos (`empates > 0`), el script omite la aserción de no repetición y emite `console.log("OBS-DETERMINISMO: empates=<n>; sin criterio de desempate en el backend; la verificación de no repetidos entre páginas no es determinista")` según L5 / M12, garantizando que el caso no sea intermitente ni cuente como falla/skip.
3. **TC-M03-305 (Valor inválido):** **FAIL PROBABLE en aserción (a)**. `clasificacion` es un `str` libre sin enum en el router; la API responde `HTTP 200` con `total = 0` en lugar de rechazar con 4xx.
4. **TC-M03-306 (Fecha desde > hasta):** **FAIL PROBABLE en aserción (a)**. La API no valida la coherencia cronológica y responde `HTTP 200` con `total = 0`.
5. **TC-M03-307 (SUPERADA):** **OMITIDO (SKIP) en modo `existentes`** si no se han sembrado evaluaciones superadas (0 en TEST actualmente). **Falla en NW-98** si `skip_cuenta_como_falla = true` para alertar en el dashboard. En modo `sandbox` (S1) o `sql_dba` (Estrategia C): **PASS**, validando que `motivo_reevaluacion` no sea nulo ni vacío en filas SUPERADA y reportando `OBS-307: id_evaluacion_superada=<n> de <m> items SUPERADA`.
6. **TC-M03-308 (Límites 201, 0 y por_pagina 0):** **PASS en aserción (a) [es 400 sin campo items] y FAIL en aserción (b) [espera 422]**, evidenciando la discrepancia arquitectural de FastAPI/Pydantic en este repositorio.

---

## 5. (d) PRECONDICIONES DE DATOS Y COMPORTAMIENTO ANTE SU INCUMPLIMIENTO

| Subcaso | Precondición Requerida | Banderas / Gating | Comportamiento si no se cumple |
| :--- | :--- | :--- | :--- |
| **TC-M03-301** | $\ge 10$ evaluaciones totales | `PRE_301` (`total >= 10`) | Se salta el test (`return`), emite log `SKIP TC-M03-301: Menos de 10 evaluaciones` y se registra en `resumen_skips`. |
| **TC-M03-302** | $\ge 1$ lectura evaluada | `PRE_302` (`items.length > 0`) | Se salta el test, emite log `SKIP TC-M03-302: No hay id_telemetria candidato`. |
| **TC-M03-304** | 1 sensor con $\ge 5$ evaluaciones y un 2do sensor distinto | `PRE_304` (`candCount >= 5 && secondSensor != null`) | Se salta el test, emite log `SKIP TC-M03-304: No existe sensor con >= 5 o no hay segundo sensor`. |
| **TC-M03-305** | N/A | `PRE_305` (`true`) | Ejecuta siempre. Si una clasificación tiene 0 registros en el oráculo, valida array vacío y registra omisión parcial (M10). |
| **TC-M03-306** | $\ge 5$ timestamps distintos | `PRE_306` (`timestamps.length >= 5`) | Se salta el test, emite log `SKIP TC-M03-306: Menos de 5 timestamps disponibles`. |
| **TC-M03-307** | $\ge 1$ evaluación en estado `SUPERADA` | `PRE_307` (`superadaCount >= 1`) | Se salta el test de SUPERADA, emite log `SKIP TC-M03-307: Cero evaluaciones SUPERADA`. |
| **TC-M03-308** | N/A | `PRE_308` (`true`) | Ejecuta siempre. Si `total <= 200`, omite la validación de exactamente 200 items y registra omisión parcial (M10). |
| **NW-98 Cobertura** | 7/7 subcasos con precondición cumplida | Variable `skip_cuenta_como_falla` (default `true`) | Nombre dinámico `[COBERTURA] Subcasos con precondicion cumplida: <cumplidos>/7`. Falla ante cualquier omisión total o parcial (M11). |

---

## 6. (e) ESTRATEGIAS DE DATOS (A, B, C) Y VIABILIDAD V1–V4 TRAS K6, L7 Y M3

1. **Estrategia A (Datos Existentes - Predeterminada):**
   * Corre contra los datos de TEST sin mutar nada. Descarga el dataset completo (páginas 1 a 5) y construye el oráculo en cliente.
   * *Limitación:* TC-307 se omite si no hay registros `SUPERADA`.
2. **Estrategia B (Sandbox Dinámico - Modo `sandbox`):**
   * **S1 (SUPERADA):** En NW-02 invoca `POST /iot/calidad/reevaluar` seleccionando dinámicamente el **segundo sensor con más evaluaciones VIGENTE** del dataset completo (nunca el candidato de TC-304), con timestamps reales (`sensor_reevaluar_desde` y `sensor_reevaluar_hasta`) y `causa_documentada` generada con `run_id`. Si `modo_datos != "sandbox"`, el test anterior salta a NW-03 mediante `postman.setNextRequest("NW-03-PreflightB-Recalcular-Gating")` (M3). Aserciones: 200 con `evaluaciones_superadas >= 1` o 422 con código `SIN_EVALUACIONES_EN_RANGO` tratado como "ya superado". Presupuesto de tiempo de 150 s medido desde `tiempos_ejecucion.inicio`.
   * **S2 (Volumen e ingesta de telemetría dinámica): DESACTIVADA / NO IMPLEMENTADA.**
     * *Análisis de Viabilidad con Cifras:* El endpoint `POST /iot/telemetria` requiere 20 lecturas consecutivas ($N=20$) por sensor para estabilizar la ventana estadística y emitir clasificaciones distintas de `INDETERMINADA`.
     * Para alcanzar $> 200$ filas sembradas vía HTTP se necesitarían un mínimo de 205 peticiones secuenciales. A una latencia media medida de ~250 ms por request contra TEST, esto requeriría un tiempo neto de ~51.2 a ~75.0 segundos solo en tráfico de red, más el procesamiento síncrono del backend.
     * Aunque el timeout por inactividad de 180 s se reinicia en cada petición, la cadena de ejecución síncrona invoca `vincular_use_case` (RF-61) y `reclasificar_semaforo_use_case` (RF-17), generando sobrecarga acumulativa en TEST y riesgo de interferencia en el estado del semáforo.
     * Por tanto, para no saturar el entorno ni alargar innecesariamente la ejecución de la suite, S2 queda descartada para volumen masivo.
3. **Estrategia C (Script SQL por DBA - Modo `sql_dba`):**
   * Se delega la generación de volumen masivo ($>200$ filas) y clasificaciones zootécnicas variadas (`APTO`, `APTO_CON_RESERVA`, `NO_APTO`, `INDETERMINADA`) al script SQL [`seed_datos_tc_m03_g164.sql`](seed_datos_tc_m03_g164.sql) y su respectiva limpieza determinista [`cleanup_seed_tc_m03_g164.sql`](cleanup_seed_tc_m03_g164.sql).
   * **Marcador unificado:** Marcador en `metadatos->>'seed_id' = 'TC_M03_G164_SEED'` en `modulo3.telemetrias`. Deja `parametros_aplicados` limpio únicamente con los campos zootécnicos del modelo (`k`, `M`, `N`, `umbral_drift`).
   * **Timestamps escalonados:** Cada fila generada utiliza un offset de 1 segundo a partir de `now() - interval '30 days'` garantizando timestamps únicos y sin fechas literales fijas (M14).
   * **Seguridad:** Encabezado de advertencia "NO EJECUTAR SIN AUTORIZACIÓN DEL EQUIPO; CONTRADICE EL PRINCIPIO DE CERO CONTAMINACIÓN", `ROLLBACK` por defecto, `COMMIT` solo manual con variable explícita `\set confirmar_commit 1`, e idempotencia estricta abortando si ya existen filas sembradas (M14).

---

## 7. (f) INSTRUCCIONES DE EJECUCIÓN

1. **Definir variables de entorno en el host:**
   ```powershell
   $env:TEST_SANDBOX_SECRET = "<secreto_del_sandbox>"
   $env:TEST_ADMIN_PASSWORD = "<password_admin>"
   $env:TEST_PRODUCER_PASSWORD = "<password_productor>"
   $env:TEST_FIELD_ENGINEER_PASSWORD = "<password_ingeniero>"
   # Opcionales para sobreescribir correos:
   # $env:TEST_ADMIN_EMAIL = "administador.dev@gmail.com"
   # $env:TEST_PRODUCER_EMAIL = "productor@pecuaria.co"
   # $env:TEST_FIELD_ENGINEER_EMAIL = "ingeniero@pecuaria.co"
   ```
2. **Ejecutar el runner automatizado:**
   ```powershell
   .\tests\Test_Testing\Test_Modulo3\RF-62\TC-M03-G164\ejecutar_tc_m03_g164.ps1 -ModoDatos "existentes"
   ```
   *(El script calcula rutas relativas mediante `$PSScriptRoot`, ejecuta previamente `verificar_hardcode_tc_m03_g164.cjs`, aplica los flags de supresión de secretos en htmlextra, valida que el HTML se haya generado y escanea el HTML generado)*.
3. **Comando de verificación pre-commit del scanner (QA Dashboard):**
   ```bash
   python3 -c "import scanner as s; print([c for c in s.scan()['casos'] if c['tc_id']=='TC-M03-G164'])"
   ```

---

## 8. (g) RESULTADOS DE VERIFICACIONES DE CÓDIGO (V1 A V5), DECLARACIÓN K1, AUDITORÍA L2 Y HALLAZGO L8 / M16

### Declaración de Peticiones en Vivo (K1 / L1 / M17)
Desde la declaración previa de K1, se confirma de forma absoluta: **NINGUNA** petición adicional fue realizada contra el entorno TEST.

*(Reconciliación de auditoría histórica de peticiones en fase previa de diagnóstico - M17:)*
En la fase previa de diagnóstico se abrieron exactamente dos runs de sandbox:
1. `run_id = diag-test-run-001`: Consulta de inventario y prueba de lectura.
2. `run_id = diag-test-run-002`: Consulta `SELECT count(*)` vía `/test-control/query`.
**Confirmación:** Ambos runs fueron cerrados deterministamente con `DELETE /test-control/runs/{run_id}` obteniendo `HTTP 200 {"status": "Rollback exitoso"}`.
Los logins generaron eventos estándar de auditoría de sesiones en `modulo1.eventos`. Cero datos de negocio fueron mutados en la base de datos de TEST.

> [!WARNING]
> **Alerta de Seguridad (M7):** Durante fases tempranas previas a esta revisión, el hash SHA-256 del secreto del sandbox estuvo presente en texto plano dentro del script auxiliar de validación estática. Aunque fue eliminado por completo, se recomienda formalmente al equipo de infraestructura/seguridad **rotar el secreto de TEST (`TEST_SANDBOX_SECRET`)** para salvaguardar la higiene del entorno.

### Verificaciones V1 a V5
* **V1 (`POST /iot/calidad/reevaluar`):**
  * *Repetición:* Solo afecta filas con `estado_evaluacion = 'VIGENTE'`. Si todas ya son `SUPERADA`, lanza `BusinessRuleError('SIN_EVALUACIONES_EN_RANGO')` con HTTP 422.
  * *Filas nuevas:* Actualiza `estado_evaluacion = 'SUPERADA'` y asigna `motivo_reevaluacion` en las filas existentes ([`solicitar_reevaluacion_use_case.py:75-80`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/application/use_cases/calidad/solicitar_reevaluacion_use_case.py#L75-L80)). Retorna `evaluaciones_superadas = N` y `evaluaciones_creadas = 0`.
  * *Efectos externos:* Escribe en `modulo3.bitacora_auditoria_iot` (RF-63) en la misma transacción de PostgreSQL. No emite llamadas a FCM, SMTP, MQTT ni módulos externos.
  * *Regla CA-17:* Exige `causa_documentada` no vacía (validador de DTO min 10 caracteres y use case lanza `REEVALUACION_SIN_CAUSA`).
* **V2 (Ingesta de Telemetría):**
  * Ingesta evalúa síncronamente en [`telemetria_router.py:106`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/telemetria_router.py#L106). Requiere $N=20$ lecturas para salir de `INDETERMINADA`. Invoca `vincular_use_case` (RF-61) y `reclasificar_semaforo_use_case` (RF-17).
* **V3 (Sandbox):**
  * `MAX_CONCURRENT_RUNS = 5`, `IDLE_TIMEOUT_SECONDS = 180` (timer de inactividad que se renueva en cada petición). Formato de run_id en la colección generado mediante UUID v4 estándar.
* **V4 (`/test-control/query`):**
  * Formato exacto de respuesta confirmado en [`test_control_router.py:82`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/shared/rollback/presentation/test_control_router.py#L82): `{"data": [{"total": N}]}`.
* **V5 (RBAC y Cuentas):**
  * `POST /sesiones/` espera `correo_electronico` y `contrasena`, y responde `token` (access token JWT) confirmado en [`usuario_dto.py:26`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/identity_access/infrastructure/dto/usuario_dto.py#L26) y [`user_schema.py:32`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/identity_access/infrastructure/schema/user_schema.py#L32).

### Tabla de Auditoría de Literales K11 / L2 / M8

| Literal / Parámetro Usado | Clasificación | Justificación / Ubicación en Colección |
| :--- | :---: | :--- |
| `"APTO", "NO_APTO", "APTO_CON_RESERVA", "INDETERMINADA"` | **A** | Constantes de especificación RF-62 Fase 6 (`constantes_especificacion.clasificaciones`) |
| `"SUPERADA", "VIGENTE"` | **A** | Estados contractuales RF-62 Restricción 9 (`constantes_especificacion.estados`) |
| `80`, `40`, `79` | **A** | Umbrales zootécnicos del índice de calidad RF-62 (`constantes_especificacion.umbrales`) |
| `50`, `200`, `201`, `0`, `1`, `3` | **A** | Límites y fronteras de paginación RF-62 / OWASP API4 (`limites_paginacion`) |
| `200, 201, 204, 400, 401, 403, 404, 422, 500, 400, 499` | **A** | Códigos de estado HTTP y rangos de error cliente (`codigos_http`) |
| `10`, `5` | **A** | Precondiciones mínimas de datos del caso (`gating`) |
| `150` s | **A** | Presupuesto temporal de seguridad en sandbox (`presupuesto_tiempo_segundos`) |
| `"VALOR_NO_CATALOGADO_ENUM"` | **A** | Valor de prueba controlado para validación de enum en TC-M03-305 |
| `{{baseUrl}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{sandbox_secret}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{admin_email}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{admin_password}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{productor_email}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{productor_password}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{ingeniero_email}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{ingeniero_password}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{modo_datos}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{status_validacion_esperado}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{skip_cuenta_como_falla}}` | **B** | Variable de entorno o de colección inyectada vía CLI / preflight |
| `{{token_admin}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{token_productor}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{token_ingeniero}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{run_id}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights (UUID v4) |
| `{{sensor_candidato}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{sensor_segundo}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{sensor_reevaluar}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{sensor_reevaluar_desde}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{sensor_reevaluar_hasta}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{id_telemetria_candidato}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{id_evaluacion_candidato}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{fecha_desde_sample}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{fecha_hasta_sample}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{fecha_exacta_sample}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{total_inventario}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{total_sql_db}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| `{{oraculo_dataset}}` | **C** | Valor descubierto dinámicamente en runtime durante los preflights |
| *(Cualquier ID fijo, fecha tipo 20xx, total inventario 18/10, o credenciales planas)* | **D** | **TOTALMENTE ERRADICADOS (0 hallazgos)**. Verificado por `verificar_hardcode_tc_m03_g164.cjs` |

### Hallazgo M16: Defecto Arquitectural en Reevaluación (Módulo 3 / RF-62)
* **Texto Real del Requerimiento RF-62:**
  * **Restricción 9 (paso 3):** *"Se crean nuevas evaluaciones con los parámetros correctos y el campo motivo_reevaluacion."*
  * **Criterio de Aceptación CA-16(b):** *"Crear nuevas evaluaciones con los parámetros correctos y motivo_reevaluacion registrado."*
* **Comportamiento Real del Backend:**
  El endpoint `POST /iot/calidad/reevaluar` implementado en [`solicitar_reevaluacion_use_case.py:74-95`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/application/use_cases/calidad/solicitar_reevaluacion_use_case.py#L74-L95) únicamente ejecuta un `UPDATE` marcando las evaluaciones existentes como `SUPERADA` y asignando el motivo. Retorna `evaluaciones_superadas = N` y `evaluaciones_creadas = 0`.
* **Impacto:**
  1. No se generan nuevas evaluaciones con los parámetros corregidos.
  2. El sensor queda sin evaluación activa en el rango especificado.
  3. No se puede repetir la operación sobre el mismo rango debido a la guarda que lanza HTTP 422 `SIN_EVALUACIONES_EN_RANGO`.
* **Acción de QA:**
  Este hallazgo se documenta formalmente para el equipo de desarrollo del Módulo 3. En la suite TC-M03-G164, las aserciones de TC-M03-307 se ajustan para validar estrictamente la presencia y no vacuidad de `motivo_reevaluacion` en las filas SUPERADA sin esperar sucesoras no emitidas por el backend.

---

## 9. (h) DECISIONES ABIERTAS PARA EL EQUIPO

1. **Defecto de Validación en `clasificacion`:** En `calidad_router.py:52`, `clasificacion` está definido como `Optional[str] = Query(default=None)` en lugar de utilizar el Enum `ClasificacionCalidad`. Esto permite enviar cualquier texto arbitrario y la API responde `HTTP 200 OK` con `total = 0`. Se recomienda actualizar a Enum para que FastAPI rechace con 400/422.
2. **Falta de Validación de Rango de Fechas:** Cuando `fecha_desde > fecha_hasta`, el repositorio aplica la condición SQL `WHERE timestamp >= desde AND timestamp <= hasta`, retornando `HTTP 200 OK` con `total = 0`. Se recomienda incorporar un validador en el caso de uso que devuelva `HTTP 400 / 422`.
3. **Homologación de Códigos HTTP (400 vs 422):** Toda la validación de entrada del backend responde contractualmente `HTTP 400 VAL_ENTRADA` mediante el handler global [`error_handlers.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/shared/error_handlers.py). Se sugiere actualizar las fichas de casos de prueba para reflejar HTTP 400 en lugar de HTTP 422.
4. **Rotación del Secreto de Sandbox en TEST:** Conforme al hallazgo M7, se recomienda rotar el secreto en el archivo `.env.test` del servidor.
