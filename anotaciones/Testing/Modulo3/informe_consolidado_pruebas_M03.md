# Informe consolidado de pruebas — Módulo 3 (Telemetría IoT) — v1.0
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M03 — Telemetría IoT (`src/telemetry/`) |
| Alcance | RF-53 a RF-63 (11 requisitos) |
| Período de ejecución | 2026-08-27 a 2026-11-15 (según la fecha de los commits de evidencia) |
| Fecha de corte del informe | 2026-11-15 |
| Ambientes | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Herramientas | Acta de ejecución / veredicto declarado (51), Newman/Postman (25), Pytest/JUnit (10), Corrida documentada (resultado.json) (8), Cypress (5), Pytest (4) |
| Casos ejecutados | 101 de 103 (98.1 %) |
| Equipo QA | Daniela Castillo Vargas, Juan Esteban, Juan Manuel Gomez Mendez, Juan Pablo, Juan Sebastian Gutierrez, Laura Valentina López Cordoba |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (tabla «Todos los casos de prueba»), evidencias en `tests/Test_Testing/Test_Modulo3/` |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso reejecutado después del corte puede cambiar de veredicto.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 103 | 100 % |
| Aprobados | **88** | **85.4 %** |
| Rechazados | 13 | 12.6 % |
| Pendientes | 2 | 1.9 % |

**El módulo supera el umbral de aprobación del 85 % (85.4 %).** Quedan 13 casos rechazados y 2 pendientes, cuyo detalle está en la sección 4.

### Verificación de los criterios de salida del plan de pruebas

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **88/103 = 85.4 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **11/11** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | Este documento (pendiente de firmas) | ✅ (firmas pendientes) |

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-53 | Recepción y almacenamiento de telemetría | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-54 | Buffer local y reenvío (store-and-forward) | 8 | 8 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-55 | Detección de desviaciones en el borde (Edge) | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-56 | Envío de paquetes de inferencia al motor IA (M04) | 6 | 5 | 0 | 1 | 83 % | ❌ Con fallas |
| RF-57 | Generación y gestión de alertas ambientales | 15 | 3 | 12 | 0 | 20 % | ❌ Con fallas |
| RF-58 | Monitoreo ambiental en tiempo real | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-59 | Historial de lecturas ambientales | 13 | 12 | 0 | 1 | 92 % | ⚠️ Parcial |
| RF-60 | Detección de sensores sin reporte | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-61 | Asociación de lecturas a activo o lote | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-62 | Evaluación de calidad de datos del sensor | 8 | 7 | 1 | 0 | 88 % | ⚠️ Parcial |
| RF-63 | Auditoría de telemetría y alertas | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| **Total** | | **103** | **88** | **13** | **2** | **85.4 %** | |

---

## 3. Cobertura y método

- **Herramientas por caso:** Acta de ejecución / veredicto declarado: 51 casos; Newman/Postman: 25 casos; Pytest/JUnit: 10 casos; Corrida documentada (resultado.json): 8 casos; Cypress: 5 casos; Pytest: 4 casos.
- **Responsables de ejecución:** Daniela Castillo Vargas: 25; Juan Manuel Gomez Mendez: 20; Laura Valentina López Cordoba: 18; Juan Pablo: 15; Juan Sebastian Gutierrez: 13; Juan Esteban: 12.
- **Evidencia:** cada caso conserva su reporte de ejecución (HTML/JSON/XML) o, en los casos con acta, el registro de la corrida.
- **Ambiente:** las ejecuciones se realizaron contra TEST con el backend en `https://api.inmero.co/back-sigab-test`.

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Casos rechazados y pendientes

| TC | RF | Responsable | Resultado | Estado | Motivo | Incidencia asociada |
|---|---|---|---:|---|---|---|
| G056 | RF-56 | Laura Valentina López Cordoba | — | Pendiente | Sin veredicto: reintentos, backoff y cola de reenvío de paquetes de inferencia no implementados | INC-M03-113-G56 (Abierto, Severo) |
| G068 | RF-57 | Daniela Castillo Vargas | 37/40 | Rechazado | No evalúa el valor contra umbrales y rangos: la severidad se copia de `severidad_edge` | INC-M03-162-G68 (Abierto, Severo) |
| G069 | RF-57 | Daniela Castillo Vargas | 21/100 | Rechazado | Rechaza con 422 `REGLA_COMPUESTA_NO_ACTIVADA` toda lectura aislada fuera de banda | INC-M03-240-G69 (Abierto, Medio) |
| G070 | RF-57 | Daniela Castillo Vargas | 9/10 | Rechazado | Alerta compuesta sin comprobar condición mínima (variables requeridas y THI) | INC-M03-163-G70 (Abierto, Medio) |
| G071 | RF-57 | Daniela Castillo Vargas | 34/49 | Rechazado | Correlación de reglas (E14) no implementada; tipos de evento de bitácora no registrados | INC-M03-165-G71 (Abierto, Medio); INC-M03-164-G71 (Abierto, Crítico) |
| G072 | RF-57 | Daniela Castillo Vargas | 55/56 | Rechazado | Espera 422 y el backend responde 200/201 (sin incidencia asociada: por confirmar) | por confirmar |
| G074 | RF-57 | Daniela Castillo Vargas | 16/79 | Rechazado | Dos eventos de IA del mismo activo dentro de la ventana generan dos alertas en vez de una | INC-M03-241-G74 (Abierto, Medio) |
| G075 | RF-57 | Daniela Castillo Vargas | 38/45 | Rechazado | Reevaluación de alertas tras recuperación del motor IA (E3/E16/CA-6) no existe | INC-M03-167-G75 (Abierto, Severo) |
| G076 | RF-57 | Daniela Castillo Vargas | 11/24 | Rechazado | Parámetro `umbral_confianza_edge_ia` no cargado en TEST: 503 `PARAMETRO_CONFIGURACION_AUSENTE` | INC-M03-168-G76 (Abierto, Severo) |
| G077 | RF-57 | Daniela Castillo Vargas | 13/19 | Rechazado | La alerta no asocia el contexto del activo y no notifica al administrador | INC-M03-170-G77 (Abierto, Medio); INC-M03-169-G77 (Abierto, Severo) |
| G078 | RF-57 | Daniela Castillo Vargas | 90/104 | Rechazado | Listado de alertas responde 500 con filtros fuera de catálogo (debe ser 400) | INC-M03-171-G78 (Abierto, Medio) |
| G085 | RF-57 | Daniela Castillo Vargas | 39/41 | Rechazado | Flujo E9 (variable sin umbrales) no implementado | INC-M03-173-G85 (Abierto, Crítico) |
| G086 | RF-57 | Daniela Castillo Vargas | 72/113 | Rechazado | No aplica la ventana de confirmación temporal | INC-M03-174-G86 (Abierto, Severo) |
| G124 | RF-59 | Juan Esteban | — | Pendiente | Diferido: la exportación PDF/Excel (RF-59) responde 503 `503`; repetir cuando el módulo de reportes genere archivos | por confirmar |
| G167 | RF-62 | Juan Sebastian Gutierrez | 23/32 | Rechazado | Defecto de producto: `posible_drift` mal calculado (oráculo 75 vs 100, 75 vs 90) en evaluación de calidad | INC-M03-254-G167 (Abierto, Severo); INC-M03-123-G167 (Abierto, Severo) |

### 4.B — Casos bloqueados y dependencias

- **RF-57** concentra 12 de los 13 rechazados: la generación de alertas copia la severidad enviada por el borde sin evaluar umbrales ni reglas compuestas. Es una deuda funcional de un mismo origen.
- **G056** depende de la política de reintentos y cola de reenvío hacia el motor IA. **G124** (exportación PDF/Excel) depende del módulo de reportes.

### 4.C — Estado del registro de incidencias

El registro (corte 2026-11-15) tiene **138 incidencias** del módulo: **11 cerradas** y **127 abiertas**. Las abiertas por requisito:

| RF | Incidencias abiertas |
|---|---:|
| RF-24 | 2 |
| RF-26 | 1 |
| RF-49 | 2 |
| RF-53 | 8 |
| RF-54 | 3 |
| RF-55 | 16 |
| RF-56 | 9 |
| RF-57 | 21 |
| RF-58 | 8 |
| RF-59 | 15 |
| RF-60 | 11 |
| RF-61 | 5 |
| RF-62 | 14 |
| RF-63 | 4 |
| Sin RF | 8 |

Por severidad: Medio 66, Severo 42, Alta 6, Crítico 5, Bajo 4, Leve 3, 2 dias habiles 1.

> El estado de cada incidencia es el que consta en el registro; la retroprueba posterior a la corrección puede cambiar el estado sin reflejarse todavía en él.

---

## 5. Condiciones de la entrega

1. **Se entrega a Desarrollo** el conjunto de casos rechazados y pendientes de la sección 4.A con su evidencia asociada.
2. **Criterio de aceptación del módulo:** el umbral global (≥ 85 %) se cumple y todos los RF tienen casos ejecutados. Resta obtener las firmas de este informe.
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
| **1.0** | 2026-11-15 | Equipo QA | Primer informe consolidado: 88/103 aprobados (85.4 %); casos rechazados en 4.A; dependencias en 4.B; incidencias en 4.C |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
