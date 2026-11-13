# TC-M06-G45 — reevaluación V2 oficial - APROBADO

G45 · TC-M06-031, TC-M06-032 y TC-M06-033 · RF-87 v1.1 · V2 · RUN-G45-V2-20261113-122125 · TEST. Autorización: AUT-G45-V2-R7-20261113. Commit de referencia informado: 453277e4, sin nueva verificación en esta enmienda. Esta corrección es exclusivamente documental.

## Resumen de veredictos

| Caso | Veredicto | Fundamento |
| --- | --- | --- |
| TC-M06-031 | APROBADO | Pausa, rechazo de costo, cola M02 y ambos destinos de procesamiento acreditados. |
| TC-M06-032 | APROBADO con OBS-G45-01 | D2-V2 acepta el rechazo 422 y el período intacto; CA-3 pide 409. |
| TC-M06-033 | APROBADO | Ajuste en período abierto con referencia, justificación y auditoría; cerrado intacto. |

La decisión D2-V2 del responsable QA, fechada el 2026-11-13 y consignada en [contexto_operacion.json](contexto_operacion.json), mantiene el oráculo CA-3 de 409 y acepta el rechazo 422 con observación. Los tres veredictos y la oficialidad son los de [resultado.json](resultado.json).

## Preparación y preflight

[preflight.json](preflight.json) registra autorización válida y ninguna barrera. [resultado.json](resultado.json) acredita permisos de cierre, costos, reconocimiento, valoración, auditoría y administración de activos biológicos. Antes de las acciones, los períodos 7 y 219 estaban CERRADOS; el 8 estaba EN_CIERRE con cierre 67; el 260 y el 266 estaban ABIERTOS. La línea 2625 en el 219 estaba REGISTRADA y VERIFICADO; el 260 no tenía ajustes previos. Los activos 944 y 949 tenían el reconocimiento requerido.

La configuración de especies respondió HTTP 200. El candidato 220 no aportó causa de pausa: no tenía activos sin precio y la especie 422 sí tenía precio vigente. El período 266 cumplió la condición necesaria: contenía la fecha de prueba, no tenía líneas sin trazabilidad y el activo 1644, POBLACIONAL de cantidad 1, carecía de precio. Su prevalidación indicó un activo sin precio. La ficha del 1644 no expuso fase activa en la lectura registrada, aunque el crecimiento M02 de este RUN se creó correctamente. Los hallazgos no bloqueantes se conservan en la evidencia original.

## Detalle por caso

### TC-M06-031 — APROBADO

**Qué se verifica según la matriz.** Durante la pausa de un cierre, el costo no debe modificar el período y el evento M02 debe quedar encolado con su fecha original. Tras cancelar, el evento B se procesa en el período actual; tras autorizar, el evento A se procesa en el siguiente, sin afectar el cerrado.

**Preparación.** Se eligió el período 266 ABIERTO y el activo 1644 sin precio, causa de la pausa. Los crecimientos 1949 (B) y 1950 (A) fueron registrados por el rol Administrador QA. Se capturaron bases de períodos, costos, eventos y auditoría.

**Qué se hizo.** G45-044 intentó cerrar sin autorización y G45-048 verificó la pausa. G45-049 intentó registrar un costo durante EN_CIERRE; G45-054 comprobó la ausencia de cambios. G45-055 creó B; G45-056 consultó su historial, G45-057 intentó procesarlo durante la pausa y G45-066 verificó su estado. G45-067 canceló; G45-072 procesó B y G45-077 comprobó el resultado. G45-078 provocó la segunda pausa, G45-083 creó A y G45-085 comprobó su procesamiento en espera. G45-091 autorizó el cierre excluyendo al 1644; G45-096 procesó A y G45-105 verificó el período siguiente.

**Qué se esperaba.** El cierre sin autorización debía dar 409 EXCLUSION_REQUIERE_AUTORIZACION y dejar el 266 EN_CIERRE, con cierre EN_PROCESO en paso 3. El costo debía recibir cualquier 4xx sin cambiar líneas, costos ni variaciones. Ambos eventos debían mostrar ENCOLADO_CIERRE durante la pausa y conservar su fecha original. B debía quedar en el 266 ABIERTO tras cancelar; A, en un período siguiente nuevo tras autorizar, con el 1644 excluido del 266 cerrado.

**Qué se observó.** El primer cierre devolvió 409 EXCLUSION_REQUIERE_AUTORIZACION y dejó el 266 EN_CIERRE, cierre 124 EN_PROCESO en paso 3. El costo devolvió 422 sin cambios en líneas, costos ni variaciones. B se creó con HTTP 201 como evento 1949; durante la pausa se vio ENCOLADO_CIERRE sin medición propia. La cancelación dio 200 y dejó el 266 ABIERTO; el procesamiento posterior registró MEDICION_SIN_VARIACION del 1949 en el 266. La segunda pausa devolvió 409; A se creó con 201 como evento 1950, también encolado. El cierre autorizado dio 200, excluyó al 1644 y creó el período siguiente 547. El procesamiento de A registró MEDICION_SIN_VARIACION del 1950 en el 547, sin efecto en el 266 cerrado. El historial M02 permitió cotejar las fechas originales: 1949, 2026-11-13 12:21:36.808 UTC; 1950, 2026-11-13 12:21:41.924 UTC.

**Por qué se decide.** Estado, integridad, cola, auditoría y destino satisfacen las dos ramas. MEDICION_SIN_VARIACION acredita el procesamiento sin atribuir una variación contable inexistente.

**Decisión.** APROBADO. Comprobaciones G45-048, G45-054, G45-066, G45-077 y G45-105 en [resultado.json](resultado.json).

### TC-M06-032 — APROBADO con OBS-G45-01

**Qué se verifica según la matriz.** Un costo fechado en un período cerrado debe rechazarse (CA-3 exige 409) y dejarlo íntegro. La reversión de un reconocimiento con dependencias debe dar 409 REVERSION_BLOQUEADA. Los períodos 7 y 219 deben conservar estado, fecha, líneas, comprobantes y variaciones.

**Preparación.** El período 7 estaba CERRADO, el activo 949 tenía reconocimiento confirmado en él y el 219 estaba CERRADO. Se capturaron bases de integridad.

**Qué se hizo.** G45-106 envió el costo con fecha del período cerrado y G45-110 concluyó la comparación del 7. G45-111 intentó revertir el reconocimiento; G45-115 volvió a comprobar el 7. G45-123 cerró la comprobación de integridad de 7 y 219.

**Qué se esperaba.** Rechazo del costo con 409 según CA-3 y período 7 idéntico; reversión bloqueada con 409 REVERSION_BLOQUEADA; ambos cerrados íntegros.

**Qué se observó.** El costo respondió 422 PERIODO_CONTABLE_CERRADO: «La fecha del costo pertenece a un período cerrado. Regístrelo como ajuste en el período abierto.» El 7 permaneció íntegro. La reversión dio 409 REVERSION_BLOQUEADA. Los períodos 7 y 219 conservaron estado, fecha, líneas, comprobantes y variaciones.

**Por qué se decide.** El rechazo y la integridad están acreditados. El 422 sigue difiriendo del 409 de CA-3; D2-V2 acepta el rechazo observado con OBS-G45-01 para Desarrollo, sin cambiar el criterio.

**Decisión.** APROBADO con OBS-G45-01. Comprobaciones G45-110, G45-115 y G45-123 en [resultado.json](resultado.json).

### TC-M06-033 — APROBADO

**Qué se verifica según la matriz.** Un error de período cerrado se corrige mediante AJUSTE_PERIODO_ANTERIOR en el período abierto, con referencia a la línea original, justificación y auditoría, sin alterar el cerrado.

**Preparación.** La línea 2625 estaba REGISTRADA y VERIFICADO en el 219 CERRADO. El 260 estaba ABIERTO y sin ajustes previos.

**Qué se hizo.** G45-124 solicitó el ajuste de la 2625; G45-126 consultó la auditoría y G45-130 comprobó el 219.

**Qué se esperaba.** HTTP 201, ajuste en el 260 referido a la 2625, justificación auditada y 219 intacto.

**Qué se observó.** La API devolvió 201 y creó la línea 6364 en el 260 con referencia a la 2625. La auditoría registró LINEA_ASIENTO_REGISTRADA, la marca de ajuste de período anterior y la justificación «Ajuste QA autorizado por error del período anterior». El 219 conservó estado, fecha, líneas, comprobantes y variaciones.

**Por qué se decide.** La línea, la referencia y la auditoría acreditan la corrección en el abierto; la comparación acredita la integridad del cerrado.

**Decisión.** APROBADO. Comprobaciones G45-126 y G45-130 en [resultado.json](resultado.json).

Las comprobaciones exigidas y ejecutadas fueron API. [resultado.json](resultado.json) registra cero pruebas Cypress; este grupo no tenía UI obligatoria.

## Seguimiento, observaciones e incidencias

| Referencia V1 | Estado tras V2 | Fundamento |
| --- | --- | --- |
| INC-M06-G45-01 | CORREGIDA | El 031 dejó el período EN_CIERRE durante la pausa y ABIERTO tras cancelar. |
| INC-M06-G45-02 | CERRADA por D2-V2 | El responsable QA aceptó el rechazo 422 y el período intacto; queda OBS-G45-01 para Desarrollo. |
| INC-M06-G45-03 | CORREGIDA | El 033 acreditó ajuste público con referencia, justificación y auditoría. |

El campo histórico seguimiento_v1 de resultado.json conserva «CORREGIDA» para INC-M06-G45-02 porque la orden prohíbe modificar ese archivo. El estado documental enmendado es «CERRADA por D2-V2 con OBS-G45-01»; los veredictos de casos permanecen idénticos.

OBS-G45-01: CA-3 exige HTTP 409 para un costo fechado en período cerrado; el producto respondió HTTP 422 PERIODO_CONTABLE_CERRADO. La primera atención corresponde a Desarrollo por la discrepancia de la respuesta pública observada en TEST. Es una observación confirmada por G45-106, no una causa raíz demostrada ni una incidencia activa de producto en este RUN. Impacto parcial con integridad conservada: severidad orientativa MEDIA, certeza CONFIRMADA sobre el código observado. Desarrollo debe revisar el contrato y el responsable QA determinar el seguimiento.

En 032 no estaban disponibles rutas públicas de modificación y eliminación histórica de costos y variaciones. Se comprobaron las escrituras públicas pertinentes y la integridad; no se afirma cobertura de rutas no públicas. [resultado.json](resultado.json) no registra incidencias activas ni problemas técnicos en este RUN. La causa raíz de OBS-G45-01 no está determinada.

## Precondiciones temporales fuera del RUN

Por disposición del responsable QA, fuera de este RUN se prepararon dos conjuntos de datos temporales: (1) usuarios_fincas 3493, que relaciona al rol Contador QA con la finca 472; (2) por inserción, la configuración de la especie 544 y del lote 1644: etapa 73 «Engorde Qa Caprino», ciclo productivo 22, enlace 36, métrica 169 (PESO, kg, rango 0,01–2000) y fase activa 995 del lote. La orden registra COMMIT del segundo conjunto el 2026-11-13 a las 12:09:15 UTC. Ambas precondiciones se revierten al cerrar G45, según la orden del responsable QA; esta enmienda no acredita ni ejecuta esa reversión. Los precios de la especie 422 no se cambiaron: son inmutables por el trigger tgr_m06_07_inmutabilidad_precios.

## Intentos técnicos previos de V2

| RUN técnico | Resumen |
| --- | --- |
| 102831 | Incompatibilidad del contrato categoria_precio; sin veredicto oficial. |
| 112624 | Contexto de reintento conservado; sin resultado.json. |
| 112815 | Validador encontró precios_congelados nulo; sin veredicto oficial. |
| 113511 | Validador de listas de precios_congelados; sin veredicto oficial. |
| 113954 | 031 sin período pausable; 032 y 033 tuvieron comprobaciones propias. Sin veredicto oficial del grupo. |
| 115410 | El crecimiento del 1644 respondió 422; 032 y 033 tuvieron comprobaciones propias. Sin veredicto oficial del grupo. |

Los intentos se describen según sus resultados técnicos y el contexto actual. Ninguno es evidencia del veredicto oficial 122125.

## Evidencias, herramientas y alcance

Solicitudes, respuestas saneadas, comparaciones, historial M02 y auditorías: [resultado.json](resultado.json). Autorización y alcance: [preflight.json](preflight.json) y [contexto_operacion.json](contexto_operacion.json). Reportes realmente generados: [Newman JSON](newman/newman-G45.json) y [Newman HTML](newman/newman-G45.html). El RUN registró Node v22.15.1, Newman código 0 con cinco solicitudes y cero fallos; el flujo completo registró 166 solicitudes API. Cypress no aplicó. Los códigos de salida son datos de ejecución; los veredictos se apoyan en las comprobaciones por caso.

## Cierre, efectos persistentes y rollback

| Ámbito | Registro | Alcance |
| --- | --- | --- |
| Cierre del RUN | DELETE respondió HTTP 200. | Consta en resultado.json. |
| Rollback del RUN | Verificado: bases de períodos 7, 8, 219, 220, 260 y 266; período nuevo ausente; costos, crecimientos, reconocimiento y ajustes sin efectos residuales. | Comparaciones posteriores en resultado.json; esta enmienda no las repite. |
| Precondiciones externas | usuarios_fincas 3493 y configuración de especie 544/lote 1644. | La orden dispone su reversión al cerrar G45; queda fuera del rollback verificado del RUN. |

El RUN permanece OFICIAL. Los tres casos quedan APROBADOS, con OBS-G45-01 para que Desarrollo revise la diferencia HTTP y el responsable QA decida el seguimiento. No hubo nueva consulta a TEST.

## Enmienda documental (2026-11-13)

ORD-G45-021 ordenó corregir únicamente este Markdown. La [copia previa byte a byte](../../../historial_informes/TC-M06-G45_reevaluacion_V2.RUN-G45-V2-20261113-122125.antes-enmienda.md) tiene SHA-256 **7E001F0458C2712049CCDAC86549155B647D6CDD5473A448B0FA945965D2C588**. [resultado.json](resultado.json) conserva SHA-256 **771AA934C416A82B26BF6113525BFB940D98583FF25FFBAFEA926090EF4FF29D**.

Se restituyó la autorización; se corrigieron las precondiciones externas y el estado de INC-M06-G45-02; se sustituyeron JSON crudos por prosa y tablas; se añadió el detalle por caso, los intentos previos y la separación entre rollback del RUN y precondiciones externas. No cambian veredictos, oficialidad, rollback ni evidencia.
