# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN
## CASO AGRUPADO: TC-M02-G31 (RF-36: Gestión Poblacional de Activos Biológicos)

- **Fecha de Ejecución:** 2026-09-11
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramientas Utilizadas:** Newman CLI v6.2.2 + Reporter `htmlextra` v1.23.1
- **Colección Ejecutada:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/test_tc_m02_g31.json`
- **Reportes HTML Generados:**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/RESULTADOS/reporte_TC-M02-196.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/RESULTADOS/reporte_TC-M02-197.html`
- **Script de Verificación:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/RESULTADOS/cleanup_tc_m02_g31.sql`
- **Veredicto Global:** **FALLIDO (0 PASSED, 2 FALLIDOS)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G31** evalúa los valores límite zootécnicos en la gestión de lotes conforme al **RF-36 (CU03)**:

| Subcaso | Enfoque Evaluado | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-196** | Densidad igual al máximo permitido | HTTP 201 sin error 409 | HTTP 500 ERROR_INTERNO en POST /activos-biologicos/130/eventos/crecimiento | `reporte_TC-M02-196.html` | **FALLIDO** |
| **TC-M02-197** | Baja total a cantidad_actual=0 | HTTP 201 con cantidad_actual=0 y biomasa=0 | HTTP 500 ERROR_INTERNO en POST /activos-biologicos/344/eventos/baja | `reporte_TC-M02-197.html` | **FALLIDO** |

---

## 2. Métricas de Ejecución

| Subcaso | Folder Newman | Peticiones HTTP | Aserciones | Duración | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: |
| TC-M02-196 | `TC-M02-196` | 2 | (fallo en HTTP 500) | N/A | FALLIDO |
| TC-M02-197 | `TC-M02-197` | 4 | (fallo en HTTP 500) | N/A | FALLIDO |

---

## 3. Detalle Técnico por Subcaso

### 3.1. TC-M02-196 — Densidad igual al máximo permitido

- **Petición:** `POST /activos-biologicos/130/eventos/crecimiento`
- **Resultado observado:** HTTP 500 ERROR_INTERNO.
- **Contexto:** La regla `densidad_maxima_por_especie` no existe en el sistema. El endpoint retorna error interno, no la aceptación esperada.
- **Estado del lote 130:** densidad inalterada en 0.002.
- **Causa raíz pendiente de investigar** por el equipo de desarrollo.

### 3.2. TC-M02-197 — Baja total a cantidad_actual=0

- **Peticiones ejecutadas:** `POST /activos-biologicos/344/eventos/baja` y `POST /activos-biologicos/345/eventos/baja` (ambos lotes existentes con marca QA-TC-M02-197).
- **Resultado observado:** HTTP 500 ERROR_INTERNO en ambos intentos.
- **Rollback transaccional:** los lotes conservan `cantidad_actual=10` en estado ACTIVO.
- **Causa raíz:** consistente con el bug de enum en el trigger `trg_fn_baja_cantidad_valida` (comparación `'poblacional'` en minúsculas contra enum en `'POBLACIONAL'`), ya en corrección en **PR #254**.

---

## 4. Posibles Causas del Bloqueo

### 4.1. TC-M02-196
- El endpoint `POST /activos-biologicos/{id}/eventos/crecimiento` retorna HTTP 500.
- Requiere revisión del equipo de desarrollo.
- Adicionalmente, la regla `densidad_maxima_por_especie` no está implementada en el modelo ni en los esquemas `modulo2`/`modulo9`.

### 4.2. TC-M02-197
- Bug de enum en trigger de BD (`trg_fn_baja_cantidad_valida`), ya identificado y en corrección vía **PR #254** (`fix/rf45-inc-m02-80-g61-trigger-baja`).
- Adicionalmente, la vinculación de fases activas a lotes está bloqueada por definiciones pendientes de Análisis sobre `ciclos_productivos`.

---

## 5. Estado de los Lotes de Prueba (Residuos Controlados)

Los siguientes lotes permanecen en BD TEST como residuos controlados (los triggers de inmutabilidad impiden su eliminación física):

| ID Activo | Tipo | Especie | Infraestructura | Marca Procedencia | Cantidad Inicial | Cantidad Actual | Estado |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 344 | POBLACIONAL | 4 (Cachama) | 3 (Alevinera-01) | QA-TC-M02-197 | 10 | 10 | ACTIVO |
| 345 | POBLACIONAL | 4 (Cachama) | 3 (Alevinera-01) | QA-TC-M02-197 | 10 | 10 | ACTIVO |

---

## 6. Verificación de Integridad de la BD TEST

Se ejecutaron las consultas de verificación del script `cleanup_tc_m02_g31.sql` (solo SELECT):
- Los lotes 344 y 345 permanecen en ACTIVO con cantidad_actual=10.
- 0 eventos de baja registrados.
- 0 eventos huérfanos.

**Declaración de inocuidad:** NO se modificó la estructura de la BD TEST. No se ejecutaron DDL, triggers, funciones ni cambios estructurales.

---

## 7. Próximos Pasos y Re-ejecución

- **TC-M02-196:** Investigar la causa del HTTP 500 en el endpoint de crecimiento. Re-ejecutar cuando esté resuelto.
- **TC-M02-197:** Re-ejecutar cuando el **PR #254** esté mergeado en TEST y cuando Análisis defina el mecanismo de asignación de `ciclos_productivos`.
- Script de retest diferido: `retest_tc_m02_g31.ps1` (preparado, pendiente de ejecutar).

---

## 8. Criterios de Cierre del Caso Agrupado

El caso agrupado TC-M02-G31 permanecerá en estado **FALLIDO** hasta que:
1. Se resuelva el HTTP 500 en el endpoint de crecimiento (TC-M02-196).
2. Se mergee el **PR #254** en TEST y se confirme la corrección del trigger de baja (TC-M02-197).
3. Análisis defina el mecanismo de creación de `ciclos_productivos` para poder asignar fase activa a lotes.
4. Se ejecute la re-evaluación de ambos subcasos y se obtenga PASS.

---

## 9. Referencias Cruzadas

- **INC-M02-37-G24** (incidente ya reportado): documenta la desconexión de modelo entre `configuracion.ciclos_biologicos` y `operacion.ciclos_productivos`.
- **PR #254** (`fix/rf45-inc-m02-80-g61-trigger-baja`): corrige el bug de enum en `trg_fn_baja_cantidad_valida`.
- **PR #260** (`fix/inc-m02-195-g24-densidad-inicial`): corrige el cálculo de densidad inicial (relacionado con TC-M02-196).
- **TC-M02-G30**: mismo RF-36, comparte los endpoints de eventos.

---

## 10. Declaración de Cumplimiento Normativo de QA

- ✅ Rutas relativas a `sgpmp-backend/`.
- ✅ NO se ejecutaron DDL ni se modificó la estructura de la BD TEST.
- ✅ NO se crearon archivos `defecto_INC-*.md` en disco.
- ✅ Solo se usaron SELECT para verificación y operaciones vía API.
- ✅ Los reportes HTML están en la ruta canónica.

---

## 11. Veredicto Final

El caso agrupado **TC-M02-G31** concluye con veredicto:

**FALLIDO (0 PASSED, 2 FALLIDOS)** — pendiente de resolución de dependencias externas.
