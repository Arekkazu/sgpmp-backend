# Informe consolidado de pruebas — Módulo 1 (Identidad y Acceso) — v2.0
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M01 — Identidad y Acceso (`src/identity_access/`) |
| Alcance | RF-01 a RF-14 (14 requisitos) |
| Período de ejecución | 2026-08-28 a 2026-10-12 (según la fecha de los commits de evidencia) |
| Fecha de corte del informe | 2026-10-12 |
| Ambientes | Backend TEST (`https://api.inmero.co/back-sigab-test`) · Frontend TEST (`https://api.inmero.co`) |
| Herramientas | Newman/Postman (91), Cypress (23), Pytest (21), Reevaluación documentada (6) |
| Casos ejecutados | 141 de 141 (100 %) |
| Equipo QA | Daniela Castillo, Juan Hernando, Juan Manuel, Juan Parra, Laura Lopez, Sebastian |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (`QA-DASHBOARD-SGRPMP/`, tabla «Todos los casos de prueba»: casos de backend y de frontend), evidencias en `tests/Test_Testing/Test_Modulo1/` y `testing/test_testing/Modulo1/` |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso reejecutado después del corte puede cambiar de veredicto. Los estados de la tabla de casos son la fuente de este informe; el registro de incidencias (`incidencias.csv`) se usa solo para asociar cada caso rechazado con su incidencia cuando existe.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 141 | 100 % |
| Aprobados | **140** | **99.3 %** |
| Rechazados | 1 | 0.7 % |
| Pendientes | 0 | 0.0 % |

**El módulo supera el umbral de aprobación del 85 % (99.3 %).** Queda 1 caso rechazado, que se considera defecto abierto; su detalle está en la sección 4.

### Verificación de los criterios de salida del plan de pruebas (§2.1)

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **140/141 = 99.3 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **14/14** (incluye transversales si aplica) | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | Este documento (pendiente de firmas) | ✅ (firmas pendientes) |

> Por decisión de QA, este informe no evalúa tres criterios del plan (§2.1): #3 defectos Crítico/Severo abiertos sin plan de mitigación, #4 casos rechazados sin incidencia formal y #5 casos con veredicto fijado a mano. Los casos rechazados se registran en la sección 4.A y, por decisión de QA, se clasifican con severidad **Medio**.

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-01 | Registro de usuarios | 20 | 19 | 1 | 0 | 95 % | ⚠️ Parcial |
| RF-02 | Autenticación de usuarios | 13 | 13 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-03 | Gestión de roles | 8 | 8 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-04 | Gestión de permisos | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-05 | Edición de datos de usuario | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-06 | Gestión de cuentas de usuario | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-07 | Cambio de contraseña | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-08 | Recuperación de contraseña | 13 | 13 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-09 | Restablecimiento de contraseña | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-10 | Historial de acceso y auditoría | 14 | 14 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-11 | Visualización de usuarios (listado) | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-12 | Visualización de detalle de usuario | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-13 | Visualización de perfil propio | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-14 | Notificar a los usuarios | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| **Total** | | **141** | **140** | **1** | **0** | **99.3 %** | |

---

## 3. Cobertura y método

- **Herramientas por caso:** Newman/Postman: 91 casos; Cypress: 23 casos; Pytest: 21 casos; Reevaluación documentada: 6 casos.
- **Casos con veredicto de reevaluación documentada:** algunos casos rechazados en la primera evaluación se reejecutaron en `EvaluacionV2`/`EvaluacionV3` y su veredicto vigente consta en el acta de reevaluación (ver sección 4.B).
- **Evidencia:** cada caso conserva su reporte de ejecución (HTML/JSON/XML) y, en las reevaluaciones, un acta `.md` con la narrativa de la corrida.
- **Ambiente:** las ejecuciones vigentes se realizaron contra TEST con el backend en `https://api.inmero.co/back-sigab-test`; algunos casos históricos se ejecutaron contra la URL anterior de TEST (`sslip.io`).

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Casos rechazados (defectos abiertos)

| TC | RF | Responsable | Resultado | Motivo | Incidencia asociada | Severidad (QA) |
|---|---|---|---:|---|---|---|
| 102 | RF-01 | Sebastian | 5/6 | Prueba extrema de pérdida de conexión: el reintento de registro tras reconectar (CP-05) recibe 400 `CAPTCHA_INVALIDO`. El backend TEST valida el reCAPTCHA con Google (comportamiento correcto del producto) y QA no dispone de un token de prueba aceptado en TEST; 5 de 6 comprobaciones pasan | INC-M01-10-11 (Abierto) | Medio |

### 4.B — Casos aprobados por reevaluación documentada

| TC | Fuente del veredicto |
|---|---|
| 040 | Reevaluacion V2 (14-sep-2026, QA/MJ) en RF-08/TC-M01-40/EvaluacionV2/RESULTADOS/TC-M01-40_reevaluacion_V2.md. Falso positivo confirmado: el paso manual 'pegar el token del correo' nunca se hizo en V1, quedo el placeholder PEGAR_AQ… |
| 050 | Falso positivo confirmado (14-sep-2026, QA/MJ), reejecutado con token real (correo real revisado por el usuario, cuenta id_usuario=45): restablecer con token real 200, contrasena anterior ya no funciona 401, contrasena nueva funci… |
| 052 | Extension de TC-M01-053 (misma frontera de expiracion de token de recuperacion, 15 min) -- confirmado por Daniela Castillo: mismo caso, mismo resultado, sin necesidad de ejecucion separada. Evidencia real de la verificacion equiva… |
| 088 | Reejecucion V2 contra TEST (11-oct-2026) con el frontend en https://api.inmero.co y el backend en /back-sigab-test: Cypress 1/1 pasa, veredicto 'SIN FALLAS BLOQUEANTES' en EvaluacionV2/RESULTADOS/TC-M01-088/TC-M01-088_resultado.md… |
| 091 | Reevaluacion V2 (15-sep-2026, QA/MJ) en RF-14/TC-M01-091/EvaluacionV2/RESULTADOS/TC-M01-091/TC-M01-091_reevaluacion_V2.md. Falso positivo de ambiente confirmado: V1 apuntaba a localhost (no disponible). Reejecutado contra TEST rea… |
| 094 | Reevaluacion V2 (14-sep-2026, QA/MJ) en RF-14/TC-M01-94/EvaluacionV2/RESULTADOS/V2-20260914-192653/TC-M01-94_reevaluacion_V2.md. Falso positivo confirmado: V1 uso una cuenta con estado sucio de una prueba anterior. Reejecutado con… |

### 4.C — Casos bloqueados y dependencias

Un caso del módulo no se pudo completar:

| TC | RF | Causa del bloqueo | Qué hace falta |
|---|---|---|---|
| M01-102 | RF-01 | El paso final (reintento de registro tras reconectar) requiere que el backend TEST acepte un token de reCAPTCHA. TEST valida el token con el servicio de Google, y QA no dispone de un token aceptado. No depende de otro módulo: es una configuración de TEST | Que Despliegue configure las claves de prueba de reCAPTCHA en TEST; con eso QA reejecuta el caso |

### 4.D — Estado del registro de incidencias

El registro (`incidencias.csv`, corte 2026-10-12) tiene **28 incidencias** del módulo: **27 cerradas** con retroprueba y **1 abierta**.

| Incidencia | Severidad | RF | Descripción |
|---|---|---|---|
| INC-M01-10-11 | Severo | RF-01 | Al enviar una solicitud de registro (POST /usuarios/) con un payload de usuario completo y válido, pero con captcha_token vacío o inválido, el backend responde HTTP 201 Created en lugar de rechazar la… |

---

## 5. Condiciones de la entrega

1. **Se entrega a Desarrollo** el conjunto de casos rechazados de la sección 4.A con su evidencia asociada.
2. **Criterio de aceptación del módulo:** el umbral global (≥ 85 %) se cumple y todos los RF tienen casos ejecutados. Los casos rechazados se entregan a Desarrollo clasificados con severidad **Medio** (decisión de QA). Resta obtener las firmas de este informe.
3. **Retorno esperado de Desarrollo:** por cada caso rechazado, rama/PR de corrección y confirmación de despliegue en TEST para que QA ejecute la retroprueba. No se cierra una incidencia sin retest.
4. **Acciones internas de QA antes de la certificación final:**
   - Registrar la incidencia de los casos marcados «por confirmar» cuando Desarrollo confirme el defecto.
   - Actualizar el estado del registro de incidencias con la evidencia del retest.
   - Obtener las firmas de la sección 6.
5. **Excepciones:** una excepción al umbral solo la autoriza Coordinación, y debe quedar registrada en el control de versiones de este informe.

---

## 6. Control del documento

| Versión | Fecha | Autor | Cambios |
|---|---|---|---|
| 1.0 – 2.1 | 2026-09-08 a 2026-09-13 | Equipo QA | Informes anteriores (`informe_consolidado_pruebas_M01.md`): 82.3 % → 91.5 % de aprobación; quedan como histórico |
| **2.0** | 2026-10-12 | Equipo QA | Informe de cierre con corte al 2026-10-12: 140/141 aprobados (99.3 %); casos rechazados detallados en 4.A; casos bloqueados y sus dependencias en 4.C; estado del registro de incidencias en 4.D |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
