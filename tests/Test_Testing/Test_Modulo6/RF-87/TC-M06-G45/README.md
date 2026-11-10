# TC-M06-G45 — RF-87

Órdenes `ORD-G45-001` y `ORD-G45-002`, fase preparar. Cubre por API TC-M06-031, 032 y 033 en TEST; este directorio contiene solo la automatización local. El lanzador externo debe proporcionar contexto y autorización particulares. Codex no ejecuta TEST.

## Archivos activos

- `g45.mjs`: ejecutor canónico, preflight, oráculos, DELETE y validación posterior.
- `G45.postman_collection.json`: única colección Newman vigente, cinco lecturas finales.
- `lib/infra.mjs`, `lib/contrato.mjs`, `pruebas/newman_hijo.mjs`: copias independientes de G44.
- `lib/informe.mjs`: plantilla de informe de G45.
- `pruebas/contrato_g45.json`: rutas y estructura de respuestas observables.
- `pruebas/simulador_g45.mjs`, `pruebas/g45_escenarios.test.mjs`, `pruebas/escenarios_g45.json`, `pruebas/verificar.mjs`: validación solo local.

No hay Cypress: la orden solo exige API. No hay ejecutores, colecciones ni artefactos históricos duplicados en G45.

## Oráculos

- 031: cierre sin autorización y lectura del período 8; solo EN_CIERRE tras 409 de exclusión aprueba.
- 032: costo y reversión sobre período 7 deben devolver 409, con 7 y 219 íntegros.
- 033: ajuste en 8 con referencia a línea del 7 y justificación, manteniendo 7 intacto.

Las operaciones no evaluables y no aplicables constan en `observaciones` del resultado. La OpenAPI es evidencia complementaria; solo se prueban `/openapi.json` y, ante 404, `/docs/openapi.json`. El ejecutor nunca autoriza exclusiones.

## Hallazgos de código local

Son `DEFECTO_FUNCIONAL_CANDIDATO`, sin veredicto de TEST: (1) el caso de uso de cierre revisado comprueba la autorización de exclusión antes de cambiar a EN_CIERRE; (2) el alta de costo revisada puede responder 422 para la fecha cerrada; (3) la reversión revisada bloquea cuando el cierre original es dependiente, mientras RF-87 exige una vía de ajuste en el período abierto. Las comprobaciones 031, 032 y 033 por API pública están preparadas para acreditar o descartar cada discrepancia en un RUN autorizado. Se consultaron la matriz de M06 línea 388, RF-87/RF-86/RF-82 en las líneas indicadas en `ORD-G45-001` y solo los tramos de backend citados allí. No se infiere el resultado de TEST del código local.

## Flujo autorizado futuro

Un inicio de sesión Contador, lectura de permisos y preflight de datos sin escrituras. Si pasa: POST cierre 8, POST costo 944, POST reversión 949, lecturas de ajustes e integridad, hasta dos GET OpenAPI, Newman, DELETE del RUN siempre y lecturas poscierre sin cabeceras. El informe solo se considera oficial con todas las comprobaciones concluyentes, reportes Newman reales, DELETE 200 y rollback verificado.

En V1 el lanzador crea `Resultados/RUN-G45-V1-<timestamp>/`; V2 requiere decisión explícita y va en `EvaluacionV2/Resultados/RUN-G45-V2-<timestamp>/`. El ejecutor escribe `resultado.json`, un solo `TC-M06-G45_resultado.md` o `TC-M06-G45_reevaluacion_V2.md`, y reportes Newman dentro del RUN. No hay RUN en esta carpeta durante preparar.

## Validación local

`node --check g45.mjs`, `node g45.mjs --comprobar`, `node g45.mjs --capacidades`, `node pruebas/verificar.mjs`. `verificar.mjs` deja un ejemplo simulado de `resultado.json` y `capacidades.json` en `os.tmpdir()/g45-verificar-ejemplo/` para validación del registro; no corresponde a TEST ni a un RUN oficial.

## Corrección ORD-G45-002 y origen de las formas simuladas

El historial de `/finanzas/activos/{id}` envuelve `DatosActivo` en `activo` y añade `reconocimientos`, `calculos`, `mediciones`, `productos`, `valoracion_costo` y `lineas` (`src/financial_valuation/infrastructure/routers/m06_router.py:196-203`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:273-293`; `src/financial_valuation/domain/entities/activo_financiero.py:17-37`). Los reconocimientos incluyen `id_reconocimiento_inicial`, `estado`, `id_periodo_contable`, `fecha_reversion` y `justificacion_reversion` (`src/financial_valuation/infrastructure/repositories/valoracion_repository.py:30-34,178-183`). El preflight de 944 exige el reconocimiento 15 CONFIRMADO en 7; el de 949 exige el 20 CONFIRMADO en 7. En `preflight_datos` solo quedan estado, finca e identificadores/estado/período de reconocimientos. La base de rollback de 949 conserva solo estado, fecha y justificación de reversión del 20 y el conjunto de ids, sin cabeceras ni datos personales. El simulador usa `TipoHecho` de `src/financial_valuation/domain/value_objects/nic41.py:11-25` y estados de período de `:110-113`; una compra no presupone línea de reconocimiento.

| Respuesta local simulada | Fuente de su forma |
| --- | --- |
| `POST /sesiones/`, `GET /sesiones/me/permisos` | `src/identity_access/infrastructure/dto/usuario_dto.py:26-30`; `src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235` |
| `GET /finanzas/periodos` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299`; `src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,65,68-72,124-130`; `src/financial_valuation/domain/entities/contabilidad.py:16-23` |
| `GET /finanzas/periodos/8/prevalidacion` | `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:63-66,93-127`; `src/financial_valuation/application/use_cases/trazabilidad/verificar_trazabilidad_use_case.py:31-42` |
| `GET /finanzas/lineas` y `TipoHecho` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230`; `src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83`; `src/financial_valuation/domain/value_objects/nic41.py:11-25` |
| `GET /finanzas/periodos/{id}/comprobantes` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325`; `src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| `GET /finanzas/periodos/{id}/variaciones` | `src/financial_valuation/infrastructure/routers/m06_router.py:241-245`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-319` |
| `GET /finanzas/costos`, `POST /finanzas/costos` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-281`; `src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114`; `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124` |
| `GET /finanzas/activos/{id}` | `src/financial_valuation/infrastructure/routers/m06_router.py:196-203`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:30-34,178-183,273-293`; `src/financial_valuation/domain/entities/activo_financiero.py:17-37` |
| `POST /finanzas/periodos/8/cierre`, `POST /finanzas/reconocimientos/949/reversion` | `src/financial_valuation/infrastructure/routers/m06_router.py:177-182,312-318`; `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134`; `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:298-302` |
| `DELETE /test-control/runs/{id}` | `src/shared/rollback/presentation/test_control_router.py:31-40` |
| Errores `{error_code, message, fields, timestamp}` (409, 422, 404 y fallo simulado de DELETE) | `src/shared/error_handlers.py:40-68` |

`/openapi.json` y el fallback `/docs/openapi.json` son lecturas complementarias aprobadas en `ORD-G45-001`; el simulador entrega la estructura OpenAPI `paths` o el error citado, sin usarla como oráculo de producto. Las referencias de las respuestas anteriores provienen de `pruebas/contrato_g45.json` y de los tramos de backend expresamente indicados en la orden; en esta ronda se consultaron directamente `m06_router.py:186-205`, `valoracion_repository.py:30-34,178-183,273-293`, `activo_financiero.py` y `nic41.py:11-25,105-115`.

## ORD-G45-004: corrección local

K4: `pruebas/verificar.mjs` se copió byte a byte del G44 con SHA-256 `b8cfd167b1f44848aa27fb6ab719dd2813fd41e3173693c3cbb31859f4c7d316`. El único diff en ese archivo es A4:

```diff
-    const ejemplo=path.join(salidas,'conforme','resultado.json');
+    const ejemplo=path.join(os.tmpdir(),'g45-verificar-ejemplo');
+    fs.mkdirSync(ejemplo,{recursive:true});
+    fs.copyFileSync(path.join(salidas,'conforme_normal','resultado.json'),path.join(ejemplo,'resultado.json'));
+    fs.writeFileSync(path.join(ejemplo,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));
```

El directorio persistente se imprime antes de borrar el temporal. `simulador_base.mjs` adapta el nombre del simulador de G45 a la importación esperada por el verificador; `g45_cli.test.mjs` y `g45_dto.test.py` cubren el CLI/preflight y los bodies literales de costo y reversión con `CostoDTO` y `RevertirReconocimientoDTO` reales. El simulador no produce respuestas con modelo Pydantic. Los archivos de salida de la prueba local se espejan temporalmente en cada carpeta de escenario para que el paso 6 del verificador conserve su lógica original.

K5: `g45.mjs:109-110` clasifica el costo: 409 por período cerrado e integridad conservada aprueba; 422 por período cerrado rechaza por CA-3; 2xx o cambio del período rechaza; otros errores quedan no concluyentes. `g45.mjs:115-116` exige 409 con `REVERSION_BLOQUEADA` para aprobar la reversión; 2xx o cambio rechaza y otros errores quedan no concluyentes. `g45.mjs:136-137` asigna ALTA a escritura aceptada o alteración del período y MEDIA al 422 por período cerrado. `costo_422_validacion` y `reversion_400_motivo` quedan `NO_CONCLUYENTE` y sin INC-M06-G45-02, con y sin campos inyectados.

Validación local: `node --check g45.mjs`, `node --check pruebas/verificar.mjs`, `--comprobar`, `--capacidades`, 24 escenarios locales y el DTO Pydantic ejecutado directamente: OK. `verificar.mjs`: pasos 3, 5, 6, 8 y RED OK; pasos 2 y 9 NO_APLICA por ausencia de UI obligatoria; pasos 1, 4 y 7 marcados SANDBOX por `spawn EPERM`. Las comprobaciones directas de sintaxis y Pydantic pasaron. No se accedió a TEST ni se creó RUN. Los efectos previstos en TEST siguen siendo los de SOL-G45-001: inicio de sesión Contador, POST cierre 8, POST costo 944, POST reversión 949, lecturas API y Newman, DELETE siempre y lecturas posteriores sin cabeceras, sujetos al preflight y a autorización externa.

SHA-256 final: `g45.mjs` `9ea11a76b79feee27e5207065da54344e5273ef12763933a701aa3eae4d0673c`; `pruebas/verificar.mjs` `902874ba54870e01283396f190a6dd3d604ba5707d0ee4d81ae23589d9824b66`; `lib/infra.mjs` sin cambios `97562a7d9269eee82413be798d116a0e271277381fc3b69ba058199358874238`.
