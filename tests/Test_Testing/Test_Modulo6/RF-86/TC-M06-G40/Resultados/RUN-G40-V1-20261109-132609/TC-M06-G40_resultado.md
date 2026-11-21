# TC-M06-G40 — RECHAZADO

## Identificación

Grupo G40; caso TC-M06-018; RF-86 v2.0, CA-21 y FA-5; RUN RUN-G40-V1-20261109-132609; V1, intento 2; ambiente TEST; autorización AUT-G40-V1-R2-20261109; commit no consultado. Node v22.15.1; Newman 6.2.2 (código 0); Cypress 14.5.4 (código 0, 1 prueba). Oficial true.

## Veredicto y oráculo

| Caso | Estado | Motivo |
| --- | --- | --- |
| TC-M06-018 | RECHAZADO | a=true; b=true; c=false; d=true |

Esperado: no se crea línea registrada con cuentas; el hecho queda PENDIENTE_CUENTA visible en M06; alerta al Contador con combinación faltante; tras completar la matriz la misma línea queda REGISTRADA con las cuentas nuevas.

| Paso | Comprobación API/UI | Esperado | Observado | Resultado |
| --- | --- | --- | --- | --- |
| a | Hecho pendiente sin cuentas | PENDIENTE_CUENTA y ninguna línea registrada con cuentas | Variación 264 y línea 930 PENDIENTE_CUENTA sin cuentas. | Cumple |
| b | Panel de configuración | Pendiente visible y conteo incrementado | Aviso visible; líneas pendientes 0 → 1. | Cumple |
| c | Alerta al Contador | Aviso nuevo que identifica VARIACION_VR_TB/GANANCIA y especie | API: 0 avisos nuevos; UI: bandeja abierta con 20 anteriores y ningún aviso nuevo de la combinación. La combinación solo consta en auditoría; el panel no la detalla. | Falla |
| d | Matriz completada | La misma línea pasa a REGISTRADA con las cuentas nuevas | POST matriz 201 para especie 39, cuentas 158405 → 424805; línea 930 REGISTRADA; pendientes 0. | Cumple |

Activo 943, período 8, variación 264, línea 930. El pesaje devolvió HTTP 201 y el procesamiento HTTP 200. Auditoría LINEA_ASIENTO_PENDIENTE_CUENTA: {"tipo_hecho":"VARIACION_VR_TB","sentido":"GANANCIA","id_especie":39}. Solicitudes API 45/150. Cypress ejecutó el acta G40-UI-018-01: RECHAZADO; su código 0 acredita ejecución, no aprobación del producto.

## Contrato y evidencias

- /finanzas/activos: coincide, HTTP 200.
- /finanzas/periodos: coincide, HTTP 200.
- /finanzas/activos/943: coincide, HTTP 200.
- /activos-biologicos/943/ficha-integral: coincide, HTTP 200.
- /finanzas/precios?id_especie=39: coincide, HTTP 200.
- /finanzas/configuracion: coincide, HTTP 200.
- /finanzas/lineas?id_periodo_contable=8: coincide, HTTP 200.
- /finanzas/periodos/8/variaciones: coincide, HTTP 200.
- /finanzas/lineas?id_periodo_contable=8&estado=PENDIENTE_CUENTA: coincide, HTTP 200.
- /notificaciones?pagina=1&tamano=50: coincide, HTTP 200.
- /notificaciones?pagina=2&tamano=50: coincide, HTTP 200.
- /finanzas/auditoria?id_activo_biologico=943&id_periodo_contable=8&formato=TECNICO&tamano=500&pagina=1: coincide, HTTP 200.
- /finanzas/configuracion/matriz/12: coincide, HTTP 204.
- /finanzas/configuracion: coincide, HTTP 200.
- /activos-biologicos/943/eventos/crecimiento: coincide, HTTP 201.
- /finanzas/eventos/procesar: coincide, HTTP 200.
- /finanzas/periodos/8/variaciones: coincide, HTTP 200.
- /finanzas/lineas?id_periodo_contable=8: coincide, HTTP 200.
- /finanzas/configuracion: coincide, HTTP 200.
- /notificaciones?pagina=1&tamano=50: coincide, HTTP 200.
- /notificaciones?pagina=2&tamano=50: coincide, HTTP 200.
- /finanzas/auditoria?id_activo_biologico=943&id_periodo_contable=8&formato=TECNICO&tamano=500&pagina=1: coincide, HTTP 200.
- /finanzas/configuracion/matriz: coincide, HTTP 201.
- /finanzas/lineas?id_periodo_contable=8: coincide, HTTP 200.
- /finanzas/configuracion: coincide, HTTP 200.
- /finanzas/configuracion: coincide, HTTP 200.
- /finanzas/lineas?id_periodo_contable=8&estado=PENDIENTE_CUENTA: coincide, HTTP 200.
- /notificaciones?pagina=1&tamano=50: coincide, HTTP 200.

Evidencias: resultado.json, TC-M06-G40_resultado.md, cypress/G40-UI-018-01.json, cypress/G40-cypress.json, cypress/screenshots/g40.cy.js/G40-UI-018-01.png, newman/newman-G40.json, newman/newman-G40.html. D1: el producto modela una línea PENDIENTE_CUENTA sin cuentas en vez de omitir la línea; QA aprobó tratarlo como observación. La asignación genérica 12 se desactivó únicamente dentro del RUN (DELETE 204) y la matriz se restauró al cerrar.

## Incidencias y análisis

### INC-M06-G40-01 — FA-5: no se alerta al Contador de la combinación faltante

- Requisito: RF-86 v2.0 FA-5 y proceso, paso 11: alerta al Contador con la combinación faltante.
- Reproducción: dejar sin par VARIACION_VR_TB/GANANCIA para la especie del activo, registrar pesaje con ganancia y procesar.
- Esperado: aviso al Contador que identifique la combinación. Observado: línea PENDIENTE_CUENTA y conteo en el panel, sin aviso nuevo en bandeja por API ni UI; combinación visible solo en la auditoría.
- Impacto: el Contador debe revisar la auditoría para identificar el par; la línea pendiente impide cerrar el período hasta completar la matriz.
- Severidad: MEDIA. El pendiente es visible en el panel y en la auditoría, y completar la matriz permite resolverlo; falla el aviso dirigido con la combinación.
- Certeza: CONFIRMADA. Equipo inicial: Desarrollo. Fundamento: Primera discrepancia comprobada por API y UI pública de M06; causa raíz no determinada
- Causa raíz: NO DETERMINADA. El código consultado en contabilizador.py:70-86 registra la auditoría y no muestra una llamada al notificador; es apoyo para investigar, no prueba de la causa en TEST.
- Evidencias: resultado.json, cypress/G40-UI-018-01.json, cypress/screenshots/g40.cy.js/G40-UI-018-01.png y newman/.

Problemas técnicos de automatización: ninguno durante el RUN. El bloque Cypress de la raíz corrige el formato que consume el registro QA.


## Cierre y rollback

DELETE HTTP 200; rollback verificado: matriz original true; nueva ausente true; línea ausente true; variación ausente true; IDs nuevos ausentes true; escritura incierta false.

## Conclusión

Remitir el RUN oficial RECHAZADO al responsable QA para actualizar el registro y derivar INC-M06-G40-01 a Desarrollo; solicitar corrección y reevaluar solo con autorización.

Actualización del informe (2026-11-09): bloque cypress para el registro e incidencia completa; veredicto sin cambios.
