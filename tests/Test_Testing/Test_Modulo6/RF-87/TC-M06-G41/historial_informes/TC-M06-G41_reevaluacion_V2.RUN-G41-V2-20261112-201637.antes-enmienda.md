# TC-M06-G41 — reevaluación V2 oficial

## Identificación

G41; caso TC-M06-019; RF-87 v1.1; V2; RUN RUN-G41-V2-20261112-201637; ambiente TEST; autorización AUT-G41-V2-R4-20261112; commit declarado por QA: origin/test 453277e4; Node v22.15.1; Newman 6.2.2.

TC-M06-020 quedó APROBADO en V1, RUN-G41-V1-20261109-175216. No se ejecuta ni evalúa en V2.

## Veredicto y seguimiento

TC-M06-019: APROBADO. Motivo: Criterios a-f conformes. INC-M06-G41-01: CORREGIDA. Oficialidad: cumple.

## Caso TC-M06-019

**Qué se verifica.** ABIERTO → EN_CIERRE → CERRADO; activos VR revaluados con los seis campos de RF-87; 1571 BAJA sin revaluación y activos COSTO sin medición de cierre; siguiente ABIERTO; aviso nuevo exacto al Contador; RF-92 y RF-93 con resultado neto.

**Preparación.** El 1572 pasó a valor razonable el 2026-11-10 por acción de un Contador en TEST; se espera revaluado si conserva ese método. El 1573 sigue por costo según la consulta de QA. Esto no cambia RF-87. Clasificación leída: VR 1569, 1570, 1572, COSTO 1573. Preflight vivo: CONFORME; período 220 ABIERTO; motivos ninguno; activos {"1569":{"estado":"ACTIVO","valorado_por_costo":false,"id_especie":422,"detalle_valorado_por_costo":false},"1570":{"estado":"ACTIVO","valorado_por_costo":false,"id_especie":422,"detalle_valorado_por_costo":false},"1571":{"estado":"ACTIVO","valorado_por_costo":false,"id_especie":422,"detalle_valorado_por_costo":false},"1572":{"estado":"ACTIVO","valorado_por_costo":false,"id_especie":423,"detalle_valorado_por_costo":false},"1573":{"estado":"ACTIVO","valorado_por_costo":true,"id_especie":423,"detalle_valorado_por_costo":true}}; precios VR {"422":{"categoria":"POR_CABEZA","ids_vigentes":[435],"simulacion_id":435},"423":{"categoria":"POR_CABEZA","ids_vigentes":[438]}}; prevalidación {"bloqueos":[],"activos_sin_precio":[],"lineas_sin_trazabilidad":[],"puede_cerrar":true,"requiere_autorizacion":false}. Dentro del RUN se registró un precio nuevo por especie VR para que cada activo tuviera variación, como en V1: [{"id_especie":422,"id_precio_mercado":668,"indice":1,"precio_anterior":"4000000.00","precio_nuevo":"5000000.00","umbral_pct":"50.00","desviacion_pct":25,"confirmar_desviacion":false},{"id_especie":423,"id_precio_mercado":669,"indice":2,"precio_anterior":"4300000.00","precio_nuevo":"4837500.00","umbral_pct":"50.00","desviacion_pct":12.5,"confirmar_desviacion":false}]. Precio usado y variación esperada por activo VR: {"1569":{"id_especie":422,"id_precio_mercado":668,"precio_unitario":"5000000.00","precio_anterior":"4000000.00","variacion_precio_unitario":"1000000.00","esperada_no_cero":true},"1570":{"id_especie":422,"id_precio_mercado":668,"precio_unitario":"5000000.00","precio_anterior":"4000000.00","variacion_precio_unitario":"1000000.00","esperada_no_cero":true},"1572":{"id_especie":423,"id_precio_mercado":669,"precio_unitario":"4837500.00","precio_anterior":"4300000.00","variacion_precio_unitario":"537500.00","esperada_no_cero":true}}.

**Qué se hizo.** Un cierre del período 220, HTTP 200, id 69. Se consultaron período, activos, mediciones, variaciones, auditoría, reportes y bandeja completa del Contador QA. No se autorizaron exclusiones.

**Esperado.** El Contador recibe «Período 2026-11 cerrado: listo para transferir desde Agrofusión.» con id nuevo frente a la línea base. Los criterios a, b, c, d y f mantienen el oráculo de V1.

**Observado.** Período CERRADO, fecha de cierre 2026-11-12T20:16:39.497414Z; procesados 4; excluidos ninguno. Período siguiente 366 ABIERTO. RF-92 id 73 (API 73); RF-93 id 63 (API 63), resultado neto -1152750.0000. Aviso nuevo id 12947, texto «Período 2026-11 cerrado: listo para transferir desde Agrofusión.». Alertas NIC 41 observadas: 12953 Al cerrar el período 2026-11, estos activos valorados por costo ya tienen precio de mercado para su especie: QA-M06O-COSTO-02. La NIC 41 ¶30 exige pasarlos a valor razonable..

**Mediciones del cierre.**

- Activo 1572: valor razonable inicio 4042000.0000, cierre 4547250.0000, variación total 505250.0000, transformación 0.0000, precio 505250.0000, método valor razonable.
- Activo 1570: valor razonable inicio 3760000.0000, cierre 4700000.0000, variación total 940000.0000, transformación 0.0000, precio 940000.0000, método valor razonable.
- Activo 1569: valor razonable inicio 3760000.0000, cierre 4700000.0000, variación total 940000.0000, transformación 0.0000, precio 940000.0000, método valor razonable.

**Por qué se decide.** Criterios a-f conformes; fallos: ninguno.

## Comprobaciones API y evidencias

- G41-API-019-01: APROBADO; Criterios a-f conformes

Solicitudes 72/130; Newman código 0, fallos 0. Evidencias reales: resultado.json, preflight.json, newman/newman-G41.json, newman/newman-G41.html. No hay UI obligatoria.

## Incidencias y análisis de causas

No se acreditó una incidencia de producto nueva.

Problemas técnicos o de datos: ninguno. Permisos faltantes: Contador ninguno; Administrador ninguno.

## Cierre y rollback

DELETE HTTP 200; rollback verificado: Lecturas poscierre sin cabeceras del RUN coinciden con línea base. El aviso de cierre, si se emitió, llega a cada Contador del sistema sin filtro de finca y persiste fuera del rollback con el texto «2026-11 cerrado», aunque el período 220 quede ABIERTO. Pueden persistir alertas NIC 41 emitidas por los precios nuevos, una por especie VR, además de la alerta del párrafo 30 si el 1573 por costo tiene precio de su especie.

## Conclusión y acción

Remitir el resultado V2 y el seguimiento de INC-M06-G41-01 al responsable QA.
