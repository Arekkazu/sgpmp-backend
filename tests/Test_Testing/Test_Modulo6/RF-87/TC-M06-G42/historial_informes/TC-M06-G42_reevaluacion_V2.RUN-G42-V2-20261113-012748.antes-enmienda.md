# TC-M06-G42 ? RUN oficial

## Identificación

Grupo G42; casos TC-M06-021, TC-M06-022 y TC-M06-023; RF-87 v1.1; V2; RUN RUN-G42-V2-20261113-012748; ambiente TEST; autorización AUT-G42-V2-R3-20261112. Código TEST 453277e4 declarado por QA, no comprobado contra TEST en este RUN. Node v22.15.1; Newman 6.2.2. UI: cero ejecuciones; no requerida por la matriz.

## Resumen de veredictos

| Caso | Esperado | Observado | Estado |
| --- | --- | --- | --- |
| TC-M06-021 | Cuatro variaciones TB/PM consolidadas por tipo, ejecutor, timestamp y origen del cierre | cuatro tipos, sumas, ejecutor y origen conformes | APROBADO |
| TC-M06-022 | Comprobante por titular, hecho y especie; suma por par, código, fecha, descarga e inmutabilidad | comprobantes, sumas, descargas e inmutabilidad conformes | APROBADO |
| TC-M06-023 | RF-93 clasifica los cuatro costos por tipo en noviembre, excluye diciembre y no aumenta el valor razonable | costos por tipo y período, valor razonable conformes | APROBADO |

## Preflight vivo y preparación

| Período | Estado leído | Puede cerrar | Bloqueos iniciales |
| --- | --- | --- | --- |
| 220 | ABIERTO | true | ninguno |
| 241 | ABIERTO | false | LINEAS_PENDIENTE_CUENTA |

Se seleccionó el bovino 1627 para TB+ y TB-; se prepararon 1832 (peso 380 a 381 kg) y 1833 (peso 400 a 400 kg) para PM-/PM+; se excluyó 1831 por su antecedente IoT. Precio vigente leído para el bovino: 18; especie caprina: 435; especie del 1572: 438. Líneas pendientes resueltas por la matriz: 1431.

En el RUN previo, la línea preexistente 1431 del período 241 correspondía a DEPRECIACION_ACTIVO_COSTO/UNICO, especie 39, sin subtipo. Una asignación genérica ya podía cubrirla sin que eso cambiara su estado PENDIENTE_CUENTA. Si una línea pendiente cubierta por asignación genérica aparece en este RUN, se guarda una asignación específica para su especie con las mismas cuentas que la genérica; si la cobertura ya es específica, se vuelve a guardar esa combinación con las mismas cuentas. La respuesta de cada guardado, el ID creado y la prevalidación inmediata constan en diagnostico_preflight.resolucion_241 y prevalidaciones.241.tras_resolucion de resultado.json. Si no se resuelve al menos una línea o persiste el bloqueo, la preparación termina NO_CONCLUYENTE y se ejecuta DELETE. Esta preparación no cambia los oráculos de TC-M06-021, 022 ni 023.

## TC-M06-021

**Qué se verifica.** El asiento consolidado del 241 contiene ganancia y pérdida TB y PM, cada total igual a la suma de líneas del tipo, sin doble conteo; lleva ejecutor, timestamp inmutable y origen del cierre.

**Preparación.** Se usaron los bovinos elegibles de finca 468 y se crearon eventos y precios dentro del RUN para producir los cuatro signos. Peso inicial 395 kg; pesajes 396 y 394 kg.

**Qu? se hizo y observ?.** Cierre HTTP 200. Ejecutor 5; timestamp 2026-11-13T01:27:51.253391Z.

| Tipo | Sentido | Variaciones | Suma líneas | Total comprobante |
| --- | --- | ---: | ---: | ---: |
| VARIACION_VR_TB | GANANCIA | 3 | 154395.00 | 154395.00 |
| VARIACION_VR_TB | GANANCIA | 1 | 54050.00 | 54050.00 |
| VARIACION_VR_TB | PERDIDA | 1 | 32430.00 | 32430.00 |
| VARIACION_VR_TB | PERDIDA | 1 | 17766.00 | 17766.00 |
| VARIACION_VR_PM | GANANCIA | 6 | 2704803.00 | 2704803.00 |
| VARIACION_VR_PM | PERDIDA | 2 | 556104.00 | 556104.00 |

**Esperado y decisión.** Se aplicó el oráculo de la matriz sin modificarlo. cuatro tipos, sumas, ejecutor y origen conformes. Estado: **APROBADO**.

## TC-M06-022

**Qué se verifica.** Comprobantes del 241 y 220 por titular, tipo y especie, con suma por par, código NIC, fecha de ?ltimo d?a de cada per?odo, CSV/PDF e inmutabilidad.

**Preparación y ejecución.** Se conservaron los dos titulares y especies de V1 y se cerraron los períodos necesarios. Se leyeron líneas RF-86, comprobantes y descargas; se intentaron PUT y DELETE y se releyeron hashes.

| Código | Tipo | Especie | Líneas | Fecha |
| --- | --- | ---: | ---: | --- |
| NIC-[NIT]-202611-CONSUMO_INSUMO-1 | CONSUMO_INSUMO | 1 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-CONSUMO_INSUMO-39 | CONSUMO_INSUMO | 39 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-DEPRECIACION_ACTIVO_COSTO-39 | DEPRECIACION_ACTIVO_COSTO | 39 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-PRODUCTO_AGRICOLA-1 | PRODUCTO_AGRICOLA | 1 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-RECONOCIMIENTO_DIFERENCIA-1 | RECONOCIMIENTO_DIFERENCIA | 1 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-RECONOCIMIENTO_DIFERENCIA-39 | RECONOCIMIENTO_DIFERENCIA | 39 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-VARIACION_VR_PM-39 | VARIACION_VR_PM | 39 | 2 | 2026-11-30 |
| NIC-[NIT]-202611-VARIACION_VR_TB-1 | VARIACION_VR_TB | 1 | 2 | 2026-11-30 |
| NIC-[NIT]-202611-VARIACION_VR_TB-39 | VARIACION_VR_TB | 39 | 2 | 2026-11-30 |
| NIC-[NIT]-202611-DEPRECIACION_ACTIVO_COSTO-423 | DEPRECIACION_ACTIVO_COSTO | 423 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-MANO_OBRA_PROPIA-422 | MANO_OBRA_PROPIA | 422 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-RECONOCIMIENTO_DIFERENCIA-422 | RECONOCIMIENTO_DIFERENCIA | 422 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-VARIACION_VR_PM-422 | VARIACION_VR_PM | 422 | 1 | 2026-11-30 |
| NIC-[NIT]-202611-VARIACION_VR_PM-423 | VARIACION_VR_PM | 423 | 2 | 2026-11-30 |

**Observado y decisión.** comprobantes, sumas, descargas e inmutabilidad conformes. Estado: **APROBADO**.

## TC-M06-023

**Qué se verifica.** RF-93 muestra ALIMENTO, MEDICAMENTO, MANO_OBRA y VETERINARIO del mes más los costos previos del mismo período; la suma coincide con costos_mantenimiento. Diciembre excluye noviembre y los costos no aumentan el valor razonable.

**Preparación y ejecución.** Se registraron los cuatro costos RF-90 del RUN, se cerró noviembre de NIT-C y luego diciembre, y se compararon RF-93 y mediciones.

| Tipo | ID costo del RUN | Monto |
| --- | ---: | ---: |
| VETERINARIO | 4452 | 104.0000 |
| MANO_OBRA | 4451 | 103.0000 |
| MEDICAMENTO | 4450 | 102.0000 |
| ALIMENTO | 4449 | 101.0000 |

| Tipo | Esperado con costos previos | Observado RF-93 |
| --- | ---: | ---: |
| ALIMENTO | 150101.0000 | 150101.0000 |
| MEDICAMENTO | 102.0000 | 102.0000 |
| MANO_OBRA | 103.0000 | 103.0000 |
| VETERINARIO | 104.0000 | 104.0000 |

**Observado y decisión.** Total noviembre 150410.0000; diciembre 0; valor razonable con costos 4230000.0000, sin costos 4230000.0000. costos por tipo y período, valor razonable conformes. Estado: **APROBADO**.

## Comprobaciones y evidencias

- G42-API-021-01: APROBADO; cuatro tipos, sumas, ejecutor y origen conformes. Evidencia: resultado.json.
- G42-API-022-01: APROBADO; comprobantes, sumas, descargas e inmutabilidad conformes. Evidencia: resultado.json.
- G42-API-023-01: APROBADO; costos por tipo y período, valor razonable conformes. Evidencia: resultado.json.

Solicitudes 178/300; Newman código 0, fallos 0. Archivos generados: descargas/comprobantes-241.csv, descargas/comprobantes-220.csv, newman/newman-G42.json, newman/newman-G42.html.

## Seguimiento e incidencias

INC-M06-G32-01 para 021: CORREGIDA. INC-M06-G42-01 para 023: CORREGIDA. 022 se evalu? como regresión.

Sin incidencia nueva acreditada.

Problemas técnicos o de datos: ninguno.

## Efectos persistentes, cierre y rollback

- Período 241, aviso 13378: ?Al cerrar el período 2026-11, estos activos valorados por costo ya tienen precio de mercado para su especie: BOV-116-TIL. La NIC 41 ¶30 exige pasarlos a valor razonable.?.
- Período 241, aviso 13372: ?Período 2026-11 cerrado: listo para transferir desde Agrofusión.?.
- Período 220, aviso 13402: ?Al cerrar el período 2026-11, estos activos valorados por costo ya tienen precio de mercado para su especie: QA-M06O-COSTO-02. La NIC 41 ¶30 exige pasarlos a valor razonable.?.
- Período 220, aviso 13396: ?Período 2026-11 cerrado: listo para transferir desde Agrofusión.?.
- Período 391, aviso 13414: ?Al cerrar el período 2026-12, estos activos valorados por costo ya tienen precio de mercado para su especie: QA-M06O-COSTO-02. La NIC 41 ¶30 exige pasarlos a valor razonable.?.
- Período 391, aviso 13408: ?Período 2026-12 cerrado: listo para transferir desde Agrofusión.?. Los avisos de cierre y alertas NIC 41 registradas pueden persistir fuera del rollback del sandbox. DELETE HTTP 200. Rollback VERIFICADO: Lecturas poscierre coinciden con línea base.

## Conclusión y acción

Se cumplieron todas las condiciones de oficialidad. Entregar el RUN y derivar las discrepancias confirmadas a Desarrollo.
