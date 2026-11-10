# TC-M06-G46 — RUN-G46-V1-20261110-084842

Grupo G46 | caso TC-M06-034 | RF-87 | V1 | TEST | autorización AUT-G46-V1-[RESERVADO] | commit no consultado (Git prohibido).

## Resumen de veredictos

| Caso | Veredicto | Motivo |
|---|---|---|
| TC-M06-034 | APROBADO | 034_iniciado, 034_completado, 034_hash_verificable, 034_hash_eventos, 034_referencias |

## Preflight de datos

| Requisito | Esperado | Observado | Cumple | Bloqueante |
|---|---|---|---|---|
| periodo_220_abierto | ABIERTO | "ABIERTO" | SI | SI |
| prevalidacion_220_bloqueos_vacio | [] | 0 | SI | SI |
| prevalidacion_220_lineas_sin_trazabilidad_vacio | [] | 0 | SI | SI |
| prevalidacion_220_activos_sin_precio_vacio | [] | 0 | SI | SI |
| matriz_34_generica_activa | MANO_OBRA_PROPIA/UNICO 158405/250505 | {"id_asignacion_cuenta_contable":34,"tipo_hecho":"MANO_OBRA_PROPIA","sentido":"UNICO","id_especie":null,"subtipo_costo":null,"cuenta_debito":"158405","cuenta_credito":"250505"} | SI | SI |
| matriz_49_generica_activa | DEPRECIACION_ACTIVO_COSTO/UNICO 516005/159205 | {"id_asignacion_cuenta_contable":49,"tipo_hecho":"DEPRECIACION_ACTIVO_COSTO","sentido":"UNICO","id_especie":null,"subtipo_costo":null,"cuenta_debito":"516005","cuenta_credito":"159205"} | SI | SI |
| activo_1573_valoracion_costo_activa | valoración por costo activa | {"es_activa":true,"vida_util_meses":120,"depreciacion_acumulada":"0.0000"} | SI | NO |

## Esperado y observado por comprobación API

| Comprobación | Esperado | Observado | Estado |
|---|---|---|---|
| 034_iniciado | Un INICIADO del 220 con id_cierre, ejecutor y timestamp | cantidad 1; referencia 46; usuario 5; ejecutor 5; timestamp true | APROBADO |
| 034_completado | Un COMPLETADO con referencia, ejecutor, comprobantes, activos y hash | cantidad 1; referencia 46; usuario 5; ejecutor 5; códigos coinciden true; truncado false | APROBADO |
| 034_hash_verificable | Tres hash publicados iguales; recálculo canónico de cierre y comprobantes | publicados iguales true; discrepancias de recálculo 0; truncado false | APROBADO |
| 034_hash_eventos | INICIADO y COMPLETADO con hash_integridad SHA-256 hexadecimal | iniciado true; completado true | APROBADO |
| 034_referencias | Variaciones masivas y depreciaciones referencian id_cierre; al menos una | variaciones 0; depreciaciones 1; referencias correctas true | APROBADO |

No hay comprobaciones UI obligatorias en esta orden. El cuerpo íntegro saneado del POST y los eventos consultados están en `resultado.json`. Los textos canónicos y hashes de discrepancias de recálculo están en `casos.TC-M06-034.comprobaciones`.

## Evidencias y herramientas

Node v22.15.1; Newman 0; Cypress no aplica (0 pruebas); solicitudes 31.
- newman/newman-G46.html
- newman/newman-G46.json

## Incidencias de producto

- Ninguna discrepancia de producto acreditada.

## Problemas técnicos

- Ninguno registrado.

## Observaciones y alcance

- El hash_integridad de auditoría lo calcula un trigger sobre la fila completa; no se puede recalcular por API.
- Las API de comprobantes y variaciones no exponen id_cierre.
- Los eventos se delimitan por id_evento, porque now() dentro del sandbox es el inicio de la transacción.
- Lectura complementaria 7 y 219: [{"periodo":7,"id_cierre":1,"eventos":[{"tipo_evento":"CIERRE_PERIODO_COMPLETADO","id_referencia":1,"id_usuario":141,"hash_presente":true,"hash_cierre_coincide":true},{"tipo_evento":"CIERRE_PERIODO_INICIADO","id_referencia":1,"id_usuario":141,"hash_presente":true,"hash_cierre_coincide":false}]},{"periodo":219,"id_cierre":43,"eventos":[{"tipo_evento":"CIERRE_PERIODO_COMPLETADO","id_referencia":43,"id_usuario":141,"hash_presente":true,"hash_cierre_coincide":true},{"tipo_evento":"CIERRE_PERIODO_INICIADO","id_referencia":43,"id_usuario":141,"hash_presente":true,"hash_cierre_coincide":false}]}].

## Cierre y rollback

DELETE del RUN: HTTP 200. Rollback verificado mediante lecturas posteriores: SI. 220 ABIERTO true; líneas true; comprobantes true; variaciones true; períodos true; sin eventos del cierre true; costo 1573 true
Registro OFICIAL. QA revisa la evidencia y decide la próxima acción autorizada.
