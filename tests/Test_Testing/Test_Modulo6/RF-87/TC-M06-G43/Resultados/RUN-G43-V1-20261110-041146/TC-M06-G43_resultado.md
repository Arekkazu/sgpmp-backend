# TC-M06-G43 — resultado oficial V1

## 1. Identificación

| Campo | Dato |
| --- | --- |
| Proyecto | SGPMP, datos financieros NIC 41 |
| Módulo, requisito, grupo | M06; RF-87 v1.1 (RF-89 CA-8 relacionado); G43 |
| Casos | TC-M06-024, TC-M06-025, TC-M06-026, TC-M06-027 |
| Versión, ambiente, RUN | V1; TEST; `RUN-G43-V1-20261110-041146` |
| Inicio y duración | 2026-11-10 04:11:46 UTC; 74 segundos, según [resultado.json](resultado.json) |
| Autorización | `AUT-G43-V1-R4-20261110`; reintento técnico V1, intento 4, según [contexto_operacion.json](contexto_operacion.json) |
| Responsable QA | Juan Esteban (matriz original) |
| Herramientas | Node v22.15.1; Cypress 14.5.4, Electron 130; Newman ejecutado, versión no registrada en este RUN |
| Commit | No consultado |

Los oráculos proceden de la fila `TC-M06-G43` de `Casos_Prueba(Modulo6Agrup).csv` (Windows-1252), RF-87 CA-1, CA-5, CA-7, CA-8 y CA-12, proceso pasos 2 y 3, precondición 5, y RF-89 CA-8. Las lecturas de código indicadas abajo son de la rama local, sin cotejo con el despliegue TEST.

## 2. Resumen ejecutivo

| Caso | Veredicto oficial | Motivo de resultado.json |
| --- | --- | --- |
| TC-M06-024 | **RECHAZADO** | `pausa_EN_CIERRE,cierre_autorizado` |
| TC-M06-025 | **APROBADO** | Criterios conformes |
| TC-M06-026 | **RECHAZADO** | `confirmacion_individual,costo_revelacion,sin_estimacion_indebida,ui_confirmacion` |
| TC-M06-027 | **RECHAZADO** | `pausa_EN_CIERRE,si_exclusion,ui_lista` |

**1 APROBADO, 3 RECHAZADO.** RUN y registro QA **OFICIALES**. Incidencias de producto: `INC-M06-G32-01` reutilizada (ALTA, atribución PROBABLE), `INC-M06-G43-01` (MEDIA), `INC-M06-G43-02` (MEDIA) y `INC-M06-G43-03` (ALTA). El selector incorrecto en Cypress 025 es `ERROR_QA` técnico y no una incidencia del producto. Fuentes: [resultado](resultado.json), [preflight](preflight.json), [Newman](newman/newman-G43.json) y actas Cypress enlazadas por caso.

## 3. Casos, pasos y comprobaciones

### TC-M06-024 — precio congelado

**Caso original y objetivo:** “Usar los precios congelados al inicio del cierre aunque cambien durante la ejecución”. La matriz exige, tras autorizar, el mismo `id_precio_referencia` y `fecha_vigencia` capturados al inicio, no el precio nuevo. RF-87 CA-1 y restricción 6 exigen congelar el precio; CA-7 exige `EN_CIERRE` durante la ejecución.

**Precondiciones y entradas:** período 8 iniciado y detenido para autorización; especie 39 con precio inicial id 18, fecha 2026-11-07, y precio nuevo RF-89 id 486, fecha 2026-11-09. Entrada: autorización de exclusión durante el cierre y posterior comparación del precio usado. [Preflight](preflight.json): `ok=true`.

**Pasos ejecutados:** prevalidación `G43-006`; POST sin autorización `G43-033` (HTTP 409); lectura de estado; alta del precio nuevo `G43-040` (HTTP 201); POST autorizado `G43-042` (HTTP 500 `ERROR_INTERNO` a las 2026-11-10T04:12:12.838Z); consulta de auditoría `G43-043` (`CIERRE_PERIODO_FALLIDO`, paso 3). [Solicitudes, precios y auditoría](resultado.json).

| Criterio | Esperado | Observado | Conclusión |
| --- | --- | --- | --- |
| API, pausa (CA-7) | `EN_CIERRE` durante la solicitud de autorización | HTTP 409; período `ABIERTO` | RECHAZADO; `INC-M06-G43-01` |
| API, cierre autorizado | HTTP 200 y cierre completado | HTTP 500 `ERROR_INTERNO`; fallo auditado en paso 3 | RECHAZADO; `INC-M06-G32-01` |
| API, precio (CA-1) | Revaluación con id 18 y fecha 2026-11-07, aunque exista id 486 del 2026-11-09 | `congelado` y `congelado_fecha` ausentes; cierre no completado | **No observable**; no se afirma uso del precio nuevo |
| UI | Decisión de autorización durante el cierre | Panel 027, usado para la pausa del período 8, se ejecutó una vez y registró lista incompleta | [Acta 027](cypress/027/G43-UI-027.json), [captura 027](cypress/027/screenshots/g43.cy.js/G43-UI-027.png); el estado se sustenta en API |

**Veredicto: RECHAZADO** por pausa en `ABIERTO` y cierre no completado. El precio congelado no pudo comprobarse. [Resultado API](resultado.json).

### TC-M06-025 — advertencia y exclusión de activos sin precio

**Caso original y objetivo:** “Alertar y permitir excluir los activos sin precio de mercado vigente”. La matriz exige advertencia previa con número, activos y especies; con **Sí**, `PENDIENTE_PRECIO` y cierre `CERRADO` con el resto; con **No**, cancelación, rollback y `ABIERTO` sin cambios. RF-87 CA-5 y CA-8.

**Precondiciones y entradas:** período 219 `ABIERTO`, activo 1568 sin precio vigente y otros activos con precio; decisión negativa y luego autorización de exclusión (`incluir_activos_sin_precio=false`). La decisión ocurrió **antes de iniciar el cierre, en la prevalidación**, no en el paso 2. [Resultado](resultado.json), [acta 025](cypress/025/G43-UI-025.json).

**Pasos ejecutados:** prevalidación `G43-007` y `G43-047`; POST sin autorización `G43-048` (409), lecturas de línea base; POST autorizado `G43-054` (200), inspección de excluidos y estado. Cypress ejecutó una prueba del panel 025. [Solicitudes](resultado.json).

| Criterio | Esperado | Observado | Conclusión |
| --- | --- | --- | --- |
| API, aviso | Número y lista completa de activos y especies | `N=1`; activo 1568, `QA-M06C-VR-01`, Caprino Qa Aislado | Conforme |
| UI, aviso | Número y lista visibles para decidir | `lista_completa=true`, `radios=2` (`sin-precio`) | Conforme al oráculo UI; [acta](cypress/025/G43-UI-025.json), [captura](cypress/025/screenshots/g43.cy.js/G43-UI-025.png) |
| No | Cancelación, `ABIERTO`, línea base intacta | POST 409, mensaje de un activo sin precio; `sin cambios=true` | Conforme |
| Sí | Excluido `PENDIENTE_PRECIO`; cierre `CERRADO` | POST 200; `CERRADO`; excluido 1568:`PENDIENTE_PRECIO`; 1 procesado | Conforme |

**Veredicto: APROBADO.** El acta Cypress global registra RECHAZADO solo por el criterio adicional del botón, que quedó no evaluable debido al selector QA erróneo; véase Problemas técnicos. [Veredicto y API](resultado.json).

### TC-M06-026 — método de costo bajo párrafo 30

**Caso original y objetivo:** “Incluir activos sin precio con el método de costo solo cuando cumplen el párrafo 30 de la NIC 41”. La matriz exige confirmar **por activo** ausencia verificada de mercado activo y vida útil en M09; el confirmado que cumple entra con `metodo_valoracion=COSTO` y marca RF-92; sin confirmación o condiciones queda `PENDIENTE_PRECIO` sin RF-88. RF-87 paso 2 y RF-89 CA-8 impiden usar precio vencido.

**Precondiciones y entradas:** período 220 `ABIERTO`; prevalidación con activos 1569, 1570 y 1571 sin precio, sin equinos en esa lista. POST con `incluir_activos_sin_precio=true`; contraste de activo elegible y no elegible con confirmación individual presente o ausente. [Resultado](resultado.json).

**Pasos ejecutados:** prevalidaciones `G43-008` y `G43-058`; POST `G43-059` (200); consultas de cálculos `G43-060`, activos `G43-061` a `G43-063`, revelación `G43-064`; una prueba UI. [Solicitudes](resultado.json), [acta 026](cypress/026/G43-UI-026.json).

| Criterio | Esperado | Observado | Conclusión |
| --- | --- | --- | --- |
| Confirmación ¶30 | Confirmar por activo antes de aplicar COSTO | Solo dos radios generales `sin-precio`; `confirmacion_individual=false`; POST `true` respondió 200 | RECHAZADO |
| COSTO/revelación | Elegible con `metodo_valoracion=COSTO` y marca RF-92 | `costo/revelacion=false`; ningún cálculo con `tiene_valor_estimado` | RECHAZADO; salida exigida no acreditada |
| Sin condiciones | Sin RF-88; `PENDIENTE_PRECIO` | `activos_excluidos` vacío; `activos_procesados=5` | RECHAZADO para caprinos sin condiciones; **no se afirma uso de precio vencido** |
| UI | Controles ¶30 por activo | Panel RECHAZADO; `confirmacion_individual=false`; dos radios generales | RECHAZADO; [acta](cypress/026/G43-UI-026.json), [captura](cypress/026/screenshots/g43.cy.js/G43-UI-026.png) |

**Veredicto: RECHAZADO.** La salida pública y la UI no acreditan la excepción contable exigida. [Resultado API](resultado.json).

### TC-M06-027 — autorización por trazabilidad incompleta

**Caso original y objetivo:** “Pedir autorización para excluir los activos con trazabilidad incompleta”. La matriz exige lista de asientos, activos y eslabón faltante antes de continuar; **Sí** excluye y deja `PENDIENTE_TRAZABILIDAD` para el período siguiente; **No** cancela con rollback y `ABIERTO`. RF-87 precondición 5 ubica la autorización **durante el paso 3**; CA-12 exige la lista y CA-7 el estado `EN_CIERRE`.

**Precondiciones y entradas:** período 8 `ABIERTO`; línea 17 del activo 944 con eslabón `lecturas_nic41` incompleto. Se probaron autorización negada y otorgada. [Resultado](resultado.json).

**Pasos ejecutados:** prevalidación `G43-006`; POST sin autorización `G43-033` (409); lecturas de línea base; POST autorizado `G43-042` (500); auditoría `G43-043`; una prueba Cypress del panel 027. [Solicitudes](resultado.json), [acta 027](cypress/027/G43-UI-027.json).

| Criterio | Esperado | Observado | Conclusión |
| --- | --- | --- | --- |
| API, lista | Asiento, activo y eslabón | Prevalidación 8: línea 17, activo 944, `lecturas_nic41` | Conforme |
| UI, lista | Detalle completo antes de autorizar | `lista_completa=false`, checkbox sin nombre registrado, `total_prevalidacion=0` en acta | RECHAZADO; [acta](cypress/027/G43-UI-027.json), [captura](cypress/027/screenshots/g43.cy.js/G43-UI-027.png) |
| Pausa | `EN_CIERRE` durante solicitud | POST 409; período `ABIERTO` | RECHAZADO |
| No | Cancelar; `ABIERTO` sin cambios | POST 409; `sin cambios=true`; `ABIERTO` | Conforme |
| Sí | `CERRADO`; línea 17 excluida y trasladada como `PENDIENTE_TRAZABILIDAD` | POST autorizado del **período 8** HTTP 500 `ERROR_INTERNO`; `CIERRE_PERIODO_FALLIDO` paso 3; línea 17 no excluida ni trasladada | RECHAZADO por cierre no completado; rama final **no observable** por `INC-M06-G32-01` |

**Veredicto: RECHAZADO.** El campo `casos.TC-M06-027.comprobaciones.si_exclusion.observado` de [resultado.json](resultado.json) muestra HTTP 200 y excluido 1568, datos del **período 219** por choque de claves `observados` en `g43.mjs`. No se modifica el JSON. El observado real del 8 consta en `G43-042`, `auditoria_g32` y `lineas` del mismo resultado. No se presume que la exclusión hubiera fallado si el cierre completaba.

## 4. Incidencias de producto

### INC-M06-G32-01 — reutilizada; 024 y 027

- **Requisito y esperado:** RF-87 CA-1, CA-8 y CA-12: cierre autorizado del período 8 completado, para comprobar precio congelado y exclusión autorizada.
- **Pasos, entrada y obtenido:** Tras pausa y autorización, POST `/finanzas/periodos/8/cierre` (`G43-042`) a **2026-11-10T04:12:12.838Z**: HTTP 500 `ERROR_INTERNO`; auditoría `CIERRE_PERIODO_FALLIDO`, paso 3. No hubo precio congelado ni exclusión final observables.
- **Evidencia:** [solicitudes, auditoría, precios y líneas](resultado.json). La auditoría no sustituye un log de backend.
- **Impacto y severidad:** Ramas autorizadas de 024 y 027 sin resultado. **ALTA:** cierre relevante bloqueado sin alternativa observada.
- **Certeza:** Discrepancia pública **CONFIRMADA**; vinculación con la incidencia previa **PROBABLE**; causa raíz **NO CONFIRMADA**. No se afirma `TGR-M06-26` como observado en este RUN.
- **Equipo inicial:** **Desarrollo**, porque la primera discrepancia se observa en la API pública de cierre. Esta derivación no establece la causa raíz.
- **Hipótesis y ruta:** Hipótesis de fallo compartido del paso 3; responsable QA solicita el log de backend de la hora UTC del POST y Desarrollo correlaciona solicitud, auditoría y transacción.
- **Acción verificable:** Tras identificar y corregir la causa, nuevo RUN autorizado que complete el cierre 8 y compruebe precio congelado y línea 17.

### INC-M06-G43-01 — pausa; 024 y 027

- **Requisito y esperado:** RF-87 CA-7, proceso paso 1 y precondición 5: `EN_CIERRE` desde el inicio, con autorización de trazabilidad durante paso 3.
- **Pasos, entrada y obtenido:** POST 8 sin autorización `G43-033` responde HTTP 409; período `ABIERTO`, no `EN_CIERRE`.
- **Evidencia:** [resultado.json: G43-033 y comprobaciones](resultado.json).
- **Impacto y severidad:** La pausa no expone el estado requerido. **MEDIA:** secuencia incumplida, con decisión aún disponible; no se demostró pérdida de datos.
- **Certeza:** Discrepancia **CONFIRMADA**; causa raíz **NO CONFIRMADA**.
- **Equipo inicial:** **Desarrollo**, por la primera discrepancia en el estado de la API pública; no implica atribución técnica.
- **Hipótesis y ruta:** Hipótesis de reversión prematura del estado. Revisar flujo de estados y auditoría de ese POST.
- **Acción verificable:** En un RUN autorizado, leer `EN_CIERRE` mientras espera la decisión y comprobar bloqueo de nuevos registros.

### INC-M06-G43-02 — lista UI de trazabilidad; 027

- **Requisito y esperado:** RF-87 CA-12, precondición 5 y paso 3: lista de asientos y activos con eslabón incompleto antes de autorizar.
- **Pasos, entrada y obtenido:** Abrir panel 8 con prevalidación de línea 17, activo 944, `lecturas_nic41`; acta UI registra `lista_completa=false`, `total_prevalidacion=0` y checkbox sin nombre registrado, aunque la API muestra el detalle.
- **Evidencia:** [acta 027](cypress/027/G43-UI-027.json), [captura 027](cypress/027/screenshots/g43.cy.js/G43-UI-027.png), [API](resultado.json).
- **Impacto y severidad:** El Contador carece en el panel de datos completos para decidir. **MEDIA:** decisión limitada, aunque la API expone datos.
- **Certeza:** Discrepancia UI **CONFIRMADA**; causa raíz **NO CONFIRMADA**.
- **Equipo inicial:** **Desarrollo**, por la primera discrepancia en la UI pública frente a API; no determina origen técnico.
- **Hipótesis y ruta:** Hipótesis de resumen o renderizado incompleto. Comparar respuesta de prevalidación con representación del panel.
- **Acción verificable:** Mostrar asiento, activo y eslabón; repetir comprobación UI autorizada antes de decidir.

### INC-M06-G43-03 — método COSTO sin confirmación individual; 026

- **Requisito y esperado:** RF-87 paso 2 y CA-5: confirmar ¶30 por activo, aplicar `COSTO` y marcar RF-92 solo al elegible; resto `PENDIENTE_PRECIO`. RF-89 CA-8 prohíbe usar precio vencido en RF-87.
- **Pasos, entrada y obtenido:** Prevalidación 220: 1569, 1570, 1571 sin precio; panel con dos radios generales y `confirmacion_individual=false`; POST `incluir_activos_sin_precio=true` HTTP 200; `activos_excluidos` vacío, `activos_procesados=5`, `costo/revelacion=false`, ningún cálculo con `tiene_valor_estimado`. No hay dato para afirmar uso de precio vencido.
- **Evidencia:** [resultado](resultado.json), [acta 026](cypress/026/G43-UI-026.json), [captura 026](cypress/026/screenshots/g43.cy.js/G43-UI-026.png).
- **Impacto y severidad:** No se acredita la excepción contable ni la exclusión obligatoria de caprinos sin condiciones. **ALTA:** posible valoración y revelación contable incorrectas, sin alternativa de confirmación individual en UI.
- **Certeza:** Falta de controles y salidas exigidas **CONFIRMADA**; causa raíz **NO CONFIRMADA**. No se presume uso de precio vencido.
- **Equipo inicial:** **Desarrollo**, por primeras discrepancias en UI de confirmación y salida API; no establece causa técnica.
- **Hipótesis y ruta:** Hipótesis de que la decisión general omite validación individual. Revisar contrato público, flujo UI, `metodo_valoracion`, exclusiones y marca RF-92 por activo.
- **Acción verificable:** Exigir condiciones y confirmación por activo; en nuevo RUN autorizado comprobar COSTO y RF-92 para el elegible, `PENDIENTE_PRECIO` para no elegibles.

## 5. Análisis de fallos y problemas técnicos

| Hallazgo | Primer punto de discrepancia | Límite causal |
| --- | --- | --- |
| Pausa 024/027 | `G43-033`: 409 y período `ABIERTO` | Causa no confirmada; hipótesis de reversión prematura |
| Cierre 8 | `G43-042`: 500; auditoría `CIERRE_PERIODO_FALLIDO` paso 3 | Vinculación con G32 probable; sin log de backend no se confirma causa ni `TGR-M06-26` |
| Lista 027 | Acta UI `lista_completa=false` frente a API con detalle | Causa no confirmada |
| Costo 026 | Panel sin confirmación individual antes de POST 200 | Causa no confirmada |

**Código efectivamente leído, solo rama local no verificada contra TEST:** `../SGPMP-FRONT-END-PWA/src/shared/i18n/locales/es-CO/finanzas.json:525` traduce `ejecutar` como “Cerrar período”; `../SGPMP-FRONT-END-PWA/src/shared/design-system/Button.tsx:37` aplica `disabled={disabled || loading}`; `../SGPMP-FRONT-END-PWA/src/financial_valuation/pages/CierreView.tsx:85,102-111,175-196` contiene `faltaAutorizar`, aviso de precios, dos radios generales y checkbox de trazabilidad. Son apoyo a hipótesis, no prueba del código desplegado. No se consultó backend en esta enmienda.

**ERROR_QA de selector, sin incidencia de producto:** [acta 025](cypress/025/G43-UI-025.json) marca RECHAZADO por `boton_deshabilitado=false` porque la aserción adicional buscó `/ejecutar/` y el botón real se denomina “Cerrar período”. El criterio “botón deshabilitado” es **no evaluable por error de selector QA**. `Button.tsx:37` demuestra que el componente local aplica la propiedad `disabled`, no cuál fue el estado del botón en TEST. El oráculo UI de la matriz, advertencia con número y lista de activos y especies, se cumplió (`lista_completa=true`, dos radios). **025 permanece APROBADO.** La corrección del selector corresponde a automatización QA.

El campo `observado` de `si_exclusion` en 027 dentro de `resultado.json` contiene datos de 219 por colisión de claves `observados` en `g43.mjs`; aquí se usa el POST y las líneas reales del período 8. Solo se corrige la narración; JSON y ejecutor permanecen intactos. Un código 0 de herramienta no prueba cumplimiento funcional.

## 6. Conclusiones y acciones

Se mantienen los cuatro veredictos. Responsable QA: solicitar log del backend para `G43-042` a 2026-11-10T04:12:12.838Z. Desarrollo: investigar estado `EN_CIERRE`, detalle UI y validación individual del COSTO. Tras corrección y autorización expresa, reevaluar precio congelado, línea 17, COSTO/revelación y `PENDIENTE_PRECIO`. Corregir selector Cypress y colisión de `observados` en otra preparación; esta orden no cambia ejecutables.

La decisión en 025 se observó antes del cierre, en prevalidación. La vida útil del oráculo pertenece a M09 según RF-88; el código local consultado la configura en M06 y no cambia la expectativa. Equinos valorados por costo con precio vigente inicial quedan fuera de G43. Los RUN técnicos `RUN-G43-V1-20261110-014922` y `RUN-G43-V1-20261110-035408` reprodujeron la evidencia API de forma idéntica según el contexto disponible; **no se releyeron sus artefactos** ni se usan como evidencia adicional de este RUN.

## 7. Herramientas, evidencias, cierre y rollback

[Resultado](resultado.json) registra 136 solicitudes API del ejecutor, con `G43-001` a `G43-084` desglosadas. [Newman JSON](newman/newman-G43.json) registra 10 solicitudes, 10 pruebas y **20 aserciones aprobadas** (`HTTP 200` y `JSON público` por lectura), cero fallos y código 0; existe [HTML real](newman/newman-G43.html). Las aserciones de lectura no acreditan los cuatro oráculos.

Cypress 14.5.4 ejecutó **tres pruebas**, una por panel 025, 026 y 027; las tres actas quedaron globalmente RECHAZADAS por las razones detalladas. Evidencias reales: [acta 025](cypress/025/G43-UI-025.json), [captura 025](cypress/025/screenshots/g43.cy.js/G43-UI-025.png), [salida 025](cypress/025/G43-cypress-salida.log), [reporte 025](cypress/025/G43-cypress.json); [acta 026](cypress/026/G43-UI-026.json), [captura 026](cypress/026/screenshots/g43.cy.js/G43-UI-026.png), [salida 026](cypress/026/G43-cypress-salida.log), [reporte 026](cypress/026/G43-cypress.json); [acta 027](cypress/027/G43-UI-027.json), [captura 027](cypress/027/screenshots/g43.cy.js/G43-UI-027.png), [salida 027](cypress/027/G43-cypress-salida.log), [reporte 027](cypress/027/G43-cypress.json). [Preflight](preflight.json): `ok=true`; enumera posibles notificaciones externas no revertidas por el sandbox.

DELETE `/test-control/runs/RUN-G43-V1-20261110-041146` (`G43-067`) respondió **HTTP 200**. [Resultado](resultado.json) marca rollback **verificado** mediante lecturas `G43-068` a `G43-084` **sin cabeceras RUN**, `eco=false`. La confirmación cubre los datos comparados por esas lecturas; no demuestra reversión de notificaciones externas. Registro y resultado permanecen **OFICIALES**.

## 8. Actualización

**Fecha:** 2026-11-10 04:19 UTC. **Orden:** `ORD-G43-014`. **Motivo:** enmienda documental trazada según ESTÁNDAR §8, con estructura del §5 y corrección de atribuciones y límites de evidencia.

| Archivo | SHA-256 |
| --- | --- |
| Markdown anterior del RUN | `1F07F77CB96739AF2C62E36464A1280FED7A10D38349A8418902288F88A687E6` |
| Copia byte a byte `../../historial_informes/TC-M06-G43_resultado.RUN-G43-V1-20261110-041146.antes-enmienda.md` | `1F07F77CB96739AF2C62E36464A1280FED7A10D38349A8418902288F88A687E6` |
| [resultado.json](resultado.json), sin cambios | `4474B78A6CBE9D10D4B59D95C570CAB60E8FD469ABBA60F0BF1A2344D65ACD78` |

Cambios documentales: identificación, pasos y comparaciones por caso, incidencias con severidad/certeza, análisis causal, referencias reales y cierre/rollback; aclaraciones sobre selector QA 025, dato ajeno de `si_exclusion` 027, salida exacta 026 y precio no observable 024. **Veredictos, contadores, clasificación, incidencias registradas en JSON, registro QA, evidencia y rollback no cambian.** Sin TEST, sin RUN nuevo y sin cambios ejecutables.
