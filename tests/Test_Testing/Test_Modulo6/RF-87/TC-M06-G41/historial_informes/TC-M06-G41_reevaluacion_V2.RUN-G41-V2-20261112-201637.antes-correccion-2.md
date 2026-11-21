# TC-M06-G41 — reevaluación V2 oficial

## Identificación

Grupo G41; caso TC-M06-019; RF-87 v1.1, CA-1, CA-7 y CA-11; V2, intento 8; RUN RUN-G41-V2-20261112-201637; operación REINTENTAR; ambiente TEST; autorización AUT-G41-V2-R4-20261112. Commit declarado por QA: origin/test 453277e4 (despliegue no comprobado aquí). Herramientas registradas: Node v22.15.1 y Newman 6.2.2.

## Veredicto y seguimiento

| Caso | Estado | Motivo |
| --- | --- | --- |
| TC-M06-019 | APROBADO | Criterios a–f conformes según las comprobaciones API de este RUN. |

INC-M06-G41-01: CORREGIDA. TC-M06-020 quedó APROBADO en V1, RUN-G41-V1-20261109-175216; no se ejecutó ni evaluó en esta V2. Oficialidad: el caso 019 quedó decidido, Newman terminó sin fallos, se usaron 72 de 130 solicitudes API, el DELETE devolvió HTTP 200 y el rollback quedó verificado en `resultado.json`.

## Detalle por caso

### TC-M06-019

**Qué se verifica.** La matriz de casos, fila 384, y RF-87 exigen cerrar el período mensual, revaluar los activos incluidos con los seis campos de medición, excluir el dado de baja, abrir el período siguiente, avisar al Contador y generar RF-92 y RF-93.

**Preparación.** El período 220 (2026-11) estaba ABIERTO. El preflight vivo fue CONFORME: sin bloqueos, activos sin precio ni líneas sin trazabilidad; la prevalidación permitió cerrar sin autorización de exclusiones. El 1572 pasó a valor razonable el 2026-11-10 por acción de un Contador (auditoría 9660, según ORD-G41-020). Por ello se creó un precio nuevo por cada especie valorada a valor razonable, de modo que los tres activos correspondientes tuvieran variación de precio. El 1573 seguía valorado por costo.

| Activo | Especie | Estado de base | Método de base | Papel en la prueba |
| --- | ---: | --- | --- | --- |
| 1569 | 422 | ACTIVO | Valor razonable | Revaluación de activo activo. |
| 1570 | 422 | ACTIVO | Valor razonable | Pasa a EN_TRATAMIENTO en el RUN y se revalúa. |
| 1571 | 422 | ACTIVO | Valor razonable | Recibe baja en el RUN; sin revaluación. |
| 1572 | 423 | ACTIVO | Valor razonable | Revaluación con precio de su especie. |
| 1573 | 423 | ACTIVO | Costo | Sin medición de valor razonable de cierre; alerta NIC 41 ¶30. |

| Especie | Precio anterior | Precio nuevo | Desviación | Umbral |
| --- | ---: | ---: | ---: | ---: |
| 422 | 4.000.000,00 | 5.000.000,00 (id 668) | 25 % | 50 % |
| 423 | 4.300.000,00 | 4.837.500,00 (id 669) | 12,5 % | 50 % |

Los precios vigentes previos eran 435 para la especie 422 y 438 para la 423, ambos por cabeza. Ningún precio nuevo requirió confirmar desviación.

**Qué se hizo.**

1. Se autenticó al Contador y al Administrador (POST, HTTP 200) y se leyeron permisos, período, activos, precios, simulación, matriz, prevalidación, mediciones, variaciones, líneas, auditoría y bandejas para fijar la línea base (GET, HTTP 200).
2. Se cambió el estado del 1570 con `PATCH /activos-biologicos/1570/estado` (HTTP 200), se registró la baja del 1571 con POST (HTTP 201) y se procesaron los eventos con `POST /finanzas/eventos/procesar` (HTTP 200). Se leyeron las líneas (GET, HTTP 200).
3. Se crearon los precios 668 y 669 con dos `POST /finanzas/precios` (HTTP 201 cada uno), seguidos de lecturas de precios, prevalidación y bandejas (GET, HTTP 200).
4. Se ejecutó `POST /finanzas/periodos/220/cierre` (HTTP 200, cierre 69), sin autorizar exclusiones.
5. Se leyeron período, activos, mediciones, variaciones, cálculos, líneas, auditoría, bandejas y los reportes RF-93 id 63 y RF-92 id 73 (GET, HTTP 200). El `DELETE /test-control/runs/RUN-G41-V2-20261112-201637` devolvió HTTP 200; luego se repitieron las lecturas para comprobar el rollback.

**Qué se esperaba.** La fila 384 de la matriz y RF-87 establecen estos criterios:

a. El período pasa de ABIERTO a EN_CIERRE y luego a CERRADO.
b. Los activos ACTIVO y EN_TRATAMIENTO se revalúan con `valor_razonable_inicio`, `valor_razonable_cierre`, `variacion_total`, `variacion_transformacion_biologica`, `variacion_precio_mercado` y `metodo_valoracion`.
c. El activo en BAJA queda excluido de la revaluación; el activo por costo no genera medición de valor razonable de cierre.
d. El período siguiente se abre automáticamente en ABIERTO.
e. El Contador recibe un aviso nuevo: «Período 2026-11 cerrado: listo para transferir desde Agrofusión.».
f. Se generan el informe de revelaciones NIC 41 (RF-92) y el estado de resultados (RF-93) con resultado neto.

**Qué se observó.**

| Criterio | Observación acreditada | Resultado |
| --- | --- | --- |
| a. Estado | El 220 estaba ABIERTO; el cierre 69 devolvió HTTP 200 y CERRADO, con fecha 2026-11-12T20:16:39.497414Z. No consta lectura independiente del estado transitorio EN_CIERRE. | Cumple el flujo de cierre comprobado, con esa limitación de observación. |
| b. Revaluación | Mediciones de cierre para 1569, 1570 y 1572, clasificados a valor razonable. Constan inicio, cierre, variación total, transformación y precio. | Cumple. |
| c. Baja y costo | El 1571 recibió baja y no figura entre las mediciones; el 1573 figura por costo y tampoco tiene medición. El cierre informó cuatro activos procesados y ninguna exclusión autorizada. | Cumple. |
| d. Siguiente período | El cierre identificó el 366 y la lectura posterior lo encontró ABIERTO. | Cumple. |
| e. Aviso | La bandeja registró el aviso nuevo 12947 con el texto exigido; se registraron cuatro avisos nuevos. | Cumple. |
| f. Reportes | RF-92: informe 73; RF-93: estado 63 y resultado neto −1.152.750,0000 en la lectura API. | Cumple. |

| Activo | Valor razonable inicio | Valor razonable cierre | Variación total | Transformación | Precio de mercado |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1569 | 3.760.000,0000 | 4.700.000,0000 | 940.000,0000 | 0,0000 | 940.000,0000 |
| 1570 | 3.760.000,0000 | 4.700.000,0000 | 940.000,0000 | 0,0000 | 940.000,0000 |
| 1572 | 4.042.000,0000 | 4.547.250,0000 | 505.250,0000 | 0,0000 | 505.250,0000 |

También se observó la alerta NIC 41 ¶30 id 12953 para el activo por costo identificado como QA-M06O-COSTO-02. Su mensaje termina en «La NIC 41 ¶30 exige pasarlos a valor razonable.».

**Por qué se decide así.** La comprobación API `G41-API-019-01` figura APROBADA y `observado.019.fallos` está vacío. El cierre y las lecturas posteriores acreditan el resultado de los seis criterios; la transición EN_CIERRE no tiene lectura separada. No hay comprobación UI obligatoria para este caso.

**Decisión.** APROBADO.

## Intentos técnicos previos de V2

El RUN-G41-V2-20261112-173232 preparó el 1572 a valor razonable desde el 2026-11-10, según ORD-G41-020. El RUN-G41-V2-20261112-180027 tuvo un contexto de operación sin `alcance.casos`. El RUN-G41-V2-20261112-180221 creó precio solo para la especie 422: el 1572, de la especie 423, quedó sin variación y sin medición de cierre; ese intento ya acreditó el aviso 12870. Estos antecedentes explican los reintentos; ninguno se usa como evidencia del veredicto de este RUN oficial.

## Comprobaciones y evidencias

La comprobación API `G41-API-019-01`, el preflight, las solicitudes y el rollback constan en [resultado.json](resultado.json), [preflight.json](preflight.json) y [contexto_operacion.json](contexto_operacion.json). Se usaron 72 de 130 solicitudes API. Newman terminó con código 0: cuatro solicitudes, nueve aserciones y cero fallos, acreditados en sus reportes [JSON](newman/newman-G41.json) y [HTML](newman/newman-G41.html). No hay UI obligatoria para TC-M06-019.

## Incidencias y análisis de causas

No se acreditó una incidencia nueva de producto. INC-M06-G41-01 queda CORREGIDA por el aviso nuevo comprobado; no se atribuye una causa raíz técnica. No se registraron problemas del ejecutor ni permisos faltantes del Contador o el Administrador en este RUN. Los antecedentes técnicos de V2 no son incidencias del producto.

## Cierre, rollback y efectos persistentes

El cierre del período 220 devolvió HTTP 200. El DELETE de rollback también devolvió HTTP 200; `resultado.json` marca rollback verificado porque las lecturas posteriores sin cabeceras del RUN coincidieron con la línea base: período 220 ABIERTO, estados, mediciones, variaciones, cálculos, líneas, matriz, eventos, detalles y reportes restaurados. Los precios 668 y 669 se revirtieron, incluidos los controles por especie 422 y 423.

Persisten fuera del rollback los avisos de cierre 12870 (intento técnico 180221) y 12947 (este RUN) para cada Contador, y las alertas NIC 41 ¶30 12876 y 12953, respectivamente. Esta persistencia no altera la verificación del rollback de los datos cubiertos por las lecturas.

## Conclusión y acciones

TC-M06-019 cumple el cierre mensual y los criterios CA-1, CA-7 y CA-11 de RF-87 comprobados en esta V2; INC-M06-G41-01 queda CORREGIDA. TC-M06-020 no se evaluó en V2: su resultado APROBADO pertenece a V1. La siguiente acción es remitir este resultado al responsable QA y cerrar la incidencia en el seguimiento si corresponde a su flujo.

**Observación para QA, sin incidencia.** En el intento técnico 180221, el 1572 no tuvo variación y el cierre no guardó medición; quedó solo la auditoría `MEDICION_SIN_VARIACION`. ORD-G41-020 cita `medidor.py:108-127` como contexto. Queda como pregunta de requisito para la líder QA si debe persistirse una medición de variación cero; no se trata como defecto ni cambia el veredicto de este RUN.

## Enmienda documental (2026-11-12)

ORD-G41-020 ordenó esta enmienda del Markdown oficial. La [copia previa byte a byte](../../../historial_informes/TC-M06-G41_reevaluacion_V2.RUN-G41-V2-20261112-201637.antes-enmienda.md) tiene SHA-256 `3CBCBF7BB9C871A9277C70F460912E558D7A4BEA12E88672D317DD7D33C8F100`. [resultado.json](resultado.json) conserva SHA-256 `9A35E7FD8F5D0CB9F7D7B2B227A81EF37DA6E314142982B81B48421825583F47`.

Se sustituyó el JSON crudo por prosa y tablas, se detallaron preparación, solicitudes HTTP, oráculo y observaciones por criterio, se contextualizaron los tres intentos técnicos y el cambio de método del 1572, y se precisaron oficialidad, efectos persistentes, conclusión y acción. No cambian el veredicto, la oficialidad, el rollback ni la evidencia del RUN.
