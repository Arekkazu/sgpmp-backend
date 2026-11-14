# TC-M06-G44 — reevaluación V3 oficial - RECHAZADO

Grupo G44; casos TC-M06-028, TC-M06-029, TC-M06-030; RF-87; versión 3; RUN RUN-G44-V3-20261114-021712; TEST; autorización AUT-G44-V3-R2-20261113.
Corrección informada: Desarrollo 0fcde3bb (#1065), origin/test 453277e4. El despliegue requiere verificación en RUN autorizado.

## Resumen

- TC-M06-028: APROBADO. Criterios conformes
- TC-M06-029: APROBADO. Criterios conformes
- TC-M06-030: RECHAZADO. 030_cerrado, 030_concurrencia

## Preflight de datos

| Requisito | Esperado | Observado | Cumple | Bloqueante |
|---|---|---|---|---|
| permiso_contador_cierre_periodo_5 | true | true | SÍ | SÍ |
| permiso_contador_cierre_periodo_2 | true | true | SÍ | SÍ |
| permiso_contador_configuracion_contable_3 | true | true | SÍ | SÍ |
| permiso_contador_costos_activos_1 | true | true | SÍ | SÍ |
| permiso_admin_fincas_3 | true | true | SÍ | SÍ |
| permiso_admin_cierre_periodo_2 | true | true | SÍ | SÍ |
| permiso_veterinario_cierre_periodo_5 | false | false | SÍ | SÍ |
| permiso_productor_cierre_periodo_5 | false | false | SÍ | SÍ |
| permiso_admin_cierre_periodo_5 | true | true | SÍ | NO |
| periodo_7_estado | CERRADO | "CERRADO" | SÍ | SÍ |
| periodo_219_estado | CERRADO | "CERRADO" | SÍ | SÍ |
| periodo_220_estado | ABIERTO | "ABIERTO" | SÍ | SÍ |
| periodo_260_estado | ABIERTO | "ABIERTO" | SÍ | SÍ |
| periodo_8_estado | ABIERTO o EN_CIERRE con cierre 67 EN_PROCESO paso 3 | "EN_CIERRE" | SÍ | SÍ |
| periodo_260_titular_466 | Mismo titular tributario | true | SÍ | SÍ |
| periodo_220_titular_467 | Mismo titular tributario | true | SÍ | SÍ |
| periodo_220_lineas_finca_467 | Líneas de finca 467 presentes | true | SÍ | SÍ |
| periodo_260_sin_lineas | Sin líneas previas | 0 | SÍ | SÍ |
| prevalidacion_220_sin_bloqueos | [] | [] | SÍ | SÍ |
| prevalidacion_260_sin_bloqueos | [] | [] | SÍ | SÍ |
| titular_466_completo | cuatro campos tributarios completos | {"tipo_id_tributaria":true,"numero_id_tributaria":true,"dv":true,"razon_social":true} | SÍ | SÍ |
| titular_467_completo | cuatro campos tributarios completos | {"tipo_id_tributaria":true,"numero_id_tributaria":true,"dv":true,"razon_social":true} | SÍ | SÍ |
| matriz_34_generica_activa | MANO_OBRA_PROPIA/UNICO 158405/250505 | true | SÍ | SÍ |
| matriz_49_generica_activa | DEPRECIACION_ACTIVO_COSTO/UNICO 516005/159205 | true | SÍ | SÍ |
| activo_1567_valorado_por_costo | Activo al costo de la finca y vida útil positiva | {"finca_correcta":true,"valorado_por_costo":true,"vida_util_meses":120} | SÍ | SÍ |
| activo_1573_valorado_por_costo | Activo al costo de la finca y vida útil positiva | {"finca_correcta":true,"valorado_por_costo":true,"vida_util_meses":120} | SÍ | SÍ |
| finca_467_activo_para_costo | Activo activo de finca 467 | 1569 | SÍ | SÍ |

## Casos y comprobaciones API

### TC-M06-028

**028_a — APROBADO.** Se verifica PENDIENTE_CUENTA y lista de faltantes; 220 ABIERTO sin cierre. Preparación: preflight_datos. Solicitudes G44-038, G44-043, G44-087, G44-115. Observado: 028_a: HTTP 422, error CIERRE_BLOQUEADO, mensaje 1 líneas no tienen cuentas en la matriz contable: Mano de obra propia (único) de Caprino Qa Aislado. Asígnelas en Configuración contable.; linea pendiente true; bloqueo LINEAS_PENDIENTE_CUENTA; estado ABIERTO. Decisión: contenido y estado conformes. Evidencia: resultado.json.

**028_b — APROBADO.** Se verifica Matriz incompleta y lista de faltantes; 260 ABIERTO sin cierre. Preparación: preflight_datos. Solicitudes G44-101. Observado: 028_b: HTTP 422, error CIERRE_BLOQUEADO, mensaje La matriz contable no cubre lo que registra el cierre: Depreciación (modelo de costo) (único) de Equino Qa Aislado. Asígnelas en Configuración contable.; bloqueo MATRIZ_CONTABLE_INCOMPLETA; estado ABIERTO. Decisión: contenido y estado conformes. Evidencia: resultado.json.

**028_c — APROBADO.** Se verifica Finca 467 sin titular y lista de faltantes; 220 ABIERTO sin cierre. Preparación: preflight_datos. Solicitudes G44-038, G44-043, G44-087, G44-115. Observado: 028_c: HTTP 422, error CIERRE_BLOQUEADO, mensaje Las fincas Finca Qa Seis Operaciones tienen movimientos en este período pero ya no tienen su titular tributario. Complételo en Configuración → Fincas.; prevalidacion FINCA_SIN_TITULAR; estado ABIERTO. Decisión: contenido y estado conformes. Evidencia: resultado.json.

### TC-M06-029

**029_acceso — APROBADO.** Se verifica 403 y 220 sin cambios para Veterinario y Productor. Preparación: preflight_datos. Solicitudes G44-038, G44-043, G44-087, G44-115. Observado: 029.acceso: true,true. Decisión: contenido y estado conformes. Evidencia: resultado.json.

**029_mensaje — APROBADO.** Se verifica 403, rol explícito y cierre exclusivo del Contador. Preparación: preflight_datos. Solicitudes G44-038, G44-043, G44-087, G44-115. Observado: 029.mensaje: true,true. Decisión: contenido y estado conformes. Evidencia: resultado.json.

**029_admin — APROBADO.** Se verifica Administrador consulta estado y prevalidación con 200. Preparación: preflight_datos. Solicitudes G44-013, G44-049, G44-086, G44-094, G44-107, G44-114. Observado: 029.admin: HTTP 200/200. Decisión: contenido y estado conformes. Evidencia: resultado.json.

### TC-M06-030

**030_cerrado — RECHAZADO.** Se verifica 409 Periodo inmutable con fecha y Contador ejecutor; 7 CERRADO. Preparación: preflight_datos. Solicitudes G44-051. Observado: 030_cerrado: HTTP 404, error PERIODO_NO_ENCONTRADO, mensaje El período contable no existe.; 7 sin cambios true. Decisión: discrepancia del producto. Evidencia: resultado.json.

**030_concurrencia — RECHAZADO.** Se verifica Segundo POST: 409 con hora de inicio y ejecutor del cierre activo. Preparación: preflight_datos. Solicitudes G44-071, G44-073. Observado: 030_concurrencia: HTTP 409, error CIERRE_EN_EJECUCION, mensaje El período tiene un cierre iniciado el 2026-11-14 02:17 por nombre del ejecutor presente que espera la autorización de las exclusiones. Autorícelas para continuar ese cierre o cancélelo.; primer cierre 127; hora y usuario presentes true. Decisión: discrepancia del producto. Evidencia: resultado.json.

**030_sin_segundo — APROBADO.** Se verifica Mismo cierre activo, sin artefactos nuevos; cancelación vuelve a ABIERTO. Preparación: preflight_datos. Solicitudes G44-071, G44-073. Observado: 030.sin_segundo: cierre igual true; cancelación 200; restauración true. Decisión: contenido y estado conformes. Evidencia: resultado.json.

## Seguimiento V2

- INC-M06-G44-01: CORREGIDA.
- INC-M06-G44-02: REPRODUCIDA.
- INC-M06-G44-03: REPRODUCIDA.
- INC-M06-G44-05: CORREGIDA.
- INC-M06-G44-06: CORREGIDA.

## Incidencias de producto

### INC-M06-G44-02

Esperado: 409 Periodo inmutable con fecha y ejecutor.
Observado: 030_cerrado: HTTP 404, error PERIODO_NO_ENCONTRADO, mensaje El período contable no existe..
Evidencia: resultado.json; solicitudes G44-051; solicitudes G44-038, G44-043, G44-051, G44-056, G44-061, G44-071, G44-073, G44-078, G44-087, G44-101, G44-115.
Equipo inicial Desarrollo: Primera discrepancia comprobada en la API pública de cierre..
Severidad MEDIA (CONFIRMADA): La discrepancia afecta parcialmente el control o la explicación al usuario.
Causa raíz no determinada. Acción: Desarrollo revisa el comportamiento y QA repite en RUN autorizado.

### INC-M06-G44-03

Esperado: Segundo cierre rechazado por concurrencia con hora y usuario.
Observado: 030_concurrencia: HTTP 409, error CIERRE_EN_EJECUCION, mensaje El período tiene un cierre iniciado el 2026-11-14 02:17 por nombre del ejecutor presente que espera la autorización de las exclusiones. Autorícelas para continuar ese cierre o cancélelo.; primer cierre 127; hora y usuario presentes true; 030.sin_segundo: cierre igual true; cancelación 200; restauración true.
Evidencia: resultado.json; solicitudes G44-073; solicitudes G44-038, G44-043, G44-051, G44-056, G44-061, G44-071, G44-073, G44-078, G44-087, G44-101, G44-115.
Equipo inicial Desarrollo: Primera discrepancia comprobada en la API pública de cierre..
Severidad MEDIA (CONFIRMADA): La discrepancia afecta parcialmente el control o la explicación al usuario.
Causa raíz no determinada. Acción: Desarrollo revisa el comportamiento y QA repite en RUN autorizado.

## Observaciones

- OBS-G44-02: GET /sesiones/me/permisos: Administrador cierre_periodo·5 observado (permiso 618 informado por DBA). Decisión D2 del responsable QA, 2026-11-13: Administrador puede ejecutar el cierre; TC-M06-029 exige 403 solo para Veterinario y Productor. RF-87 CA-6 y FA-4 y la fila TC-M06-G44 de la matriz (punto 2) requieren actualización formal.
- OBS-G44-01: 029_veterinario: recibido «Acceso denegado: el cierre del período contable es competencia exclusiva del Contador. Su rol actual (Veterinario) no tiene permisos de cierre contable.»; especificado FA-4 «Acceso denegado: El proceso de cierre del periodo contable es competencia exclusiva del Contador del sistema. Su rol actual ([ROL_USUARIO]) no tiene permisos de cierre contable bajo la política RBAC del módulo M06.».
- OBS-G44-01: 029_productor: recibido «Acceso denegado: el cierre del período contable es competencia exclusiva del Contador. Su rol actual (Productor) no tiene permisos de cierre contable.»; especificado FA-4 «Acceso denegado: El proceso de cierre del periodo contable es competencia exclusiva del Contador del sistema. Su rol actual ([ROL_USUARIO]) no tiene permisos de cierre contable bajo la política RBAC del módulo M06.».
- 030_cerrado_219: HTTP 404, error PERIODO_NO_ENCONTRADO, mensaje El período contable no existe.; 219 sin cambios true
- Incidencia de V2 INC-M06-G44-01 (TC-M06-029): CORREGIDA.
- Incidencia de V2 INC-M06-G44-02 (TC-M06-030): REPRODUCIDA.
- Incidencia de V2 INC-M06-G44-03 (TC-M06-030): REPRODUCIDA.
- Incidencia de V2 INC-M06-G44-05 (TC-M06-028): CORREGIDA.
- Incidencia de V2 INC-M06-G44-06 (TC-M06-028): CORREGIDA.

## Herramientas y evidencias

Node v22.15.1; Newman 0; Cypress no aplica.
- newman/newman-G44.html
- newman/newman-G44.json

## Problemas técnicos


## Cierre, rollback y acciones

Registro OFICIAL. Cierre del RUN HTTP 200. Rollback verificado: Lecturas poscierre sin cabeceras: matriz true; costo ausente true; titular true; periodos true; líneas y artefactos true.
Desarrollo revisa las discrepancias confirmadas. QA decide la siguiente acción con evidencia del RUN autorizado.
