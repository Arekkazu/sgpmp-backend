# TC-M06-G46 — RF-87, TC-M06-034

Preparación local de auditoría del cierre. La matriz original está en `Casos_Prueba(Modulo6Agrup).csv`, fila 389. El RF exige INICIADO y COMPLETADO con hash SHA-256 y referencias del cierre (RF-87, pasos 1, 5, 6, 9 y CA-13). La orden ORD-G46-001 define cinco comprobaciones API. No se ejecutó TEST ni se creó RUN en esta fase.

## Archivos vigentes

- `g46.mjs`: único ejecutor y oráculos.
- `G46.postman_collection.json`: cinco GET de solo lectura para Newman.
- `lib/infra.mjs`, `lib/contrato.mjs`, `lib/informe.mjs`: infraestructura, contrato de lecturas e informe.
- `pruebas/newman_hijo.mjs`, `pruebas/verificar.mjs`: lanzador y verificación local.
- `pruebas/simulador_g46.mjs`, `pruebas/g46_escenarios.test.mjs`: trece escenarios locales, con y sin campos extra; Newman genera reportes reales contra el simulador local en la carpeta temporal de cada escenario. `matriz_49_inactiva` omite la asignación 49, exige `NO_CONCLUYENTE`, ningún POST de cierre y DELETE.
- `pruebas/g46_hash.test.py`, `pruebas/g46_dto.test.py`, `pruebas/g46_cli.test.mjs`: serialización contra backend real, DTO y CLI.

G46 estaba vacía antes de esta preparación; no hay duplicados ni legado del grupo. G45 se consultó como referencia, sin modificación. No hay UI obligatoria ni Cypress en esta orden.

## Origen de cada forma simulada

| Forma | Fuente de código leída |
|---|---|
| `POST /sesiones/`, `GET /sesiones/me/permisos` | `src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235`; `src/identity_access/infrastructure/dto/usuario_dto.py:26-30` |
| `DELETE /test-control/runs/{id}` | `src/shared/rollback/presentation/test_control_router.py:31-40` |
| `GET /finanzas/periodos`: `ultimo_cierre` incrustado en cada período; `hash_cierre` e `id_usuario_ejecutor` vienen de la última ejecución | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299`; `src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| `GET /finanzas/periodos/220/prevalidacion`: `Prevalidacion.a_dict()` añade `puede_cerrar` y `requiere_autorizacion` | `src/financial_valuation/infrastructure/routers/m06_router.py:302-309`; `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:53-66` |
| `GET /finanzas/configuracion`: matriz solo de asignaciones activas; 34 `MANO_OBRA_PROPIA/UNICO` 158405/250505 y 49 `DEPRECIACION_ACTIVO_COSTO/UNICO` 516005/159205, ambas genéricas | `src/financial_valuation/infrastructure/routers/m06_router.py:79-85`; `src/financial_valuation/infrastructure/repositories/configuracion_contable_repository.py:103-108`; referencia de comprobación `tests/Test_Testing/Test_Modulo6/RF-87/TC-M06-G44/g44.mjs:84-85,98-99` |
| `GET /finanzas/lineas?id_periodo_contable=220`: líneas y estado de trazabilidad | `src/financial_valuation/infrastructure/routers/m06_router.py:225-231`; `src/financial_valuation/infrastructure/repositories/asiento_repository.py:77-85` |
| `GET /finanzas/periodos/220/comprobantes`: código, fecha, líneas, valor y hash | `src/financial_valuation/infrastructure/routers/m06_router.py:321-324`; `src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| `GET /finanzas/periodos/220/variaciones`: variaciones con evidencia y trazabilidad | `src/financial_valuation/infrastructure/routers/m06_router.py:241-245`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:307-319` |
| `GET /finanzas/activos/1573`: `activo`, `reconocimientos`, `calculos`, `mediciones`, `productos`, `valoracion_costo` y `lineas`; la valoración usa `es_activa` | `src/financial_valuation/infrastructure/routers/m06_router.py:196-203`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:273-293` |
| `POST /finanzas/periodos/220/cierre`: resultado de cierre, comprobantes y hash | `src/financial_valuation/infrastructure/routers/m06_router.py:312-318`; `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:264-302` |
| `GET /finanzas/auditoria` en `TECNICO`: filtros, eventos y paginación con `resumen_severidad`; payload truncado `{resumen, payload_truncado:true}` | `src/financial_valuation/infrastructure/routers/m06_router.py:498-508`; `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:26-30,54-79`; `src/financial_valuation/application/use_cases/auditoria/consultar_auditoria_financiera_use_case.py:58-82` |
| Eventos INICIADO, COMPLETADO, variación y depreciación | `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:185-195,292-297,322-327`; `src/financial_valuation/application/services/medidor.py:129-134` |
| Hash de comprobante y serialización canónica | `src/financial_valuation/domain/services/consolidacion.py:30-62`; `src/financial_valuation/domain/services/nic41.py:225-228` |

Los valores del simulador son ficticios y solo prueban el flujo del ejecutor. Las expectativas provienen de la matriz, RF y ORD-G46-001. La presencia de la asignación en la lista significa activa; `id_especie` y `subtipo_costo` nulos con `sentido=UNICO` significan genérica. El rollback compara únicamente `id_valoracion_por_costo`, `es_activa`, `depreciacion_acumulada` y `valor_contable_por_costo` de la valoración. El hash de auditoría se valida por formato: lo calcula un trigger sobre la fila completa y la API no expone datos suficientes para recalcularlo.

## Flujo previsto por el lanzador autorizado

Un login como Contador; permisos `cierre_periodo` 5 y 2 y `auditoria_financiera` 2; lecturas basales y preflight del 220; un POST `/finanzas/periodos/220/cierre` con `{}` dentro del sandbox; lecturas de auditoría, comprobantes y períodos; lecturas complementarias de 7 y 219; Newman de solo lectura; DELETE del RUN siempre; lecturas sin cabeceras para verificar rollback. Si el POST no responde 200, no se reintenta. El ejecutor nunca envía autorización de exclusiones.

El POST, si se autoriza y ejecuta en TEST, cierra el 220, abre el siguiente período, genera comprobantes, variaciones, depreciación y eventos RF-94, procesa eventos M02 pendientes y genera reportes RF-92/93. El DELETE debe revertir esos efectos; el ejecutor comprueba el resultado con lecturas posteriores antes de marcar rollback verificado.

## Validación local

`node --check g46.mjs`; `node g46.mjs --comprobar`; `node g46.mjs --capacidades`; `.venv/Scripts/python.exe pruebas/g46_hash.test.py`; `.venv/Scripts/python.exe pruebas/g46_dto.test.py`; `node pruebas/verificar.mjs`. Solo realizan trabajo local. El guard de `verificar.mjs` bloquea destinos remotos.
