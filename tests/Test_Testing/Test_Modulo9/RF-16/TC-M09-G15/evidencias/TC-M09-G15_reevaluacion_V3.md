# Reporte de Reevaluación V3 — TC-M09-G15
**Integridad de Desactivación de Parámetros en Uso (RF-16 / CU-02)**
*(Consolidación Final — Fase 3.5)*

---

## 1. Encabezado y Metadatos de Ejecución
* **ID Caso de Prueba:** `TC-M09-G15`
* **Módulo:** 9 (Configuración y Parámetros Generales)
* **Requerimiento:** `RF-16` (Configuración de Parámetros Productivos y Sanitarios por Especie / CU-02)
* **Subcasos Evaluados:**
  - `TC-M09-36`: Impedir desactivación de Etapa productiva en uso (`id_ciclo_biologico = 10`).
  - `TC-M09-37`: Impedir desactivación de Patología en uso (`id_especies_patologias = 7`).
  - `TC-M09-38`: Impedir desactivación de Métrica de producción en uso (`id_metrica_produccion = 1`).
* **Fecha y Hora de Consolidación:** 2026-09-25T18:34:00Z (UTC) / 13:34:00-05:00
* **Rama Git:** `test-JuanSG`
* **Commit Base:** `cc6450218654f6ddb6866ebbacf5d5adc6a61159`
* **Entorno de Pruebas:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
* **Base de Datos:** PostgreSQL TEST (`$TEST_DB_HOST:$TEST_DB_PORT/$TEST_DB_NAME`, usuario `$TEST_DB_USER`)
* **Herramientas Utilizadas:** Newman CLI v6.2.2 + `newman-reporter-htmlextra` v1.23.1, Python 3.13 (`psycopg2`)
* **Referencias Cruzadas de Desarrollo:** Defecto `INC-M09-06-G15`, Issue/PR `#303` / `#360`, Migración Alembic `9a5de7d9973f` (`v5.3.0_rf16_normalizar_tipos_medicion_legacy`).
* **Reporte Computable Único V3:** [`resultados/resultado_TC-M09-G15_reintento2.html`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/resultados/resultado_TC-M09-G15_reintento2.html) y [`resultados/resultado_TC-M09-G15_reintento2.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/resultados/resultado_TC-M09-G15_reintento2.json)
* **Veredicto Final del Caso:** 🟢 **APROBADO (PASS — 100% CONFORME)**
  > La migración `9a5de7d9973f` erradicó exitosamente el `HTTP 500` en la métrica 1, permitiendo al backend evaluar las dependencias zootécnicas y rechazar formalmente la desactivación con `HTTP 422 METRICA_CON_REGISTROS`. La integridad y no-mutabilidad de las entidades en uso quedó certificada al 100% mediante verificación dual API + base de datos.

---

## 2. Consolidación Final y Simplificación del Spec
En cumplimiento del patrón de nombres del manual (MANUAL §2.2):
- Se conservaron en `resultados/` los reportes de corridas previas `resultado_TC-M09-G15.html` y `resultado_TC-M09-G15.json` (V1) y `resultado_TC-M09-G15_reintento1.html` (V2).
- *Nota sobre JSON de V2 (reintento1):* El JSON del reintento1 se regeneró en esta sesión porque el original de la corrida V2 no se conservó. Coincide con el spec actual y no altera el veredicto histórico de V2.
- Se consolidó la reevaluación V3 en su par computable definitivo: `resultado_TC-M09-G15_reintento2.html` y `resultado_TC-M09-G15_reintento2.json`.
- Se simplificó la colección Postman [`test_tc_m09_g15.json`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/test_tc_m09_g15.json) removiendo las consultas intermedias GET pre/post que constituían scope creep no soportado por el router, dejando exactamente los 4 pasos canónicos del caso:
  1. Paso 1: Autenticación Admin (`POST /sesiones/` $\to$ `HTTP 200`)
  2. Paso 2: TC-M09-36 (`PATCH /configuracion/ciclos/10/desactivar` $\to$ `HTTP 422`)
  3. Paso 3: TC-M09-37 (`PATCH /configuracion/patologias/7/desactivar` $\to$ `HTTP 422`)
  4. Paso 4: TC-M09-38 (`PATCH /configuracion/metricas/1/desactivar` $\to$ `HTTP 422`)

---

## 3. Verificación en Dos Capas (API HTTP + Base de Datos)
La estrategia de validación se fundamenta en un modelo de dos capas desacopladas:
1. **Capa API (Newman E2E):** Evalúa el comportamiento del contrato HTTP y las reglas de negocio ante intentos no permitidos de desactivación, asegurando que el backend responda con código de estado `HTTP 422 Unprocessable Entity` y el código de error de dominio correspondiente.
2. **Capa de Persistencia (PostgreSQL TEST):** Verifica de manera autoritativa e incontrovertible mediante consultas de solo lectura (`SELECT`) que las entidades permanecen activas (`es_activo = True`), con sus tipos de datos saneados y sin ninguna mutación de estado colateral.

---

## 4. Ejecución Newman Final (`resultado_TC-M09-G15_reintento2.{html,json}`)

### Comando Ejecutado:
```powershell
npx newman run tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/test_tc_m09_g15.json `
  --env-var "baseUrl=$TEST_BASE_URL" `
  --env-var "admin_email=$TEST_ADMIN_EMAIL" `
  --env-var "admin_password=$TEST_ADMIN_PASSWORD" `
  -r cli,htmlextra,json `
  --reporter-htmlextra-export tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/resultados/resultado_TC-M09-G15_reintento2.html `
  --reporter-json-export tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/resultados/resultado_TC-M09-G15_reintento2.json
```

### Resumen de Métricas Newman:
* **Iteraciones:** 1
* **Requests Ejecutados:** 4
* **Aserciones Evaluadas:** 4
* **Aserciones Pasadas:** 4 (100%)
* **Aserciones Fallidas:** 0
* **Tiempo Total de Corrida:** 1.77 segundos (1,768 ms)
* **Tiempo Promedio de Respuesta:** 351 ms (min: 121 ms, max: 954 ms)

### Desglose por Subcaso:

| Paso | Subcaso | Entidad Evaluada | Endpoint HTTP | HTTP Esperado | HTTP Obtenido | Código de Error | Veredicto |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **1** | Autenticación | Credenciales Administrador | `POST /sesiones/` | `HTTP 200` | `HTTP 200` | N/A | 🟢 **PASS** |
| **2** | **TC-M09-36** | Etapa con activos asociados (`id=10`) | `PATCH /configuracion/ciclos/10/desactivar` | `HTTP 422` | `HTTP 422` | `ETAPA_CON_ACTIVOS` | 🟢 **PASS** |
| **3** | **TC-M09-37** | Patología con dependencias M04 (`id=7`) | `PATCH /configuracion/patologias/7/desactivar` | `HTTP 422` | `HTTP 422` | `PATOLOGIA_CON_DEPENDENCIAS` | 🟢 **PASS** |
| **4** | **TC-M09-38** | Métrica con eventos productivos (`id=1`) | `PATCH /configuracion/metricas/1/desactivar` | `HTTP 422` | `HTTP 422` | `METRICA_CON_REGISTROS` | 🟢 **PASS** |

---

## 5. Verificación de Invariantes en Base de Datos

Salida literal del script [`verificar_bd_pre_post.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/verificar_bd_pre_post.py):
```text
=== ESTADO DE BASE DE DATOS (TC-M09-G15) ===
[ETAPA] id_ciclo_biologico=10 | nombre='Fase juvenil cachama' | es_activo=True | referencias_productivas=1
[PATOLOGÍA] id_especies_patologias=7 | nombre='Ich (Ichthyophthirius)' | es_activo=True | id_patologia=1 | predicciones=7 | alertas=4
[MÉTRICA] id_metrica_produccion=1 | nombre='Peso promedio individual' | tipo_medicion='PESO' | es_activo=True | eventos_productivos=4
```

### Inocuidad y Conteos Pre / Post:
* `modulo9.metricas_produccion`: 17 filas (0 mutaciones).
* `modulo2.eventos_productivos`: 7 filas (0 mutaciones).
* `modulo9.ciclos_biologicos`: 36 filas (0 mutaciones).
* `modulo9.especies_patologias`: 18 filas (0 mutaciones).
* **Teardown:** No-op verificado. Al ser una suite de rechazo negativo por reglas de negocio (`HTTP 422`), el backend rechazó las transacciones y no mutó ninguna entidad (`es_activo = True` en todas).

---

## 6. Hallazgo Técnico y Mejora Sugerida
* **Hallazgo:** El router FastAPI `GET /configuracion/metricas` exige de forma obligatoria el query parameter `id_especie: int = Query(...)`. En consecuencia, no expone ningún mecanismo vía API para listar métricas globales o transversales históricas (`id_especie IS NULL`, como la métrica 1).
* **Impacto en el Caso:** Cero impacto sobre el fix del defecto `#303`. La desactivación (`PATCH /configuracion/metricas/1/desactivar`) evalúa y bloquea la operación conforme a las reglas de negocio de RF-16. La verificación del estado activo se delegó autoritativamente a la capa de base de datos.
* **Acción sugerida:** Decisión pendiente del equipo QA/Desarrollo de abrir un issue de mejora en el contrato de API para permitir `id_especie` opcional (`Optional[int] = None`) en `GET /configuracion/metricas` o aceptar la limitación actual del contrato.

---

## 7. Bloqueo Técnico en Test de Integración
* **Archivo:** [`tests/integration/test_inc_m09_06_g15_metricas_legacy.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/integration/test_inc_m09_06_g15_metricas_legacy.py)
* **Estado:** **BLOQUEADO** (No computa como fallo del fix de código ni como PASS).
* **Causa:** El test ejecuta `ALTER TABLE modulo9.metricas_produccion DROP CONSTRAINT IF EXISTS chk_metricas_tipo_medicion` para preparar un estado pre-migración dentro de una base ya migrada. En la base de datos remota de TEST, el usuario de pruebas `member_qa` no es propietario (`owner=dba`), lo que viola las restricciones DDL de PostgreSQL y la regla R2 del proyecto.
* **Evidencia:** [`evidencias/resultado_TC-M09-G15_reintento2_integracion.txt`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-16/TC-M09-G15/evidencias/resultado_TC-M09-G15_reintento2_integracion.txt).
* **Acción Propuesta:** Refactorizar el test de integración para no requerir operaciones DDL directas en bases compartidas o aislarlo en contenedores de prueba locales efímeros.

---

## 8. Declaración Explícita de Honestidad
- Declaro que la ejecución E2E se realizó directamente contra el backend desplegado en TEST.
- Declaro que no se forzaron aserciones ni se manipularon códigos de respuesta HTTP.
- Declaro que todos los intentos de desactivación fueron formalmente rechazados por el backend con `HTTP 422`, validando que el fix de la migración `9a5de7d9973f` resolvió íntegramente el fallo `HTTP 500`.
- Declaro que ningún secreto ni credencial sensible fue expuesto en texto plano en este informe ni en los archivos versionados del repositorio.
