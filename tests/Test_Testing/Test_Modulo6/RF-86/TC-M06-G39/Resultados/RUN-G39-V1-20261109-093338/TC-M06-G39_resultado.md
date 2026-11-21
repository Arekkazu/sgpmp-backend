# TC-M06-G39 — APROBADO

## Identificación

Grupo G39; casos TC-M06-016 y TC-M06-017; RF-86 v2.0; RUN RUN-G39-V1-20261109-093338; versión 1; intento 3; autorización AUT-G39-V1-R3-20261109; ambiente TEST; commit no consultado. Node v22.15.1; Newman 6.2.2. Oficial true.

## Veredictos

| Caso | Estado | Fundamento |
| --- | --- | --- |
| TC-M06-016 | APROBADO | Cuatro operaciones RF-90 conformes; una línea de mano de obra, ninguna de factura. |
| TC-M06-017 | APROBADO | Venta y muerte con BAJA_ACTIVO por valor en libros; venta sin ingreso. |

## Detalle por caso

### TC-M06-016

- Adaptación de precondición: la fila pide un bovino con precio vigente. Los bovinos disponibles (NIT-A) tienen CERRADO el período de la fecha del costo y RF-90 lo rechaza por FA-4. Se usó el caprino 1569 de la finca 467, sin precio de mercado; su período ABIERTO se comprueba antes de escribir. RF-90 y la línea MANO_OBRA_PROPIA usan el monto del costo, no el precio de mercado; CONSUMO_INVENTARIO se rechaza antes de consultar el activo. La matriz RF-109 es genérica (id_especie NULL). Ni la especie ni la ausencia de precio cambian las cuentas o el oráculo.

- Esperado: CONSUMO_INVENTARIO manual → 422 sin costo ni línea; MANO_OBRA_PROPIA → una línea según RF-109; COMPRA_PROVEEDOR y SERVICIO_TERCERO → sin línea.
- Observado (valores, cuentas e IDs de la API):

Activo 1569, período 220. En «costo» y «línea» se muestran los IDs nuevos, o 0 cuando no se creó ninguno.

| origen | HTTP | código | costo | vehículo | línea | tipo/sentido | valor | débito→crédito | resultado esperado | cumple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CONSUMO_INVENTARIO | 422 | ORIGEN_RESERVADO_M05 | 0 | — | 0 | — | — | — | 422; 0 costos y 0 líneas | Sí |
| MANO_OBRA_PROPIA | 201 | — | 24 | ASIENTO_NIC41 | 925 | MANO_OBRA_PROPIA/UNICO | 123.45 | 158405→250505 | 201; 1 costo y 1 línea RF-109 | Sí |
| COMPRA_PROVEEDOR | 201 | — | 25 | FACTURA_COMPRA | ninguno | — | — | — | 201; 1 costo y 0 líneas | Sí |
| SERVICIO_TERCERO | 201 | — | 26 | FACTURA_COMPRA | ninguno | — | — | — | 201; 1 costo y 0 líneas | Sí |

RF-90 FA-12 reserva CONSUMO_INVENTARIO a M05; el catálogo tipo_hecho de RF-86 exige MANO_OBRA_PROPIA y no genera líneas para las facturas. La línea de mano de obra consta como REGISTRADA, tabla_origen registros_costos e id_origen 24. Las cuatro comprobaciones coinciden con ese oráculo.

- Comparación y decisión: **APROBADO**. Cuatro operaciones RF-90 conformes; una línea de mano de obra, ninguna de factura.

### TC-M06-017

- Esperado: Venta y muerte → una BAJA_ACTIVO por valor en libros truncado, sentidos y cuentas RF-109; venta sin línea de ingreso.
- Observado (valores, cuentas e IDs de la API):

Período destino 8. «Línea de ingreso» indica si apareció otra línea del activo.

| baja | activo | valor en libros | línea | sentido | valor | débito→crédito | línea de ingreso | cumple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| venta (baja HTTP 201, proceso HTTP 200, evento 1358) | 943 | 3015990.0000 | 926 BAJA_ACTIVO | UNICO | 3015990.00 | 613505→158405 | No | Sí |
| muerte (baja HTTP 201, proceso HTTP 200, evento 1359) | 944 | 2779956.0000 | 927 BAJA_ACTIVO | PERDIDA | 2779956.00 | 539510→158405 | No | Sí |

Las líneas 926 y 927 constan REGISTRADAS, con tabla_origen procesamientos_eventos_m02 e id_origen 1358 y 1359, respectivamente. CA-20 exige una BAJA_ACTIVO por valor en libros para cada baja, con débito en costo de venta o pérdida según el tipo y crédito al activo biológico; la venta no genera ingreso. Las dos bajas coinciden con ese oráculo y no agregaron otra línea del activo.

- Comparación y decisión: **APROBADO**. Venta y muerte con BAJA_ACTIVO por valor en libros; venta sin ingreso.

Comprobaciones API 2; UI 0 (solo API); solicitudes del ejecutor 45/150.

## Contraste de contrato

- `/finanzas/activos` (ejecutor): coincide, HTTP 200.
- `/finanzas/periodos` (ejecutor): coincide, HTTP 200.
- `/finanzas/precios?id_especie=39` (ejecutor): coincide, HTTP 200.
- `/finanzas/precios?id_especie=423` (ejecutor): coincide, HTTP 200.
- `/finanzas/precios?id_especie=42` (ejecutor): coincide, HTTP 200.
- `/finanzas/precios?id_especie=422` (ejecutor): coincide, HTTP 200.
- `/finanzas/precios?id_especie=421` (ejecutor): coincide, HTTP 200.
- `/finanzas/activos/943` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/943/ficha-integral` (ejecutor): coincide, HTTP 200.
- `/finanzas/activos/944` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/944/ficha-integral` (ejecutor): coincide, HTTP 200.
- `/finanzas/activos/945` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/945/ficha-integral` (ejecutor): coincide, HTTP 200.
- `/finanzas/activos/946` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/946/ficha-integral` (ejecutor): coincide, HTTP 200.
- `/finanzas/activos/947` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/947/ficha-integral` (ejecutor): coincide, HTTP 200.
- `/finanzas/activos/948` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/948/ficha-integral` (ejecutor): coincide, HTTP 200.
- `/finanzas/activos/1569` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/1569/ficha-integral` (ejecutor): coincide, HTTP 200.
- `/finanzas/configuracion` (ejecutor): coincide, HTTP 200.
- `/finanzas/lineas?id_periodo_contable=220` (ejecutor): coincide, HTTP 200.
- `/finanzas/lineas?id_periodo_contable=8` (ejecutor): coincide, HTTP 200.
- `/finanzas/costos?id_activo_biologico=1569` (ejecutor): coincide, HTTP 200.
- `/finanzas/costos` (ejecutor): coincide, HTTP 201.
- `/activos-biologicos/943/eventos/baja` (ejecutor): coincide, HTTP 201.
- `/finanzas/eventos/procesar` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/944/eventos/baja` (ejecutor): coincide, HTTP 201.
- `/finanzas/configuracion` (Newman): coincide, HTTP 200.
- `/finanzas/lineas?id_periodo_contable=220` (Newman): coincide, HTTP 200.
- `/finanzas/costos?id_activo_biologico=1569` (Newman): coincide, HTTP 200.

Discrepancias: 0.

## Evidencias reales

- resultado.json
- TC-M06-G39_resultado.md
- newman/newman-G39.json
- newman/newman-G39.html

## Incidencias

Ninguna incidencia de producto.

Problemas técnicos: ninguno. La primera discrepancia pública orienta la atención; la causa raíz requiere investigación.

## Observación de configuración

Con política GASTO, la matriz de TEST conocida asigna 158405 como débito de MANO_OBRA_PROPIA/UNICO, cuenta del activo biológico en TB/PM. El oráculo usa la matriz leída. QA debe decidir si reporta la configuración.

## Cierre y rollback

DELETE HTTP 200; rollback verificado: IDs del RUN ausentes en lecturas públicas.. Lecturas poscierre: /finanzas/costos?id_activo_biologico=1569 HTTP 200; /finanzas/lineas?id_periodo_contable=220 HTTP 200; /finanzas/lineas?id_periodo_contable=8 HTTP 200; /activos-biologicos/943/eventos HTTP 200; /activos-biologicos/944/eventos HTTP 200; /activos-biologicos/943/ficha-integral HTTP 200; /activos-biologicos/944/ficha-integral HTTP 200.

## Conclusión

Registro OFICIAL. Revisar la observación de configuración; sin acción correctiva de producto acreditada.

Actualización del informe (2026-11-09): detalle por caso en tablas; veredictos sin cambios.
