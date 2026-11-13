# TC-M06-G32 — APROBADO

## Identificación

TC-M06-G32 / TC-M06-001, TC-M06-G32 / TC-M06-002, TC-M06-G32 / TC-M06-003, TC-M06-G32 / TC-M06-004; RF-86 v2.0; RUN RUN-G32-V2-20261111-203044; versión 2; intento 8; ambiente TEST; autorización AUT-G32-V2-20261111. Node v22.15.1; Newman 6.2.2. Commit de TEST informado por responsable QA: 453277e4; no verificado por este ejecutor. Solo API.

## Decisión del caso

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-G32 / TC-M06-001 | APROBADO | Se observaron 1 registros con tipos, montos, componentes, origen y responsable esperados. |
| TC-M06-G32 / TC-M06-002 | APROBADO | Se observaron 1 registros con tipos, montos, componentes, origen y responsable esperados. |
| TC-M06-G32 / TC-M06-003 | APROBADO | Se observaron 2 registros con tipos, montos, componentes, origen y responsable esperados. |
| TC-M06-G32 / TC-M06-004 | APROBADO | Se observaron 1 registros con tipos, montos, componentes, origen y responsable esperados. |

## Preflight vivo

- periodo_actual_abierto: esperado titular con período que contiene hoy ABIERTO, observado [241,241,"período que contiene hoy CERRADO","período que contiene hoy CERRADO","período que contiene hoy CERRADO","período que contiene hoy CERRADO","período que contiene hoy CERRADO",241,241,241], cumple true, bloqueante true.
- cuatro_bovinos_elegibles: esperado 4 bovinos individuales reconocidos, distintos, sin costo activo y con cálculo/peso, observado {"seleccionados":4,"diagnostico":{"medido":true,"total_recibido":23,"bovino":12,"individual":12,"estado":11,"sin_costo":10,"valor_positivo":10,"precio_vigente":10,"periodo_destino":5,"peso_kg":5,"calculo_previo":5,"primera_condicion_fallida":null}}, cumple true, bloqueante true.
- precio_peso_kg_vigente: esperado precio PESO_KG vigente para los 4 activos, observado [18,18,18,18], cumple true, bloqueante true.
- matriz_tb_pm_activa: esperado asignaciones activas VARIACION_VR_TB y VARIACION_VR_PM, observado {"http":200,"tipos":["VARIACION_VR_TB","VARIACION_VR_PM"]}, cumple true, bloqueante true.
- periodo_8_linea_conflictiva: esperado período 8 ABIERTO y línea no verificada de variación CERRADA, observado {"estado_periodo":"EN_CIERRE","existe":false,"motivo":"Condición ausente: período 8 en estado EN_CIERRE; se requiere ABIERTO."}, cumple false, bloqueante false.

## Diagnóstico de candidatos

Conteos acumulados, sin titular tributario ni datos personales: medido: true; total_recibido: 23; bovino: 12; individual: 12; estado: 11; sin_costo: 10; valor_positivo: 10; precio_vigente: 10; periodo_destino: 5; peso_kg: 5; calculo_previo: 5; primera_condicion_fallida: ninguna.

## Datos y método

Se usaron activos reconocidos ya existentes. Solo se usa el período del titular que contiene hoy en America/Bogota si está ABIERTO; un período posterior no satisface la precondición. La selección del precio sigue precios.py:38-52. El oráculo TB/PM compara el último cálculo previo con el nuevo valor neto y las magnitudes según medidor.py:62-75, valorador.py:88-112 y nic41.py:129-148. La regla M02 permite registrar eventos de crecimiento únicamente para activos ACTIVO (Especificacion-Requerimientos-Modulo2.md:2194); en TC-M06-002 se registra el pesaje en ACTIVO, luego PATCH a EN_TRATAMIENTO y después POST /finanzas/eventos/procesar dentro del RUN. El proceso de fondo usa otra sesión y no ve la escritura sin confirmar del sandbox. No se ingresaron datos contables manuales. Tras comprobar importes y estado inicial se invoca una verificacion RF-91 por periodo destino y luego se consulta cada cadena.

## Verificacion RF-91 y origen

- Periodo 241: POST /finanzas/periodos/241/trazabilidad -> HTTP 200; codigo ninguno; cuerpo saneado {"verificadas":98,"pendientes":[]}; eco RUN true.

## Consultas de cadena RF-91

- TC-M06-001, variacion 388, linea 5613: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":5613,"tipo_hecho":"VARIACION_VR_TB","sentido":"GANANCIA","valor":"71289.60","tabla_origen":"variaciones_valor_razonable","id_origen":388,"tipo_evidencia":"REGISTRO_MANUAL","estado_trazabilidad":"VERIFICADO","id_activo_biologico":1627,"fecha_hecho":"2026-11-11","cuenta_debito":"158405","cuenta_credito":"424805","estado_verificacion":"VERIFICADO","nivel_fallo":null,"fecha_verificacion":"2026-11-11T20:30:47.573517Z","eslabones_faltantes":null,"eslabones":{"ids":{"id_evento":1564,"id_precio_mercado":18,"id_variacion_valor_razonable":388},"cierre":null,"origen":true,"faltantes":[],"evento_m02":true,"nivel_fallo":null,"lecturas_nic41":null,"evento_sanitario":null,"precio_documentado":true}}; ids {"id_evento":1564,"id_precio_mercado":18}.
- TC-M06-002, variacion 389, linea 5614: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":5614,"tipo_hecho":"VARIACION_VR_TB","sentido":"PERDIDA","valor":"64972.80","tabla_origen":"variaciones_valor_razonable","id_origen":389,"tipo_evidencia":"REGISTRO_MANUAL","estado_trazabilidad":"VERIFICADO","id_activo_biologico":1831,"fecha_hecho":"2026-11-11","cuenta_debito":"539505","cuenta_credito":"158405","estado_verificacion":"VERIFICADO","nivel_fallo":null,"fecha_verificacion":"2026-11-11T20:30:47.573517Z","eslabones_faltantes":null,"eslabones":{"ids":{"id_evento":1565,"id_precio_mercado":18,"id_variacion_valor_razonable":389},"cierre":null,"origen":true,"faltantes":[],"evento_m02":true,"nivel_fallo":null,"lecturas_nic41":null,"evento_sanitario":null,"precio_documentado":true}}; ids {"id_evento":1565,"id_precio_mercado":18}.
- TC-M06-003, variacion 391, linea 5616: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":5616,"tipo_hecho":"VARIACION_VR_PM","sentido":"PERDIDA","valor":"171456.00","tabla_origen":"variaciones_valor_razonable","id_origen":391,"tipo_evidencia":"VARIACION_PRECIO","estado_trazabilidad":"VERIFICADO","id_activo_biologico":1832,"fecha_hecho":"2026-11-11","cuenta_debito":"539505","cuenta_credito":"158405","estado_verificacion":"VERIFICADO","nivel_fallo":null,"fecha_verificacion":"2026-11-11T20:30:47.573517Z","eslabones_faltantes":null,"eslabones":{"ids":{"id_evento":1566,"id_precio_mercado":655,"id_variacion_valor_razonable":391},"cierre":null,"origen":true,"faltantes":[],"evento_m02":true,"nivel_fallo":null,"lecturas_nic41":null,"evento_sanitario":null,"precio_documentado":true}}; ids {"id_evento":1566,"id_precio_mercado":655}.
- TC-M06-003, variacion 390, linea 5615: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":5615,"tipo_hecho":"VARIACION_VR_TB","sentido":"GANANCIA","valor":"325766.40","tabla_origen":"variaciones_valor_razonable","id_origen":390,"tipo_evidencia":"REGISTRO_MANUAL","estado_trazabilidad":"VERIFICADO","id_activo_biologico":1832,"fecha_hecho":"2026-11-11","cuenta_debito":"158405","cuenta_credito":"424805","estado_verificacion":"VERIFICADO","nivel_fallo":null,"fecha_verificacion":"2026-11-11T20:30:47.573517Z","eslabones_faltantes":null,"eslabones":{"ids":{"id_evento":1566,"id_precio_mercado":655,"id_variacion_valor_razonable":390},"cierre":null,"origen":true,"faltantes":[],"evento_m02":true,"nivel_fallo":null,"lecturas_nic41":null,"evento_sanitario":null,"precio_documentado":true}}; ids {"id_evento":1566,"id_precio_mercado":655}.
- TC-M06-004, variacion 392, linea 5617: GET cadena HTTP 200; codigo ninguno; cuerpo saneado {"id_linea_asiento_nic41":5617,"tipo_hecho":"VARIACION_VR_PM","sentido":"GANANCIA","valor":"180480.00","tabla_origen":"variaciones_valor_razonable","id_origen":392,"tipo_evidencia":"VARIACION_PRECIO","estado_trazabilidad":"VERIFICADO","id_activo_biologico":1833,"fecha_hecho":"2026-11-11","cuenta_debito":"158405","cuenta_credito":"424805","estado_verificacion":"VERIFICADO","nivel_fallo":null,"fecha_verificacion":"2026-11-11T20:30:47.573517Z","eslabones_faltantes":null,"eslabones":{"ids":{"id_evento":1567,"id_precio_mercado":656,"id_variacion_valor_razonable":392},"cierre":null,"origen":true,"faltantes":[],"evento_m02":true,"nivel_fallo":null,"lecturas_nic41":null,"evento_sanitario":null,"precio_documentado":true}}; ids {"id_evento":1567,"id_precio_mercado":656}.

## Detalle por caso

### TC-M06-G32 / TC-M06-001

- **Preparación:** activo 1627, evento M02 1564, precio vigente 18, período destino 241; estado al pesaje ACTIVO y al procesar ACTIVO. 
- **Esperado:** una ganancia por transformación del componente RF-83 y ningún registro de precio, con precio sin cambio; origen navegable por la cadena de trazabilidad.
- **Observado:**
  - Variación 388: GANANCIA_TRANSFORMACION_BIOLOGICA, monto 71289.60, VR 3564480.00 → 3635769.60, estado VERIFICACION_PENDIENTE.
  - Medición RF-83: transformación 71289.6000, precio 0.0000, total 71289.6000, VR 3564480.0000 → 3635769.6000; estado COMPLETADO.
  - Valores contrastados: transformación 71289.6, precio 0, total 71289.6; magnitud 395 → 402.9.
- **Cumplido:** Los tipos, montos, período y estado inicial observados coincidieron con los componentes medidos; la consulta del origen quedó pendiente.
- **Fallo y motivo:** Ninguno confirmado.
- **Decisión:** APROBADO.

### TC-M06-G32 / TC-M06-002

- **Preparación:** activo 1831, evento M02 1565, precio vigente 18, período destino 241; estado al pesaje ACTIVO y al procesar EN_TRATAMIENTO. 
- **Esperado:** una pérdida por transformación en EN_TRATAMIENTO y ningún registro de precio; origen navegable por la cadena de trazabilidad.
- **Observado:**
  - Variación 389: PERDIDA_TRANSFORMACION_BIOLOGICA, monto -64972.80, VR 3248640.00 → 3183667.20, estado VERIFICACION_PENDIENTE.
  - Medición RF-83: transformación -64972.8000, precio 0.0000, total -64972.8000, VR 3248640.0000 → 3183667.2000; estado COMPLETADO.
  - Valores contrastados: transformación -64972.8, precio 0, total -64972.8; magnitud 360 → 352.8.
- **Cumplido:** Los tipos, montos, período y estado inicial observados coincidieron con los componentes medidos; la consulta del origen quedó pendiente.
- **Fallo y motivo:** Ninguno confirmado.
- **Decisión:** APROBADO.

### TC-M06-G32 / TC-M06-003

- **Preparación:** activo 1832, evento M02 1566, precio vigente 655, período destino 241; estado al pesaje ACTIVO y al procesar ACTIVO. 
- **Esperado:** dos registros separados: ganancia por transformación y pérdida por precio, cada uno con su origen; origen navegable por la cadena de trazabilidad.
- **Observado:**
  - Variación 391: PERDIDA_PRECIO_MERCADO, monto -171456.00, VR 3429120.00 → 3583430.40, estado VERIFICACION_PENDIENTE.
  - Variación 390: GANANCIA_TRANSFORMACION_BIOLOGICA, monto 325766.40, VR 3429120.00 → 3583430.40, estado VERIFICACION_PENDIENTE.
  - Medición RF-83: transformación 325766.4000, precio -171456.0000, total 154310.4000, VR 3429120.0000 → 3583430.4000; estado COMPLETADO.
  - Valores contrastados: transformación 325766.4, precio -171456, total 154310.4; magnitud 380 → 418.
- **Cumplido:** Los tipos, montos, período y estado inicial observados coincidieron con los componentes medidos; la consulta del origen quedó pendiente.
- **Fallo y motivo:** Ninguno confirmado.
- **Decisión:** APROBADO.

### TC-M06-G32 / TC-M06-004

- **Preparación:** activo 1833, evento M02 1567, precio vigente 656, período destino 241; estado al pesaje ACTIVO y al procesar ACTIVO. 
- **Esperado:** solo una ganancia por precio, sin transformación porque no cambia la magnitud física; origen navegable por la cadena de trazabilidad.
- **Observado:**
  - Variación 392: GANANCIA_PRECIO_MERCADO, monto 180480.00, VR 3609600.00 → 3790080.00, estado VERIFICACION_PENDIENTE.
  - Medición RF-83: transformación 0.0000, precio 180480.0000, total 180480.0000, VR 3609600.0000 → 3790080.0000; estado COMPLETADO.
  - Valores contrastados: transformación 0, precio 180480, total 180480; magnitud 400 → 400.
- **Cumplido:** Los tipos, montos, período y estado inicial observados coincidieron con los componentes medidos; la consulta del origen quedó pendiente.
- **Fallo y motivo:** Ninguno confirmado.
- **Decisión:** APROBADO.

## Comprobaciones API y evidencias

- G32-API-001-01: APROBADO. Se observaron 1 registros con tipos, montos, componentes, origen y responsable esperados. Evidencia: resultado.json.
- G32-API-002-01: APROBADO. Se observaron 1 registros con tipos, montos, componentes, origen y responsable esperados. Evidencia: resultado.json.
- G32-API-003-01: APROBADO. Se observaron 2 registros con tipos, montos, componentes, origen y responsable esperados. Evidencia: resultado.json.
- G32-API-004-01: APROBADO. Se observaron 1 registros con tipos, montos, componentes, origen y responsable esperados. Evidencia: resultado.json.

## Observaciones auxiliares

Ninguna.

## Observaciones

Efecto persistente declarado bajo la autorización de este RUN (AUT-G32-V2-20261111) y su SOL de V2: 2 precios de mercado registrados, id_precio_mercado 655, 656. Cada precio ACTIVO no PRODUCTO puede dejar un evento M01 y un aviso ALERTA_FINANCIERA_NIC41 por Contador en bandeja interna, con referencia a un precio revertido por el sandbox. Si falta ID de precio, registros sin conciliar: 0. Bandeja del Contador QA: OBSERVADO; avisos observados 2. Es informativo; no altera veredictos ni oficialidad.

### Seguimiento de incidencias V1

- INC-M06-G32-01: NO_REPRODUCIDA. Condición ausente: período 8 en estado EN_CIERRE; se requiere ABIERTO.

Sin incidencias nuevas.

## Impedimentos observados en precios de mercado

Ninguno observado.

## Observación de identificadores

RF-86 define UUID para variación, activo, origen y período; las rutas y objetos observados en el backend usan enteros. Se registra como observación independiente; no modifica por sí sola la decisión.

## Incidencias de producto

No se confirmaron incidencias de producto.

## Problemas técnicos y análisis de causas

Ninguno. Los códigos de error no prueban causa raíz por sí solos.

## Cierre y rollback

DELETE HTTP 200. Rollback verificado: DELETE 200 y ausencia pública poscierre de los registros del RUN; estado M02 restaurado si se preparó. Efecto persistente declarado bajo la autorización de este RUN (AUT-G32-V2-20261111) y su SOL de V2: 2 precios de mercado registrados, id_precio_mercado 655, 656. Cada precio ACTIVO no PRODUCTO puede dejar un evento M01 y un aviso ALERTA_FINANCIERA_NIC41 por Contador en bandeja interna, con referencia a un precio revertido por el sandbox. Si falta ID de precio, registros sin conciliar: 0. Bandeja del Contador QA: OBSERVADO; avisos observados 2. Es informativo; no altera veredictos ni oficialidad. El rollback verificado se limita a los datos del sandbox.

## Conclusión y acciones

Los cuatro oráculos se demostraron con API pública.

## Herramientas y cierre

Newman: 4 solicitudes y 0 aserciones fallidas. Cypress: 0 pruebas, sin UI requerida.
