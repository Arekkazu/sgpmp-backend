# TC-M06-G40 — APROBADO

## Identificación

Grupo G40; caso TC-M06-018; RF-86 v2.0, CA-21 y FA-5; V2, intento 4; RUN RUN-G40-V2-20261112-161443; operación REINTENTAR sobre V1; ambiente TEST; autorización AUT-G40-V2-R2-20261112. Referencia backend: origin/test 453277e4 (despliegue no comprobado en vivo). Herramientas registradas: Node v22.15.1, Newman 6.2.2 (código 0, tres solicitudes y seis aserciones sin fallos) y Cypress 14.5.4 (código 0, una prueba aprobada). Oficialidad: true según resultado.json.

## Veredicto y oráculo

| Caso | Estado | Motivo |
| --- | --- | --- |
| TC-M06-018 | APROBADO | Se cumplen los cuatro pasos del oráculo: hecho pendiente, panel, aviso al Contador y resolución al completar la matriz. |

La matriz de casos (fila 383) espera que el hecho sin par de cuentas quede pendiente y visible en M06, que el Contador reciba una alerta con la combinación faltante y que al completar la matriz se genere la línea. Se conserva la observación D1 de V1: el producto representa el hecho mediante una línea PENDIENTE_CUENTA sin cuentas, en lugar de omitir físicamente la línea; el responsable QA aceptó esta interpretación.

## Detalle por caso

### TC-M06-018

**Qué se verifica.** CA-21 y FA-5 de RF-86, trazados en la matriz de casos, fila 383, exigen el hecho pendiente sin cuentas, su visibilidad en M06, el aviso al Contador y su registro al completar la matriz.

**Preparación.** Se usaron el activo bovino 1833, el período abierto 241 y la combinación VARIACION_VR_TB/PERDIDA/Bovino. El sentido se eligió en modo automático: la ganancia ya tenía el aviso 12796 en ese período, acreditado en el intento V2 anterior, y el backend emite un aviso por combinación y período. Se desactivó una sola asignación del sentido elegido, la 13, únicamente dentro de este RUN.

**Qué se hizo.**

1. Se leyeron activo, período, configuración, líneas, variaciones, bandeja y auditoría para fijar la base: una línea pendiente.
2. Se desactivó la asignación 13 mediante DELETE, con HTTP 204.
3. Se registró un pesaje con 1 kg menos y se procesó el evento contable; las solicitudes devolvieron HTTP 201 y 200, respectivamente.
4. Se consultaron de nuevo variación, línea, configuración, panel, bandeja y auditoría. Cypress comprobó panel y bandeja, y guardó una captura real.
5. Se completó la matriz mediante POST, con HTTP 201.
6. Se leyeron líneas, configuración y pendientes finales; también constan lecturas de bandeja y comprobaciones de cierre y rollback.

**Qué se esperaba.** Sin par de cuentas, el hecho debía quedar pendiente y visible, sin cuentas registradas; el Contador debía recibir un aviso con la combinación faltante. Al completar la matriz, la línea del hecho debía quedar REGISTRADA con las cuentas nuevas.

**Qué se observó.**

| Paso | Observación acreditada | Resultado |
| --- | --- | --- |
| a. Hecho pendiente | Variación 420 y línea 5655 PENDIENTE_CUENTA sin cuentas. | Cumple |
| b. Panel | La combinación apareció en M06; el conteo de pendientes pasó de 1 a 2. Cypress comprobó panel visible y conteo 2. | Cumple |
| c. Aviso | Se comprobó un aviso nuevo por API, el 12817: «Falta la cuenta contable de Variación por transformación biológica (pérdida) para Bovino. El registro quedó pendiente de cuenta y el período no podrá cerrarse hasta configurarla en Configuración contable.» Cypress comprobó la bandeja abierta y la combinación visible. | Cumple |
| d. Matriz | El POST resolvió dos líneas. La 5655 quedó REGISTRADA con débito 539505 y crédito 158405, iguales a los de la asignación creada 5139. El conteo final fue 0. | Cumple |

Antes de completar la matriz, los identificadores pendientes del período eran 1431 y 5655; después, la lista comprobada quedó vacía. La 1431 ya estaba pendiente antes de este RUN: el conteo base era 1. El POST resolvió ambas porque la matriz completada cubría las dos pendientes; es el comportamiento esperado al resolver pendientes. Según la verificación de rollback registrada, los cambios del sandbox se revirtieron y la 1431 volvió a su estado previo.

**Por qué se decide así.** El resultado acredita los cuatro pasos por API, y la comprobación UI obligatoria confirma panel y bandeja. La resolución de dos líneas explica que el conteo final sea 0; la línea del caso quedó registrada con las cuentas nuevas. Se usaron 39 de 150 solicitudes API y 10 solicitudes Cypress con presupuesto independiente.

**Decisión.** APROBADO.

## Comprobaciones y evidencias

La comprobación API G40-API-018-01 y la UI G40-UI-018-01 figuran APROBADAS en [resultado.json](resultado.json). Cypress registró una prueba aprobada: panel visible, conteo 2, bandeja abierta y combinación visible; constan [acta UI](cypress/G40-UI-018-01.json), [resumen Cypress](cypress/G40-cypress.json) y [captura](cypress/screenshots/g40.cy.js/G40-UI-018-01.png). Newman registró tres solicitudes, seis aserciones y ningún fallo en [JSON](newman/newman-G40.json) y [HTML](newman/newman-G40.html). Las lecturas API contrastadas, el preflight y la autorización constan en [resultado.json](resultado.json), [preflight.json](preflight.json) y [contexto_operacion.json](contexto_operacion.json). El código 0 acredita ejecución; el veredicto se apoya en las comprobaciones del caso.

## Incidencias y análisis

La incidencia V1 INC-M06-G40-01, por falta de aviso al Contador, queda CORREGIDA en esta V2: el aviso se comprobó por API y UI. No se acreditaron incidencias nuevas de producto ni problemas técnicos de automatización durante este RUN; no hay nueva severidad ni equipo que asignar. La severidad MEDIA y la derivación inicial a Desarrollo de V1 correspondían a la discrepancia entonces comprobada; la causa raíz sigue sin determinarse.

El intento V2 anterior, RUN-G40-V2-20261112-154819, quedó TECNICO por ERROR_QA del oráculo (d): exigía que el conteo global volviera a 1 aunque completar la matriz resolvía también una pendiente preexistente. ORD-G40-014 corrigió ese oráculo. Aquel intento ya había acreditado por API y UI el aviso 12796 para la ganancia; por eso este RUN eligió pérdida. Ese error de automatización no es una incidencia nueva del producto.

## Cierre, rollback y efectos persistentes

El cierre devolvió HTTP 200. resultado.json registra rollback verificado: matriz original restaurada, asignación nueva ausente, línea y variación del RUN ausentes, período ABIERTO, identificadores nuevos ausentes y ninguna escritura incierta. La verificación se limita a esas comprobaciones registradas.

Persisten fuera del rollback los avisos 12796 (ganancia, intento anterior) y 12817 (pérdida, este RUN) en las bandejas de los Contadores de la finca 468, con su evento M01.

## Conclusión y acciones

TC-M06-018 cumple CA-21 y FA-5 según las comprobaciones API y UI del RUN oficial APROBADO. No queda nada pendiente de evaluación dentro de este caso; el efecto sobre el cierre del período corresponde a otro caso de la matriz. La siguiente acción es cerrar INC-M06-G40-01 en el seguimiento, si corresponde al flujo del responsable QA.

## Enmienda documental (2026-11-12)

ORD-G40-017 ordenó esta enmienda del Markdown oficial. La [copia previa byte a byte](../../../historial_informes/TC-M06-G40_reevaluacion_V2.RUN-G40-V2-20261112-161443.antes-enmienda.md) tiene SHA-256 8CE216A5AEA265873E350132E0B90EBFF6F6E3DC747C5CC3B575126C837E81F3. [resultado.json](resultado.json) conserva SHA-256 2AA806C12AEE02E54C98B1CDBBA314DFA964C318114424BF73BAE843340D3124.

Se ordenó el detalle por caso, se corrigieron la redacción y las erratas, se explicó la elección de pérdida y la línea 1431, se contextualizó el intento técnico anterior y se precisaron incidencias, efectos persistentes y acciones. No cambian el veredicto, la oficialidad, el rollback ni la evidencia del RUN.
