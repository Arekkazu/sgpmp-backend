# TC-M07-G037 — reevaluación V3 preparada, RF-98 v1.2

Orden ORD-G037-011. Oráculo de ORD-G037-009 conservado sin cambios. Ejecutor canónico: `g037.mjs`; colección Newman: `G037.postman_collection.json`. Los tres casos son solo API; no corresponde Cypress. La V1 oficial en `Resultados/RUN-G037-V1-20261118-071829/` y la V2 previa en `EvaluacionV2/Resultados/RUN-G037-V2-20261120-210522/` son históricas y permanecen intactas. La V2 es OFICIAL; el reintento fue rechazado porque ya existe RUN oficial. La decisión QA abre V3 para los tres casos.

## Oráculos y datos

Fuente: fila G037 de `tests/Test_Testing/Test_Modulo7/Casos_Prueba(Modulo7Agrup).csv`, RF-98 v1.2 (precondiciones, 5.8 y RNF-98.10), y decisiones D1–D5 de `ANALISIS-G037-V2.md`. Se cotejó también `SIGAB_QA_ORQUESTACION/estado/Casos_Prueba(Modulo7Agrup).respaldo-G037.csv`.

- TC-M07-06: los valores `4`, `4.0.1`, `v4.0`, `4.x`, `4.`, `.4` y la cadena vacía se rechazan con cualquier 4xx sin crear contrato. Una versión libre MAJOR.MINOR desde 6.0 se registra en PENDIENTE. La matriz usa 4.0 como ejemplo válido; en TEST ya existe y por eso el ejecutor elige una versión libre.
- TC-M07-07: RF-98 fija 30 días como mínimo y 90 por defecto en la configuración base. El ejecutor lee el mínimo efectivo `m` y el defecto efectivo `d` en M09; comprueba `m-1`, `m` y omisión. Dentro del RUN cambia ambos valores por PATCH (45/120, o 46/121 si alguno coincide), comprueba el GET con fuente CONFIGURADO y repite límites y defecto. Un PATCH con defecto menor que el mínimo se aprueba solo si devuelve HTTP 400 y el GET posterior conserva la misma firma de gracia; HTTP 2xx o gracia cambiada se rechazan. Otro 4xx/5xx inesperado queda NO_CONCLUYENTE. `error_code` y `field` se anotan como observación cuando difieren del formato específico previo; RF-98 no los fija para este PATCH. `m09_configurable` se aprueba únicamente si el registro usa los valores configurados. Falta de permiso U: D3 NO_CONCLUYENTE.
- TC-M07-08: toma la ACTIVO del momento. Tras el PATCH, si se pudo hacer, usa el mínimo configurado; en otro caso usa el mínimo leído inicialmente. `m-1` debe rechazarse sin cambiar ACTIVO; `m` debe dejarla DEPRECADO con inactivación exactamente `m` días después, comparando instantes.

Un anexo APROBADO se selecciona en vivo. La ausencia de ACTIVO afecta solo al 08; la ausencia de anexo o del permiso C afecta al 06/07. Solo la falta del permiso R de contratos impide todo el grupo. Los otros permisos solo afectan las comprobaciones que los necesitan. El ejecutor consulta eventos `CONTRATO_REGISTRADO` y `CONTRATO_DEPRECADO` por API pública cuando hay permiso R de auditoría.

## Contrato y fuentes consultadas

`pruebas/contrato_g037.json` cita por ruta y campo los DTO y routers actuales. Se leyeron realmente `src/accounting_integration/infrastructure/dto/m07_dto.py`, `src/accounting_integration/infrastructure/routers/m07_router.py`, `src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py`, `src/accounting_integration/infrastructure/factoria.py`, `src/configuration/infrastructure/routers/parametros_integracion_contable_router.py`, `src/configuration/application/use_cases/configuracion_global/parametros_integracion_contable_use_case.py`, `src/configuration/application/use_cases/configuracion_global/parametros_alertas_use_case.py`, `src/configuration/infrastructure/dto/actualizar_parametros_alertas_dto.py`, `src/configuration/infrastructure/schema/parametros_alertas_schema.py` y los esquemas compartidos de G036 y G038–G041. La ruta M09 exige R/U sobre recurso 21. `factoria.gracia()` se invoca en el registro y la deprecación; el DTO acepta enteros desde 1 y el caso de uso valida el mínimo efectivo. Los valores configurados pueden serializarse como cadenas decimales JSON porque el esquema usa `Any`; el ejecutor exige que representen enteros seguros. Las pruebas T2–T4 comprueban compatibilidad de contrato, cuerpos estrictos y aislamiento local.

## Uso local y futura ejecución

Sin red remota ni TEST, desde esta carpeta:

```powershell
node g037.mjs --capacidades
node g037.mjs --comprobar
node --check g037.mjs
node --check pruebas/verificar.mjs
node pruebas/g037_local.test.mjs
node pruebas/contrato_cruzado.test.mjs
node pruebas/escenarios_g037.mjs
node pruebas/verificar.mjs
```

`verificar.mjs` toma la base V2 de G040: pasos 1, 3–8, 10 y RED; 2 y 9 son NO_APLICA por ser solo API. Sus simulaciones van a TEMP. En el sandbox de Codex, pasos que crean procesos pueden fallar con `spawn EPERM`; el responsable QA ejecutará la verificación completa fuera de ese sandbox. Un código 0 de Newman no sustituye los veredictos ni el rollback.

El lanzador externo, con autorización particular, debe crear un RUN nuevo en `EvaluacionV3/Resultados/RUN-G037-V3-<timestamp>/contexto_operacion.json` y pasar operación `reevaluar`, versión 3, intento 1, `version_anterior: 2`, decisión explícita de reevaluación completa y referencia de autorización. Un reintento de V3 solo corresponde a una V3 ABIERTA sin RUN oficial y conserva su decisión histórica. La carpeta nueva contendrá un solo informe `TC-M07-G037_reevaluacion_V3.md`, `resultado.json`, `preflight.json` y los reportes Newman JSON/HTML realmente generados. No se ejecuta TEST en esta preparación. El login previo al RUN puede dejar último acceso, auditoria y notificación; PATCH, altas y deprecación se hacen dentro del RUN, y el DELETE más lecturas públicas comprueban el rollback de contratos y parámetros.

## Integridad

SHA-256 esperado de `g037.mjs`: `4af54149d15223e7a209ee3e3c526b9db26a84210e35fcb052fa212cac2dfe31`

SHA-256 esperado de `verificar.mjs`: `55922d2bd9117b7cd005839fa093c0686c5c3bca135f22b9d8a085716283674b`
