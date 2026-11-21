# TC-M06-G42 — reevaluación V2 oficial

## Identificación

Grupo G42; casos TC-M06-021, TC-M06-022 y TC-M06-023; RF-87 v1.1; matriz `Casos_Prueba(Modulo6Agrup).csv`, fila 385; V2; RUN `RUN-G42-V2-20261113-012748`; ambiente TEST; autorización `AUT-G42-V2-R3-20261112`. Código TEST `453277e4` declarado por QA, sin comprobación del despliegue en este RUN. Herramientas registradas: Node v22.15.1 y Newman 6.2.2. La matriz exige API con Postman/Newman; no exige UI y hubo cero ejecuciones UI.

## Resumen de veredictos

| Caso | Esperado | Observado | Estado |
| --- | --- | --- | --- |
| TC-M06-021 | Ganancias y pérdidas TB/PM consolidadas, sin doble conteo, con ejecutor, timestamp y origen del cierre. | Cuatro tipos, sumas, ejecutor y origen conformes. | APROBADO |
| TC-M06-022 | Comprobantes por titular, hecho y especie; suma por par de cuentas, código, fecha, descarga e inmutabilidad. | Comprobantes, sumas, descargas e inmutabilidad conformes. | APROBADO |
| TC-M06-023 | Costos del período clasificados en RF-93, sin arrastre al período siguiente ni aumento del valor razonable. | Costos por tipo y período, y valor razonable conformes. | APROBADO |

**Oficialidad.** Los tres casos quedaron decididos; Newman terminó sin fallos; se usaron 178 de 300 solicitudes API; el DELETE devolvió HTTP 200 y el rollback quedó verificado en `resultado.json`.

## Preflight del RUN

| Período | Estado inicial | Prevalidación inicial | Resultado de preparación |
| --- | --- | --- | --- |
| 241, NIT-D | ABIERTO | No podía cerrar: `LINEAS_PENDIENTE_CUENTA`. | La línea 1431 quedó resuelta y la prevalidación posterior permitió cerrar. |
| 220, NIT-C | ABIERTO | Podía cerrar, sin bloqueos. | Se cerró tras preparar los costos y precios del RUN. |

El período 219 de V1 estaba CERRADO por el cierre 43 fuera de QA. V2 utilizó los períodos 241 y 220. Este cambio de datos de prueba no altera el oráculo de la matriz.

## TC-M06-021

**Qué se verifica.** La fila 385 de la matriz y RF-87, CA-4 y CA-9, exigen un asiento consolidado con ganancia y pérdida por transformación biológica (TB) y por precio de mercado (PM). Cada total debe sumar los registros de su tipo durante el período, sin contar dos veces una variación. El asiento lleva `id_usuario_ejecutor` y timestamp inmutable; las variaciones generadas por el cierre llevan `evento_origen_id = id_cierre`.

**Preparación.** Se utilizó el período 241 de NIT-D y el bovino 1627 para TB positiva y negativa. Se prepararon los bovinos 1832 y 1833 para PM negativa y positiva; el 1831 se excluyó por su antecedente IoT. El peso inicial del 1627 fue 395 kg, con pesajes de 396 y 394 kg; el 1832 pasó de 380 a 381 kg y el 1833 permaneció en 400 kg. La línea 1431, pendiente de cuenta, se resolvió mediante `POST /finanzas/configuracion/matriz` (HTTP 201): asignación específica 5716, copia de las cuentas de la asignación genérica 49; `lineas_resueltas = 1`. La prevalidación posterior de 241 pasó a `puede_cerrar = true`, sin bloqueos. En el RUN se registraron eventos y precios para obtener los cuatro signos requeridos.

**Qué se hizo.**

1. Se autenticó a Contador y Administrador (POST, HTTP 200); se leyeron períodos, activos, precios, líneas, variaciones y prevalidación (GET, HTTP 200).
2. Se guardó la asignación 5716 (POST, HTTP 201), se comprobó la prevalidación (GET, HTTP 200), y se crearon precios y eventos de crecimiento (POST, HTTP 201) que se procesaron por `POST /finanzas/eventos/procesar` (HTTP 200).
3. Se cerró `POST /finanzas/periodos/241/cierre` (HTTP 200, cierre 71) y se consultaron líneas, variaciones, comprobantes y auditoría (GET, HTTP 200).

**Qué se esperaba.** Debían figurar TB ganancia, TB pérdida, PM ganancia y PM pérdida; las sumas por tipo debían igualar las líneas consolidadas, sin duplicados, con ejecutor, timestamp inmutable y origen del cierre.

**Qué se observó.** Las filas de un mismo tipo y sentido se separan por especie; por eso TB ganancia y TB pérdida aparecen dos veces. Las cifras provienen de `observado.021.tipos` en `resultado.json`.

| Tipo | Sentido | Especie | Variaciones | Suma de líneas | Total comprobado |
| --- | --- | ---: | ---: | ---: | ---: |
| VARIACION_VR_TB | GANANCIA | 39 | 3 | 154395.00 | 154395.00 |
| VARIACION_VR_TB | GANANCIA | 1 | 1 | 54050.00 | 54050.00 |
| VARIACION_VR_TB | PERDIDA | 1 | 1 | 32430.00 | 32430.00 |
| VARIACION_VR_TB | PERDIDA | 39 | 1 | 17766.00 | 17766.00 |
| VARIACION_VR_PM | GANANCIA | 39 | 6 | 2704803.00 | 2704803.00 |
| VARIACION_VR_PM | PERDIDA | 39 | 2 | 556104.00 | 556104.00 |

El ejecutor fue 5 y el timestamp fue `2026-11-13T01:27:51.253391Z`. La auditoría incluida en `observado.021` vincula las variaciones generadas por el cierre con el cierre 71. No hubo líneas ni variaciones excluidas.

**Por qué se decide así.** La comprobación API `G42-API-021-01` consta APROBADA: las sumas coinciden, están presentes los cuatro signos y los datos de ejecutor y origen son conformes. No hay comprobación UI obligatoria.

**Decisión.** APROBADO.

## TC-M06-022

**Qué se verifica.** La fila 385 de la matriz y RF-87 v1.1 exigen un comprobante por combinación de titular, tipo de hecho y especie; una línea por par de cuentas distinto, cuyo valor sume las líneas RF-86 del par. El código sigue `NIC-{NIT}-{AAAAMM}-{TIPO_HECHO}-{ESPECIE}`, la fecha es el último día del período, hay descarga CSV y PDF, y no se admite modificación.

**Preparación.** Se utilizaron los comprobantes generados por los cierres de noviembre de 2026: período 241 de NIT-D y período 220 de NIT-C, con hechos y especies registrados en cada uno. No se reutilizó el período 219 de V1.

**Qué se hizo.**

1. Se cerraron los períodos 241 y 220 por `POST /finanzas/periodos/{id}/cierre` (HTTP 200 en ambos casos; cierres 71 y 72).
2. Se leyeron líneas RF-86 y comprobantes de ambos períodos (GET, HTTP 200), y se descargaron CSV y PDF por `GET /finanzas/periodos/{id}/comprobantes/descarga` (HTTP 200).
3. Se intentaron PUT y DELETE sobre los comprobantes de ambos períodos (HTTP 405); las lecturas GET posteriores (HTTP 200) conservaron los hashes.

**Qué se esperaba.** Un comprobante por titular, hecho y especie, con sumas por par de cuentas, código NIC, fecha `2026-11-30`, descargas CSV/PDF e inmutabilidad.

**Qué se observó.** Los códigos están saneados como `NIC-[NIT]-...` en `resultado.json`; la columna período distingue los dos titulares sin revelar el NIT.

| Período | Código saneado | Tipo | Especie | Líneas | Fecha |
| --- | --- | --- | ---: | ---: | --- |
| 241 | NIC-[NIT]-202611-CONSUMO_INSUMO-1 | CONSUMO_INSUMO | 1 | 1 | 2026-11-30 |
| 241 | NIC-[NIT]-202611-CONSUMO_INSUMO-39 | CONSUMO_INSUMO | 39 | 1 | 2026-11-30 |
| 241 | NIC-[NIT]-202611-DEPRECIACION_ACTIVO_COSTO-39 | DEPRECIACION_ACTIVO_COSTO | 39 | 1 | 2026-11-30 |
| 241 | NIC-[NIT]-202611-PRODUCTO_AGRICOLA-1 | PRODUCTO_AGRICOLA | 1 | 1 | 2026-11-30 |
| 241 | NIC-[NIT]-202611-RECONOCIMIENTO_DIFERENCIA-1 | RECONOCIMIENTO_DIFERENCIA | 1 | 1 | 2026-11-30 |
| 241 | NIC-[NIT]-202611-RECONOCIMIENTO_DIFERENCIA-39 | RECONOCIMIENTO_DIFERENCIA | 39 | 1 | 2026-11-30 |
| 241 | NIC-[NIT]-202611-VARIACION_VR_PM-39 | VARIACION_VR_PM | 39 | 2 | 2026-11-30 |
| 241 | NIC-[NIT]-202611-VARIACION_VR_TB-1 | VARIACION_VR_TB | 1 | 2 | 2026-11-30 |
| 241 | NIC-[NIT]-202611-VARIACION_VR_TB-39 | VARIACION_VR_TB | 39 | 2 | 2026-11-30 |
| 220 | NIC-[NIT]-202611-DEPRECIACION_ACTIVO_COSTO-423 | DEPRECIACION_ACTIVO_COSTO | 423 | 1 | 2026-11-30 |
| 220 | NIC-[NIT]-202611-MANO_OBRA_PROPIA-422 | MANO_OBRA_PROPIA | 422 | 1 | 2026-11-30 |
| 220 | NIC-[NIT]-202611-RECONOCIMIENTO_DIFERENCIA-422 | RECONOCIMIENTO_DIFERENCIA | 422 | 1 | 2026-11-30 |
| 220 | NIC-[NIT]-202611-VARIACION_VR_PM-422 | VARIACION_VR_PM | 422 | 1 | 2026-11-30 |
| 220 | NIC-[NIT]-202611-VARIACION_VR_PM-423 | VARIACION_VR_PM | 423 | 2 | 2026-11-30 |

`observado.022.descargas` registra CSV y PDF HTTP 200 para ambos períodos, PDF con cabecera `%PDF`, y PUT y DELETE HTTP 405; `hashesIguales = true` tras los intentos de modificación. Los CSV generados están en `descargas/`; los resultados de PDF constan en `resultado.json`.

**Por qué se decide así.** La comprobación API `G42-API-022-01` consta APROBADA: agrupación y sumas, códigos, fechas, descargas e inmutabilidad fueron conformes. La evaluación de regresión no encontró discrepancias nuevas. No hay comprobación UI obligatoria.

**Decisión.** APROBADO.

## TC-M06-023

**Qué se verifica.** La fila 385 de la matriz y RF-87, CA-10, exigen que RF-93 registre como gasto los costos de mantenimiento del período, clasificados por tipo; debe excluir los del período anterior. Los costos tampoco deben aumentar el valor razonable de los activos.

**Preparación.** En el período 220 de NIT-C se registraron los cuatro costos RF-90 del RUN, IDs 4449 a 4452, junto con costos que ya existían en ese mismo período. Se utilizaron noviembre y diciembre consecutivos para comprobar el corte temporal. El desglose esperado de ALIMENTO en noviembre incluye 150000.0000 previos del período 220 y 101.0000 del RUN.

**Qué se hizo.**

1. Se consultaron costos y cálculos de 220 (GET, HTTP 200), se crearon cuatro costos por `POST /finanzas/costos` (HTTP 201) y se repitieron las lecturas (GET, HTTP 200).
2. Se cerró 220 por POST (HTTP 200, cierre 72), y se leyeron RF-93, costos, cálculos y mediciones (GET, HTTP 200).
3. Se cerró el período siguiente 391 de diciembre por POST (HTTP 200, cierre 73), y se consultaron RF-93 de ambos períodos y el valor razonable (GET, HTTP 200).

**Qué se esperaba.** RF-93 debía clasificar ALIMENTO, MEDICAMENTO, MANO_OBRA y VETERINARIO de noviembre; su suma debía coincidir con `costos_mantenimiento`. Diciembre no debía arrastrar esos costos; el valor razonable debía permanecer igual con y sin ellos.

**Qué se observó.**

| Tipo | ID del costo creado | Monto del RUN | Esperado en RF-93 con costos previos de 220 | Observado en RF-93 |
| --- | ---: | ---: | ---: | ---: |
| ALIMENTO | 4449 | 101.0000 | 150101.0000 | 150101.0000 |
| MEDICAMENTO | 4450 | 102.0000 | 102.0000 | 102.0000 |
| MANO_OBRA | 4451 | 103.0000 | 103.0000 | 103.0000 |
| VETERINARIO | 4452 | 104.0000 | 104.0000 | 104.0000 |

RF-93 de noviembre, id 66, registró `costos_mantenimiento = 150410.0000`; RF-93 de diciembre, id 67, registró 0. El valor razonable fue 4230000.0000 tanto con costos como sin ellos.

**Por qué se decide así.** La comprobación API `G42-API-023-01` consta APROBADA: los cuatro importes por tipo coinciden con lo esperado, diciembre no arrastra los costos y el valor razonable no aumenta. No hay comprobación UI obligatoria.

**Decisión.** APROBADO.

## Intentos técnicos previos de V2

El `RUN-G42-V2-20261113-004229` se detuvo porque el período 219 de V1 ya estaba CERRADO por el cierre 43 fuera de QA (`PERIODO_219_NO_ABIERTO`). El `RUN-G42-V2-20261113-010212` se detuvo porque la línea 1431 del período 241 seguía pendiente de cuenta (`PENDIENTE_241_NO_RESUELTO`). Ambos fueron intentos técnicos no oficiales; ninguno se usa como evidencia de los veredictos del RUN 012748.

## Comprobaciones y evidencias

Las comprobaciones API `G42-API-021-01`, `G42-API-022-01` y `G42-API-023-01` están APROBADAS en [resultado.json](resultado.json), junto con las solicitudes, observaciones y el rollback. El preflight y el contexto constan en [preflight.json](preflight.json) y [contexto_operacion.json](contexto_operacion.json). Los CSV generados están en [comprobantes-241.csv](descargas/comprobantes-241.csv) y [comprobantes-220.csv](descargas/comprobantes-220.csv). Newman registró código 0, ocho solicitudes y cero fallos en sus reportes [JSON](newman/newman-G42.json) y [HTML](newman/newman-G42.html). Se usaron 178 de 300 solicitudes API. No se exigieron comprobaciones UI.

## Seguimiento, incidencias y análisis de causas

INC-M06-G32-01, seguida en TC-M06-021, e INC-M06-G42-01, seguida en TC-M06-023, quedan CORREGIDAS según las comprobaciones de este RUN. TC-M06-022 se comprobó como regresión sin discrepancia. No se acreditaron incidencias nuevas de producto; no procede asignar severidad, equipo inicial ni causa raíz a una incidencia nueva. Los dos intentos técnicos previos explican la preparación del RUN oficial, pero no son incidencias del producto ni evidencia de sus veredictos. `resultado.json` no registra problemas técnicos o permisos faltantes en este RUN oficial.

## Cierre, rollback y efectos persistentes

Los cierres 71, 72 y 73 de los períodos 241, 220 y 391 devolvieron HTTP 200. El `DELETE /test-control/runs/RUN-G42-V2-20261113-012748` devolvió HTTP 200; `resultado.json` marca el rollback como VERIFICADO porque las lecturas poscierre coincidieron con la línea base. Los avisos y alertas de la siguiente tabla pueden persistir fuera del rollback del sandbox; cada texto se cita una vez.

| Período | Tipo | ID | Texto |
| --- | --- | ---: | --- |
| 241 | Aviso de cierre | 13372 | «Período 2026-11 cerrado: listo para transferir desde Agrofusión.» |
| 241 | Alerta NIC 41 ¶30 | 13378 | «Al cerrar el período 2026-11, estos activos valorados por costo ya tienen precio de mercado para su especie: BOV-116-TIL. La NIC 41 ¶30 exige pasarlos a valor razonable.» |
| 220 | Aviso de cierre | 13396 | «Período 2026-11 cerrado: listo para transferir desde Agrofusión.» |
| 220 | Alerta NIC 41 ¶30 | 13402 | «Al cerrar el período 2026-11, estos activos valorados por costo ya tienen precio de mercado para su especie: QA-M06O-COSTO-02. La NIC 41 ¶30 exige pasarlos a valor razonable.» |
| 391, diciembre | Aviso de cierre | 13408 | «Período 2026-12 cerrado: listo para transferir desde Agrofusión.» |
| 391, diciembre | Alerta NIC 41 ¶30 | 13414 | «Al cerrar el período 2026-12, estos activos valorados por costo ya tienen precio de mercado para su especie: QA-M06O-COSTO-02. La NIC 41 ¶30 exige pasarlos a valor razonable.» |

## Conclusión y acciones

TC-M06-021, TC-M06-022 y TC-M06-023 cumplen los criterios comprobados de RF-87 y la fila 385 de la matriz: consolidación del asiento, comprobantes NIC 41 y tratamiento de costos en RF-93. No quedó ningún caso pendiente de evaluación en este RUN. La siguiente acción es entregar el informe al responsable QA y cerrar INC-M06-G32-01 e INC-M06-G42-01 en el seguimiento, si corresponde a su flujo.

## Enmienda documental (2026-11-13)

La orden `ORD-G42-022` dispuso esta enmienda del Markdown oficial. La [copia previa byte a byte](../../../historial_informes/TC-M06-G42_reevaluacion_V2.RUN-G42-V2-20261113-012748.antes-enmienda.md) tiene SHA-256 `D462990E8F9FA517363C89570B58C4571ED426B1917E5A354876B9CF1E67B584`. [resultado.json](resultado.json) conserva SHA-256 `01091F5FBABE8A87CEB416606763B371E15CA50D39943962528B291B97C85331`.

Se corrigieron caracteres rotos, la referencia errónea a los períodos de V1 y la conclusión sobre incidencias; se distinguieron las especies del 021 y se estructuraron los tres casos por criterio, preparación, ejecución, esperado, observado y decisión. Se documentaron los intentos técnicos previos, el seguimiento y los seis efectos persistentes. No cambian los veredictos, la oficialidad, el rollback ni la evidencia del RUN.