# Informe consolidado de pruebas — Módulo 9 (Configuración) — v2.0
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M09 — Configuración (`src/configuration/`) |
| Alcance | RF-15 a RF-32 (18 requisitos) |
| Período de ejecución | 2026-09-07 a 2026-10-12 (según la fecha de los commits de evidencia) |
| Fecha de corte del informe | 2026-10-12 |
| Ambientes | Backend TEST (`https://api.inmero.co/back-sigab-test`) · Frontend TEST (`https://api.inmero.co`) |
| Herramientas | Newman/Postman (96), Reevaluación documentada (20), Cypress (17), Pytest (14), k6 (2), Acta de ejecución (1) |
| Casos ejecutados | 150 de 150 (100 %) |
| Equipo QA | Daniela Castillo, Juan Esteban, Juan Manuel, Juan Pablo, Laura Lopez, Maria Jose, Sebastian |
| Umbral de aceptación | **≥ 85 % de casos aprobados** |
| Fuente de datos | Panel QA (`QA-DASHBOARD-SGRPMP/`, tabla «Todos los casos de prueba»: casos de backend y de frontend), evidencias en `tests/Test_Testing/Test_Modulo9/` y `testing/test_testing/Modulo9/` |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso reejecutado después del corte puede cambiar de veredicto. Los estados de la tabla de casos son la fuente de este informe; el registro de incidencias (`incidencias.csv`) se usa solo para asociar cada caso rechazado con su incidencia cuando existe.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 150 | 100 % |
| Aprobados | **146** | **97.3 %** |
| Rechazados | 4 | 2.7 % |
| Pendientes | 0 | 0.0 % |

**El módulo supera el umbral de aprobación del 85 % (97.3 %).** Quedan 4 casos rechazados, que se consideran defectos abiertos; su detalle está en la sección 4.

### Verificación de los criterios de salida del plan de pruebas (§2.1)

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **146/150 = 97.3 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **18/18** (incluye transversales si aplica) | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | Este documento (pendiente de firmas) | ✅ (firmas pendientes) |

> Por decisión de QA, este informe no evalúa tres criterios del plan (§2.1): #3 defectos Crítico/Severo abiertos sin plan de mitigación, #4 casos rechazados sin incidencia formal y #5 casos con veredicto fijado a mano. Los casos rechazados se registran en la sección 4.A y, por decisión de QA, se clasifican con severidad **Medio**.

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-15 | Catálogo de especies productivas | 10 | 10 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-16 | Etapas productivas y patologías por especie | 11 | 11 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-17 | Umbrales de monitoreo y niveles de alerta | 11 | 11 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-18 | Parámetros operativos del sistema | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-19 | Datos de la finca | 8 | 8 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-20 | Infraestructura productiva | 7 | 7 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-21 | Dispositivos IoT | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-22 | Asociación de sensores a estructuras | 9 | 7 | 2 | 0 | 78 % | ❌ Con fallas |
| RF-23 | Configuración remota de dispositivos IoT | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-24 | Calibración de dispositivos IoT | 13 | 12 | 1 | 0 | 92 % | ⚠️ Parcial |
| RF-25 | Adaptación de interfaz operativa | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-26 | Identidad visual del sistema | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-27 | Configuración visual (temas) | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-28 | Personalización del dashboard | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-29 | Idioma | 5 | 5 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-30 | Plantillas de configuración | 8 | 8 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-31 | Creación de plantilla | 8 | 7 | 1 | 0 | 88 % | ⚠️ Parcial |
| RF-32 | Aplicación de plantilla | 14 | 14 | 0 | 0 | 100 % | ✅ Aprobado |
| **Total** | | **150** | **146** | **4** | **0** | **97.3 %** | |

---

## 3. Cobertura y método

- **Herramientas por caso:** Newman/Postman: 96 casos; Reevaluación documentada: 20 casos; Cypress: 17 casos; Pytest: 14 casos; k6: 2 casos; Acta de ejecución: 1 casos.
- **Casos con veredicto de reevaluación documentada:** algunos casos rechazados en la primera evaluación se reejecutaron en `EvaluacionV2`/`EvaluacionV3` y su veredicto vigente consta en el acta de reevaluación (ver sección 4.B).
- **Evidencia:** cada caso conserva su reporte de ejecución (HTML/JSON/XML) y, en las reevaluaciones, un acta `.md` con la narrativa de la corrida.
- **Higiene de carpetas (M09):** se retiraron las carpetas duplicadas `TC-M09-109` y `TC-M09-111` (numeración anterior; sus versiones vigentes son `G109` y `G111`). El identificador `G130` lo comparten tres carpetas (RF-16, RF-21 y RF-24), y `G133` y `G136` existen también en una segunda carpeta con solo una `ficha.md`; el panel puede atribuir un caso a un RF equivocado (por ejemplo, G136, que es de RF-24, aparece en RF-23).
- **Ambiente:** las ejecuciones vigentes se realizaron contra TEST con el backend en `https://api.inmero.co/back-sigab-test`; algunos casos históricos se ejecutaron contra la URL anterior de TEST (`sslip.io`).

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Casos rechazados (defectos abiertos)

| TC | RF | Responsable | Resultado | Motivo | Incidencia asociada | Severidad (QA) |
|---|---|---|---:|---|---|---|
| G062 | RF-22 | Juan Pablo | 9/11 | Reintento del 12-oct: 9 de 11 comprobaciones pasan; el resto queda bloqueado porque `POST /configuracion/dispositivos-iot/{id}/sensores` responde 500 en TEST y no se puede crear el sensor que usan los pasos siguientes (INC-M09-NN-SENSORES-500) | INC-M09-NN-G62 (Abierto) | Medio |
| G111 | RF-31 | Daniela Castillo | 11/12 | La prueba v2.0 exige 404 para una plantilla asociada a una especie inactiva y el backend responde 422; la especificación de RF-31 no fija el código HTTP (por decidir) | INC-M09-77-G111 (Abierto) | Medio |
| G130 | RF-24 | Maria Jose | 35/37 | El nombre G130 agrupa tres carpetas (RF-16, RF-21, RF-24). El caso de RF-16 pasa completo en la ejecución del 12-oct (16/16). El de RF-24 queda bloqueado: un sensor inexistente (ID 999999) responde 422 y la prueba espera 404; la decisión 404 contra 422 está pendiente con Desarrollo (INC-M09-73-G130) | INC-M09-G130 (Abierto); INC-M09-73-G130 (Cerrado) | Medio |
| G133 | RF-22 | Juan Pablo | 6/8 | Reintento del 12-oct: bloqueado; el mismo 500 en `POST …/dispositivos-iot/{id}/sensores` impide crear el sensor que el caso necesita, y el sensor inexistente responde 422 donde la prueba espera 404 (INC-M09-NN-SENSORES-500, INC-M09-NN-G133) | INC-M09-NN-G133 (Abierto) | Medio |

### 4.B — Casos aprobados por reevaluación documentada

| TC | Fuente del veredicto |
|---|---|
| G022 | Reevaluacion V2 (14-sep-2026, corrida por QA/MJ) en EvaluacionV2/RESULTADOS/G22-REEVAL-V2-20260914-171827/TC-M09-G22_reevaluacion_V2.md. Los 4 originales (TC-M09-46/47/48/49) APROBADOS: HTTP 201 y persistencia confirmada en 4 comb… |
| G024 | Reevaluacion V2 (13-sep-2026, Juan Esteban) en EvaluacionV2/RESULTADOS/G24-REEVAL-V2-20260913-012209/TC-M09-G24_reevaluacion_V2.md. Los 3 originales (TC-M09-52/53/54) APROBADOS. El defecto original (HTTP 500, QA-JE-G22-01) fue cor… |
| G028 | Reevaluacion V2 (14-sep-2026, corrida por QA/MJ) en EvaluacionV2/RESULTADOS/G28-REEVAL-V2-20260914-172556/TC-M09-G28_reevaluacion_V2.md. TC-M09-60 APROBADO: creacion de umbral valido devuelve HTTP 201 con precision Decimal exacta… |
| G029 | Reevaluacion V5 (8-oct-2026, TEST con Gateway Edge real) en RF-17/TC-M09-G29/EvaluacionV5/RESULTADOS/G29-REEVAL-V5-20261008-200906/TC-M09-G29_reevaluacion_V5.md: APROBADO. TC-M09-62 APROBADO: la propagacion del u… |
| G030 | Reevaluacion V3 (26-sep-2026, Juan Esteban) en EvaluacionV3/RESULTADOS/G30-REEVAL-V3-20260926-212150/TC-M09-G30_reevaluacion_V3.md. TC-M09-64 APROBADO: 1 POST + 1 PATCH sobre el mismo umbral correlacionan CREATE y UPDATE con recur… |
| G038 | Estado: PASA en Resultados/TC-M09-G38-resultados.md (Juan Manuel). 2/2 pytest OK: rollback ante fallo de auditoria en ActualizarConfiguracionUseCase revierte la modificacion de parametros (RF-18); control de modificacion exitosa p… |
| G039 | Estado: PASA en Resultados/TC-M09-G39-resultados.md (Juan Manuel). 1/1 pytest OK: segunda actualizacion concurrente sobre la misma configuracion se rechaza con 412 CONFLICTO_CONCURRENCIA sin alterar el estado (RF-18, FA-14). Solo… |
| G136 | Reevaluacion V2 (10-oct-2026, TEST) en RF-24/TC-M09-G136/EvaluacionV2/RESULTADOS/run-20261010-010830/TC-M09-G136_reevaluacion_V2.md: APROBADO. TC-M09-274 APROBADO en ambas variantes: RANGE devuelve 400 VALOR_FUERA_DE_RANGO con el… |
| G075 | Veredicto APROBADO en RESULTADOS/run-20260906/TC-M09-G75_resultado.md (Juan Esteban). Los 4 originales (TC-M09-142/143/144/145) APROBADOS: limites tecnicos inclusivos aceptados, valores fuera de rango y no numericos rechazados con… |
| G077 | Reevaluacion V2 (12-sep-2026) en EvaluacionV2/RESULTADOS/G77-REEVAL-V2-20260912-211848/TC-M09-G77_reevaluacion_V2.md (Newman, 11/11 assertions, 0 failed). TC-M09-148 APROBADO: el bloqueo V1 (cuentas TEST Productor y Contador desac… |
| G079 | Veredicto APROBADO en RESULTADOS/run-20260906/TC-M09-G79_resultado.md (Juan Esteban). Ante fallo controlado en la persistencia de auditoria el producto hace rollback, no deja datos parciales y devuelve el error de trazabilidad HTT… |
| G138 | Reevaluacion V2 (10-oct-2026, run-20261010-115458) en EvaluacionV2/RESULTADOS/run-20261010-115458/TC-M09-G138_reevaluacion_V2.md: veredicto APROBADO. Newman 179 aserciones, 0 fallos (newman/newman-TC-M09-G138.html). Los 4 casos (T… |
| G140 | Reevaluacion V2 (10-oct-2026, TEST) en RF-24/TC-M09-G140/EvaluacionV2/RESULTADOS/run-20261010-150013/TC-M09-G140_reevaluacion_V2.md: APROBADO. TC-M09-284, 285 y 286 APROBADOS; Pytest TEST 16 de 16 sin fallos. Evolucion del grupo B… |
| G143 | Reevaluacion V2 (10-oct-2026, TEST) en RF-24/TC-M09-G143/EvaluacionV2/RESULTADOS/run-20261010-181553/TC-M09-G143_reevaluacion_V2.md: APROBADO (RECHAZADO a APROBADO). TC-M09-290, 291 y 292 APROBADOS; la comprobacion previa de OpenA… |
| G082 | Confirmado por Laura Lopez. rev4 TEST (25-sep-2026): GET /configuracion/fincas/19 con el productor id=2 devuelve 403 FINCA_NO_AUTORIZADA sin datos de la finca; control positivo finca 1 = 200 y finca 999 = 404. Evidencia en Resulta… |
| G083 | Reevaluado (25-sep-2026) en Resultados/G83-rev4-test-ejecucion.txt: login real con usuario existente id=30 (gestor.granja.test@pecuaria.co, rol=7 Gestor de Granja, sin permiso R sobre el recurso 22 contexto_interfaz) contra TEST.… |
| G086 | Aprobado por la reejecucion final. El intento 1 (13-sep-2026 23:57, TC-M09-G86_rev1_dev_intento1_coleccion.html) fallo por precondicion (la finca 6 ya tenia identidad visual: 409/412 en cascada, 16 de 27 aserciones) y es el que el… |
| G090 | Confirmado por Laura Lopez. Veredicto consolidado de rev2 + rev3 TEST (25-sep-2026): TC-M09-170 Claro y 171 Oscuro aprobados en rev2 (G90-rev2-test-ejecucion.txt); TC-M09-172 Automatico aprobado en rev3 (G90-172-rev3-test-ejecucio… |
| G094 | Confirmado por Laura Lopez. TC-M09-178 aprobado en rev2 (axe color-contrast 0 violaciones); TC-M09-179 aprobado en rev4 TEST (25-sep-2026): con primary=#FFFFFF el frontend aplica color_ajustado #757575 a --brand-500 (G94-rev4-179-… |
| G116 | Retest v2.0 (12-sep-2026) en RF-32/TC-M09-G116/resultado-g116-v2.0.html: Newman 10 aserciones, 0 fallos. Repite el camino feliz de TC-M09-224 (crear plantilla y aplicarla sobre otra especie), que en la corrida del 5-sep fallaba co… |

### 4.C — Casos bloqueados y dependencias

- **G062 y G133 (RF-22):** el alta de sensores (`POST /configuracion/dispositivos-iot/{id}/sensores`) responde 500 en TEST. Sin ese alta no se puede crear el sensor que usan las comprobaciones siguientes, así que no se pueden ejecutar los demás pasos de ambos casos. Se registró la incidencia INC-M09-NN-SENSORES-500.
- **G130 (RF-24):** la parte de RF-16 pasa completa. El sub-caso de RF-24 queda a la espera de decidir si un sensor inexistente debe responder 404 o 422 (INC-M09-73-G130).
- **G111 (RF-31):** la especificación no fija el código HTTP (404 o 422) para una plantilla asociada a una especie inactiva; la prueba se ajusta cuando Desarrollo lo defina.
- Las operaciones que dependen de elementos de otros componentes (Gateway Edge para umbrales, operación VISION de calibración) ya se validaron en las reevaluaciones del 8 y 10 de octubre y no quedan bloqueadas.

### 4.D — Estado del registro de incidencias

El registro (`incidencias.csv`, corte 2026-10-12) tiene **107 incidencias** del módulo: **100 cerradas** con retroprueba y **7 abiertas**.

| Incidencia | Severidad | RF | Descripción |
|---|---|---|---|
| INC-M09-G130 | Medio | RF-16 | Al registrar una métrica de producción sin enviar tipo_dato (POST /configuracion/metricas), el backend responde 201 y le asigna un tipo_dato por su cuenta (NUMERICO para PESO) en vez de rechazar la pe… |
| INC-M09-NN-G62 | Baja | RF-22 v2.0 | Sensor inexistente en /asociar responde 404 SENSOR_NO_ENCONTRADO; la matriz pide 422 |
| INC-M09-NN-G133 | Madia | RF-22 v2.0 | Dispositivo inexistente en /asociar responde 422 SENSOR_DISPOSITIVO_INVALIDO, no 404 |
| INC-M09-NN-G56 | Baja | RF-21 v2.0 | Área inexistente al registrar dispositivo responde 404 AREA_NO_ENCONTRADA; la matriz pide 422 |
| INC-M09-NN-G57 | Media | RF-21 v2.0 | El campo protocolo en /configurar no existe en el contrato y se acepta con 202, ignorado en silencio |
| INC-M09-77-G111 | Baja | RF-31 | Al crear una plantilla asociada a una especie INACTIVA (POST /configuracion/plantillas), el sistema responde 422 Unprocessable Entity con error_code ESPECIE_INACTIVA ('No se puede crear una plantilla… |
| INC-M09-NN-SENSORES-500 | Severo | RF-22 v2.0 | POST /configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores responde 500 Internal Server Error con un dispositivo recién creado y un cuerpo válido. El alta del dispositivo sí responde 201. Impi… |

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
| 1.0 – 2.0 | 2026-09-08 a 2026-10-11 | Equipo QA | Informes anteriores (`informe_consolidado_pruebas_M09.md`); esta versión los sustituye |
| **2.0** | 2026-10-12 | Equipo QA | Informe de cierre con corte al 2026-10-12: 146/150 aprobados (97.3 %); casos rechazados detallados en 4.A; casos bloqueados y sus dependencias en 4.C; estado del registro de incidencias en 4.D |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
