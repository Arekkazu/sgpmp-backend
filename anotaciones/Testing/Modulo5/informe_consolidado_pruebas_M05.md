# Informe consolidado de pruebas — Módulo 5 (Suministros) — v1.0
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M05 — Suministros (`src/supplies/`) |
| Alcance | RF-74 a RF-81 (8 requisitos) |
| Período de ejecución | 2026-08-27 a 2026-11-15 (según la fecha de los commits de evidencia) |
| Fecha de corte del informe | 2026-11-15 |
| Ambientes | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Herramientas | Newman/Postman (20), Cypress (19), Pytest/JUnit (5) |
| Casos ejecutados | 44 de 44 (100.0 %) |
| Equipo QA | Juan Manuel Gomez Mendez, Juan Sebastian Gutierrez |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (tabla «Todos los casos de prueba»), evidencias en `tests/Test_Testing/Test_Modulo5/` |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso reejecutado después del corte puede cambiar de veredicto.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 44 | 100 % |
| Aprobados | **40** | **90.9 %** |
| Rechazados | 4 | 9.1 % |
| Pendientes | 0 | 0.0 % |

**El módulo supera el umbral de aprobación del 85 % (90.9 %).** Quedan 4 casos rechazados y 0 pendientes, cuyo detalle está en la sección 4.

### Verificación de los criterios de salida del plan de pruebas

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **40/44 = 90.9 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **8/8** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | Este documento (pendiente de firmas) | ✅ (firmas pendientes) |

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-74 | Índice de Conversión Alimenticia (ICA) y batch | 7 | 5 | 2 | 0 | 71 % | ❌ Con fallas |
| RF-75 | Consumo de alimentos | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-76 | Aplicación de medicamentos | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-77 | Reporte de gastos acumulados | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-78 | Costeo directo por ciclo | 6 | 5 | 1 | 0 | 83 % | ❌ Con fallas |
| RF-79 | Provisión / consolidado de ciclo (NIC 41) | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-80 | Auditoría de suministros | 4 | 3 | 1 | 0 | 75 % | ❌ Con fallas |
| RF-81 | Historial y trazabilidad de suministros | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| **Total** | | **44** | **40** | **4** | **0** | **90.9 %** | |

---

## 3. Cobertura y método

- **Herramientas por caso:** Newman/Postman: 20 casos; Cypress: 19 casos; Pytest/JUnit: 5 casos.
- **Responsables de ejecución:** Juan Manuel Gomez Mendez: 23; Juan Sebastian Gutierrez: 21.
- **Evidencia:** cada caso conserva su reporte de ejecución (HTML/JSON/XML) o, en los casos con acta, el registro de la corrida.
- **Ambiente:** las ejecuciones se realizaron contra TEST con el backend en `https://api.inmero.co/back-sigab-test`.

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Casos rechazados y pendientes

| TC | RF | Responsable | Resultado | Estado | Motivo | Incidencia asociada |
|---|---|---|---:|---|---|---|
| G002 | RF-74 | Juan Manuel Gomez Mendez | 114/116 | Rechazado | ICA crítico: el aviso «Urgencia ALTA» no llega al Veterinario/Productor, muestra id interno y valor crudo; 500 en el cálculo crítico | INC-M05-368-G02 (Abierto, Medio); INC-M05-367-G02 (Abierto, Medio); INC-M05-357-G02 (Abierto, Bajo); INC-M05-338-G02 (Abierto, Severo) |
| G007 | RF-74 | Juan Manuel Gomez Mendez | 5/8 | Rechazado | Batch ICA: un fallo técnico de BD se cuenta como procesado, no avisa al Administrador y el panel informa 0 pendientes | INC-M05-259-G07 (Abierto, Severo) |
| G031 | RF-78 | Juan Manuel Gomez Mendez | 3/4 | Rechazado | Costeo directo: esperas entre reintentos [1, 3] en vez de [1, 3, 5] s | INC-M05-264-G31 (Abierto, Bajo) |
| G037 | RF-80 | Juan Sebastian Gutierrez | 11/14 | Rechazado | Rechazos de negocio (409/422) de costeo, consolidado e historial no quedan en la bitácora de auditoría | INC-M05-353-G37 (Abierto, Severo); INC-M05-275-G37 (Abierto, Medio) |

### 4.B — Casos bloqueados y dependencias

Los 4 rechazados son defectos propios de Suministros, sin dependencias de otros módulos: manejo de fallos técnicos de BD (G007, G031), aviso de conversión crítica y error 500 en el cálculo (G002) y auditoría de rechazos de negocio (G037). No hay casos pendientes.

### 4.C — Estado del registro de incidencias

El registro (corte 2026-11-15) tiene **42 incidencias** del módulo: **12 cerradas** y **30 abiertas**. Las abiertas por requisito:

| RF | Incidencias abiertas |
|---|---:|
| RF-74 | 7 |
| RF-75 | 1 |
| RF-76 | 4 |
| RF-77 | 4 |
| RF-78 | 4 |
| RF-79 | 1 |
| RF-80 | 6 |
| RF-81 | 3 |

Por severidad: Medio 20, Bajo 6, Severo 3, Crítico 1.

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
| **1.0** | 2026-11-15 | Equipo QA | Primer informe consolidado: 40/44 aprobados (90.9 %); casos rechazados en 4.A; dependencias en 4.B; incidencias en 4.C |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
