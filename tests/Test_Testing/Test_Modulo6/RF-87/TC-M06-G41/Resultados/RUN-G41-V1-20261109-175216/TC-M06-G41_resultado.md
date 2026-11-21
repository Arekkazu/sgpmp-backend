# TC-M06-G41 → RUN oficial: 019 RECHAZADO solo por notificación; 020 APROBADO

## Identificación

Grupo G41; casos TC-M06-019 y TC-M06-020; RF-87 v1.1; V1; RUN RUN-G41-V1-20261109-175216; TEST. Autorización AUT-G41-V1-R4-20261109; intento 4; commit no consultado. Herramientas verificadas en el RUN: Node v22.15.1 y Newman 6.2.2. Registro QA emulado: OFICIAL; rollback CONFIRMADO. La corrección documental no incluye nuevo acceso a TEST.

## Veredictos

| Caso | Veredicto | Motivo |
| --- | --- | --- |
| TC-M06-019 | RECHAZADO | notificacion |
| TC-M06-020 | APROBADO | Valor inicial y descomposición de ambos cierres conformes |

Severidad global: MEDIA. El rechazo de 019 corresponde únicamente al aviso obligatorio ausente.

## TC-M06-019: esperado y observado

| Criterio | Esperado | Observado en el RUN | Cumple |
| --- | --- | --- | --- |
| (a) Transición y auditoría | ABIERTO → EN_CIERRE → CERRADO; eventos de inicio y fin referidos al cierre. | POST cierre del período 220 HTTP 200; cierre 22; noviembre CERRADO a las 2026-11-09T17:52:19Z. CIERRE_PERIODO_INICIADO y CIERRE_PERIODO_COMPLETADO con id_referencia 22. | Sí |
| (b) Activos | Revaluar ACTIVO 1569 y EN_TRATAMIENTO 1570; no revaluar BAJA 1571; 1572 y 1573 por costo. | Solo 1569 y 1570 tienen medición CIERRE_PERIODO: cada una anterior 3760000.0000, actual 4700000.0000, total 940000.0000, TB 0.0000 y PM 940000.0000. 1571 sin medición del cierre. Procesados 4 (1569, 1570, 1572, 1573); excluidos []; sin activos ajenos. Depreciación por costo 205000.00. | Sí |
| (c) Período siguiente | Abrir automáticamente diciembre. | Período 242 (2026-12) ABIERTO. | Sí |
| (d) Reportes | RF-92 y RF-93 con resultado neto. | RF-93 estado 22, resultado neto -1605000.00; RF-92 informe 25, versión 2026-M11-V1. | Sí |
| (e) Notificación | El Contador recibe «Período 2026-11 cerrado: listo para transferir desde Agrofusión». | 0 avisos nuevos frente a la línea base tras noviembre; tampoco llegó aviso nuevo tras diciembre. | **No** |
| (f) Integridad del cierre | Sin exclusiones indebidas ni activos ajenos; cierre verificable. | 4 procesados, activos_excluidos [], sin activos ajenos; cierre y reportes consultados por API. | Sí |

Comprobantes: VARIACION_VR_PM 1880000.00, DEPRECIACION_ACTIVO_COSTO 205000.00, BAJA_ACTIVO 3760000.00 y RECONOCIMIENTO_DIFERENCIA 480000.00. Los dos últimos corresponden a la baja RF-45 dentro del RUN, anterior al cierre, y no a la revaluación.

## TC-M06-020: inicio por activo y cierre

| Activo | Cierre | Rama | Inicio esperado | Anterior observado | Actual | Total esperado y observado | TB | PM | Cumple |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1569 | Noviembre, 22 | a, sin intermedias | 3760000.0000 (RF-82) | 3760000.0000 | 4700000.0000 | 940000.0000 | 0.0000 | 940000.0000 | Sí |
| 1570 | Noviembre, 22 | a, sin intermedias | 3760000.0000 (RF-82) | 3760000.0000 | 4700000.0000 | 940000.0000 | 0.0000 | 940000.0000 | Sí |
| 1569 | Diciembre, 23 | Segundo cierre | 4700000.0000 (cierre previo) | 4700000.0000 | 5287500.0000 | 587500.0000 | 0.0000 | 587500.0000 | Sí |
| 1570 | Diciembre, 23 | Segundo cierre | 4700000.0000 (cierre previo) | 4700000.0000 | 5287500.0000 | 587500.0000 | 0.0000 | 587500.0000 | Sí |

Precio POR_CABEZA, id 435 contrastado con la simulación: 4000000.00 → 5000000.00 → 5625000.00. Umbral 50 %; incrementos 25 % y 12.5 %, sin confirmar desviación. Ambos activos siguieron la rama (a) del primer cierre, sin mediciones intermedias.

## Corrección del oráculo

Se retira el subcriterio QA costo_baja_sin_hechos. Comparaba todas las líneas nuevas de 1571, 1572 y 1573 contra una línea base tomada antes de la baja RF-45. Esa baja genera por diseño BAJA_ACTIVO y RECONOCIMIENTO_DIFERENCIA; D3 exige DEPRECIACION_ACTIVO_COSTO para 1572 y 1573. Su presencia no demuestra revaluación de 1571 en el cierre. El criterio aprobado de 019(b) exige que 1571 no sea revaluado por CIERRE_PERIODO: no tiene medición de ese origen; las únicas mediciones del cierre corresponden a 1569 y 1570. Para versiones futuras, el evaluador comprueba además ausencia en 1571 de variación o línea asociada al id_cierre o al tipo_evidencia CIERRE_PERIODO.

## Comprobaciones API y evidencias

- G41-API-019-01: RECHAZADO; detalle notificacion. POST cierre, GET períodos, mediciones, auditoría, RF-92, RF-93 y bandeja.
- G41-API-020-01: APROBADO; ambos cierres y continuidad del valor inicial comprobados por API.
- Newman: código 0, 0 fallos. Evidencias reales: newman/newman-G41.json y newman/newman-G41.html.
- 64/200 solicitudes; 18 s. Resultado estructurado: resultado.json. Contexto: contexto_operacion.json. Preflight: preflight.json. Sin UI obligatoria en estos casos.

## Incidencia INC-M06-G41-01

- Caso y requisito: TC-M06-019; RF-87 v1.1, Actualización «Notificación» y Proceso paso 9.
- Pasos: con Contador autenticado y período 220 ABIERTO, tomar línea base de GET /notificaciones; ejecutar POST /finanzas/periodos/220/cierre; comprobar CERRADO y volver a leer la bandeja. Repetir el contraste tras cerrar 242.
- Esperado: aviso «Período 2026-11 cerrado: listo para transferir desde Agrofusión» en la bandeja del Contador.
- Obtenido: cierre HTTP 200 y período CERRADO, pero 0 avisos nuevos frente a la línea base. Tampoco se observó aviso de diciembre.
- Impacto y severidad: MEDIA; el cierre, la revaluación, el período siguiente y los reportes se completan; falla el aviso obligatorio al Contador de RF-87 v1.1. Certeza de la discrepancia: CONFIRMADA.
- Equipo inicial: Desarrollo. La primera discrepancia comprobada está en la bandeja consultada por API pública tras el cierre M06. Esta derivación no demuestra la causa raíz.
- Apoyo de código, sin atribución causal: el adaptador notifica mediante CIERRE_PERIODO_CONTABLE (id 39 en TEST); ese id no figura en _CATEGORIA_POR_TIPO_EVENTO (src/identity_access/domain/value_objects/evento_categoria.py:25-89). SqlAlchemyEventoRepository.registrar puede lanzar CATEGORIA_EVENTO_NO_DEFINIDA (src/identity_access/infrastructure/repositories/evento_repository.py:291-302); NotificacionFinancieraM01Adapter captura el error, hace rollback y lo registra en log (src/financial_valuation/infrastructure/adapters/notificacion_financiera_m01_adapter.py:51-53). Patrón semejante observado en G37 con ALERTA_FINANCIERA_NIC41 (id 40). Causa raíz: NO DETERMINADA; requiere traza del evento en TEST.
- Evidencias: resultado.json, observado.019.avisos_nuevos=0, observado.020.segundo_aviso=false, comprobación G41-API-019-01 y solicitudes GET /notificaciones; newman/newman-G41.json. El código solo orienta la investigación.

## Observaciones y efectos persistentes

Diciembre se cerró anticipadamente conforme a D2. No se registró aviso nuevo en la bandeja; no consta aviso real a los Contadores. Persisten dos logins y su auditoría; la bitácora RF-52 podría persistir, sin verificación en este RUN. Problemas técnicos o de datos: ninguno documentado.

## Cierre, rollback y conclusión

DELETE /test-control/runs/RUN-G41-V1-20261109-175216: HTTP 200. Lecturas poscierre iguales a la línea base; rollback CONFIRMADO para los datos comparados. El registro QA emulado sigue OFICIAL. Derivar INC-M06-G41-01 a Desarrollo; reevaluar solo con decisión y autorización explícitas.

Actualización del informe (2026-11-09): retirado el subcriterio QA costo_baja_sin_hechos y ajustada la severidad; veredictos sin cambios
