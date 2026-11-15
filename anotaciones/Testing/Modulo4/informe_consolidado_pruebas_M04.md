# Informe consolidado de pruebas — Módulo 4 (Predicción y Motor IA) — v1.0
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M04 — Predicción / Motor IA (`src/prediction/`) |
| Alcance | RF-64 a RF-73 (10 requisitos) |
| Período de ejecución | 2026-08-27 a 2026-11-15 (según la fecha de los commits de evidencia) |
| Fecha de corte del informe | 2026-11-15 |
| Ambientes | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Herramientas | Corrida documentada (resultado.json) (16), Acta de ejecución / veredicto declarado (14), Newman/Postman (13), Pytest/JUnit (7), Cypress (7), Pytest (2), Sin evidencia ejecutada (1) |
| Casos ejecutados | 59 de 60 (98.3 %) |
| Equipo QA | Daniela Castillo Vargas, Juan Esteban, Juan Manuel Gomez Mendez, Juan Pablo, Juan Sebastian Gutierrez, Laura Valentina López Cordoba |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (tabla «Todos los casos de prueba»), evidencias en `tests/Test_Testing/Test_Modulo4/` |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso reejecutado después del corte puede cambiar de veredicto.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 60 | 100 % |
| Aprobados | **51** | **85.0 %** |
| Rechazados | 8 | 13.3 % |
| Pendientes | 1 | 1.7 % |

**El módulo supera el umbral de aprobación del 85 % (85.0 %).** Quedan 8 casos rechazados y 1 pendientes, cuyo detalle está en la sección 4.

### Verificación de los criterios de salida del plan de pruebas

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **51/60 = 85.0 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **10/10** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | Este documento (pendiente de firmas) | ✅ (firmas pendientes) |

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-64 | Catálogo de patologías | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-65 | Configuración del motor IA | 3 | 3 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-66 | Inferencia de patologías en tiempo real | 4 | 2 | 2 | 0 | 50 % | ❌ Con fallas |
| RF-67 | Historial de diagnósticos | 2 | 2 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-68 | Modelo de riesgo de contagio | 8 | 4 | 4 | 0 | 50 % | ❌ Con fallas |
| RF-69 | Validación y versionado de modelos IA | 8 | 8 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-70 | Actualización OTA del modelo en el borde | 2 | 2 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-71 | Reentrenamiento del modelo | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-72 | Retroalimentación clínica del veterinario | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-73 | Auditoría del motor de predicción | 11 | 8 | 2 | 1 | 73 % | ❌ Con fallas |
| **Total** | | **60** | **51** | **8** | **1** | **85.0 %** | |

---

## 3. Cobertura y método

- **Herramientas por caso:** Corrida documentada (resultado.json): 16 casos; Acta de ejecución / veredicto declarado: 14 casos; Newman/Postman: 13 casos; Pytest/JUnit: 7 casos; Cypress: 7 casos; Pytest: 2 casos; Sin evidencia ejecutada: 1 casos.
- **Responsables de ejecución:** Juan Esteban: 17; Daniela Castillo Vargas: 12; Juan Sebastian Gutierrez: 11; Juan Pablo: 9; Juan Manuel Gomez Mendez: 6; Laura Valentina López Cordoba: 5.
- **Evidencia:** cada caso conserva su reporte de ejecución (HTML/JSON/XML) o, en los casos con acta, el registro de la corrida.
- **Ambiente:** las ejecuciones se realizaron contra TEST con el backend en `https://api.inmero.co/back-sigab-test`.

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Casos rechazados y pendientes

| TC | RF | Responsable | Resultado | Estado | Motivo | Incidencia asociada |
|---|---|---|---:|---|---|---|
| G018 | RF-66 | Daniela Castillo Vargas | 3/4 | Rechazado | Endpoint de inferencia inexistente (rutas candidatas devuelven 404/405) | por confirmar |
| G024 | RF-66 | Daniela Castillo Vargas | 3/4 | Rechazado | Bloqueo: sin dataset etiquetado de 4 clases ni nodo Edge aislable para medir F1/recall y disponibilidad | INC-M04-195-G024 (Abierto, Medio) |
| G029 | RF-68 | Daniela Castillo Vargas | 27/28 | Rechazado | Con densidad inválida responde 400 y no usa el histórico de ocupación de 30 días | INC-M04-218-G029 (Abierto, Medio) |
| G030 | RF-68 | Daniela Castillo Vargas | 96/97 | Rechazado | No aplica la cobertura mínima de inferencias (55 % corre normal; 45 % corre sin Fs) | INC-M04-219-G030 (Abierto, Severo) |
| G032 | RF-68 | Daniela Castillo Vargas | 36/37 | Rechazado | Recálculo dentro de 5 s responde 429; modo MVP inexistente (422 `MODO_EJECUCION_INVALIDO`) | INC-M04-221-G032 (Abierto, Medio); INC-M04-220-G032 (Abierto, Medio) |
| G034 | RF-68 | Daniela Castillo Vargas | 69/72 | Rechazado | Cuenta salidas de otros lotes y el resultado de contagio no aparece en el historial | INC-M04-223-G034 (Abierto, Medio); INC-M04-222-G034 (Abierto, Severo) |
| G082 | RF-73 | Juan Sebastian Gutierrez | — | Pendiente | Sin veredicto: carpeta sin evidencia ejecutada | por confirmar |
| G084 | RF-73 | Juan Sebastian Gutierrez | 3/7 | Rechazado | Pipeline de reentrenamiento y scheduler de degradación no implementados (3 subcasos fallan) | INC-M04-153-G084 (Abierto, Severo) |
| G092 | RF-73 | Juan Sebastian Gutierrez | 1/4 | Rechazado | Cadenas causales y filtro `correlacion_id` no disponibles (RF-66 sin productores) | INC-M04-209-G092 (Abierto, Medio) |

### 4.B — Casos bloqueados y dependencias

- **RF-66 (G018, G024)**: falta el endpoint de inferencia en línea y los insumos de validación (dataset etiquetado, nodo Edge aislable).
- **RF-68 (G029, G030, G032, G034)**: reglas del modelo de contagio por ajustar (cobertura mínima, histórico de densidad, modo MVP, aislamiento por lote).
- **RF-73 (G084, G092, G082)** depende de RF-66 y del reentrenamiento (RF-71), aún sin implementar.

### 4.C — Estado del registro de incidencias

El registro (corte 2026-11-15) tiene **54 incidencias** del módulo: **1 cerradas** y **53 abiertas**. Las abiertas por requisito:

| RF | Incidencias abiertas |
|---|---:|
| RF-57 | 1 |
| RF-59 | 2 |
| RF-62 | 1 |
| RF-64 | 3 |
| RF-65 | 3 |
| RF-66 | 2 |
| RF-67 | 3 |
| RF-68 | 7 |
| RF-69 | 3 |
| RF-70 | 2 |
| RF-71 | 7 |
| RF-72 | 5 |
| RF-73 | 10 |
| Sin RF | 4 |

Por severidad: Medio 22, Severo 20, Bajo 6, Alta 3, Crítico 2.

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
| **1.0** | 2026-11-15 | Equipo QA | Primer informe consolidado: 51/60 aprobados (85.0 %); casos rechazados en 4.A; dependencias en 4.B; incidencias en 4.C |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
