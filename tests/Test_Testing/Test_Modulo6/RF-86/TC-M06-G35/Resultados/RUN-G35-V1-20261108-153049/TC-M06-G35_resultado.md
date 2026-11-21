# TC-M06-G35 — APROBADO

## Identificación

Grupo G35; caso TC-M06-008; RF-86 FA-2 y precondiciones 1 y 7, RF-45; versión 1, intento 3; RUN RUN-G35-V1-20261108-153049; ambiente TEST; autorización AUT-G35-V1-R3-20261108; commit TEST no verificado; Node v22.15.1; Newman 6.2.2; solo API.

## Decisión del caso

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-008 | APROBADO | baja: APROBADO, Se cumplen estado, vínculo, rechazo específico y ausencias. baja_rechazo: APROBADO, Se cumplen estado, vínculo, rechazo específico y ausencias. inexistente: APROBADO, Se cumplen estado, vínculo, rechazo específico y ausencias. |

Oficial: true.

## Detalle por caso

### baja — Baja RF-45 y efecto contable

- **Preparación:** Activo 943, período 8 y evento de baja RF-45 1283.
- **Esperado:** Activo BAJA; evento RF-45 y línea BAJA_ACTIVO ligada; sin variación posterior.
- **Observado:** HTTP 201. Estado del activo ACTIVO → BAJA. Eventos nuevos: 1283; variaciones: ninguno; líneas: 889; mediciones: ninguno.
- **Qué se cumplió:** Estado BAJA: sí; evento RF-45 nuevo: sí; línea BAJA_ACTIVO vinculada: 889; valor en libros esperado: 3015990; valor de línea observado: 3015990.00; ausencia de variación posterior: sí.
- **Qué falló y por qué:** Ningún incumplimiento comprobado en este subcaso.
- **Decisión:** APROBADO. Se cumplen estado, vínculo, rechazo específico y ausencias.

### baja_rechazo — Crecimiento sobre activo en BAJA

- **Preparación:** Activo 943, período 8 y evento de baja RF-45 1283.
- **Esperado:** 4xx específico por BAJA; sin evento, variación, línea ni medición.
- **Observado:** HTTP 409, código ESTADO_NO_PERMITE_EVENTOS, mensaje saneado «El activo no se encuentra en estado ACTIVO. Estado actual: BAJA. Los eventos de crecimiento solo se pueden registrar sobre activos en estado ACTIVO.». Estado del activo BAJA → BAJA. Eventos nuevos: ninguno; variaciones: ninguno; líneas: ninguno; mediciones: ninguno.
- **Qué se cumplió:** Rechazo 4xx: sí; ausencia de evento, variación, línea y medición nuevos: sí. La causa específica se decide con el código y mensaje observados.
- **Qué falló y por qué:** Ningún incumplimiento comprobado en este subcaso.
- **Decisión:** APROBADO. Se cumplen estado, vínculo, rechazo específico y ausencias.

### inexistente — Crecimiento sobre activo inexistente

- **Preparación:** ID inexistente 100951, contrastado por GET previo; activo de control 943 y período 8.
- **Esperado:** 404 o 4xx equivalente por inexistencia; sin datos nuevos.
- **Observado:** HTTP 404, código ACTIVO_NO_ENCONTRADO, mensaje saneado «El activo biológico con id 100951 no existe.». Estado del activo BAJA → BAJA. Eventos nuevos: ninguno; variaciones: ninguno; líneas: ninguno; mediciones: ninguno. Datos financieros creados para el ID inexistente: 0.
- **Qué se cumplió:** Rechazo 4xx: sí; ausencia de evento, variación, línea y medición nuevos: sí. La causa específica se decide con el código y mensaje observados.
- **Qué falló y por qué:** Ningún incumplimiento comprobado en este subcaso.
- **Decisión:** APROBADO. Se cumplen estado, vínculo, rechazo específico y ausencias.

## Comprobaciones API

- G35-API-008-01 (TC-M06-008): APROBADO; Se cumplen estado, vínculo, rechazo específico y ausencias.; evidencia resultado.json.
- G35-API-008-02 (TC-M06-008): APROBADO; Se cumplen estado, vínculo, rechazo específico y ausencias.; evidencia resultado.json.
- G35-API-008-03 (TC-M06-008): APROBADO; Se cumplen estado, vínculo, rechazo específico y ausencias.; evidencia resultado.json.

## Evidencias reales

- preflight.json
- resultado.json
- TC-M06-G35_resultado.md
- newman/newman-G35.json
- newman/newman-G35.html

## Incidencias de producto

Ninguna discrepancia de producto comprobada.

## Problemas técnicos

Ninguno observado.

Las lecturas de código local no demuestran causa raíz de producto.

## Cierre y rollback

DELETE HTTP 200; rollback verificado. Activo ACTIVO restaurado a ACTIVO; evento RF-45, línea BAJA_ACTIVO y datos nuevos del RUN ausentes en las lecturas públicas poscierre. RF-52 puede dejar archivo de bitácora o logs fuera de la base; este efecto no queda cubierto por el DELETE ni por las lecturas poscierre.

## Conclusión y acciones

APROBADO: baja: APROBADO, Se cumplen estado, vínculo, rechazo específico y ausencias. baja_rechazo: APROBADO, Se cumplen estado, vínculo, rechazo específico y ausencias. inexistente: APROBADO, Se cumplen estado, vínculo, rechazo específico y ausencias. Las tres reglas comprobadas cumplen; conservar la evidencia del RUN y cerrar el caso. Solicitudes registradas: 59/80.
