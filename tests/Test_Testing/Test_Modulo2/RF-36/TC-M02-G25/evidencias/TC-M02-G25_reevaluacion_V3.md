# Reevaluación V3 — TC-M02-G25

## 1. Metadata
- **RUN_ID:** `G25-REEVAL-V3-20260919-053900`
- **Fecha:** 2026-09-19
- **Hora Local:** 05:39:07 COT (UTC-5)
- **Hora UTC:** 10:39:07 UTC
- **Entorno:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Evaluador:** Sebastian (según asignaciones.csv)
- **Ronda:** V3
- **Reintento:** `_reintento2`
- **Incidencia Asociada:** `INC-M02-38-G25`

---

## 2. Preflight ejecutado
- **A.1 Conectividad (GET /health):** HTTP 200 OK (`{"status": "ok", "message": "API funcionando correctamente"}`).
- **A.2 Autenticación (POST /sesiones/):** HTTP 200 OK. Token JWT obtenido exitosamente sin rate-limiting (credenciales inyectadas vía variables de entorno).
- **A.3 Estado de Lotes:**
  - Lote 130: `HTTP 200`, `id_estado = 1` (ACTIVO), tipo POBLACIONAL, `cantidad_actual = 3`.
  - Lote 345: `HTTP 200`, reactivado a `id_estado = 1` (ACTIVO) previo a la corrida, tipo POBLACIONAL, `cantidad_actual = 10`.

---

## 3. Contexto histórico
- **V1 (2026-09-08):** FALLIDO (1/2).
  - TC-M02-051: PASS (`HTTP 422 CANTIDAD_BAJA_SUPERIOR_EXISTENCIA`).
  - TC-M02-052: FAIL (`HTTP 201 Created` en lugar de 409 Conflict; el backend no validaba densidad).
- **V2 (2026-09-14):** FALLIDO (1/2).
  - TC-M02-051: PASS (`HTTP 422 CANTIDAD_BAJA_SUPERIOR_EXISTENCIA`).
  - TC-M02-052: FAIL bloqueado por precondición (`HTTP 422 SIN_FASE_ACTIVA` sobre Lote 345).
- **Cambios esperados en V3:** Verificación del fix #330 anunciado por desarrollo.

---

## 4. Hallazgos previos (resumen)
- **H-A (Despliegue):** El commit `d6d4bf93` (PR #330) fue mergeado a `dev` local pero no ha sido desplegado al contenedor de TEST.
- **H-B (Lógica del Fix):** El fix compara `densidad_actual` (basada en `cantidad_actual`) contra `densidad_maxima`. Un evento de crecimiento no altera `cantidad_actual`, por lo que nunca incrementará la densidad.
- **H-C (Discrepancia Contractual):** RF-36 establece que la densidad máxima proviene del catálogo de especies de M09 (`densidad_maxima_por_especie`). La implementación de #330 la calcula desde `infraestructuras.capacidad_maxima / superficie`.
- **H-D (Seeds NULL):** Las infraestructuras en TEST tienen `capacidad_maxima = NULL`, lo cual inhabilita el bloque `if infra and infra.capacidad_maxima:`.
- **H-E (Diseño del Subcaso 052):** El spec asume que `"cantidad_medida": 250` incrementa la población a 250 peces, cuando en realidad es el tamaño muestral de la pesada.
- **H-F (Precondición de Fase Activa):** El spec no asigna fase productiva activa al lote previo al evento de crecimiento.

---

## 5. Resultados de la ejecución V3
Ejecutada la suite Newman `test_tc_m02_g25.json` tal como está, contra el entorno TEST:

- **TC-M02-051 (Rechazar baja con cantidad superior a existencia):**
  - **Estado:** **PASS (OK)**
  - **Endpoint:** `POST /activos-biologicos/345/eventos/baja`
  - **HTTP Obtenido:** `422 Unprocessable Entity`
  - **Código de Error:** `CANTIDAD_BAJA_SUPERIOR_EXISTENCIA`
  - **Mensaje:** *"La cantidad a dar de baja (15) es superior a la existencia actual del lote (10)."*
  - **Comprobación:** Aserciones 2/2 aprobadas. La existencia del lote permaneció intacta (10 individuos).

- **TC-M02-052 (Rechazar crecimiento que excede densidad máxima):**
  - **Estado:** **FAIL (FALLA)**
  - **Endpoint:** `POST /activos-biologicos/345/eventos/crecimiento`
  - **HTTP Obtenido:** `422 Unprocessable Entity` *(Esperado: 409 Conflict)*
  - **Código de Error:** `SIN_FASE_ACTIVA`
  - **Mensaje:** *"El activo no tiene una fase productiva activa. Asocie el activo a un ciclo productivo antes de registrar eventos de crecimiento."*
  - **Comprobación:** Aserciones 0/2 aprobadas (falló por código 409 esperado y por mensaje de densidad). En el preflight empírico con lote con fase activa respondió `201 Created` sin validar densidad.

---

## 6. Resumen de checkpoints

| Paso | Esperado | Obtenido | Estado |
| :--- | :--- | :--- | :--- |
| **0. Autenticación como Administrador** | `HTTP 200 OK` con token JWT | `HTTP 200 OK` - Token JWT obtenido correctamente | **OK** |
| **1. TC-M02-051: Baja con cantidad > existencia** | `HTTP 400` / `422` con `CANTIDAD_BAJA_SUPERIOR_EXISTENCIA` | `HTTP 422 Unprocessable Entity` - `CANTIDAD_BAJA_SUPERIOR_EXISTENCIA` (cantidad 15 > existencia 10) | **OK** |
| **2. TC-M02-052: Crecimiento con densidad excedida** | `HTTP 409 Conflict` con `DENSIDAD_MAXIMA_SUPERADA` | `HTTP 422 Unprocessable Entity` - `SIN_FASE_ACTIVA` (esperado: 409 Conflict) | **FALLA** |
| **3. Cleanup: Inactivación lógica del lote sintético** | `HTTP 200 OK` con estado INACTIVO (`id_estado = 2`) | `HTTP 200 OK` - Lote 345 inactivado lógicamente (`estado_nuevo: 2`) | **OK** |

---

## 7. Idempotencia y limpieza
- **Lotes involucrados:** Lote 345.
- **Teardown en Suite:** El request 3 de Newman ejecutó `PATCH /activos-biologicos/345/estado` con `INACTIVO` obteniendo `HTTP 200 OK`.
- **Verificación en BD:** Lote 345 quedó en `id_estado = 2` (INACTIVO).
- **Cero DELETE físico:** No se ejecutó ningún DELETE a nivel de base de datos ni API.

---

## 8. Veredicto final
- **Veredicto:** **Rechazado**
- **Justificación:** El fix #330 no se encuentra desplegado en TEST y presenta inconsistencias de diseño conceptual. El subcaso TC-M02-052 continúa fallando (en preflight responde `201 Created` sin validar y en la suite ejecutada tal como está devuelve `422 SIN_FASE_ACTIVA`). El caso queda bloqueado formalmente por dependencias externas de Desarrollo y Análisis.

---

## 9. Recomendaciones
1. **Equipo de Desarrollo Backend:**
   - Desplegar el fix #330 en el ambiente TEST.
   - Corregir el cortocircuito cuando `infra.capacidad_maxima` sea nula.
   - Revisar la regla de cálculo de densidad en crecimiento vs. traslados/ingresos.
2. **Equipo de Análisis:**
   - Definir si `densidad_maxima` se rige por M09 (especie) o M09 (infraestructura) o fórmula compuesta.
   - Definir unidad de medida (individuos/m² vs biomasa kg/m²).
3. **Equipo de QA:**
   - Mantener el caso en estado **Rechazado** en el dashboard.
   - Aplazar la ronda V4 hasta que Backend y Análisis entreguen la versión corregida y desplegada.
