# TC-M06-G32 — RECHAZADO

## Identificación

TC-M06-G32 / TC-M06-001, TC-M06-G32 / TC-M06-002, TC-M06-G32 / TC-M06-003, TC-M06-G32 / TC-M06-004; RF-86 v2.0; RUN RUN-G32-V1-20261108-061927; versión 1; intento 7; ambiente TEST; autorización AUT-G32-V1-R7-20261108. Node v22.15.1; Newman 6.2.2. Código de TEST: no verificado por este ejecutor. Solo API.

## Decisión del caso

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-G32 / TC-M06-001 | RECHAZADO | Origen no consultable por cadena RF-91: POST /finanzas/periodos/8/trazabilidad HTTP 500, código ERROR_INTERNO. |
| TC-M06-G32 / TC-M06-002 | RECHAZADO | Origen no consultable por cadena RF-91: POST /finanzas/periodos/8/trazabilidad HTTP 500, código ERROR_INTERNO. |
| TC-M06-G32 / TC-M06-003 | RECHAZADO | Origen no consultable por cadena RF-91: POST /finanzas/periodos/8/trazabilidad HTTP 500, código ERROR_INTERNO. |
| TC-M06-G32 / TC-M06-004 | RECHAZADO | Origen no consultable por cadena RF-91: POST /finanzas/periodos/8/trazabilidad HTTP 500, código ERROR_INTERNO. |

## Diagnóstico de candidatos

Conteos acumulados, sin titular tributario ni datos personales: medido: true; total_recibido: 9; bovino: 6; individual: 6; estado: 5; sin_costo: 5; valor_positivo: 5; precio_vigente: 5; periodo_destino: 5; peso_kg: 5; calculo_previo: 5; primera_condicion_fallida: ninguna.

## Datos y método

Se usaron activos reconocidos ya existentes. Según contabilizador.py:39-66 y la regla de período destino, un hecho con período CERRADO se registra en el primer período ABIERTO posterior del titular; la línea base y la variación se leen allí. La selección del precio sigue precios.py:38-52. El oráculo TB/PM compara el último cálculo previo con el nuevo valor neto y las magnitudes según medidor.py:62-75, valorador.py:88-112 y nic41.py:129-148. La regla M02 permite registrar eventos de crecimiento únicamente para activos ACTIVO (Especificacion-Requerimientos-Modulo2.md:2194); en TC-M06-002 se registra el pesaje en ACTIVO, luego PATCH a EN_TRATAMIENTO y después POST /finanzas/eventos/procesar dentro del RUN. El proceso de fondo usa otra sesión y no ve la escritura sin confirmar del sandbox. No se ingresaron datos contables manuales. Tras comprobar importes y estado inicial se invoca una verificacion RF-91 por periodo destino y luego se consulta cada cadena.

## Verificacion RF-91 y origen

- Periodo 8: POST /finanzas/periodos/8/trazabilidad -> HTTP 500; codigo ERROR_INTERNO; cuerpo saneado {"error_code":"ERROR_INTERNO","message":"Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.","fields":[],"timestamp":"2026-11-08T06:19:37.646675+00:00"}; eco RUN true.

## Consultas de cadena RF-91

- TC-M06-001, variacion 152, linea 391: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":391,"tipo_hecho":"VARIACION_VR_PM","sentido":"GANANCIA","valor":"97290.00","tabla_origen":"variaciones_valor_razonable","id_origen":152,"tipo_evidencia":"VARIACION_PRECIO","estado_trazabilidad":"VERIFICACION_PENDIENTE","id_activo_biologico":943,"fecha_hecho":"2026-11-08","cuenta_debito":"158405","cuenta_credito":"424805","estado_verificacion":null,"nivel_fallo":null,"fecha_verificacion":null,"eslabones_faltantes":null,"eslabones":null}; ids {"id_evento":null,"id_precio_mercado":null}.
- TC-M06-001, variacion 151, linea 390: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":390,"tipo_hecho":"VARIACION_VR_TB","sentido":"GANANCIA","valor":"62265.60","tabla_origen":"variaciones_valor_razonable","id_origen":151,"tipo_evidencia":"IOT_DIRECTO","estado_trazabilidad":"VERIFICACION_PENDIENTE","id_activo_biologico":943,"fecha_hecho":"2026-11-08","cuenta_debito":"158405","cuenta_credito":"424805","estado_verificacion":null,"nivel_fallo":null,"fecha_verificacion":null,"eslabones_faltantes":null,"eslabones":null}; ids {"id_evento":null,"id_precio_mercado":null}.
- TC-M06-002, variacion 153, linea 392: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":392,"tipo_hecho":"VARIACION_VR_TB","sentido":"PERDIDA","valor":"55226.88","tabla_origen":"variaciones_valor_razonable","id_origen":153,"tipo_evidencia":"REGISTRO_MANUAL","estado_trazabilidad":"VERIFICACION_PENDIENTE","id_activo_biologico":945,"fecha_hecho":"2026-11-08","cuenta_debito":"539505","cuenta_credito":"158405","estado_verificacion":null,"nivel_fallo":null,"fecha_verificacion":null,"eslabones_faltantes":null,"eslabones":null}; ids {"id_evento":null,"id_precio_mercado":null}.
- TC-M06-003, variacion 155, linea 394: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":394,"tipo_hecho":"VARIACION_VR_PM","sentido":"PERDIDA","valor":"53805.60","tabla_origen":"variaciones_valor_razonable","id_origen":155,"tipo_evidencia":"VARIACION_PRECIO","estado_trazabilidad":"VERIFICACION_PENDIENTE","id_activo_biologico":944,"fecha_hecho":"2026-11-08","cuenta_debito":"539505","cuenta_credito":"158405","estado_verificacion":null,"nivel_fallo":null,"fecha_verificacion":null,"eslabones_faltantes":null,"eslabones":null}; ids {"id_evento":null,"id_precio_mercado":null}.
- TC-M06-003, variacion 154, linea 393: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":393,"tipo_hecho":"VARIACION_VR_TB","sentido":"GANANCIA","valor":"272615.04","tabla_origen":"variaciones_valor_razonable","id_origen":154,"tipo_evidencia":"IOT_DIRECTO","estado_trazabilidad":"VERIFICACION_PENDIENTE","id_activo_biologico":944,"fecha_hecho":"2026-11-08","cuenta_debito":"158405","cuenta_credito":"424805","estado_verificacion":null,"nivel_fallo":null,"fecha_verificacion":null,"eslabones_faltantes":null,"eslabones":null}; ids {"id_evento":null,"id_precio_mercado":null}.
- TC-M06-004, variacion 156, linea 395: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":395,"tipo_hecho":"VARIACION_VR_PM","sentido":"GANANCIA","valor":"241956.00","tabla_origen":"variaciones_valor_razonable","id_origen":156,"tipo_evidencia":"VARIACION_PRECIO","estado_trazabilidad":"VERIFICACION_PENDIENTE","id_activo_biologico":946,"fecha_hecho":"2026-11-08","cuenta_debito":"158405","cuenta_credito":"424805","estado_verificacion":null,"nivel_fallo":null,"fecha_verificacion":null,"eslabones_faltantes":null,"eslabones":null}; ids {"id_evento":null,"id_precio_mercado":null}.

## Detalle por caso

### TC-M06-G32 / TC-M06-001

- **Preparación observada:** activo 943, evento M02 832, precio vigente 18, período destino 8 ABIERTO; estado al pesaje ACTIVO y al procesar ACTIVO. No se hizo rebase previo de precio en este RUN.
- **Esperado:** Una sola GANANCIA_TRANSFORMACION_BIOLOGICA con el componente RF-83 y ningún registro de precio de mercado, bajo la precondición de precio sin cambio; origen M02 navegable.
- **Variaciones observadas:**
  - Variación 152: GANANCIA_PRECIO_MERCADO, monto 97.290,00, VR 3.015.990,00 → 3.175.545,60, estado VERIFICACION_PENDIENTE.
  - Variación 151: GANANCIA_TRANSFORMACION_BIOLOGICA, monto 62.265,60, VR 3.015.990,00 → 3.175.545,60, estado VERIFICACION_PENDIENTE.
- **Medición RF-83:** COMPLETADO; transformación 62.265,60, precio 97.290,00, total 159.555,60, VR 3.015.990,00 → 3.175.545,60; magnitud 345 → 351.9 kg.
- **Qué se cumplió:** La ganancia por transformación de 62.265,60 y la ganancia por precio de 97.290,00 coinciden con los componentes RF-83. La precondición «sin cambio de precio» no se cumplió: el cálculo previo del activo 943 usó precio 17 (9.300), mientras el vigente fue el 18 (9.600). Por eso se creó también una ganancia de precio, conforme a RF-83 (pasos 4–6). La parte del oráculo «no se crea registro de precio de mercado» no quedó comprobada aquí. Los registros observados corresponden al período destino y tienen estado inicial VERIFICACION_PENDIENTE.
- **Qué falló y por qué:** el origen exigido no se pudo consultar. POST /finanzas/periodos/8/trazabilidad devolvió HTTP 500 ERROR_INTERNO; la cadena de la línea asociada quedó con eslabones nulos. Véase INC-M06-G32-01.
- **Decisión:** RECHAZADO por INC-M06-G32-01.

### TC-M06-G32 / TC-M06-002

- **Preparación observada:** activo 945, evento M02 833, precio vigente 18, período destino 8 ABIERTO; estado al pesaje ACTIVO y al procesar EN_TRATAMIENTO. No se hizo rebase previo de precio en este RUN.
- **Esperado:** Una sola PERDIDA_TRANSFORMACION_BIOLOGICA negativa con el componente RF-83, aun en EN_TRATAMIENTO; ningún registro de precio de mercado y origen M02 navegable.
- **Variaciones observadas:**
  - Variación 153: PERDIDA_TRANSFORMACION_BIOLOGICA, monto -55.226,88, VR 2.761.344,00 → 2.706.117,12, estado VERIFICACION_PENDIENTE.
- **Medición RF-83:** COMPLETADO; transformación -55.226,88, precio 0,00, total -55.226,88, VR 2.761.344,00 → 2.706.117,12; magnitud 306 → 299.88 kg.
- **Qué se cumplió:** Solo se observó la pérdida por transformación de −55.226,88, igual a RF-83. El componente de precio fue 0 y no generó registro; el activo estaba EN_TRATAMIENTO al procesar. Los registros observados corresponden al período destino y tienen estado inicial VERIFICACION_PENDIENTE.
- **Qué falló y por qué:** el origen exigido no se pudo consultar. POST /finanzas/periodos/8/trazabilidad devolvió HTTP 500 ERROR_INTERNO; la cadena de la línea asociada quedó con eslabones nulos. Véase INC-M06-G32-01.
- **Decisión:** RECHAZADO por INC-M06-G32-01.

### TC-M06-G32 / TC-M06-003

- **Preparación observada:** activo 944, evento M02 834, precio vigente 172, período destino 8 ABIERTO; estado al pesaje ACTIVO y al procesar ACTIVO. No se hizo rebase previo de precio en este RUN.
- **Esperado:** Dos registros independientes: GANANCIA_TRANSFORMACION_BIOLOGICA y PERDIDA_PRECIO_MERCADO, con montos de RF-83 y orígenes navegables del evento M02 y del precio de mercado.
- **Variaciones observadas:**
  - Variación 155: PERDIDA_PRECIO_MERCADO, monto -53.805,60, VR 2.779.956,00 → 2.998.765,44, estado VERIFICACION_PENDIENTE.
  - Variación 154: GANANCIA_TRANSFORMACION_BIOLOGICA, monto 272.615,04, VR 2.779.956,00 → 2.998.765,44, estado VERIFICACION_PENDIENTE.
- **Medición RF-83:** COMPLETADO; transformación 272.615,04, precio -53.805,60, total 218.809,44, VR 2.779.956,00 → 2.998.765,44; magnitud 318 → 349.8 kg.
- **Qué se cumplió:** Se observaron por separado la ganancia por transformación de 272.615,04 y la pérdida por precio de −53.805,60, iguales a RF-83; suman 218.809,44. Los registros observados corresponden al período destino y tienen estado inicial VERIFICACION_PENDIENTE.
- **Qué falló y por qué:** el origen exigido no se pudo consultar. POST /finanzas/periodos/8/trazabilidad devolvió HTTP 500 ERROR_INTERNO; la cadena de la línea asociada quedó con eslabones nulos. Véase INC-M06-G32-01.
- **Decisión:** RECHAZADO por INC-M06-G32-01.

### TC-M06-G32 / TC-M06-004

- **Preparación observada:** activo 946, evento M02 835, precio vigente 173, período destino 8 ABIERTO; estado al pesaje ACTIVO y al procesar ACTIVO. No se hizo rebase previo de precio en este RUN.
- **Esperado:** Una sola GANANCIA_PRECIO_MERCADO con monto de RF-83 y origen de precio navegable; ninguna transformación sin cambio físico.
- **Variaciones observadas:**
  - Variación 156: GANANCIA_PRECIO_MERCADO, monto 241.956,00, VR 2.884.860,00 → 3.126.816,00, estado VERIFICACION_PENDIENTE.
- **Medición RF-83:** COMPLETADO; transformación 0,00, precio 241.956,00, total 241.956,00, VR 2.884.860,00 → 3.126.816,00; magnitud 330 → 330 kg.
- **Qué se cumplió:** Solo se observó la ganancia por precio de 241.956,00, igual a RF-83. El componente de transformación fue 0 y no generó registro; la magnitud quedó en 330 kg. Los registros observados corresponden al período destino y tienen estado inicial VERIFICACION_PENDIENTE.
- **Qué falló y por qué:** el origen exigido no se pudo consultar. POST /finanzas/periodos/8/trazabilidad devolvió HTTP 500 ERROR_INTERNO; la cadena de la línea asociada quedó con eslabones nulos. Véase INC-M06-G32-01.
- **Decisión:** RECHAZADO por INC-M06-G32-01.

## Comprobaciones API y evidencias

- G32-API-001-01: RECHAZADO. Origen no consultable por cadena RF-91: POST /finanzas/periodos/8/trazabilidad HTTP 500, código ERROR_INTERNO. Evidencia: resultado.json.
- G32-API-002-01: RECHAZADO. Origen no consultable por cadena RF-91: POST /finanzas/periodos/8/trazabilidad HTTP 500, código ERROR_INTERNO. Evidencia: resultado.json.
- G32-API-003-01: RECHAZADO. Origen no consultable por cadena RF-91: POST /finanzas/periodos/8/trazabilidad HTTP 500, código ERROR_INTERNO. Evidencia: resultado.json.
- G32-API-004-01: RECHAZADO. Origen no consultable por cadena RF-91: POST /finanzas/periodos/8/trazabilidad HTTP 500, código ERROR_INTERNO. Evidencia: resultado.json.

## Observaciones auxiliares

Ninguna.

## Observaciones

Efecto persistente aceptado por responsable QA (2026-11-07): 2 precios de mercado registrados, id_precio_mercado 172, 173. Cada precio ACTIVO no PRODUCTO puede dejar un evento M01 y un aviso ALERTA_FINANCIERA_NIC41 por Contador en bandeja interna, con referencia a un precio revertido por el sandbox. Si falta ID de precio, registros sin conciliar: 0. Bandeja del Contador QA: OBSERVADO; avisos observados 0. Es informativo; no altera veredictos ni oficialidad.

## Impedimentos observados en precios de mercado

Ninguno observado.

## Observación de identificadores

RF-86 define UUID para variación, activo, origen y período; las rutas y objetos observados en el backend usan enteros. Se registra como observación independiente; no modifica por sí sola la decisión.

## Incidencias de producto

### INC-M06-G32-01 — La verificación de trazabilidad del período falla con 500 y deja sin consultar el origen de las variaciones

- **Requisito afectado:** RF-86 Salida exige un vínculo navegable entre el asiento y su `evento_origen_id` para el Contador y auditores externos mediante la cadena RF-91; la tabla de Entradas y CA-6 exigen origen obligatorio y verificable. RF-91 R4 protege las cadenas de variaciones de períodos cerrados.
- **Pasos para reproducir:** con el período 8 ABIERTO y alguna línea ligada a una variación de un período CERRADO, registrar las variaciones; como Contador, ejecutar `POST /finanzas/periodos/8/trazabilidad`; consultar `GET /finanzas/lineas/{id}/cadena` para las líneas del RUN.
- **Resultado esperado:** la verificación permite navegar desde cada variación del período abierto a su origen sin modificar cadenas de períodos cerrados.
- **Resultado obtenido:** el POST devolvió HTTP 500 `ERROR_INTERNO` el 2026-11-08 a las 06:19:37.646675 UTC (01:19:37.646675 en Bogotá). Los GET de las líneas 390–395 devolvieron HTTP 200, pero las cadenas siguieron en `VERIFICACION_PENDIENTE` con `eslabones: null`; en particular, 391–395 no exponen origen.
- **Causa confirmada por el log de backend TEST aportado por el responsable QA:** «[TGR-M06-26] La cadena de trazabilidad id=46 está vinculada a la variación id=4 que pertenece a un período contable CERRADO. Las cadenas de trazabilidad de períodos cerrados son inmutables y no pueden modificarse ni completarse retroactivamente. Operación: INSERT. Requerimiento RF-91, Restricción 4». El trigger aplica RF-91 R4 al período de la variación. El caso de uso obtiene todas las líneas del período con `asientos.del_periodo`, intenta registrar la verificación de cada una y, ante la excepción, hace rollback y la propaga. Un solo rechazo aborta la verificación de todo el período: la API responde 500 y las cadenas del RUN no muestran el origen. Rutas de código leídas: `alembic/baseline/esquema_baseline.sql:13407-13447`, `verificar_trazabilidad_use_case.py:44-68,79-90` y `trazabilidad_repository.py:106-117`. El listado de variaciones omite el origen (`valoracion_repository.py:307-319`), aunque el registro lo persiste (`:110-122`).
- **Dato a revisar:** por qué existe en el período 8 ABIERTO una línea ligada a la variación 4 de un período CERRADO. Su origen no está confirmado y no se atribuye causa.
- **Impacto:** en estas condiciones no se puede verificar ninguna variación del período ni consultar su origen por la cadena. La trazabilidad NIC 41 obligatoria para Contador y auditores queda indisponible en todo el período, no solo en este RUN.
- **Severidad y certeza:** ALTA porque una función relevante queda bloqueada sin alternativa pública observada. Discrepancia y causa del rechazo CONFIRMADAS por API y log; origen de la línea conflictiva NO DETERMINADO.
- **Equipo inicial:** Desarrollo, por el HTTP 500 de la API pública y la interrupción de la verificación. Esta asignación inicial no atribuye la causa de la línea conflictiva.
- **Evidencias:** `resultado.json` (en este RUN) (`verificaciones_trazabilidad` y `consultas_cadena`), `newman/newman-G32.json` y este informe. El log fue aportado por el responsable QA; no consta como archivo del RUN.
- **Acción:** Desarrollo revisa INC-M06-G32-01 para restablecer la consulta del origen exigido; QA hará la reevaluación V2 con nueva autorización.

## Problemas técnicos y análisis de causas

Ninguno. Los códigos de error no prueban causa raíz por sí solos.

## Cierre y rollback

DELETE HTTP 200. Rollback verificado: DELETE 200 y ausencia pública poscierre de los registros del RUN; estado M02 restaurado si se preparó. Efecto persistente aceptado por responsable QA (2026-11-07): 2 precios de mercado registrados, id_precio_mercado 172, 173. Cada precio ACTIVO no PRODUCTO puede dejar un evento M01 y un aviso ALERTA_FINANCIERA_NIC41 por Contador en bandeja interna, con referencia a un precio revertido por el sandbox. Si falta ID de precio, registros sin conciliar: 0. Bandeja del Contador QA: OBSERVADO; avisos observados 0. Es informativo; no altera veredictos ni oficialidad. El rollback verificado se limita a los datos del sandbox.

## Conclusión y acciones

Los cuatro casos cumplen los tipos, montos, período y estado inicial observados. El TC-M06-001 no comprobó la ausencia de registro de precio porque la precondición de precio sin cambio no se cumplió; en TC-M06-002 y TC-M06-004 sí se observó que un componente cero no genera registro. Los cuatro casos siguen RECHAZADO porque el origen no fue consultable por la cadena de trazabilidad. Desarrollo atiende INC-M06-G32-01 y QA hará la reevaluación V2 con nueva autorización.

## Herramientas y cierre

Newman: 4 solicitudes y 0 aserciones fallidas. Cypress: 0 pruebas, sin UI requerida.

Actualización del informe (2026-11-08): incidencia descrita con la causa confirmada por el log del backend TEST y aclaración del caso TC-M06-001; veredictos sin cambios.
