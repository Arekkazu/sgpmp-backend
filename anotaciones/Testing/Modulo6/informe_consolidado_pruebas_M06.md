# Informe consolidado de pruebas — Módulo 6 (Valoración financiera de activos biológicos) — v1.0
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M06 — Valoración financiera (`src/financial_valuation/`) |
| Alcance | RF-82 a RF-94 y RF-COT (14 requisitos) |
| Período de ejecución | 2026-11-07 a 2026-11-16 (según la fecha de los reportes y de los commits de evidencia) |
| Fecha de corte del informe | 2026-11-16 |
| Ambientes | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Herramientas | Pytest (54), Corridas documentadas (resumen/resultado JSON) (34), Newman/Postman (24), Actas con dictamen oficial de QA (6), Cypress/Mochawesome (1) |
| Casos con veredicto | 119 de 119 (100.0 %) |
| Equipo QA | Daniela Castillo Vargas, Juan Esteban, Juan Parra, Julian Badillo, Laura Valentina López Cordoba |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (tabla «Todos los casos de prueba»), evidencias en `tests/Test_Testing/Test_Modulo6/` |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso reejecutado después del corte puede cambiar de veredicto.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 119 | 100 % |
| Aprobados | **104** | **87.4 %** |
| Rechazados | 15 | 12.6 % |
| Pendientes | 0 | 0.0 % |

**El módulo supera el umbral de aprobación del 85 % (87.4 %).** Quedan 15 casos rechazados y 0 pendientes, cuyo detalle está en la sección 4.

### Verificación de los criterios de salida del plan de pruebas

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **104/119 = 87.4 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **14/14** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | Este documento (pendiente de firmas) | ✅ (firmas pendientes) |

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-82 | Reconocimiento inicial del activo biológico | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-83 | Medición posterior del valor razonable | 7 | 5 | 2 | 0 | 71 % | ❌ Con fallas |
| RF-84 | Valor razonable menos costos de venta | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-85 | Reconocimiento del producto agrícola en la cosecha | 8 | 5 | 3 | 0 | 62 % | ❌ Con fallas |
| RF-86 | Registro automático de variaciones de valor | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-87 | Cierre mensual y revaluación de activos | 6 | 5 | 1 | 0 | 83 % | ❌ Con fallas |
| RF-88 | Valor en libros y control de valores negativos | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-89 | Precios de referencia y sus fuentes | 8 | 7 | 1 | 0 | 88 % | ⚠️ Parcial |
| RF-90 | Costos de mantenimiento (capitalización o gasto) | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-91 | Verificación de la cadena de evidencia contable | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-92 | Informe de valoración de activos biológicos | 12 | 10 | 2 | 0 | 83 % | ❌ Con fallas |
| RF-93 | Estado de resultados de activos biológicos | 12 | 9 | 3 | 0 | 75 % | ❌ Con fallas |
| RF-94 | Repositorio de eventos contables | 12 | 10 | 2 | 0 | 83 % | ❌ Con fallas |
| RF-COT | Cotizaciones de precios | 5 | 4 | 1 | 0 | 80 % | ❌ Con fallas |
| **Total** | | **119** | **104** | **15** | **0** | **87.4 %** | |

---

## 3. Cobertura y método

- **Herramientas por caso:** Pytest: 54 casos; Corridas documentadas (resumen/resultado JSON): 34 casos; Newman/Postman: 24 casos; Actas con dictamen oficial de QA: 6 casos; Cypress/Mochawesome: 1 casos.
- **Responsables de ejecución:** Daniela Castillo Vargas: 31; Laura Valentina López Cordoba: 25; Julian Badillo: 24; Juan Parra: 24; Juan Esteban: 15.
- **Evidencia:** cada caso conserva su reporte de ejecución (HTML/JSON/XML) o, en los casos con acta, el registro de la corrida y el dictamen oficial de QA.
- **Reejecuciones:** varios casos tuvieron una primera evaluación y una o más reevaluaciones; para cada subcaso vale el resultado de la corrida más reciente.
- **Ambiente:** las ejecuciones se realizaron contra TEST con el backend en `https://api.inmero.co/back-sigab-test`.

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Casos rechazados y pendientes

| TC | RF | Responsable | Resultado | Estado | Motivo | Incidencia asociada |
|---|---|---|---:|---|---|---|
| G014 | RF-83 | Daniela Castillo Vargas | 10/11 | Rechazado | Un activo no elegible (PENDIENTE_RECONOCIMIENTO) excluido de la medición no deja registro de auditoría `MEDICION_EXCLUIDA` con su motivo | INC-M06-313-G14 (Abierto, Severo); INC-M06-312-G14 (Abierto, Medio) |
| G015 | RF-83 | Daniela Castillo Vargas | 7/10 | Rechazado | No se logra el escenario «períodos distintos»: el activo queda con mediciones en un solo período tras el cierre del período 1 | INC-M06-314-G15 (Abierto, Medio) |
| G024 | RF-85 | Daniela Castillo Vargas | 3/8 | Rechazado | Tras la cosecha total el activo no queda en 0,0000 ni pasa a COSECHADO_COMPLETAMENTE / baja: queda ACTIVO con la medición anterior | INC-M06-364-G24 (Abierto, Medio); INC-M06-361-G24 (Abierto, Severo); INC-M06-320-G24 (Abierto, Severo) |
| G027 | RF-85 | Daniela Castillo Vargas | 13/14 | Rechazado | Con precio manual justificado registrado, la cosecha pendiente no se reconoce (la cola de eventos responde SIN_EFECTO) | INC-M06-363-G27 (Abierto, Severo); INC-M06-324-G27 (Abierto, Medio); INC-M06-323-G27 (Abierto, Severo) |
| G030 | RF-85 | Daniela Castillo Vargas | 8/9 | Rechazado | El valor del activo queda negativo: las reducciones acumuladas (20 680 000) superan el valor inicial (18 800 000) | INC-M06-362-G30 (Abierto, Severo); INC-M06-326-G30 (Abierto, Severo); INC-M06-325-G30 (Abierto, Medio) |
| G044 | RF-87 | Juan Esteban | 2/3 | Rechazado | Períodos cerrados responden 404 en lugar de informar su inmutabilidad; falla el escenario de cierre concurrente (TC-M06-030) | INC-M06-93-G44 (Abierto, Medio); INC-M06-350-G44 (Abierto, Alta) |
| G062 | RF-92 | Julian Badillo | 33/34 | Rechazado | Una petición termina por `ESOCKETTIMEDOUT`; sin incidencia registrada, por confirmar si es de la prueba o del servicio | por confirmar |
| G063 | RF-92 | Julian Badillo | 16/17 | Rechazado | Para el activo QA-M06-COSTO-01 el valor «No determinable» se repite entre períodos cuando se esperaba una variación; sin incidencia registrada, por confirmar | por confirmar |
| G071 | RF-93 | Juan Parra | 9/13 | Rechazado | Estado de resultados: una baja por venta no contribuye a ningún componente de INGRESOS (se acumula como gasto en `bajas_activos`) y los componentes de ingresos reales no coinciden con los de la ficha | INC-M06-364-G71 (Abierto, Alta); INC-M06-285-G71 (Cerrado, Medio) |
| G074 | RF-93 | Juan Parra | 0/5 | Rechazado | Conciliación del estado de resultados: el error 422 `ESTADO_RESULTADOS_NO_CONCILIA`, el aviso al Contador y el registro `ERROR_CONCILIACION` no están desplegados | INC-M06-290-G74 (Cerrado, Medio) |
| G080 | RF-93 | Juan Parra | 5/7 | Rechazado | Ante un fallo del cálculo no se registra en auditoría y el cálculo combina todas las fuentes sin identificar cuál falló | INC-M06-298-G80 (Abierto, Severo) |
| G093 | RF-94 | Juan Parra | 6/11 | Rechazado | Consulta de eventos sin filtros implícitos por rol, y `monto_afectado` se devuelve sin formato de moneda (CA-13) | INC-M06-365-G93 (Abierto, Medio); INC-M06-360-G93 (Abierto, Alta) |
| G094 | RF-94 | Juan Parra | 2/9 | Rechazado | El repositorio solo recibe eventos con `modulo_origen` fijo en «M06» y no existe el endpoint centralizado `GET /api/v1/audit/events` | INC-M06-366-G94 (Abierto, Medio); INC-M06-362-G94 (Abierto, Bajo) |
| G109 | RF-89 | Laura Valentina López Cordoba | 3/6 | Rechazado | Los avisos al Contador por vencimiento de precio (30, 15 y 7 días) no se generan: 0 avisos, se esperaba 1 en cada plazo | por confirmar |
| G117 | RF-COT | Laura Valentina López Cordoba | 1/3 | Rechazado | Cotización con valor propuesto ≤ 0: el backend responde 400 `VAL_ENTRADA` en lugar de 422 `VALOR_COTIZACION_INVALIDO` | INC-M06-88-G117 (Abierto, Medio) |

### 4.B — Casos bloqueados y dependencias

- **RF-93 (G074, G080):** los mecanismos que esperan los casos (error 422 `ESTADO_RESULTADOS_NO_CONCILIA`, aviso al Contador con registro `ERROR_CONCILIACION` y registro en auditoría del fallo de cada fuente del cálculo) llegan con un cambio (PR #1121) que aún no está desplegado en TEST. Ambos casos deben reejecutarse tras el despliegue.
- **RF-85 (G024, G027, G030):** la corrección anunciada para el cierre de la cosecha total no está efectiva en TEST: el rerun del 2026-11-13 sigue fallando. Verificar el despliegue antes de reejecutar.
- **RF-89 (G109):** los avisos diarios al Contador por vencimiento de precios no se generan. El caso G104 se aprobó con alcance delimitado y deja pendiente esa misma validación (CA-8 / FA-5) por falta de evidencia.
- **G062 y G063 (RF-92)** no tienen incidencia registrada: hay que confirmar si el fallo es del servicio o de la prueba (timeout de la petición; comparación de «No determinable» entre períodos).
- No hay casos pendientes.

### 4.C — Casos aprobados con alcance delimitado

Tres casos de RF-89 quedaron aprobados por decisión de QA con un alcance menor al plan original; el manual de usuario debe reflejarlo:

| TC | RF | Alcance de la aprobación |
|---|---|---|
| G102 | RF-89 | Aprobados TC-M06-16, 17 y 18 (HTTP 201, precio aplicado, históricos en SUPERADO, auditoría registrada). Los subcasos TC-M06-19 a 21 y el rechazo por justificación corta no se probarán. Observación: la especificación pide HTTP 400 para justificación corta y el backend responde 422 |
| G104 | RF-89 | Aprobados TC-M06-25, 26 y 29 (alcance delimitado). Queda pendiente la validación complementaria del aviso diario al Contador (CA-8 / FA-5), sin evidencia |
| G107 | RF-89 | Verificación de solo lectura de los precios y las rutas publicadas. La recepción y confirmación de precios externos aún no está desarrollada, por lo que no se pudo ejecutar de extremo a extremo; se aprueba por decisión de QA y se retoma cuando exista |

### 4.D — Estado del registro de incidencias

El registro (corte 2026-11-16) tiene **108 incidencias** del módulo: **12 cerradas** y **96 abiertas**. Las abiertas por requisito:

| RF | Incidencias abiertas |
|---|---:|
| RF-82 | 6 |
| RF-83 | 8 |
| RF-84 | 6 |
| RF-85 | 11 |
| RF-86 | 6 |
| RF-87 | 8 |
| RF-88 | 4 |
| RF-89 | 5 |
| RF-90 | 4 |
| RF-91 | 4 |
| RF-92 | 6 |
| RF-93 | 9 |
| RF-94 | 12 |
| RF-COT | 6 |
| Sin RF | 1 |

Por severidad: Medio 47, Severo 20, Alta 18, Bajo 6, Crítico 4, Alto 1.

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
| **1.0** | 2026-11-16 | Equipo QA | Primer informe consolidado: 104/119 aprobados (87.4 %); casos rechazados en 4.A; dependencias en 4.B; alcances delimitados en 4.C; incidencias en 4.D |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
