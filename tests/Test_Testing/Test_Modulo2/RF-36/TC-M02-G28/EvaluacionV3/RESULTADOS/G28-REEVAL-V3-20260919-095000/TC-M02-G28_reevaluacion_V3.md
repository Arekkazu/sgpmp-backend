# Reevaluación V3 — TC-M02-G28

## 1. Metadata
- **RUN_ID:** `G28-REEVAL-V3-20260919-095000`
- **Fecha:** `2026-09-19`
- **Hora Local:** `09:50:00 -05:00`
- **Hora UTC:** `14:50:00 UTC`
- **Entorno:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Evaluador:** Sebastian
- **Ronda:** V3
- **Reintento:** `_reintento2`
- **Archivo de Colección Ejecutado:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G28/test_tc_m02_g28.json`

## 2. Preflight ejecutado
El preflight empírico automatizado ejecutado antes de la suite arrojó los siguientes resultados:
- **B.1. Health Check (`GET /health`):** HTTP 200 OK (`{"status":"healthy","version":"1.0.0"}`).
- **B.2. Login Admin (`POST /sesiones/`):** HTTP 200 OK. Token JWT administrativo emitido correctamente.
- **B.3. Estado Lote 130 (`GET /activos-biologicos/130`):** HTTP 200 OK. `id_infraestructura: 1` (*Estanque-01*), `cantidad_actual: 3`, `densidad: 0.0012` ($3 / 2500\text{ m}^2$).
- **B.4. Existencia de Infraestructuras Requeridas:**
  - ID 10 (*Invernadero Norte*): Inactiva (Finca 1) $\rightarrow$ Confirmada.
  - ID 4 (*Canal-Trucha-01*): Activa perteneciente a Finca 2 $\rightarrow$ Confirmada.
  - ID 1 (*Estanque-01*, 2500 m²) e ID 3 (*Alevinera-01*, 500 m²): Ambas de Finca 1 $\rightarrow$ Confirmadas.
- **Confirmación de Fixes:**
  - **Fix #333 (Frontera territorial de finca):** DESPLEGADO. Responde `HTTP 422 Unprocessable Entity` con código `DESTINO_OTRA_FINCA`.
  - **Fix #334 (Recálculo automático de densidad):** DESPLEGADO. Actualiza automáticamente el campo `densidad` en `modulo2.detalles_activos_biologicos_poblacionales` según la superficie destino.

## 3. Contexto histórico
- **V1 (2026-09-08):** `FAIL PARCIAL` (1 PASS, 2 FAIL — Veredicto: `Rechazado`).
  - *TC-M02-200 (Infraestructura inactiva):* PASS (`HTTP 400 Bad Request` — `INFRAESTRUCTURA_DESTINO_INVALIDA`).
  - *TC-M02-201 (Otra finca):* FAIL (`HTTP 201 Created` — El backend permitió transferir el lote de Finca 1 a infraestructura de Finca 2 sin validar pertenencia territorial).
  - *TC-M02-202 (Densidad):* FAIL (`HTTP 201 Created` — El lote fue trasladado pero la densidad permaneció congelada en `0.01`, omitiendo el recálculo zootécnico).
- **V2: NO EJECUTADA (SALTADA)**
  - *Motivo:* Los fixes #333 y #334 no estaban integrados ni desplegados en el entorno TEST en esa fecha (2026-09-14). Ejecutar V2 habría duplicado los fallos sin aportar valor. Se decidió esperar el despliegue formal de ambos fixes y saltar a V3.
- **V3 (2026-09-19, esta corrida):** Verificación integral del despliegue de los fixes #333 y #334, con precondición dinámica de infraestructura y teardown de reversión.

## 4. Cambios aplicados al spec
- **A.1: Credenciales Dinámicas:**
  - Se eliminó el hardcoding de `admin@pecuaria.co` (cuenta bloqueada en TEST).
  - Se parametrizó con `{{admin_email}}` y `{{admin_password}}`, inyectando la cuenta activa `administador.dev@gmail.com`.
- **A.2: Precondición Dinámica de Infraestructura Origen:**
  - Se añadió el paso `Setup Precondición` (`GET /activos-biologicos/{{id_lote}}`) que detecta dinámicamente la ubicación física actual del lote 130 y asigna `infraestructura_origen_id` (`1`), `infraestructura_destino_valida` (`3`) y `superficie_destino` (`500`).
- **A.3: Consolidación en Suite Única (`test_tc_m02_g28.json`):**
  - Se unificaron los subcasos 200, 201 y 202 en un flujo ordenado y determinístico de 10 requests ejecutables con Newman.
- **A.4: Teardown Formal:**
  - Se implementó la reversión obligatoria del lote a su infraestructura original tras la prueba de transferencia válida, garantizando la idempotencia del entorno.
- **A.5: Ajuste de Aserciones:**
  - Se alineó el código esperado en subcasos de rechazo con la respuesta contractual `HTTP 422 Unprocessable Entity` (`BusinessRuleError`).
  - Se validó el recálculo de densidad con tolerancia numérica mediante `closeTo(densidadEsperada, 0.0001)`.

## 5. Resultados por subcaso

### TC-M02-200 — Rechazar transferencia a infraestructura inactiva
- **Estado:** `OK` (APROBADO)
- **POST Transferencia:**
  - Endpoint: `POST /activos-biologicos/130/transferencias`
  - Destino: ID 10 (*Invernadero Norte*, inactiva)
  - HTTP Status: `422 Unprocessable Entity`
  - Error Code: `INFRAESTRUCTURA_DESTINO_INVALIDA`
  - Mensaje: *"La infraestructura con id 10 se encuentra inactiva."*
- **GET Verificación:**
  - Lote permanece en infraestructura origen (ID 1). Aserción superada.

### TC-M02-201 — Rechazar transferencia a infraestructura de otra finca
- **Estado:** `OK` (APROBADO — Fix #333 Confirmado)
- **POST Transferencia:**
  - Endpoint: `POST /activos-biologicos/130/transferencias`
  - Destino: ID 4 (*Canal-Trucha-01*, Finca 2)
  - HTTP Status: `422 Unprocessable Entity`
  - Error Code: `DESTINO_OTRA_FINCA`
  - Mensaje: *"La infraestructura Canal-Trucha-01 pertenece a una finca distinta a la del activo. Seleccione un destino dentro de la misma finca."*
- **GET Verificación:**
  - Lote permanece en infraestructura origen (ID 1). Frontera territorial validada estrictamente.

### TC-M02-202 — Transferencia válida y recálculo de densidad
- **Estado:** `OK` (APROBADO — Fix #334 Confirmado)
- **POST Transferencia:**
  - Endpoint: `POST /activos-biologicos/130/transferencias`
  - Origen: ID 1 (*Estanque-01*, 2500 m²)
  - Destino: ID 3 (*Alevinera-01*, 500 m²)
  - HTTP Status: `201 Created`
  - Movimiento registrado: ID `34`
- **GET Verificación y Recálculo:**
  - Lote asignado a infraestructura destino: ID 3.
  - Densidad anterior: `0.0012` ($3 / 2500\text{ m}^2$)
  - Densidad nueva recalculada: **`0.006`** ($3 / 500\text{ m}^2$)
  - Densidad esperada vs obtenida: `0.0060 == 0.0060` (Diferencia: `0.0000`).

---

## 6. Resumen de checkpoints

| Paso | Esperado | Obtenido | Estado |
| :--- | :--- | :--- | :---: |
| **0. Autenticación Administrador** | HTTP 200 OK con JWT | HTTP 200 OK - Token emitido | `OK` |
| **0.1 Setup Precondición** | HTTP 200 OK detectando infraestructura | HTTP 200 OK - Origen: 1, Destino: 3, Sup: 500 | `OK` |
| **1. TC-M02-200 (Infra inactiva)** | HTTP 422/400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | HTTP 422 Unprocessable Entity | `OK` |
| **1.1 TC-M02-200 Check** | HTTP 200 OK lote permanece en origen | HTTP 200 OK - Lote en ID 1 intacto | `OK` |
| **2. TC-M02-201 (Otra finca)** | HTTP 422/400 `DESTINO_OTRA_FINCA` | HTTP 422 Unprocessable Entity (`DESTINO_OTRA_FINCA`) | `OK` |
| **2.1 TC-M02-201 Check** | HTTP 200 OK lote permanece en origen | HTTP 200 OK - Lote en ID 1 intacto | `OK` |
| **3. TC-M02-202 (Transferencia válida)** | HTTP 201 Created confirmando traslado | HTTP 201 Created - Traslado a Alevinera-01 | `OK` |
| **3.1 TC-M02-202 Check** | HTTP 200 OK y densidad recalculada (0.006) | HTTP 200 OK - Densidad recalculada a 0.006 | `OK` |
| **4. Teardown (Reversión a origen)** | HTTP 201 Created revirtiendo a ID 1 | HTTP 201 Created - Reversión exitosa | `OK` |
| **4.1 Teardown Check** | HTTP 200 OK lote restaurado en ID 1 | HTTP 200 OK - Lote restaurado en Estanque-01 | `OK` |

---

## 7. Idempotencia y Limpieza
- **Restauración del Lote:** El Lote 130 fue revertido mediante el paso formal de teardown a su infraestructura original (`id_infraestructura: 1`, *Estanque-01*) y su densidad fue restaurada a `0.0012`.
- **Cero Residuos Activos:** No se crearon lotes ni activos huérfanos durante la corrida.
- **Cero DELETE Físico:** Se confirma que no se ejecutó ninguna sentencia de eliminación física en base de datos.

---

## 8. Veredicto Final
**Veredicto Oficial:** **`Aprobado`**

**Justificación:**
1. **Fix #333 validado:** El sistema bloquea de manera determinística las transferencias entre distintas unidades territoriales/fincas con `HTTP 422 DESTINO_OTRA_FINCA`.
2. **Fix #334 validado:** Se comprobó que el caso de uso `RegistrarTransferenciaUseCase` recalcula automáticamente la densidad poblacional en función de la superficie de la nueva infraestructura receptora, cerrando el defecto zootécnico histórico.
3. **Manejo de infraestructura inactiva:** Se ratifica el rechazo a infraestructuras dadas de baja con `HTTP 422 INFRAESTRUCTURA_DESTINO_INVALIDA`.
4. **Tasa de Aprobación:** 100% de aserciones de prueba pasadas (18/18) y 100% de checkpoints normativos en estado `OK` (5/5).

---

## 9. Recomendaciones
- **Cierre de Incidencias en Taiga:** Se recomienda proceder con el cierre formal de los 2 defectos históricos asociados al grupo TC-M02-G28:
  1. *Defecto de frontera de finca:* "Ausencia de validación de frontera de finca en transferencia interna" (Fix #333 / commit `df73a16`). QA debe verificar en Taiga el ID canónico antes de cerrarla formalmente.
  2. *Defecto de recálculo zootécnico:* "Omisión de recálculo de densidad poblacional tras transferencia de lote" (Fix #334 / commit en `RegistrarTransferenciaUseCase`). QA debe verificar en Taiga el ID canónico antes de cerrarla formalmente.
- Los IDs citados en borradores previos son placeholders y no deben emplearse en comunicaciones oficiales sin la verificación previa en Taiga.

---

## 10. Lista Final de Archivos en `resultados/`

Directorio: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G28/resultados/`

| Archivo | Ronda | Rango Scanner | Veredicto |
| :--- | :--- | :---: | :---: |
| `resultado_TC-M02-G28.json` | V1 (2026-09-08) | 0 | `Rechazado` |
| *(V2 no ejecutada — saltada)* | — | — | — |
| `resultado_TC-M02-G28_reintento2.json` | V3 (2026-09-19) | 2 | **`Aprobado` (DEFINITIVO)** |

> **Nota:** El sufijo `_reintento1` (rango 1) no existe debido a que la corrida V2 fue saltada intencionalmente (al no estar desplegados los fixes en TEST en esa fecha). El scanner del dashboard selecciona el archivo de mayor rango disponible (`reintento2`), sin verse afectado por el hueco intermedio.
