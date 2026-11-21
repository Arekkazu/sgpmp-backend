# TC-M06-G37 — APROBADO

## Identificación

Casos V2: TC-M06-011, TC-M06-013. TC-M06-012: APROBADO en V1, RUN-G37-V1-20261108-233956; fuera de V2. RF-86, versión 2, intento 10, RUN RUN-G37-V2-20261112-150948. Ambiente TEST. Autorización AUT-G37-V2-R2-20261112. Commit de backend indicado para la reevaluación: 453277e4; no verificado por el ejecutor. Node v22.15.1; Newman 6.2.2.

## Precondiciones preparadas

Con autorización del responsable QA se vinculó por SQL el dispositivo 856 al bovino 1831 porque no hay API. Se insertó por SQL la lectura 120035 con apto_para_nic41=true; telemetria_calidad figura INDETERMINADA. Se aceptó la desviación TEMP_CORPORAL frente al pesaje IoT de la matriz porque el producto no ofrece variable de peso. Son precondiciones persistentes fuera del rollback del RUN; el preflight vivo comprueba dispositivo y ventana antes de escribir.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-011 | APROBADO | Los componentes y totales cambian exactamente; otro período sin cambios. |
| TC-M06-013 | APROBADO | VERIFICACION_PENDIENTE inicial, VERIFICADO final y navegación a M02 y M03. |

## Detalle por caso

### TC-M06-011

**Qué se verifica.** El acumulado del período abierto cambia por componente y total exactamente con las variaciones del RUN; el de otro período abierto permanece igual.

**Preparación.** Período 241 y control 260; cuatro bovinos y precio vigente.

**Qué se hizo.** GET del acumulado antes y después de procesar, sin POST de RF-93 ni recálculo manual.

**Esperado.** Ganancias en ingresos; pérdidas en gastos por valor absoluto; otro período sin cambios.

**Observado.** Período antes: ingresos 155610.00, gastos 5063850.0000; TB+ 135360.00, TB- 32430.00, PM+ 0, PM- 0. Después: ingresos 726829.20, gastos 5306595.6000; TB+ 526099.20, TB- 103719.60, PM+ 180480.00, PM- 171456.00. Otro período antes: ingresos 0, gastos 0; TB+ 0, TB- 0, PM+ 0, PM- 0. Después: ingresos 0, gastos 0; TB+ 0, TB- 0, PM+ 0, PM- 0.

| Variación | Activo | Tipo | Monto | Línea |
|---|---:|---|---:|---:|
| 414 | 1831 | GANANCIA_TRANSFORMACION_BIOLOGICA | 64972.80 | 5649 |
| 415 | 1627 | PERDIDA_TRANSFORMACION_BIOLOGICA | -71289.60 | 5650 |
| 417 | 1832 | PERDIDA_PRECIO_MERCADO | -171456.00 | 5652 |
| 416 | 1832 | GANANCIA_TRANSFORMACION_BIOLOGICA | 325766.40 | 5651 |
| 418 | 1833 | GANANCIA_PRECIO_MERCADO | 180480.00 | 5653 |

**Por qué se decide.** Los componentes y totales cambian exactamente; otro período sin cambios. Estado: APROBADO.

### TC-M06-013

**Qué se verifica.** La variación TB+ inicia VERIFICACION_PENDIENTE, RF-91 recibe la verificación y la cadena llega a VERIFICADO con navegación a M02 y M03.

**Preparación.** Bovino 1831; dispositivo 856; lectura 120035 apta dentro de la ventana de 24 h.

**Qué se hizo.** Se consultó la variación y la cadena inicial, se invocó POST RF-91 y se consultaron variación y cadena finales.

**Esperado.** HTTP 200 con verificadas y pendientes; VERIFICADO, evento M02 del paso y lectura M03 120035 en ids_lectura_iot.

**Observado.** Evento M02 1658; estado final VERIFICADO; nivel_fallo sin dato; evento en cadena 1658; lecturas en cadena 120035; verificadas RF-91 98.

**Por qué se decide.** VERIFICACION_PENDIENTE inicial, VERIFICADO final y navegación a M02 y M03. Estado: APROBADO.

## Comprobaciones API/UI

| ID | Caso | Estado | Observación | Evidencia |
|---|---|---|---|---|
| G37-API-011-01 | TC-M06-011 | APROBADO | Los componentes y totales cambian exactamente; otro período sin cambios. | resultado.json |
| G37-API-013-01 | TC-M06-013 | APROBADO | VERIFICACION_PENDIENTE inicial, VERIFICADO final y navegación a M02 y M03. | resultado.json |

UI no exigida por estos casos de la matriz.

## Evidencias reales

newman/newman-G37.json, newman/newman-G37.html, preflight.json, resultado.json, TC-M06-G37_reevaluacion_V2.md. Los montos, cuatro acumulados y la cadena completa están en resultado.json. Solicitudes del ejecutor y Newman: 58 / 150.

## Seguimiento e incidencias

INC-M06-G37-01: CORREGIDA. INC-M06-G32-01: CORREGIDA. Cualquier otra discrepancia acreditada en V2 se registra como nueva en V2.

Sin incidencia de producto nueva comprobada.

## Análisis de causas y problemas técnicos

La derivación inicial usa la primera respuesta pública discrepante. Causa raíz solo donde exista evidencia independiente. Problemas internos de automatización o datos: ninguno observado. 

## Conclusión y acciones

TC-M06-011: APROBADO; TC-M06-013: APROBADO. Ejecución oficial. Desarrollo revisará las incidencias reproducidas; QA decidirá la siguiente evaluación con nueva autorización.

## Cierre y rollback

DELETE del RUN HTTP 200. Rollback verificado: IDs del RUN ausentes y estado M02 restaurado en lecturas públicas poscierre.. Lecturas poscierre sin cabeceras del RUN: 16. La lectura M03 y el vínculo del dispositivo persisten como precondiciones.
