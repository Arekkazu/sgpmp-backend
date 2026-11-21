# TC-M07-G036 — preparación local V2 (ORD-G036-018)

Cobertura: TC-M07-01 a TC-M07-05, RF-98 v1.2. Ejecutor canónico: g036.mjs; una colección Newman (G036.postman_collection.json) y un spec/config Cypress (g036.cy.js, g036.cypress.config.cjs). La V1 en Resultados/ conserva su evidencia. La V2 escribe únicamente en EvaluacionV2/Resultados/RUN-G036-V2-AAAAMMDD-HHMMSS/ cuando el lanzador autorizado crea el RUN.

## Validación local

Ejecutar desde esta carpeta. Los escenarios usan exclusivamente 127.0.0.1 y archivos temporales; las pruebas con spawn las ejecuta el responsable QA.

```powershell
node g036.mjs --comprobar
node g036.mjs --capacidades
node pruebas/g036_local.test.mjs
node pruebas/contrato_cruzado.test.mjs
node pruebas/verificar.mjs
```

SHA-256 esperado de g036.mjs: 78c2002c8141779b766f612027c8ca1b0a98500f7d829fba2469a5b18e59bb06
SHA-256 esperado de verificar.mjs: 42a620200f5576a8a1bbac42025e11d7a0cffac54e0d6c8f3b3f2037364acb88

pruebas/verificar.mjs ejecuta once pasos y RED. Comprueba sintaxis, Cypress real y Newman local, preflight sin red, diecis?is escenarios, forma de resultado, privacidad, DTO Pydantic, contrato T2–T4, intercepción, clasificación de registro QA y pruebas locales. El ejemplo sintético queda en %TEMP%\g036-v2-verificar-ejemplo; no es evidencia de TEST.

## Fuentes leídas y selección

Oráculos: fila TC-M07-G036 de tests/Test_Testing/Test_Modulo7/Casos_Prueba(Modulo7Agrup).csv, RF-98 v1.2 según esa matriz y SIGAB_QA_ORQUESTACION/estado/ANALISIS-G036-V2.md. Código leído: src/accounting_integration/infrastructure/dto/m07_dto.py:79-116, src/accounting_integration/infrastructure/routers/m07_router.py:181-228,252-279, src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py:94-127,269-288, src/accounting_integration/domain/entities/contrato.py:169-178, src/accounting_integration/infrastructure/repositories/auditoria_integracion_repository.py:102-105, src/accounting_integration/application/use_cases/auditoria/consultar_auditoria_integracion_use_case.py:40-60, src/shared/error_handlers.py:61-68, frontend src/accounting_integration/pages/ContratosView.tsx:125-183,289-323 y src/shared/i18n/locales/es-CO/integracion.json:162-190.

El ejecutor elige tres versiones libres desde 6.0, la versión ACTIVO y los anexos APROBADO, EN_REVISION y BORRADOR en las lecturas públicas del RUN. Si falta BORRADOR, registra uno dentro del RUN con el DTO vigente. La colección Newman consulta contratos y anexos; la auditoría la compara el ejecutor y guarda solo el resumen sin nombres. Si falta EN_REVISION, la variante 03c queda NO_CONCLUYENTE y los casos independientes continúan. El cupo vigente se registra como dato, sin bloquear 01–04. Cypress exige Activar visible y ajustado a motivo_no_activable del listado: deshabilitado con motivo si existe, habilitado si no existe. No pulsa Activar ni Retirar con plazo.







Orden de cierre comprobado en g036.mjs: se espera el resultado de lanzarCypress/ensayoLocal.cypress antes de salir de try; el DELETE del RUN se ejecuta despu?s, en finally. El doble local separa lecturas por X-Test-Run-Id y rechaza concurrencia del mismo RUN. El paso 2 de verificar.mjs exige cabeceras y ausencia de concurrencia en las peticiones API de pantalla.
