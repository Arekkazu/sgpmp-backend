# TC-M06-G42 — RUN oficial

## Identificación

G42; TC-M06-021, TC-M06-022 y TC-M06-023; RF-87 v1.1; V1; RUN RUN-G42-V1-20261109-212424; ambiente TEST; autorización AUT-G42-V1-R5-20261109. Commit no consultado; Node v22.15.1 y Newman 6.2.2 verificados en el RUN. Registro QA: OFICIAL; rollback: CONFIRMADO.

## Resumen de veredictos

| Caso | Esperado | Observado | Veredicto |
| --- | --- | --- | --- |
| TC-M06-021 | Asiento con ganancia y pérdida TB/PM, suma por tipo, ejecutor, timestamp inmutable y vínculo con cierre | Cierre 8 HTTP 500 ERROR_INTERNO; paso 3 RF-91 falló por TGR-M06-26 según log del backend aportado por QA; cuatro tipos pendientes de reevaluación | RECHAZADO |
| TC-M06-022 | Comprobante por titular, hecho y especie; suma por par; código, fecha, CSV/PDF e inmutabilidad | Siete comprobantes de 219 y 220 conformes según comprobación API; descargas e inmutabilidad conformes | APROBADO |
| TC-M06-023 | RF-93 incluye costos del período clasificados por tipo, excluye el período anterior y no aumenta valor razonable | Cierre completado; RF-93 incluye 410.0000 de costos de mantenimiento de noviembre como gasto, sin clasificación por tipo | RECHAZADO |

Severidad global: **ALTA**, por la reutilización de INC-M06-G32-01 en 021. La incidencia de 023 es MEDIA.

## TC-M06-021: cierre del período 8

El bovino 945 de NIT-A, sin IoT, fue seleccionado para las variaciones TB/PM. Se autorizó la exclusión de la línea 17 preexistente bajo D1 extendida; la prevalidación inicial y la previa al cierre mostraron puede_cerrar=true, cero bloqueos y esa línea pendiente. El cierre respondió HTTP 500 ERROR_INTERNO. La auditoría registró CIERRE_PERIODO_FALLIDO, paso 3, id_referencia 27.

**Atribución por log aportado por QA (extracto saneado):** POST /finanzas/periodos/8/cierre -> 500 ERROR_INTERNO; TGR-M06-26: cadena de trazabilidad id=191 vinculada a variación id=4 del período 7 CERRADO; operación INSERT; RF-91 restricción 4, fn_tgr_m06_26_trazabilidad_periodo_cerrado línea 27. El log y la auditoría vinculan este fallo con INC-M06-G32-01. La respuesta pública fue genérica y no exhibió el mensaje de RF-87 FA-1.

El cierre no se completó. Por ello no se evaluaron los cuatro tipos, sus sumas, el ejecutor, el timestamp ni el vínculo de las variaciones al cierre. Esa comprobación queda para una reevaluación después de corregir INC-M06-G32-01. No se afirma que los cuatro tipos hayan fallado.

## TC-M06-022: comprobantes de 219 y 220

| Período | Código saneado | Tipo de hecho | Especie (id) | Líneas | Fecha | Par débito/crédito | Suma del par |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| 219 | NIC-[NIT]-202611-DEPRECIACION_ACTIVO_COSTO-423 | DEPRECIACION_ACTIVO_COSTO | 423 | 1 | 2026-11-30 | 516005/159205 | 112500.00 |
| 219 | NIC-[NIT]-202611-RECONOCIMIENTO_DIFERENCIA-422 | RECONOCIMIENTO_DIFERENCIA | 422 | 1 | 2026-11-30 | 158405/424815 | 260000.00 |
| 219 | NIC-[NIT]-202611-VARIACION_VR_PM-422 | VARIACION_VR_PM | 422 | 1 | 2026-11-30 | 158405/424805 | 470000.00 |
| 220 | NIC-[NIT]-202611-DEPRECIACION_ACTIVO_COSTO-423 | DEPRECIACION_ACTIVO_COSTO | 423 | 1 | 2026-11-30 | 516005/159205 | 205000.00 |
| 220 | NIC-[NIT]-202611-MANO_OBRA_PROPIA-422 | MANO_OBRA_PROPIA | 422 | 1 | 2026-11-30 | 158405/250505 | 103.00 |
| 220 | NIC-[NIT]-202611-RECONOCIMIENTO_DIFERENCIA-422 | RECONOCIMIENTO_DIFERENCIA | 422 | 1 | 2026-11-30 | 158405/424815 | 480000.00 |
| 220 | NIC-[NIT]-202611-VARIACION_VR_PM-422 | VARIACION_VR_PM | 422 | 1 | 2026-11-30 | 158405/424805 | 1410000.00 |

Las sumas por par anteriores proceden de los CSV saneados guardados en descargas/. La comprobación API del RUN comparó cada suma con las líneas RF-86.

| Período | CSV HTTP / tipo | PDF HTTP / tipo | PDF bytes | SHA-256 PDF | PUT / DELETE | Hashes tras rechazo |
| --- | --- | --- | ---: | --- | --- | --- |
| 219 | 200 / text/csv; charset=utf-8 | 200 / application/pdf | 2676 | `f8bbe5e5a272791394b9bba98e941e56b728a586130d7cfe4ff3bab5e9a1d7ea` | 405 / 405 | iguales |
| 220 | 200 / text/csv; charset=utf-8 | 200 / application/pdf | 2830 | `6fc6b6d66dbeab17f23db1936992f5dad7d2f7315a761181783f95929c1f0ad5` | 405 / 405 | iguales |

Ambos PDF tuvieron cabecera %PDF. La salida PDF se comprobó en memoria; no consta archivo PDF persistido. Los CSV saneados, el resultado y los reportes Newman están en este RUN.

## TC-M06-023: costos de mantenimiento

| Tipo | ID costo | Monto |
| --- | ---: | ---: |
| VETERINARIO | 824 | 104.0000 |
| MANO_OBRA | 823 | 103.0000 |
| MEDICAMENTO | 822 | 102.0000 |
| ALIMENTO | 821 | 101.0000 |

Total de noviembre: **410.0000**. El cierre de 220 y el cierre anticipado de 248 (diciembre NIT-C) respondieron HTTP 200. RF-93 noviembre id 28 mostró `componentes.costos_mantenimiento=410.0000`; el desglose por tipo fue nulo. Las claves reales de `componentes` fueron: `bajas_activos`, `costos_mantenimiento`, `perdida_precio_mercado`, `deterioro_activos_costo`, `ganancia_precio_mercado`, `activos_excluidos_cierre`, `depreciacion_activos_costo`, `ingresos_productos_agricolas`, `inversiones_llevadas_a_gasto`, `perdida_reconocimiento_inicial`, `ganancia_reconocimiento_inicial`, `perdida_transformacion_biologica`, `ganancia_transformacion_biologica`, `perdida_ajustes_periodos_anteriores`, `ganancia_ajustes_periodos_anteriores`. RF-93 diciembre id 29 mostró `costos_mantenimiento=0`. El valor razonable comparado fue `4230000.0000` con y sin costos.

## Comprobaciones API, UI y evidencias

- G42-API-021-01 (TC-M06-021): **RECHAZADO** — Cierre 8 HTTP 500 ERROR_INTERNO; paso 3 RF-91 falló por TGR-M06-26 según log del backend aportado por QA; cuatro tipos pendientes de reevaluación. Evidencia: resultado.json.
- G42-API-022-01 (TC-M06-022): **APROBADO** — comprobantes, sumas, descargas e inmutabilidad conformes. Evidencia: resultado.json.
- G42-API-023-01 (TC-M06-023): **RECHAZADO** — Cierre completado; RF-93 incluye 410.0000 de costos de mantenimiento de noviembre como gasto, sin clasificación por tipo. Evidencia: resultado.json.

Solicitudes 123/260; Newman código 0, 0 fallos. UI no exigida por los tres casos. Evidencias reales: descargas/comprobantes-219.csv, descargas/comprobantes-220.csv, newman/newman-G42.json, newman/newman-G42.html. La atribución de 021 y la ausencia de avisos usan el log del backend aportado por QA, separado de las lecturas API guardadas.

## Incidencias de producto

### INC-M06-G32-01 — reutilizada para TC-M06-021

- Requisito: RF-91 paso 3; RF-87 CA-4/CA-9 y proceso pasos 5-6.
- Esperado: Cierre 8 completado y asiento consolidado con cuatro tipos TB/PM, sumas, ejecutor, timestamp y vínculo al cierre. Obtenido: Cierre 8 HTTP 500 ERROR_INTERNO; log del backend: TGR-M06-26 al insertar trazabilidad de la variación 4 del período 7 CERRADO; auditoría CIERRE_PERIODO_FALLIDO paso 3, id_referencia 27.
- Severidad **ALTA**: El cierre del período 8 queda bloqueado y no hay alternativa comprobada; el oráculo contable de 021 no puede evaluarse. Certeza **CONFIRMADA** de la discrepancia y de la atribución por log; causa raíz **NO DETERMINADA**.
- Atención inicial: **Desarrollo**. Primera discrepancia comprobada en el cierre público M06; la atribución a la incidencia existente se apoya en el log aportado por QA, sin asignar causa raíz definitiva. Evidencia: resultado.json; extracto saneado del log del backend aportado por QA.
- Acción: Reevaluar los cuatro tipos tras corregir INC-M06-G32-01.

### INC-M06-G42-01 — TC-M06-023

- Requisito: RF-87 CA-10, proceso paso 7 y Salida; estado de resultados RF-93.
- Pasos: Registrar en RF-90 los costos de mantenimiento ALIMENTO 101.0000, MEDICAMENTO 102.0000, MANO_OBRA 103.0000 y VETERINARIO 104.0000 del período 220; cerrar noviembre y leer RF-93, luego cerrar diciembre y comparar valor razonable.
- Esperado: RF-93 muestra 410.0000 como gasto de noviembre clasificado por tipo; excluye esos costos de diciembre y no aumenta el valor razonable de los activos.
- Obtenido: Cierres 220 y 248 HTTP 200; RF-93 noviembre id 28: componentes.costos_mantenimiento=410.0000, desglose=null. Claves de componentes reales: bajas_activos, costos_mantenimiento, perdida_precio_mercado, deterioro_activos_costo, ganancia_precio_mercado, activos_excluidos_cierre, depreciacion_activos_costo, ingresos_productos_agricolas, inversiones_llevadas_a_gasto, perdida_reconocimiento_inicial, ganancia_reconocimiento_inicial, perdida_transformacion_biologica, ganancia_transformacion_biologica, perdida_ajustes_periodos_anteriores, ganancia_ajustes_periodos_anteriores. RF-93 diciembre id 29: costos_mantenimiento=0; valor razonable 4230000.0000 con y sin costos.
- Apoyo de código: Lectura de src/financial_valuation/domain/services/consolidacion.py:125-140 y src/financial_valuation/application/services/reportes.py:29-40; apoyo, no atribución de causa raíz.
- Impacto: Gasto total correcto, pero salida RF-93 incompleta para analizar costos por tipo.
- Severidad **MEDIA**: Impacto parcial: el cierre se completa y el total del gasto es correcto, pero falta el desglose exigido. Certeza **CONFIRMADA** de la discrepancia; causa raíz **NO DETERMINADA**.
- Atención inicial: **Desarrollo**. La primera discrepancia comprobada está en la salida pública de RF-93; la causa raíz no está demostrada. Evidencia: resultado.json, lecturas RF-93 y comprobaciones API del RUN.

## Observaciones sin veredicto

- **respuesta de cierre fallido**: HTTP 500 ERROR_INTERNO genérico; no expone el mensaje de RF-87 FA-1. No se emite veredicto adicional.
- **IoT y pesaje manual**: Un activo con IoT y pesaje manual deja la línea TB en PENDIENTE_TRAZABILIDAD sin telemetría apta de las 24 h previas, conforme a la dependencia RF-91; sin veredicto adicional.
- **línea 17**: La línea 17 preexistente fue excluible por autorización D1 extendida; la prevalidación inicial y previa al cierre la muestran. El cierre 8 falló antes de completar la exclusión.
- **redondeo**: No hay suma de cuatro tipos evaluable en 021 por cierre fallido; no se acreditaron diferencias de redondeo en este RUN.
- **diciembre NIT-C**: El período 248, diciembre de NIT-C, se cerró por adelantado para comparar RF-93 con noviembre; rollback confirmado para datos del sandbox.

## Efectos persistentes, cierre y rollback

Las únicas persistencias identificadas son los dos inicios de sesión y su auditoría, fuera del rollback del sandbox. Según el log aportado por QA, no se registraron avisos CIERRE_PERIODO_CONTABLE (tipo 39) ni ALERTA_FINANCIERA_NIC41 (tipo 40) en los cierres 219, 220 y 248: ambos tipos carecían de categoría, el mismo patrón de INC-M06-G41-01. No se atribuye una nueva incidencia de producto a G42 por ello.

DELETE del RUN: HTTP 200. Las lecturas posteriores coincidieron con la línea base; rollback **VERIFICADO/CONFIRMADO** para los datos comprobados. El log registra un timeout posterior que forzó rollback del mismo run_id; ocurrió después de esas lecturas, que aún llevaban las cabeceras del RUN. La corrección del ejecutor para futuros RUN elimina esas cabeceras después del DELETE. No se infiere de ello un cambio en el veredicto ni una nueva ejecución.

## Conclusión y acciones

Mantener 021 RECHAZADO y vinculado a INC-M06-G32-01; reevaluar el oráculo de los cuatro tipos tras su corrección. Mantener 022 APROBADO. Derivar INC-M06-G42-01 a Desarrollo para completar el desglose RF-93 y reevaluar 023 por decisión explícita. Registro QA emulado: OFICIAL; no se creó RUN ni se accedió a TEST en esta actualización.

Actualización del informe (2026-11-09): atribución de 021 a INC-M06-G32-01 por el log del backend; severidad de 023 a MEDIA; observaciones y efectos persistentes; veredictos sin cambios
