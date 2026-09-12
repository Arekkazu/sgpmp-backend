# Informe consolidado de pruebas — Módulo 9 (Configuración)
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M09 — Configuración / Parámetros Generales (`src/configuration/`) |
| Alcance | RF-15 a RF-32 (18 requisitos) |
| Período de ejecución | 2026-09-03 a 2026-09-08 |
| Fecha de corte del informe | 2026-09-08 |
| Ambientes | Backend TEST (`sigab-backendtest-…/api-sgpmp-test`) · Frontend TEST (`sigab-frontendtest-…`) |
| Herramientas | Newman/Postman (API), Pytest (backend + seguridad OWASP), Cypress (frontend), k6 (rendimiento) |
| Casos ejecutados | 102 de 129 (79.1 %) |
| Equipo QA | Juan Pablo, Laura Lopez, Juan Manuel, Sebastian, Daniela Castillo, Juan Esteban |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (`qa-dashboard/`), evidencias en `tests/Test_Testing/Test_Modulo9/` y `testing/test_testing/Modulo9/` |

> ⚠️ **Advertencia crítica sobre el ambiente de pruebas.** Buena parte de las
> ejecuciones se corrió contra un despliegue de TEST basado en la rama de QA
> `qa/juan-esteban-m09`, que **divergió antes del PR #146 y perdió el fix
> `use_insertmanyvalues=False`** (`src/shared/database.py`). Ese ajuste ya está en
> `dev`/`rc.33`. En consecuencia, el bloque de fallos "HTTP 500 — Error inesperado
> en base de datos" (sección 5.A) **no refleja el comportamiento del build
> actual** y requiere redespliegue de TEST desde `rc.33` y reejecución. Ver
> `inc_m09_umbrales_500_enum_insertmanyvalues.md`.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| **Total de casos** | 129 | 100 % |
| Aprobados | 70 | **54.3 %** |
| Rechazados | 32 | 24.8 % |
| Pendientes de ejecución | 27 | 20.9 % |

```
Aprobado    ██████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░  54.3%
Rechazado   ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  24.8%
Pendiente   ██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  20.9%
```

**Veredicto del módulo: NO CONFORME — no cumple el umbral del 85 %.**

Con 70 de 129 casos aprobados (54.3 %), el módulo está **30.7 puntos por debajo**
del umbral de aceptación. Incluso en el escenario optimista de que los 27 casos
pendientes se aprueben en su totalidad, la cobertura llegaría al 75.2 % — aún por
debajo del 85 %. El cierre del módulo exige **corregir defectos y reejecutar**,
no solo completar la ejecución pendiente.

El resultado se explica por tres factores, en orden de impacto:

1. **Ambiente de TEST desactualizado** (sección 4) — ~16 rechazos son fallos "HTTP
   500 / Error inesperado en base de datos" en la creación o edición de entidades
   de configuración, consistentes con la ausencia del fix del PR #146 en el
   despliegue evaluado. Ya resuelto en `dev`.
2. **Ejecución incompleta** — RF-23, RF-28 y RF-29 no tienen **ningún** caso
   ejecutado (18 casos); otros 9 casos sueltos quedaron pendientes.
3. **Defectos funcionales y de seguridad confirmados** (secciones 5.B y 5.C) —
   condición de carrera en RF-32, exposición de datos entre fincas (OWASP API1) en
   RF-22, falta de validación de charset y de rate-limit en RF-21, y
   funcionalidad de UI no disponible en RF-25/26/27.

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | ¿≥85 %? | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|:-------:|-----------|
| RF-15 | Catálogo de especies productivas | 10 | 4 | 6 | 0 | 40 % | ❌ | No conforme — cluster HTTP 500 |
| RF-16 | Etapas, patologías y métricas por especie | 11 | 10 | 1 | 0 | 91 % | ✅ | Aprobado con observaciones |
| RF-17 | Umbrales de monitoreo y niveles de alerta | 11 | 6 | 3 | 2 | 55 % | ❌ | No conforme — HTTP 500 (fix en dev) + no ejecutados |
| RF-18 | Parámetros operativos del sistema | 7 | 5 | 0 | 2 | 71 % | ❌ | Condicionado — falta ejecución |
| RF-19 | Registro y gestión de datos de la finca | 8 | 8 | 0 | 0 | 100 % | ✅ | Aprobado |
| RF-20 | Gestión de infraestructura productiva | 7 | 3 | 3 | 1 | 43 % | ❌ | No conforme — cluster HTTP 500 |
| RF-21 | Registro de dispositivos IoT | 7 | 6 | 1 | 0 | 86 % | ✅ | Aprobado con observaciones (hallazgo OWASP) |
| RF-22 | Asociación de sensores a estructuras | 8 | 5 | 2 | 1 | 63 % | ❌ | No conforme — OWASP API1 + HTTP 500 |
| RF-23 | Configuración remota de dispositivos IoT | 9 | 0 | 0 | 9 | 0 % | ❌ | Sin ejecutar |
| RF-24 | Calibración de dispositivos IoT | 7 | 4 | 1 | 2 | 57 % | ❌ | Condicionado — falta ejecución |
| RF-25 | Adaptación de interfaz operativa | 4 | 1 | 2 | 1 | 25 % | ❌ | No conforme — funcionalidad UI no disponible |
| RF-26 | Personalización de identidad visual | 5 | 1 | 4 | 0 | 20 % | ❌ | No conforme — funcionalidad UI no disponible |
| RF-27 | Configuración visual del sistema (tema) | 5 | 4 | 1 | 0 | 80 % | ❌ | Condicionado — funcionalidad UI no disponible |
| RF-28 | Personalización del dashboard | 4 | 0 | 0 | 4 | 0 % | ❌ | Sin ejecutar |
| RF-29 | Configuración de idioma | 5 | 0 | 0 | 5 | 0 % | ❌ | Sin ejecutar |
| RF-30 | Plantillas de configuración | 6 | 5 | 1 | 0 | 83 % | ❌ | Aprobado con observaciones |
| RF-31 | Creación de plantilla de configuración | 6 | 2 | 4 | 0 | 33 % | ❌ | No conforme — validación y auditoría |
| RF-32 | Aplicación de plantilla de configuración | 9 | 6 | 3 | 0 | 67 % | ❌ | No conforme — condición de carrera + HTTP 500 |

**RFs que cumplen el umbral (≥85 %):** RF-16, RF-19, RF-21. **3 de 18.**

---

## 3. Cobertura y método

- **API backend:** colecciones Postman ejecutadas con Newman (reporter `htmlextra`);
  76 casos. Pruebas de seguridad (OWASP API, ASVS) y de lógica interna con Pytest
  (6 casos). Rendimiento de consulta de catálogos con k6 (2 casos).
- **Frontend:** recorridos Cypress con veredicto en JSON propio / reporte
  `mochawesome` / log de consola; 18 casos.
- **Casos agrupados:** el plan de M09 consolida los casos originales en 129 grupos
  `TC-M09-G01` … `TC-M09-G129`. Dos casos tienen veredicto declarado a mano en
  `declarados_sin_evidencia.csv` por tener evidencia en formato no consolidable:
  **TC-M09-G28 (Rechazado)** y **TC-M09-G79 (Aprobado)**.
- **Tipos de prueba:** funcional, validación, valores límite, integridad,
  seguridad (OWASP API1/API4/API8, ASVS), rendimiento, resiliencia.

---

## 4. Hallazgo transversal — ambiente de TEST desactualizado

**Impacto: ~16 casos rechazados (12 % del módulo).**

El despliegue de TEST evaluado se basó en la rama `qa/juan-esteban-m09`, que
divergió de `dev` **antes del PR #146** y perdió la línea
`use_insertmanyvalues=False` del `create_engine()` en `src/shared/database.py`.
Sin ese guard, SQLAlchemy 2.0 usa el modo `insertmanyvalues` con casteo a
`::VARCHAR`, que rompe la inserción en columnas `ENUM` nativas de PostgreSQL
(`DatatypeMismatch`). Como es una configuración **global del motor**, afecta a
todo endpoint que haga inserción multi-fila con columnas enum/array —
consistente con el patrón observado: HTTP 500 `ERROR_INTERNO` en la creación y
edición de especies (RF-15), umbrales (RF-17), infraestructura (RF-20),
asociaciones (RF-22) y aplicación de plantillas (RF-32).

- **Estado:** corregido en `dev` (PR #146, `rc.19`); presente en `rc.33`.
- **Documento:** `inc_m09_umbrales_500_enum_insertmanyvalues.md`
  (issues #144, #146, #148, #149, #158).
- **Acción requerida:** redesplegar TEST desde `dev`/`rc.33` y reejecutar la
  totalidad de la sección 5.A antes de emitir un veredicto definitivo por RF.

---

## 5. Entrega a Desarrollo — registro de defectos

### 5.A — Cluster HTTP 500 «Error inesperado en base de datos» (reejecutar contra rc.33)

| Casos | RF | Operación | Observado |
|---|---|---|---|
| TC-M09-G01, G02, G03, G04, G07, G08 | RF-15 | Crear / editar especie | HTTP 500 `ERROR_INTERNO`; sin persistencia |
| TC-M09-G22, G24, G28 | RF-17 | Crear umbral ambiental con 3 niveles | HTTP 500 `ERROR_INTERNO` — **INC-M09-27-G24 / INC-M09-26-G28 / INC-M09-31-G22**, causa raíz confirmada (enum `nivel` + `insertmanyvalues`) |
| TC-M09-G48, G49, G50 | RF-20 | Crear / editar infraestructura | HTTP 500 `ERROR_INTERNO` |
| TC-M09-G64 | RF-22 | Asociar sensor | HTTP 500 (esperaba 201) |
| TC-M09-G116, G118, G119 | RF-32 | Aplicar plantilla / editar ciclo | HTTP 500 donde se esperaba 200 / 412 |

**Acción:** redesplegar TEST desde `rc.33` y reejecutar. Confirmar por RF cuáles
se resuelven con el fix del PR #146 y cuáles son defectos independientes —
en particular **RF-32 (G118/G119)**, cuyo `expected 412 to be at most 200` / `got
500` apunta también a la condición de carrera de la sección 5.B.

### 5.B — Defectos funcionales confirmados

| Caso(s) | RF | Capa | Observado | Clasificación / referencia |
|---|---|---|---|---|
| TC-M09-G118, G119 | RF-32 | backend | El control de concurrencia optimista compara el campo equivocado; una edición concurrente devuelve 500 en vez de 412 | Defecto de producto — condición de carrera (ver `estado_M09.md` §RF-32) |
| TC-M09-G111, G112 | RF-31 | backend | Validación de plantilla: `404` donde se esperaba `422`; y `201` (acepta) donde se esperaba `422` (rechazo) | Defecto de producto — validación |
| TC-M09-G115 | RF-31 | backend | La creación de plantilla no deja entrada de auditoría categorizada como `PLANTILLA` | Defecto de producto — auditoría |
| TC-M09-G109 | RF-30 | backend | Aserción de conteo de auditoría en `0` (`expected +0 to be above +0`) | Triage — posible defecto de auditoría o contrato de prueba |
| TC-M09-G86, G89 | RF-26 | backend | Crear identidad visual devuelve `400`; la respuesta no incluye `id_identidad_visual` | Retest — posiblemente cubierto por PR #186 (`fix/rf26-almacenamiento-logo-persistente`, ya en `rc.33`) |
| TC-M09-G75 | RF-24 | backend | Mensaje de validación dice "número" donde el contrato de prueba espera "numero decimal" | Menor — ajuste de mensaje o de aserción |
| TC-M09-G18 | RF-16 | frontend | `EventoSanitarioForm` usa textarea libre y `EventoCrecimientoForm` un selector hardcodeado (PESO/TALLA/BIOMASA) en vez de consumir el catálogo dinámico por especie | Defecto de producto (frontend) — **nota:** ejercita formularios de RF-39/RF-40, alcance de M02 |
| TC-M09-G110 | RF-31 | frontend | El snapshot de la plantilla no se construye correctamente al leer la configuración real de la especie (probado con Cachama Blanca y Camarón Blanco) | Defecto de producto (frontend) |

### 5.C — Hallazgos de seguridad (OWASP API / ASVS)

| Caso | RF | Norma | Observado | Severidad |
|---|---|---|---|---|
| TC-M09-G126 | RF-22 | OWASP API1 (BOLA) | Un sensor de un dispositivo de la Finca A puede asociarse a un área de la Finca B; un Productor sin relación con la Finca B consulta el historial de asociaciones de un sensor de esa finca | **Alta** — exposición de datos entre fincas |
| TC-M09-G125 | RF-21 | OWASP API8 / API4 | No se valida el charset de `serial`/`descripcion` (no rechaza payloads con sintaxis de inyección SQL/NoSQL con `400`); no hay bloqueo ni `429` ante una ráfaga de 50 registros en ~7 s | Media |
| TC-M09-G83 | RF-25 | OWASP API1 / API5 | Un endpoint responde `200` donde se esperaba `401`/`403` | Triage — confirmar contra el fix INC-M09-G82 (#178, ya en `rc.33`) |

### 5.D — Funcionalidad no disponible en la interfaz (frontend)

*Los recorridos Cypress se bloquean porque la opción no existe en la UI desplegada.
Confirmar si es alcance de frontend pendiente o si la funcionalidad es solo backend.*

| Caso(s) | RF | Bloqueo |
|---|---|---|
| TC-M09-G85, G88 | RF-26 | La opción "Identidad Visual" no está disponible en Configuración / la interfaz |
| TC-M09-G90 | RF-27 | La configuración de temas Claro/Oscuro/Automático no está disponible en la interfaz |
| TC-M09-G82 | RF-25 | Fallo de automatización: `cy.injectAxe is not a function` (plugin `cypress-axe` no cargado) → corregir el proyecto Cypress (QA) |

### 5.E — Bloqueados por brecha de correlación cross-módulo (no constituyen defecto de producto)

| Caso(s) | RF | Situación | Referencia |
|---|---|---|---|
| TC-M09-G29, G30 | RF-17 | Monitoreo (M03) no expone el umbral efectivo de M09 porque `umbral_historico_m09_adapter` es un stub que siempre devuelve `None`; faltan precondiciones de datos en TEST. QA lo clasifica como BLOCKED, "defecto funcional confirmado: No" | `inc_m09_monitoreo_umbral_efectivo_bloqueado.md` (issues #159, #160) |

### 5.F — Incidencias corregidas en `dev` durante la campaña (retest pendiente)

| Incidencia | RF | Descripción | Estado |
|---|---|---|---|
| INC-M09-27/26/31 | RF-17 | `POST /configuracion/umbrales` → 500 por enum + `insertmanyvalues` | Corregido — PR #146 (`rc.19`), en `rc.33` |
| INC-M09-30-G30 | RF-17 | Faltaba endpoint `GET /umbrales/{id}/auditoria` | Corregido — `693fd57`, en `rc.33` |
| INC-M09-G82 | RF-25 | `GET /configuracion/fincas` daba alcance global a roles de solo lectura distintos de Productor | Corregido — PR #178, en `rc.33` |
| INC-M09 RF-26 logo | RF-26 | Almacenamiento no persistente y validación insuficiente del logo institucional | Corregido — PR #186, en `rc.33` |
| INC-M09 RF-23 MQTT | RF-23 | No se advertía si `MQTT_BROKER_TOKEN` quedaba desincronizado de la BD | Corregido — PR #187, en `rc.33` |
| INC-M09-29-G83 | RF-25 | "Rol inexistente en el JWT" — investigado: el producto resuelve el rol desde BD, no del claim; responde `403` correctamente | Cerrado — no es defecto (`inc_m09_rol_inexistente.md`) |

---

## 6. Casos no ejecutados (27) — plan de cierre

| RF | Casos | Responsable | Alcance |
|---|---|---|---|
| RF-23 — Configuración remota de dispositivos IoT | G68–G73, G127–G129 (9) | Juan Pablo | **RF completo sin ejecutar** |
| RF-28 — Personalización del dashboard | G95–G98 (4) | Laura Lopez | **RF completo sin ejecutar** |
| RF-29 — Configuración de idioma | G99–G103 (5) | Laura Lopez | **RF completo sin ejecutar** |
| RF-17 | G29, G30 (2) | Juan Esteban | Bloqueados — ver 5.E |
| RF-18 | G38, G39 (2) | Juan Manuel | Pendiente |
| RF-20 | G54 (1) | Juan Manuel | Pendiente |
| RF-22 | G67 (1) | Juan Pablo | Pendiente |
| RF-24 | G77, G78 (2) | Juan Esteban | Pendiente (G77 con evidencia parcial no reconocida) |
| RF-25 | G81 (1) | Laura Lopez | Pendiente (evidencia mochawesome no consolidada) |

**Prioridad de ejecución:** RF-23, RF-28 y RF-29 primero (18 casos, 3 RF sin
ninguna cobertura), contra TEST redesplegado desde `rc.33`.

---

## 7. Condiciones de la entrega

1. **Este informe no emite un veredicto definitivo por RF** hasta que se
   redespliegue TEST desde `dev`/`rc.33` y se reejecuten la sección 5.A y los
   casos marcados "retest". El veredicto **NO CONFORME** del módulo se sostiene con
   los datos actuales, pero la magnitud real de la deuda solo se conocerá tras esa
   reejecución.
2. **Se entrega a Desarrollo:**
   - Confirmación de despliegue de `rc.33` en TEST (prerrequisito de todo lo demás).
   - Los defectos de las secciones 5.B y 5.C con su evidencia.
   - Triage de los casos de 5.A que **no** se resuelvan con el redespliegue.
3. **Prioridad sugerida de corrección:**
   - **Alta:** condición de carrera RF-32 (G118/G119), BOLA entre fincas RF-22
     (G126), validación de plantillas RF-31 (G111/G112).
   - **Media:** auditoría de plantillas RF-31 (G115) y RF-30 (G109), charset y
     rate-limit RF-21 (G125), formularios dinámicos RF-16/frontend (G18).
   - **Baja:** mensajes de validación (G75), snapshot de plantilla frontend (G110).
4. **Criterio de aceptación del módulo:** ≥ 85 % de casos aprobados (≥ 110 de 129),
   con RF-23, RF-28 y RF-29 ejecutados en su totalidad y sin defectos de severidad
   Alta abiertos.
5. **Retorno esperado de Desarrollo:** confirmación de `rc.33` en TEST; por cada
   defecto de 5.B/5.C, rama/PR y despliegue para retroprueba.
6. **Acciones internas de QA:** ejecutar los 27 casos pendientes, corregir el
   proyecto Cypress (G82), consolidar la evidencia de G77/G81, y reejecutar la
   sección 5.A tras el redespliegue.

---

## 8. Control del documento

| Versión | Fecha | Autor | Cambios |
|---|---|---|---|
| 1.0 | 2026-09-08 | Equipo QA | Versión inicial — corte al 2026-09-08 |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
