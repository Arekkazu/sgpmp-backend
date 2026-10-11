# Informe consolidado de pruebas — Módulo 2 (Activos Biológicos)
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M02 — Activos Biológicos (`src/biological_assets/`) |
| Alcance | RF-33 a RF-52 (20 requisitos) + casos transversales (RF-00) |
| Período de ejecución | 2026-09-09 a 2026-10-11 (según la fecha de los commits de evidencia) |
| Fecha de corte del informe | 2026-10-11 |
| Ambientes | Backend TEST (`https://api.inmero.co/back-sigab-test`) · Frontend TEST (`https://api.inmero.co`) |
| Herramientas | Newman/Postman (65), Pytest (22), Cypress (10), Reevaluación documentada (10), Acta de ejecución (4) |
| Casos ejecutados | 111 de 111 (100 %) |
| Equipo QA | Daniela Castillo, Juan Esteban, Juan Manuel, Juan Pablo, Laura Lopez, Maria Jose, Sebastian |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (`QA-DASHBOARD-SGRPMP/`, tabla «Todos los casos de prueba»), evidencias en `tests/Test_Testing/Test_Modulo2/` |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso reejecutado después del corte puede cambiar de veredicto. Los estados de la tabla de casos son la fuente de este informe; el registro de incidencias (`incidencias.csv`) se usa solo para asociar cada caso rechazado con su incidencia cuando existe.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 111 | 100 % |
| Aprobados | **102** | **91.9 %** |
| Rechazados | 9 | 8.1 % |
| Pendientes | 0 | 0.0 % |

**El módulo supera el umbral de aprobación del 85 % (91.9 %).** Quedan 9 casos rechazados, que se consideran defectos abiertos; su detalle está en la sección 4.

### Verificación de los criterios de salida del plan de pruebas (§2.1)

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **102/111 = 91.9 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **21/21** (incluye transversales si aplica) | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | Este documento (pendiente de firmas) | ✅ (firmas pendientes) |

> Por decisión de QA, este informe no evalúa tres criterios del plan (§2.1): #3 defectos Crítico/Severo abiertos sin plan de mitigación, #4 casos rechazados sin incidencia formal y #5 casos con veredicto fijado a mano. Los casos rechazados se registran en la sección 4.A y, por decisión de QA, se clasifican con severidad **Medio**.

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-00 | Casos transversales | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-33 | Registro de activos biológicos | 11 | 11 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-34 | Asociación a infraestructura productiva | 2 | 2 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-35 | Gestión individual de activos | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-36 | Gestión poblacional de activos | 8 | 8 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-37 | Fases del ciclo productivo | 2 | 2 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-38 | Cierre del ciclo productivo | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-39 | Registro de eventos biológicos | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-40 | Eventos de crecimiento | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-41 | Eventos sanitarios | 5 | 4 | 1 | 0 | 80 % | ❌ Con fallas |
| RF-42 | Eventos reproductivos | 8 | 7 | 1 | 0 | 88 % | ⚠️ Aprobado con observaciones |
| RF-43 | Eventos productivos | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-44 | Estado del activo biológico | 1 | 1 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-45 | Bajas del activo | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-46 | Consulta de historial | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-47 | Ficha integral del activo | 2 | 2 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-48 | Transferencia interna | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-49 | Asociación con sensores IoT | 8 | 8 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-50 | Disponibilidad de datos para módulos analíticos | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-51 | Indicadores zootécnicos | 2 | 2 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-52 | Auditoría y trazabilidad de eventos | 11 | 4 | 7 | 0 | 36 % | ❌ Con fallas |
| **Total** | | **111** | **102** | **9** | **0** | **91.9 %** | |

---

## 3. Cobertura y método

- **Herramientas por caso:** Newman/Postman: 65 casos; Pytest: 22 casos; Cypress: 10 casos; Reevaluación documentada: 10 casos; Acta de ejecución: 4 casos.
- **Casos con veredicto de reevaluación documentada:** algunos casos rechazados en la primera evaluación se reejecutaron en `EvaluacionV2`/`EvaluacionV3` y su veredicto vigente consta en el acta de reevaluación (ver sección 4.B).
- **Evidencia:** cada caso conserva su reporte de ejecución (HTML/JSON/XML) y, en las reevaluaciones, un acta `.md` con la narrativa de la corrida.
- **Ambiente:** las ejecuciones vigentes se realizaron contra TEST con el backend en `https://api.inmero.co/back-sigab-test`; algunos casos históricos se ejecutaron contra la URL anterior de TEST (`sslip.io`).

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Casos rechazados (defectos abiertos)

| TC | RF | Responsable | Resultado | Motivo | Incidencia asociada | Severidad (QA) |
|---|---|---|---:|---|---|---|
| G049 | RF-41 | Daniela Castillo | 24/25 | Defecto de producto: tras volver el activo a ACTIVO por PATCH, el siguiente evento sanitario responde 409 `ESTADO_ACTIVO_INCONSISTENTE` (estado anterior 1 vs último registrado 3); dos cambios de estado el mismo día se ordenan mal en el historial (v3_1, 24/25) | INC-M02-60-G49 (Cerrado) | Medio |
| G059 | RF-42 | Juan Pablo | 7/11 | La prueba (v2.0, 3-oct) espera 409 en activos EN_TRATAMIENTO/AISLADO y el backend responde 201. RF-41 ya se corrigió el 2-oct para admitir esos estados; la especificación de RF-42 sigue diciendo «solo ACTIVO». Requiere decidir/corregir RF-42 y actualizar la prueba | por confirmar | Medio |
| G100 | RF-52 | Juan Pablo | 10/12 | 50 de 50 registros de auditoría con `id_evento_correlacionado` nulo | por confirmar | Medio |
| G101 | RF-52 | Juan Pablo | 8/11 | La bitácora no tiene trigger ni REVOKE (no es inmutable) y no define política de retención | por confirmar | Medio |
| G103 | RF-52 | Juan Pablo | 6/8 | 8 intentos de alteración dejan solo 1 fila de auditoría; sin trigger ni REVOKE | por confirmar | Medio |
| G104 | RF-52 | Juan Pablo | 6/7 | El registro de auditoría es síncrono dentro de la petición, sin timeout ni cola asíncrona | por confirmar | Medio |
| G105 | RF-52 | Juan Pablo | 5/6 | La auditoría no aplica restricción de alcance por rol (200 en vez de 403/404); reintento2 pasaba y reintento3 (5-oct) falla | INC-M02-84-G105 (Abierto) | Medio |
| G106 | RF-52 | Juan Pablo | 5/8 | Sin campo de correlación en RF-63 y sin trigger sobre la bitácora | por confirmar | Medio |
| G108 | RF-52 | Juan Pablo | 1/3 | RF-52 no expone `retencion_aplicable` y no hay política de retención | por confirmar | Medio |

### 4.B — Casos aprobados por reevaluación documentada

| TC | Fuente del veredicto |
|---|---|
| G042 | Estado general: PASS -- 10/10 tests en RESULTADOS/TC-M02-G42_resultado.md (Juan Manuel), pytest contra backend y BD de TEST reales. Confirma inmutabilidad de eventos (RF-39): no existe endpoint de edicion/eliminacion (5 rutas prob… |
| G078 | Estado general: PASS -- 4/4 tests en RESULTADOS/TC-M02-G78_resultado.md (Juan Manuel). TC-M02-131 (control de acceso a ficha integral sin permisos, 403) PASS de seguridad genuino; TC-M02-132 (accesos directos por rol) tambien PASS… |
| G079 | Reevaluacion (sep/oct-2026) en EvaluacionV2/Resultados/TC_M02_G79_reevaluacion_V2.md: veredicto APROBADO / SIN REGRESION. Newman 75/75, 0 fallos (reporte_tc_m02_g79_v2.html). El 201 es el codigo de exito del contrato vigente (RF-4… |
| G080 | Reevaluacion (sep/oct-2026) en EvaluacionV2/Resultados/TC_M02_G80_reevaluacion_V2.md: veredicto APROBADO / SIN REGRESION. Newman 146/146, 0 fallos (reporte_tc_m02_g80_v2.html). V1 Rechazado corregido; la auditoria RF-52 registro l… |
| G081 | Reevaluacion (sep/oct-2026) en EvaluacionV2/Resultados/TC_M02_G81_reevaluacion_V2.md: veredicto APROBADO / SIN REGRESION. Newman 103/103 (reporte_tc_m02_g81_v2.html) y pytest de rollback 6/6 (reporte_tc_m02_g81_rollback_v2.xml). B… |
| G083 | Reevaluacion V2 (20-sep-2026) en EvaluacionV2/Resultados/TC_M02_G83_reevaluacion_V2.md: APROBADO / SIN REGRESION (V1: RECHAZADO). Newman 132/134. Las 2 aserciones fallidas (TC-M02-308-B, Productor y Administrador, 'destino 50 INAC… |
| G093 | Reevaluacion (sep/oct-2026) en EvaluacionV3/RESULTADOS/G93-REEVAL-V3-20260927-191233/TC-M02-G93_reevaluacion_V3.md: veredicto APROBADO / SIN REGRESION. Newman 33/33, 0 fallos (newman-g93-v3.html). Sub-casos TC-M02-155, 156-A/B y 1… |
| G095 | Reevaluacion (sep/oct-2026) en EvaluacionV2/Resultados/TC_M02_G95_reevaluacion_V2.md: veredicto APROBADO / SIN REGRESION. Newman 17/17, 0 fallos (reporte_tc_m02_g95_v2.html). Defecto TC-M02-310 corregido (INC-M02-97-G95, PR #272).… |
| G096 | Reevaluacion (sep/oct-2026) en EvaluacionV2/Resultados/TC_M02_G96_reevaluacion_V2.md: veredicto APROBADO / SIN REGRESION. Newman 71/71, 0 fallos (reporte_tc_m02_g96_v2.html). TC-M02-160 y 162 ahora devuelven 422 INDICADOR_NO_DISPO… |
| G097 | Reevaluacion (sep/oct-2026) en EvaluacionV2/Resultados/TC_M02_G97_reevaluacion_V2.md: veredicto APROBADO / SIN REGRESION. Newman 50/50 y pytest 7/7, 0 fallos (reporte_tc_m02_g97_v2_newman.html / _pytest.xml). DEF-G97-01 corregido:… |

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
| 1.0 | 2026-10-11 | Equipo QA | Versión inicial: 102/111 aprobados (91.9 %); rechazados detallados en 4.A |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
