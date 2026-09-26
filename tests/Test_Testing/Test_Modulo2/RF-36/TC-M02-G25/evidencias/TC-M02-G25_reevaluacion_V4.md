# Reevaluación V4 — TC-M02-G25

## 1. Metadata
- **RUN_ID:** `G25-REEVAL-V4-20260925-151300`
- **Fecha:** 2026-09-25
- **Hora Local:** 15:13:00 COT (UTC-5)
- **Entorno:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Ronda:** V4
- **Reintento:** `_reintento3` (intento final consolidado)
- **Incidencia Asociada:** `INC-M02-48-G25`
- **Módulo:** Módulo 2 (Activos Biológicos)
- **Requerimiento:** RF-36 / RF-40 (CU03)

---

## 2. Preflight y Configuración de Precondición
- **2.1 Conectividad (GET /health):** HTTP 200 OK.
- **2.2 Autenticación (POST /sesiones/):** HTTP 200 OK con token JWT.
- **2.3 Detección H-A (GET /configuracion/especies):** HTTP 200 OK. Clave `densidad_maxima_por_especie` presente en el esquema del catálogo de especies de M09.
- **2.4 Confirmación DDL en Base de Datos:** Columna `densidad_maxima_por_especie` (`numeric(10,4)`) confirmada en `modulo9.especies`.
- **2.5 Selección de Lote de Prueba (SQL):**
  - **Lote ID:** `130` (tipo `POBLACIONAL`, activo `id_estado = 1`)
  - **Especie ID:** `4` (`Cachama Blanca`)
  - **Cantidad Actual:** `2` individuos
  - **Superficie:** `2500.00` m²
  - **Densidad Calculada:** `0.0008` ind/m²
  - **Fase Activa:** `True` (confirmada en `modulo2.gestiones_fases`)
- **2.6 Configuración de Densidad vía API (Precondición):**
  - Valor objetivo: `0.0004` ind/m² (estrictamente menor a la densidad calculada de 0.0008).
  - Ejecutado `PATCH /configuracion/especies/4` con optimistic locking: HTTP 200 OK.
  - Verificado en SQL que $densidad\_calculada (0.0008) > densidad\_maxima (0.0004)$.

---

## 3. Corrección de Defectos en el Spec Newman (Fase 3.1)
Previo a la re-ejecución definitiva, se corrigieron dos bugs identificados en el spec `test_tc_m02_g25.json`:
1. **Bug 1 (Fecha estática de baja):** El spec utilizaba la fecha estática `"fecha_baja": "2026-09-14"`. Dado que el lote 130 poseía eventos posteriores (`2026-09-19`), el validador cronológico rechazaba con `HTTP 400 FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA` antes de alcanzar la regla zootécnica de existencia. Se parametrizó mediante la variable dinámica `{{fecha_baja_dinamica}}` inyectada con la fecha actual (`2026-09-25`).
2. **Bug 2 (Aserción por nombre de propiedad de mensaje):** El spec evaluaba `res.mensaje` cuando el contrato estándar de error del backend emite la propiedad `message`. Se corrigieron las aserciones en los dos subcasos (`TC-M02-051` y `TC-M02-052`) a `pm.expect(res.message)...`.

---

## 4. Ejecución Newman Definitiva

**Comando ejecutado:**
```bash
npx newman run \
  tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/test_tc_m02_g25.json \
  --env-var "baseUrl=$TEST_BASE_URL" \
  --env-var "admin_email=$TEST_ADMIN_EMAIL" \
  --env-var "admin_password=$TEST_ADMIN_PASSWORD" \
  --env-var "id_lote=130" \
  --env-var "fecha_baja_dinamica=2026-09-25" \
  -r cli,htmlextra \
  --reporter-htmlextra-export \
    tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/resultados/resultado_TC-M02-G25_reintento3.html
```

- **Estadísticas de Ejecución:**
  - **Iteraciones:** 1
  - **Requests:** 3 ejecutados (1 login + 2 funcionales), 0 fallidos.
  - **Assertions:** 3 evaluadas, 3 aprobadas (**0 fallidas**).
  - **Tiempo Total:** 1921 ms
  - **Tiempo Promedio de Respuesta:** 562 ms

---

## 5. Resumen de Checkpoints

| Paso | Esperado | Obtenido | Estado | Fuente |
| :--- | :--- | :--- | :---: | :--- |
| **0. Autenticación Administrador** | `HTTP 200 OK` con token | `HTTP 200 OK` - Token JWT obtenido | **OK** | `resultados/resultado_TC-M02-G25_reintento3.html` |
| **1. TC-M02-051: Baja > existencia** | `HTTP 422 CANTIDAD_BAJA_SUPERIOR_EXISTENCIA` | `HTTP 422 CANTIDAD_BAJA_SUPERIOR_EXISTENCIA` (15 > 2) | **OK** | `resultados/resultado_TC-M02-G25_reintento3.html` |
| **2. TC-M02-052: Crecimiento con densidad excedida** | `HTTP 409 DENSIDAD_MAXIMA_SUPERADA` | `HTTP 409 DENSIDAD_MAXIMA_SUPERADA` ("La densidad del lote supera el máximo permitido para la especie.") | **OK** | `resultados/resultado_TC-M02-G25_reintento3.html` |

---

## 6. Verificación de Inocuidad (Conteos Pre/Post)

| Tabla | Conteo PRE | Conteo POST | Mutaciones |
| :--- | :---: | :---: | :---: |
| `modulo2.activos_biologicos` | 386 | 386 | **0** |
| `modulo2.detalles_activos_biologicos_poblacionales` | 120 | 120 | **0** |
| `modulo2.eventos_productivos` | 7 | 7 | **0** |

Se verificó **cero mutaciones** e inocuidad total en las tablas biológicas y transaccionales tras las solicitudes rechazadas.

---

## 7. Teardown vía API
- Se ejecutó `PATCH /configuracion/especies/4` restaurando `"densidad_maxima_por_especie": null` con token administrativo.
- Respuesta HTTP: `200 OK`.
- Verificación en base de datos:
  `SELECT id_especie, nombre, densidad_maxima_por_especie FROM modulo9.especies WHERE id_especie = 4;`
  Resultado: `(4, 'Cachama Blanca', None)`.
- Estado del catálogo restaurado al valor por defecto sin intervención DML directa.

---

## 8. Veredicto Final
- **Veredicto:** **Aprobado**
- **Fundamento Técnico:**
  1. El fix `INC-M02-48-G25` (migración `7abae1ee50f6`) se encuentra completamente desplegado y operativo en el entorno TEST.
  2. La validación zootécnica de baja por cantidad superior a existencia (`TC-M02-051`) bloquea satisfactoriamente con `HTTP 422 CANTIDAD_BAJA_SUPERIOR_EXISTENCIA`.
  3. La validación de densidad máxima por especie de M09 (`TC-M02-052`) bloquea satisfactoriamente los eventos de crecimiento cuando la densidad del lote supera el umbral configurado con `HTTP 409 DENSIDAD_MAXIMA_SUPERADA`.
  4. Los 2 checkpoints del caso se encuentran en estado **OK** en la suite Newman con 100% de aserciones aprobadas.
