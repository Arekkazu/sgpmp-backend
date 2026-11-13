# TC-M06-G40 — APROBADO

## Identificación

Grupo G40; caso TC-M06-018; RF-86 v2.0, CA-21 y FA-5; RUN RUN-G40-V2-20261112-161443; V2, intento 4; operación REINTENTAR, V1 previo; ambiente TEST; autorización AUT-G40-V2-R2-20261112; referencia backend origin/test 453277e4 (despliegue a verificar en RUN). Node v22.15.1; Newman 6.2.2 (código 0); Cypress 14.5.4 (código 0, 1 prueba). Oficial true.

## Veredicto y oráculo

| Caso | Estado | Motivo |
| --- | --- | --- |
| TC-M06-018 | APROBADO | a=true; b=true; c=true; d=true |

Esperado: no se crea línea registrada con cuentas; el hecho queda PENDIENTE_CUENTA visible en M06; alerta al Contador con combinación faltante; tras completar la matriz la misma línea queda REGISTRADA con las cuentas nuevas.

| Paso | Comprobación API/UI | Esperado | Observado | Resultado |
| --- | --- | --- | --- | --- |
| a | Hecho pendiente sin cuentas | PENDIENTE_CUENTA y ninguna línea registrada con cuentas | Variación 420 y línea 5655 PENDIENTE_CUENTA sin cuentas. | Cumple |
| b | Panel de configuración | Pendiente visible y conteo incrementado | Aviso visible; líneas pendientes 1 → 2. | Cumple |
| c | Alerta al Contador | Aviso nuevo que identifica VARIACION_VR_TB/PERDIDA y Bovino | API: 1 avisos nuevos; aviso coincidente 12817: Falta la cuenta contable de Variación por transformación biológica (pérdida) para Bovino. El registro quedó pendiente de cuenta y el período no podrá cerrarse hasta configurarla en Configuración contable.. UI: bandeja abierta, texto coincidente visible. | Cumple |
| d | Matriz completada | La misma línea pasa a REGISTRADA con las cuentas nuevas | POST matriz HTTP 201: 2 líneas resueltas; línea 5655 REGISTRADA con débito 539505 y crédito 158405; asignación creada 5139 con débito 539505 y crédito 158405; conteos base 1, pendiente 2, final 0. | Cumple |

Detalle del caso — qué se verifica: el hecho pendiente, su visibilidad en M06, el aviso al Contador y la resolución al completar la matriz. Preparación: activo 1833, período 241, combinación VARIACION_VR_TB/PERDIDA/Bovino. Modo AUTO; Se usó pérdida porque la ganancia de Bovino ya tenía aviso en el período 241 (aviso 12796). Se identificaron 1 asignaciones del sentido elegido. Qué se hizo: se registró el pesaje y se observó la variación 420 y la línea 5655. Esperado: los cuatro pasos del oráculo original. Observado: paso a cumple, b cumple, c cumple y d cumple; aviso 12817; auditoría pendiente acreditada. Antes del POST, los IDs pendientes del período fueron 1431, 5655; después, ninguno o no comprobados. El POST resolvió además otras líneas pendientes preexistentes; es el comportamiento esperado de resolver_pendientes. Por qué se decide: se cumplieron los cuatro pasos; veredicto aprobado. Solicitudes API 39/150; solicitudes Cypress 10 con presupuesto independiente. Cypress: APROBADO; un código 0 acredita ejecución, no funcionalidad.

## Contrato y evidencias

- /finanzas/activos: coincide, HTTP 200.
- /finanzas/periodos: coincide, HTTP 200.
- /finanzas/activos/1833: coincide, HTTP 200.
- /activos-biologicos/1833/ficha-integral: coincide, HTTP 200.
- /finanzas/precios?id_especie=39: coincide, HTTP 200.
- /finanzas/configuracion: coincide, HTTP 200.
- /finanzas/lineas?id_periodo_contable=241: coincide, HTTP 200.
- /finanzas/periodos/241/variaciones: coincide, HTTP 200.
- /finanzas/lineas?id_periodo_contable=241&estado=PENDIENTE_CUENTA: coincide, HTTP 200.
- /notificaciones?pagina=1&tamano=50: coincide, HTTP 200.
- /notificaciones?pagina=2&tamano=50: coincide, HTTP 200.
- /notificaciones?pagina=3&tamano=50: coincide, HTTP 200.
- /finanzas/auditoria?id_activo_biologico=1833&id_periodo_contable=241&formato=TECNICO&tamano=500&pagina=1: coincide, HTTP 200.
- /finanzas/configuracion/matriz/13: coincide, HTTP 204.
- /finanzas/configuracion: coincide, HTTP 200.
- /activos-biologicos/1833/eventos/crecimiento: coincide, HTTP 201.
- /finanzas/eventos/procesar: coincide, HTTP 200.
- /finanzas/periodos/241/variaciones: coincide, HTTP 200.
- /finanzas/lineas?id_periodo_contable=241: coincide, HTTP 200.
- /finanzas/configuracion: coincide, HTTP 200.
- /notificaciones?pagina=1&tamano=50: coincide, HTTP 200.
- /notificaciones?pagina=2&tamano=50: coincide, HTTP 200.
- /notificaciones?pagina=3&tamano=50: coincide, HTTP 200.
- /finanzas/auditoria?id_activo_biologico=1833&id_periodo_contable=241&formato=TECNICO&tamano=500&pagina=1: coincide, HTTP 200.
- /finanzas/configuracion/matriz: coincide, HTTP 201.
- /finanzas/lineas?id_periodo_contable=241: coincide, HTTP 200.
- /finanzas/configuracion: coincide, HTTP 200.
- /finanzas/configuracion: coincide, HTTP 200.
- /finanzas/lineas?id_periodo_contable=241&estado=PENDIENTE_CUENTA: coincide, HTTP 200.
- /notificaciones?pagina=1&tamano=50: coincide, HTTP 200.

Evidencias reales: cypress/G40-UI-018-01.json, cypress/G40-cypress.json, cypress/screenshots/g40.cy.js/G40-UI-018-01.png, newman/newman-G40.json, newman/newman-G40.html. D1: la línea PENDIENTE_CUENTA sin cuentas representa el hecho pendiente. La matriz del sentido elegido se desactiva solo en el RUN. El aviso ALERTA_FINANCIERA_NIC41 persiste fuera del rollback: uno por cada Contador activo de la finca 468 y un evento M01, si el backend lo emitió.

## Incidencias y análisis

Ninguna incidencia de producto acreditada.
Seguimiento INC-M06-G40-01: CORREGIDA. Problemas técnicos de automatización: ninguno durante el RUN. Oficialidad: se cumplieron los criterios de API, UI, Newman, presupuesto y rollback.

## Cierre y rollback

DELETE HTTP 200; rollback de datos del sandbox verificado: matriz original true; nueva ausente true; línea ausente true; variación ausente true; período ABIERTO true; IDs nuevos ausentes true; escritura incierta false. El aviso persistente y su evento M01 quedan excluidos del rollback.

## Conclusión

Remitir el RUN oficial APROBADO al responsable QA; actualizar INC-M06-G40-01 como CORREGIDA.
