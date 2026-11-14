# TC-M06-G44 — RUN-G44-V1-20261110-055212

G44 | RF-87 | TC-M06-028, TC-M06-029, TC-M06-030 | V1 | TEST | autorización AUT-G44-V1-R2-20261110 | commit no consultado (Git prohibido).

## Resumen

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-028 | RECHAZADO | 028_b, 028_c |
| TC-M06-029 | RECHAZADO | 029_mensaje |
| TC-M06-030 | RECHAZADO | 030_cerrado, 030_concurrencia |

## Criterios API y UI

| Caso | Criterio | Esperado | Observado | Cumple |
|---|---|---|---|---|
| TC-M06-028 | 028_a | PENDIENTE_CUENTA y lista de faltantes; 220 ABIERTO sin cierre | 028_a: HTTP 422, error CIERRE_BLOQUEADO, mensaje 1 líneas no tienen cuentas en la matriz contable: Mano de obra propia (único) de Caprino Qa Aislado. Asígnelas en Configuración contable.; línea pendiente true; bloqueo LINEAS_PENDIENTE_CUENT | APROBADO |
| TC-M06-028 | 028_b | Matriz incompleta informada; 219 ABIERTO sin cierre | 028_b: HTTP 200, error ausente, mensaje ausente; estado CERRADO | RECHAZADO |
| TC-M06-028 | 028_c | Finca sin titular informada; 219 ABIERTO sin cierre | 028_c: HTTP 409, error PERIODO_CERRADO, mensaje El período 2026-11 ya fue cerrado el 2026-11-10. Los períodos cerrados no se reabren: corrija con ajustes en el período abierto.; prevalidación ; estado CERRADO | RECHAZADO |
| TC-M06-029 | 029_acceso | 403 y 219 sin cambios para tres roles | 029.acceso: true,true,true | APROBADO |
| TC-M06-029 | 029_mensaje | FA-4 y rol explícito para cada 403 | 029.mensaje: false,false,false | RECHAZADO |
| TC-M06-029 | 029_admin | Administrador consulta estado y prevalidación con 200 | 029.admin: HTTP 200/200 | APROBADO |
| TC-M06-030 | 030_cerrado | 409 Periodo inmutable con fecha y Contador ejecutor; 7 CERRADO | 030_cerrado: HTTP 409, error PERIODO_CERRADO, mensaje El período 2026-11 ya fue cerrado el 2026-11-07. Los períodos cerrados no se reabren: corrija con ajustes en el período abierto.; 7 sin cambios true | RECHAZADO |
| TC-M06-030 | 030_concurrencia | Segundo 409 de concurrencia con hora y usuario del primero | 030_concurrencia: HTTP 409, error EXCLUSION_REQUIERE_AUTORIZACION, mensaje 1 asientos tienen la cadena de trazabilidad incompleta y no pueden entrar al cierre. Autorice su exclusión para continuar.; primero 030.primero: HTTP 409, error EXCL | RECHAZADO |
| TC-M06-030 | 030_sin_segundo | 8 ABIERTO sin segundo cierre ni comprobantes nuevos | 030.sin_segundo: estado ABIERTO; comprobantes 0; líneas 8 | APROBADO |

## Precios

| Especie | P_ini id/fecha | P_nuevo id/fecha | Congelado id/fecha |
|---|---|---|---|

## Activos sin precio

| Periodo | Prevalidacion | Excluidos | Procesados |
|---|---|---|---|

## Lineas

| Linea | Activo | Eslabon faltante | Excluida | Destino |
|---|---|---|---|---|

## UI

| Panel | Pruebas ejecutadas | Estado | Acta |
|---|---|---|---|

## Incidencias

- INC-M06-G44-01 (casos TC-M06-029): esperado 403 FA-4 con rol y sin cambios; obtenido 029.admin: HTTP 403, error ACCESO_DENEGADO, mensaje Acceso denegado. Su rol no tiene permisos para realizar esta operación.; sin cambios true; rol en mensaje false. Evidencia: resultado.json. Impacto: Control de acceso o explicación al rol incorrectos.. Severidad MEDIA: La discrepancia afecta parcialmente el control o la explicación al usuario.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada en la API pública de cierre.. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar.. Acción: Desarrollo revisa el comportamiento y QA repite en RUN autorizado..
- INC-M06-G44-02 (casos TC-M06-030): esperado 409 Periodo inmutable con fecha y ejecutor; obtenido 030_cerrado: HTTP 409, error PERIODO_CERRADO, mensaje El período 2026-11 ya fue cerrado el 2026-11-07. Los períodos cerrados no se reabren: corrija con ajustes en el período abierto.. Evidencia: resultado.json. Impacto: El 409 omite información de auditoría requerida.. Severidad MEDIA: La discrepancia afecta parcialmente el control o la explicación al usuario.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada en la API pública de cierre.. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar.. Acción: Desarrollo revisa el comportamiento y QA repite en RUN autorizado..
- INC-M06-G44-03 (casos TC-M06-030): esperado Segundo cierre rechazado por concurrencia con hora y usuario; obtenido 030_concurrencia: HTTP 409, error EXCLUSION_REQUIERE_AUTORIZACION, mensaje 1 asientos tienen la cadena de trazabilidad incompleta y no pueden entrar al cierre. Autorice su exclusión para continuar.. Evidencia: resultado.json. Impacto: El estado de cierre activo no se representa como exige RF-87.. Severidad MEDIA: La discrepancia afecta parcialmente el control o la explicación al usuario.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada en la API pública de cierre.. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar.. Acción: Desarrollo revisa el comportamiento y QA repite en RUN autorizado..
- INC-M06-G44-05 (casos TC-M06-028): esperado Bloqueo por matriz incompleta con lista; obtenido 028_b: HTTP 200, error ausente, mensaje ausente. Evidencia: resultado.json. Impacto: Cierre con depreciación sin cuenta no informado como exige RF-87.. Severidad ALTA: La discrepancia bloquea un control relevante del cierre sin alternativa demostrada.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada en la API pública de cierre.. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar.. Acción: Desarrollo revisa el comportamiento y QA repite en RUN autorizado..
- INC-M06-G44-06 (casos TC-M06-028): esperado Bloqueo por finca sin titular; obtenido 028_c: HTTP 409, error PERIODO_CERRADO, mensaje El período 2026-11 ya fue cerrado el 2026-11-10. Los períodos cerrados no se reabren: corrija con ajustes en el período abierto.. Evidencia: resultado.json. Impacto: Cierre puede completarse o fallar sin informar titular ausente.. Severidad ALTA: La discrepancia bloquea un control relevante del cierre sin alternativa demostrada.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada en la API pública de cierre.. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar.. Acción: Desarrollo revisa el comportamiento y QA repite en RUN autorizado..

## Herramientas y evidencias

Node v22.15.1; Newman codigo 0; Cypress codigo 0, pruebas 0.
- newman/newman-G44.html
- newman/newman-G44.json

## Problemas tecnicos


## Observaciones


## Cierre, rollback y accion

Registro OFICIAL. Rollback verificado: si. Lecturas poscierre sin cabeceras: matriz true; costo ausente true; titular true; periodos true; líneas y artefactos true
Las incidencias requieren correccion y reevaluacion expresamente autorizada.
