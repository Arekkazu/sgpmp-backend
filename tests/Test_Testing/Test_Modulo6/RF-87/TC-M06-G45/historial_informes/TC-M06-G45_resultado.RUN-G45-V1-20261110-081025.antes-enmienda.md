# TC-M06-G45 — RUN-G45-V1-20261110-081025

Grupo G45 | casos TC-M06-031, TC-M06-032, TC-M06-033 | RF-87 v1.1 | V1 | TEST | autorización AUT-G45-V1-[RESERVADO] | commit no consultado (Git prohibido).

## Resumen de veredictos

| Caso | Veredicto | Motivo |
|---|---|---|
| TC-M06-031 | RECHAZADO | 031_en_cierre |
| TC-M06-032 | RECHAZADO | 032_alta_costo |
| TC-M06-033 | RECHAZADO | 033_ajuste |

## Preflight de datos

| Requisito | Esperado | Observado | Cumple | Bloqueante |
|---|---|---|---|---|
| periodo_7_estado | CERRADO | "CERRADO" | SI | SI |
| periodo_8_estado | ABIERTO | "ABIERTO" | SI | SI |
| periodo_219_estado | CERRADO | "CERRADO" | SI | SI |
| prevalidacion_8_sin_bloqueos | [] | [] | SI | SI |
| prevalidacion_8_linea_sin_trazabilidad | al menos una línea | 1 | SI | SI |
| activo_944_activo_finca_463 | ACTIVO, finca 463 | {"estado":"ACTIVO","id_finca":463} | SI | SI |
| activo_944_reconocimiento_vigente | reconocimiento 15 CONFIRMADO en período 7 | {"id":15,"estado":"CONFIRMADO","id_periodo_contable":7} | SI | SI |
| activo_949_reconocimiento_vigente_periodo_7 | reconocimiento 20 CONFIRMADO en período 7 y activo ACTIVO | {"reconocimiento":{"id":20,"estado":"CONFIRMADO","id_periodo_contable":7},"estado":"ACTIVO"} | SI | SI |
| periodo_8_sin_ajustes_previos | 0 | 0 | SI | SI |

## Esperado y observado por comprobación API

| Caso | Comprobación | Esperado | Observado | Estado |
|---|---|---|---|---|
| TC-M06-031 | 031_en_cierre | EN_CIERRE mientras se solicita autorización de exclusión | HTTP 409; error EXCLUSION_REQUIERE_AUTORIZACION; estado ABIERTO | RECHAZADO |
| TC-M06-032 | 032_alta_costo | HTTP 409 por período cerrado y período 7 idéntico | HTTP 422; error PERIODO_CONTABLE_CERRADO; mensaje La fecha del costo pertenece a un período cerrado. Regístrelo como ajuste en el período abierto.; período 7 idéntico true | RECHAZADO |
| TC-M06-032 | 032_eliminar_reconocimiento | HTTP 409 con REVERSION_BLOQUEADA y período 7 idéntico | HTTP 409; error REVERSION_BLOQUEADA; mensaje No es posible revertir el reconocimiento inicial del activo None. Existen registros contables dependientes: cierre del período del 2026-11-07; cierre del período del 2026-11-30. Para corregir la valoración use un ajuste en el período vigente.; período 7 i | APROBADO |
| TC-M06-032 | 032_integridad | líneas, comprobantes, variaciones, estado, fecha y último cierre de 7 y 219 idénticos | 7 true; 219 true | APROBADO |
| TC-M06-033 | 033_ajuste | AJUSTE_PERIODO_ANTERIOR en 8, referencia a línea de 7 y justificación | líneas de ajuste 0; referencia y justificación false | RECHAZADO |
| TC-M06-033 | 033_cerrado_intacto | 7 CERRADO con fecha, líneas y comprobantes idénticos | estado CERRADO; contenido idéntico true | APROBADO |

No hay comprobaciones UI obligatorias en esta orden.

## Respuestas y lecturas de integridad

Los cuerpos saneados de cierre, costo y reversión constan en `resultado.json` (`respuestas`).
Bases: {"periodo_7":{"estado":"CERRADO","fecha_cierre":"2026-11-07T20:11:44.408365Z","ultimo_cierre":{"id_cierre":1,"estado":"COMPLETADO","paso_actual":9,"activos_procesados":8,"activos_pendientes":0,"activos_excluidos":[{"id_linea":9,"faltantes":["lecturas_nic41"],"tipo_hecho":"VARIACION_VR_TB","nivel_fallo":1,"id_activo_biologico":943}],"precios_congelados":[{"fuente":"MERCADO_ACTIVO","id_especie":39,"fecha_vigencia":"2026-11-07","precio_unitario":"9300.00","id_precio_mercado":17},{"fuente":"UPRA","id_especie":421,"fecha_vigencia":"2026-11-01","precio_unitario":"14500.00","id_precio_mercado":16}],".
Integridad final: {"periodo_7":{"estado":"CERRADO","fecha_cierre":"2026-11-07T20:11:44.408365Z","ultimo_cierre":{"id_cierre":1,"estado":"COMPLETADO","paso_actual":9,"activos_procesados":8,"activos_pendientes":0,"activos_excluidos":[{"id_linea":9,"faltantes":["lecturas_nic41"],"tipo_hecho":"VARIACION_VR_TB","nivel_fallo":1,"id_activo_biologico":943}],"precios_congelados":[{"fuente":"MERCADO_ACTIVO","id_especie":39,"fecha_vigencia":"2026-11-07","precio_unitario":"9300.00","id_precio_mercado":17},{"fuente":"UPRA","id_especie":421,"fecha_vigencia":"2026-11-01","precio_unitario":"14500.00","id_precio_mercado":16}],".
OpenAPI complementaria: {"http":200,"rutas_ajuste":[]}.

## Incidencias de producto

- INC-M06-G45-01 (TC-M06-031): esperado EN_CIERRE durante la espera; obtenido HTTP 409; estado ABIERTO. Evidencia: resultado.json. Severidad MEDIA: El estado de espera del cierre no se representa como exige CA-7.. Certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada por la API pública en TEST. Causa raíz Por determinar. Acción: Desarrollo revisa la discrepancia; QA repite con autorización. Relacionada con INC-M06-G43-01.
- INC-M06-G45-02 (TC-M06-032): esperado HTTP 409 por período cerrado y reversión bloqueada, con períodos cerrados intactos; obtenido costo 422 PERIODO_CONTABLE_CERRADO; reversión 409 REVERSION_BLOQUEADA; integridad true. Evidencia: resultado.json. Severidad MEDIA: El rechazo 422 por período cerrado incumple el HTTP 409 exigido por CA-3.. Certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada por la API pública en TEST. Causa raíz Por determinar. Acción: Desarrollo revisa la discrepancia; QA repite con autorización.
- INC-M06-G45-03 (TC-M06-033): esperado Ajuste en período 8 con referencia y justificación; obtenido No se halló ajuste completo. Evidencia: resultado.json. Severidad ALTA: La vía de corrección de prioridad Must no se acreditó por API pública.. Certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia comprobada por la API pública en TEST. Causa raíz Por determinar. Acción: Desarrollo revisa la discrepancia; QA repite con autorización. Clasificación DEFECTO_FUNCIONAL_CANDIDATO.

## Evidencias y herramientas

Node v22.15.1; Newman 0; Cypress no aplica (0 pruebas); solicitudes 62.
- newman/newman-G45.html
- newman/newman-G45.json

## Problemas técnicos

- Ninguno registrado.

## Observaciones y alcance

- 031: costo, variación, reconocimiento y medición durante la pausa, pesaje M02 y cola A/B no evaluables: la API pública M06 no crea hechos fechados dentro del 8 ni eventos M02; no existe EN_CIERRE previo.
- 032: modificación/eliminación de costos y variaciones, altas fechadas en período cerrado y notificación de variaciones no aplican: no existe ruta pública M06 para fijar tales fechas o modificar esos registros; RF-86 prohíbe modificarlos.

## Cierre y rollback

DELETE del RUN: HTTP 200. Rollback verificado mediante lecturas posteriores: SI. Lecturas sin cabeceras: 7 true; 8 ABIERTO e idéntico true; 219 true; reconocimiento de 949 vigente true; costos 944 true; períodos nuevos false
Registro OFICIAL. La próxima acción es revisar las incidencias acreditadas y decidir una reevaluación autorizada si procede.
