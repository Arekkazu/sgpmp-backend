# TC-M03-G96 — APROBADO

## 1. Identificación

Grupo G96; caso TC-M03-187; RF-58/CU04 con catálogo vigente RF-60; versión V1; RUN RUN-G96-V1-20261031-153625; ambiente TEST; autorización AUT-G96-V1-R4-20261031; referencia backend origin/test 5b46ca00a0ba92774f8e3d4b9eeaeec169344f17 (despliegue no verificado). Node v22.15.1; Newman 6.2.2; Postman/Cypress no ejecutados. Contrato solo API.

## 2. Resumen ejecutivo y decisión del grupo

**APROBADO**. Catálogo y cinco coberturas acreditadas. Oficial: SÍ. Newman: una ejecución con reporte; 3 páginas registradas.

## 3. Detalle por caso y comprobaciones API/UI

### TC-M03-187

**Objetivo:** comprobar el catálogo cerrado de conectividad y la correspondencia de cada estado del dispositivo con sus sensores visibles al Productor.

**Precondiciones:** Productor y Administrador acreditados; dispositivos con sensores asociados y área visible al rol consultado. La ausencia de datos deja esa cobertura NO_CONCLUYENTE sin escrituras. El 2026-10-31, la IA de BD creó con autorización del responsable QA dos semillas persistentes fuera del RUN: SIN_SEÑAL en área 701, finca 184, dispositivo 787 y sensor 1208 (caché SIN_SEÑAL, semáforo GRIS, dato desactualizado); EN_MANTENIMIENTO en dispositivo 788 y sensor 1209 (caché EN_MANTENIMIENTO, semáforo VERDE, dato no desactualizado). Fueron necesarias porque en TEST no había dispositivos SIN_SEÑAL y los tres EN_MANTENIMIENTO existentes no permitían cobertura segura: uno carecía de sensores y los de áreas 664 y 665 tenían sensores DESCONOCIDO, GRIS y no desactualizados, excluidos por riesgo E7. Las semillas fijaron el estado del dispositivo; la propagación al dashboard correspondió al producto mediante RFC-020.

**Pasos:** iniciar sesión con ambos roles; listar dispositivos por cada estado como Administrador y el alcance completo como Productor; recorrer los candidatos, priorizar áreas del Productor y aceptar solo dispositivos cuyos sensores propios aparecen en canarios; excluir áreas cuyo canario muestre GRIS no desactualizado o sin umbral; si falta un estado, probar áreas como Administrador; consultar hasta ocho áreas aptas y sus páginas con Newman; cotejar id_dispositivo_iot y estado_conectividad de todos los dispositivos de las áreas consultadas.

**Entradas:** GET /iot/dispositivos?estado=<E> (Administrador) para los cinco estados; GET /iot/dispositivos (Productor) para identificar sus dispositivos; GET /iot/monitoreo/dashboard?id_infraestructura=<ID>&pagina=<N>&por_pagina=1 (canario) y por_pagina=50 (Newman) con el rol indicado por área.

**Esperado:** El dashboard presenta los cinco estados de conectividad de RF-60, fase 7 y postcondición 3: ACTIVO, SIN_SEÑAL, BUFFER_ACTIVO, INACTIVO y EN_MANTENIMIENTO. Todo valor fuera del catálogo, incluidos ONLINE, OFFLINE, null y ausente, rechaza el catálogo. DESCONOCIDO se registra como observación de requisito pendiente sin rechazo por sí solo. Cada dispositivo con sensores visibles conserva su estado en el dashboard.

**Observado:** valores por área en tabla posterior; 10 sensor(es) DESCONOCIDO en 3 área(s) (347, 664, 665), contando páginas Newman y canarios de áreas sin página Newman, observación de requisito pendiente. Las semillas 787 (SIN_SEÑAL) y 788 (EN_MANTENIMIENTO), ambas en área 701, aparecieron con un sensor propio concordante cada una en el dashboard. Catálogo y cinco coberturas acreditadas.

**Decisión del caso:** **APROBADO**. Catálogo y cinco coberturas acreditadas

| Comprobación | Fuente | Tipo | Estado | Motivo | Evidencia |
|---|---|---|---|---|---|
| API-187-01 | API | ASSERT | APROBADO | Todos los estados observados pertenecen al catálogo; DESCONOCIDO se informa aparte | newman/newman-G96.json |
| API-187-02 | API | ASSERT | APROBADO | ACTIVO: APROBADO; SIN_SEÑAL: APROBADO; BUFFER_ACTIVO: APROBADO; INACTIVO: APROBADO; EN_MANTENIMIENTO: APROBADO | newman/newman-G96.json |

**Cobertura por estado**

| Estado RF-60 | Candidatos | Área | Dispositivo | Rol dashboard | Sensores cotejados | Estado | Motivo |
|---|---:|---:|---:|---|---:|---|---|
| ACTIVO | 1 | 347 | 341 | Administrador | 1 | APROBADO | Dispositivo 341 y 1 sensor(es) concordantes |
| SIN_SEÑAL | 1 | 701 | 787 | Productor | 1 | APROBADO | Dispositivo 787 y 1 sensor(es) concordantes |
| BUFFER_ACTIVO | 1 | 1 | 3 | Productor | 1 | APROBADO | Dispositivo 3 y 1 sensor(es) concordantes |
| INACTIVO | 1 | 1 | 1 | Productor | 3 | APROBADO | Dispositivo 1 y 3 sensor(es) concordantes |
| EN_MANTENIMIENTO | 1 | 701 | 788 | Productor | 1 | APROBADO | Dispositivo 788 y 1 sensor(es) concordantes |

**Dispositivos cotejados**

| Estado RF-60 | Dispositivo | Área | Rol dashboard | Sensores cotejados |
|---|---:|---:|---|---:|
| ACTIVO | 341 | 347 | Administrador | 1 |
| SIN_SEÑAL | 787 | 701 | Productor | 1 |
| BUFFER_ACTIVO | 3 | 1 | Productor | 1 |
| INACTIVO | 1 | 1 | Productor | 3 |
| EN_MANTENIMIENTO | 788 | 701 | Productor | 1 |

**Áreas descartadas**

| Área | Rol | Dispositivo | Estado | Motivo |
|---:|---|---:|---|---|
| 389 | Productor | 353 | ACTIVO | Sin sensores propios en el área |
| 390 | Productor | 354 | INACTIVO | Sin sensores propios en el área |
| 6 | Administrador | 114 | ACTIVO | Sin sensores propios en el área |
| 664 | Administrador | — | — | E7: GRIS no desactualizado o sin umbral |
| 6 | Administrador | 348 | ACTIVO | Sin sensores propios en el área |
| 479 | Administrador | 482 | EN_MANTENIMIENTO | Sin sensores propios en el área |
| 665 | Administrador | — | — | E7: GRIS no desactualizado o sin umbral |

**Valores observados**

| Área | Estado exacto | Sensores |
|---|---|---:|
| 701 | SIN_SEÑAL | 1 |
| 701 | EN_MANTENIMIENTO | 1 |
| 1 | INACTIVO | 3 |
| 1 | BUFFER_ACTIVO | 1 |
| 347 | DESCONOCIDO | 8 |
| 347 | ACTIVO | 1 |
| 347 | INACTIVO | 3 |
| 347 | BUFFER_ACTIVO | 1 |

## 4. Incidencias y observaciones

Ninguna incidencia funcional confirmada. El RUN acreditó en la respuesta pública del dashboard los cinco estados, incluidos BUFFER_ACTIVO y EN_MANTENIMIENTO; la divergencia señalada durante la lectura del código local quedó superada por RFC-020.

Decisión del líder de análisis (2026-10-31): RF-60 rige con cinco estados; los tres de RF-58 son inconsistencia documental; ONLINE/OFFLINE solo RF-54. DESCONOCIDO sigue en revisión, sin correspondencia definida.

RFC-020: el RUN acreditó por API pública BUFFER_ACTIVO y EN_MANTENIMIENTO en el dashboard; la IA de BD confirmó la función desplegada y la revisión Alembic c31f8a6d920e. La evidencia funcional es la respuesta pública del RUN; la versión exacta del backend referida en la identificación no quedó verificada.

**Observaciones para Análisis, sin efecto en el veredicto:**

- Se observaron 10 sensores con estado_conectividad DESCONOCIDO en las áreas 347, 664 y 665. Ese estado no está definido en la ficha y sigue en revisión. Los sensores de 664 y 665 aparecen GRIS y no desactualizados, condición de aviso E7.
- En EN_MANTENIMIENTO, el sensor 1209 aparece VERDE con un dato de hace siete días. RFC-020 no cambia el semáforo ni la marca de desactualización en ese estado; revisar si RF-60 fase 7 exige otro color.
- En el intento 2 (RUN técnico 150253) se consultó completa el área 664, cuyos sensores estaban GRIS y no desactualizados. Pudo generarse un aviso E7 a Administradores de cuentas ficticias; el envío no quedó acreditado.

**Historial de intentos técnicos V1:** intento 1, [extracto saneado](api/antecedentes/intento-1.json): NO_CONCLUYENTE, faltaba SIN_SEÑAL y varios estados no tenían sensores visibles al Productor. Intento 2, [extracto saneado](api/antecedentes/intento-2.json): NO_CONCLUYENTE, cuatro estados cubiertos y EN_MANTENIMIENTO sin sensor propio visible; incluyó la consulta completa del área 664. Intento 3, [extracto saneado](api/antecedentes/intento-3.json): NO_CONCLUYENTE, EN_MANTENIMIENTO siguió sin sensor propio visible en las páginas inspeccionadas o se agotó el presupuesto de canarios; 664 y 665 se excluyeron por E7. El intento 4, presente RUN 153625, acredita los cinco estados. [Indice de origen y SHA-256](api/antecedentes/indice.json). Los RUN de origen fueron eliminados de los enlaces vigentes; la eliminacion fisica de sus carpetas corresponde al orquestador y sigue pendiente.

**Problemas técnicos QA:** Ninguno.

## 5. Análisis de fallos

Primera discrepancia y certeza: sin incumplimiento funcional concluyente. Código consultado en esta preparación: src/telemetry/infrastructure/schema/monitoreo_schema.py, src/telemetry/infrastructure/repositories/monitoreo_repository.py y alembic/versions/8a8f1dae36f1_rfc020_conectividad_dashboard_estado_dispositivo.py. La respuesta pública acredita el comportamiento de RFC-020 y la IA de BD confirmó su función desplegada; no se identificó causa de fallo funcional.

## 6. Conclusiones y acciones

APROBADO: Catálogo y cinco coberturas acreditadas. Conservar evidencia y cerrar el caso.

## 7. Herramientas, evidencias, bitácora y rollback

Newman: 3 páginas, límite 12; listados: TODOS_PRODUCTOR (Productor) HTTP 200, eco true, 187 dispositivo(s); ACTIVO (Administrador) HTTP 200, eco true, 4 dispositivo(s); SIN_SEÑAL (Administrador) HTTP 200, eco true, 1 dispositivo(s); BUFFER_ACTIVO (Administrador) HTTP 200, eco true, 21 dispositivo(s); INACTIVO (Administrador) HTTP 200, eco true, 33 dispositivo(s); EN_MANTENIMIENTO (Administrador) HTTP 200, eco true, 4 dispositivo(s); canarios 20/20: área 389 (Productor) total 0; área 701 (Productor) total 2; área 701 (Productor) total 2; área 1 (Productor) total 4; área 1 (Productor) total 4; área 1 (Productor) total 4; área 1 (Productor) total 4; área 390 (Productor) total 0; área 6 (Administrador) total 0; área 664 (Administrador) total 2; área 479 (Administrador) total 0; área 347 (Administrador) total 13; área 347 (Administrador) total 13; área 347 (Administrador) total 13; área 347 (Administrador) total 13; área 347 (Administrador) total 13; área 347 (Administrador) total 13; área 347 (Administrador) total 13; área 347 (Administrador) total 13; área 665 (Administrador) total 1; áreas aptas 701 (Productor), 1 (Productor), 347 (Administrador). Máximo 38 GET en RUN y 1500 segundos. Evidencias reales: preflight.json, newman/newman-G96.json, newman/newman-G96.html, resultado.json, TC-M03-G96_resultado.md. Cierre DELETE RUN HTTP 200. Rollback: SIN_ESCRITURAS_QUE_REVERTIR: 29 GET con eco y DELETE 200; efectos externos de login/E7 no verificados. Login previo puede registrar auditoría y las lecturas pueden activar correo E7; su reversión no se acredita.
