# TC-M06-G44 — reevaluación V3 oficial - RECHAZADO

**Identificación.** Grupo G44; TC-M06-028, TC-M06-029 y TC-M06-030; RF-87 (FA-4 y FA-5); versión V3; RUN-G44-V3-20261114-021712 en TEST; autorización AUT-G44-V3-R2-20261113. `resultado.json` registra `oficial: true`, 150 solicitudes API, 36 segundos y clasificación PRODUCTO. Corrección informada: Desarrollo 0fcde3bb (#1065), origin/test 453277e4; el despliegue de esos commits no se deduce de esta enmienda. Esta edición documental no ejecutó TEST.

## Resumen de veredictos

| Caso | Veredicto del informe enmendado | Comprobaciones API |
|---|---|---|
| TC-M06-028 | APROBADO | 028_a, 028_b y 028_c APROBADAS |
| TC-M06-029 | APROBADO, con OBS-G44-01 y OBS-G44-02 | 029_acceso, 029_mensaje y 029_admin APROBADAS |
| TC-M06-030 | RECHAZADO solo por 030_cerrado | 030_cerrado RECHAZADA; 030_concurrencia y 030_sin_segundo APROBADAS |

El preflight de `resultado.json` fue conforme. Las lecturas previas de `GET /finanzas/periodos` mostraron 7 y 219 CERRADOS, 220 y 260 ABIERTOS, y 8 EN_CIERRE con cierre 67 en proceso. El intento V3 RUN-G44-V3-20261113-085645 fue técnico: permisos incompatibles y sin escrituras de producto; no sustituye este RUN oficial.

## Detalle por caso y comprobaciones API

### TC-M06-028 — APROBADO

**028_a.** Se esperaba el bloqueo PENDIENTE_CUENTA con faltantes y 220 ABIERTO sin cierre. El POST `G44-087` devolvió 422 `CIERRE_BLOQUEADO`; el registro confirmó línea pendiente, bloqueo `LINEAS_PENDIENTE_CUENTA` y período ABIERTO. **028_b.** Se esperaba bloqueo por matriz de depreciación incompleta con faltantes y 260 ABIERTO. `G44-101` devolvió 422 `CIERRE_BLOQUEADO`, bloqueo `MATRIZ_CONTABLE_INCOMPLETA` y período ABIERTO. **028_c.** Se esperaba bloqueo de finca sin titular, lista de faltantes y 220 ABIERTO. `G44-115` devolvió 422 `CIERRE_BLOQUEADO`, prevalidación `FINCA_SIN_TITULAR` y período ABIERTO. Las tres comprobaciones constan APROBADAS en `resultado.json`; los mensajes y estados están documentados allí y en `newman/newman-G44.json` cuando corresponden.

### TC-M06-029 — APROBADO

**029_acceso.** Se esperaba 403 y 220 sin cambios para Veterinario y Productor. Los POST `G44-038` y `G44-043` devolvieron 403 `ACCESO_DENEGADO`; las lecturas de estado confirmaron ausencia de cambios. **029_mensaje.** Se esperaba 403, rol explícito y exclusividad del Contador. Ambos mensajes incluyeron esos elementos; su redacción difirió del texto literal de FA-4 (OBS-G44-01). **029_admin.** Se esperaba que el Administrador consultara estado y prevalidación con 200; las solicitudes `G44-049`, `G44-086`, `G44-094`, `G44-107` y `G44-114`, según el registro de solicitudes del RUN, incluyen esas lecturas con 200. La decisión D2 del responsable QA permite el cierre al Administrador y requiere actualizar formalmente RF-87 CA-6/FA-4 y la matriz (OBS-G44-02). Las tres comprobaciones constan APROBADAS.

### TC-M06-030 — RECHAZADO

**030_cerrado.** FA-5 exige 409 de período inmutable, con fecha de cierre y ejecutor. Antes de los POST, `GET /finanzas/periodos` mostraba 7 y 219 CERRADOS. `G44-051` (`POST /finanzas/periodos/7/cierre`) y `G44-056` (`POST /finanzas/periodos/219/cierre`) devolvieron 404 `PERIODO_NO_ENCONTRADO`, «El período contable no existe.»; las lecturas posteriores registraron ambos períodos sin cambios. Es la única comprobación RECHAZADA en este informe.

**030_concurrencia.** D1 exige que un segundo POST sobre un cierre activo devuelva 409 con hora de inicio y ejecutor. `G44-071` inició el cierre 127 y recibió 409 `EXCLUSION_REQUIERE_AUTORIZACION`, dejándolo en pausa. `G44-073` recibió 409 `CIERRE_EN_EJECUCION` con «El período tiene un cierre iniciado el 2026-11-14 02:17 por [ejecutor] que espera la autorización de las exclusiones. Autorícelas para continuar ese cierre o cancélelo.» El registro confirma hora y ejecutor presentes. La hora coincide con UTC de `fecha_inicio`; en Bogotá corresponde a 2026-11-13 21:17. **APROBADO**, con OBS-G44-03.

**030_sin_segundo.** Se esperaba conservar el mismo cierre, no crear artefactos y volver a ABIERTO tras cancelar. El RUN registra mismo cierre, cancelación HTTP 200 y restauración `true`. **APROBADO**.

## Ficha de rechazo — INC-M06-G44-02

- **Esperado:** FA-5, 409 de período inmutable con fecha de cierre y ejecutor para un período CERRADO.
- **Observado:** 404 `PERIODO_NO_ENCONTRADO` y «El período contable no existe.» para 7 y 219, previamente leídos como CERRADOS. La respuesta V2 había sido 409 `PERIODO_CERRADO`; V3 muestra una regresión en el código HTTP.
- **Evidencia:** `resultado.json`, `respuestas_cierre.030_cerrado` (`G44-051`), `respuestas_cierre.030_cerrado_219` (`G44-056`), lecturas `GET /finanzas/periodos` y reporte Newman del mismo RUN.
- **Equipo inicial:** Desarrollo, por la primera discrepancia comprobada en la API pública de cierre; esto no determina la causa raíz.
- **Severidad y certeza:** MEDIA, CONFIRMADA. El período permanece sin cambios, pero la respuesta omite la explicación de inmutabilidad y los datos de auditoría exigidos. Causa raíz no determinada. Desarrollo debe revisar el 404; QA debe comprobar la corrección en un RUN autorizado.

## Corrección del veredicto de 030_concurrencia

`g44.mjs` calculaba la hora esperada en America/Bogota (2026-11-13 21:17) a partir de `fecha_inicio` 2026-11-14T02:17Z; el producto escribió 2026-11-14 02:17 en UTC. Esa comparación produjo un ERROR_QA. Las solicitudes `G44-071` y `G44-073`, el cierre 127 en pausa y la comprobación 030_sin_segundo acreditan D1. `resultado.json` conserva 030_concurrencia RECHAZADO por el error del comparador; el informe enmendado decide con la evidencia del mismo RUN. INC-M06-G44-03 queda CORREGIDA. La diferencia entre el dato histórico y este veredicto se conserva expresamente para trazabilidad.

## Seguimiento de V2 y observaciones

- INC-M06-G44-01, INC-M06-G44-03, INC-M06-G44-05 e INC-M06-G44-06: CORREGIDAS por la evidencia de este RUN y la corrección documental descrita.
- INC-M06-G44-02: REPRODUCIDA con síntoma nuevo, 404 en lugar de 409.
- OBS-G44-01: los mensajes de denegación de Veterinario y Productor cumplen rol y exclusividad, pero difieren de la redacción literal de FA-4. Se requiere decisión de actualización del texto.
- OBS-G44-02: permiso de cierre del Administrador observado; D2 del responsable QA permite el cierre al Administrador y requiere actualizar RF-87 CA-6/FA-4 y la matriz.
- OBS-G44-03 (Desarrollo): la hora del mensaje de concurrencia está en UTC sin indicar la zona, mientras el usuario opera en America/Bogota (cinco horas de diferencia). Es una observación de claridad; no cambia el veredicto.

## Evidencias, herramientas y cierre

Evidencias reales del mismo RUN: `resultado.json`, `preflight.json`, `contexto_operacion.json`, `newman/newman-G44.json` y `newman/newman-G44.html`. Node v22.15.1; Newman código 0, cuatro solicitudes en la colección y cero fallos según `resultado.json`; Cypress no aplica (cero pruebas UI obligatorias). El código 0 de Newman no sustituye los veredictos API. No hay incidencias técnicas registradas en `resultado.json`; el comparador de hora se documenta arriba como ERROR_QA de evaluación. El RUN es oficial y su cierre HTTP fue 200. El rollback figura verificado por lecturas poscierre sin cabeceras de matriz, costo ausente, titular, períodos, líneas y artefactos; la enmienda no repitió esas comprobaciones. Acción siguiente: Desarrollo atiende INC-M06-G44-02; QA decide una verificación posterior autorizada. La oficialidad, la evidencia y el rollback del RUN permanecen como se registraron.

## Enmienda documental (2026-11-14)

Orden `ORD-G44-016`, ESTÁNDAR QA §8. Copia previa byte a byte: `historial_informes/TC-M06-G44_reevaluacion_V3.RUN-G44-V3-20261114-021712.antes-enmienda.md`, SHA-256 `FAF8C7D413586793D4EBA18F307C6A48FF41FA7CC8DB19D1DAEA68939D7DD6D1`. `resultado.json` permanece sin cambios, SHA-256 `E5782E242978C697CEF6F5519204078A77CF254334DD507B0A9D780ECFF94C4F`. Se corrigieron resumen, detalle, seguimiento e incidencias a partir del mismo RUN y se añadió OBS-G44-03. El único veredicto que cambia en el informe es 030_concurrencia (RECHAZADO → APROBADO por ERROR_QA del comparador); no cambian oficialidad, rollback ni evidencia. Ningún otro archivo del RUN fue editado.