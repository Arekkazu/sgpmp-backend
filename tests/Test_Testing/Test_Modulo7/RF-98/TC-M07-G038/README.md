# TC-M07-G038 — preparación local RF-98 v1.2

Ejecutor canónico: `g038.mjs`. Colección canónica: `G038.postman_collection.json`. Los cuatro casos exigen solo API; Cypress es NO_APLICA. El RUN técnico V1 del intento 1 se conserva intacto en Resultados/RUN-G038-V1-20261118-090819.

## Orden y oráculos

El lanzador externo crea `Resultados/RUN-G038-V1-<timestamp>/contexto_operacion.json`. El ejecutor hace un login previo, preflight de lectura y líneas base. Fase A: 09, 12, 11, DELETE y lectura pública de rollback. Fase B: reabre el mismo `run_id` desde la base, ejecuta 10, Newman de contraste, DELETE y otra lectura pública. El segundo DELETE es `cierre.http`. La fase B requiere rollback A verificado. Máximo 70 solicitudes y 600 segundos.

- 09: 4.0 MAJOR ACTIVO, anterior DEPRECADO al mismo instante, inactivación a 90 días exactos y dos eventos RF-102 nuevos.
- 12: rechazo `LIMITE_VERSIONES_EXCEDIDO` y mensaje que nombra una vigente; 4.1 PENDIENTE y vigentes intactas.
- 11: `CONTRATO_NO_VALIDO`, fixture 3.9 PENDIENTE y aviso nuevo al Administrador con motivo específico en `/notificaciones`.
- 10: 3.2 MINOR ACTIVO, anterior ACTIVO sin fechas de deprecación, exactamente dos vigentes, `CONTRATO_ACTIVADO` nuevo y ningún `CONTRATO_DEPRECADO` nuevo.

Fuente: fila G038 corregida de `Casos_Prueba(Modulo7Agrup).csv` y `Especificacion-Requerimientos-Modulo7.md`, RF-98 v1.2, restricciones 5.3–5.5 y 5.8, FA-5/6 y CA-5/6/7/9/16/18/21/29. El código local de activación manual no llama al alertador; el aviso faltante es `DEFECTO_FUNCIONAL_CANDIDATO` hasta una evaluación autorizada de TEST.

## Comandos para QA

Desde esta carpeta en PowerShell:

```powershell
node g038.mjs --capacidades
node g038.mjs --comprobar
node --check g038.mjs
node --check pruebas/verificar.mjs
node pruebas/g038_local.test.mjs
node pruebas/verificar.mjs
& '..\..\..\..\..\.venv\Scripts\python.exe' -m pytest -p no:cacheprovider pruebas/g038_dto_test.py -q
```

`verificar.mjs` usa un servidor de loopback y guarda los escenarios bajo TEMP. Los 13 escenarios ejecutan Newman real en proceso; los pasos 3, 4, 7, 8 y 10 usan procesos hijos. Las l?neas `OK escenario_*` prueban la l?gica local, no el producto en TEST. Los pasos 6 y 10 comprueban `resultado.json` y el paso 10 llama a `registro_qa.py validar` real. El lanzador autorizado es el único que puede crear el RUN oficial y llamar a TEST.

## SHA-256 esperado

SHA-256 esperado de `g038.mjs`: `868e7e16877229464a64c4e7ad20148f67626cb1924182cb6190e27009219c7f`

SHA-256 esperado de `verificar.mjs`: `6c8ff4e0f34d57800326756fef61ee837fa2f956ddade660edd6e656e8284c65`

SHA-256 de `newman_hijo.mjs`: `5d4fa00d0f73da24d00850a83b2910b9da5e34f5db32cc53d4528dae6a053595`

SHA-256 de `contrato.mjs`: `9ad85ae57fed79bfd10d3c027f7c1f4ace5780a7c2a20ec1534a29927a0394b5`

SHA-256 de `contrato_g038.json`: `54c977d86c9157ec50c46ce162e0ed0ddd79263591aaf9ce3dad77bbbfdf312d`

SHA-256 de `G038.postman_collection.json`: `0c5d5d080488e0bf5af7e3a569d1cfe531321094abc47206e897b3a8c0711f4b`

## Ajuste ORD-G038-002

La bandeja del Administrador se consulta solo con pagina=1 y tamano=50 antes y después del intento 11. Se toma el mayor id_notificacion previo y se busca un aviso posterior con id mayor, tipo_evento 41, versión de la fixture y motivo. La auditoría de integración conserva paginación completa filtrada por tipo_evento. La simulación local con 1000 avisos y 300 eventos de auditoría verifica 41 solicitudes sin Newman y 44 con sus 3 solicitudes, ambas menores que 70. El detalle de preparación está en SIGAB_QA_ORQUESTACION/informes/ y estado/preparaciones/M07/TC-M07-G038/.

SHA-256 de simulador_g038.mjs: cead49d2a336021bdc8172534282b9e25d457a6d1f502c9e6b927969fa804707

SHA-256 de escenarios_g038.mjs: b515016d57a5dbaf3cb54e32d224ad846b1a8824538639f7305e5171c7093438

SHA-256 de escenarios_g038.json: db83d1ae13c50c199e27f515bd460998a1368caafe0375704304e9662e382dca

## Ajuste ORD-G038-005

La revisión campo por campo de los tipos y la nulidad declarados en pruebas/contrato_g038.json consultó src/accounting_integration/domain/entities/evento_integracion.py:40-64, src/accounting_integration/domain/entities/contrato.py:26-36,55-69, src/accounting_integration/infrastructure/repositories/contrato_repository.py:17-27, src/identity_access/infrastructure/schema/notificacion_schema.py:7-33, src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235 y src/shared/error_handlers.py:40-68. Solo difería el tipo de id_evento_integracion: ahora es texto UUID. La prueba cruzada compara todos los campos comunes con G036/G037 y exige una cita por campo para cualquier diferencia futura. La prueba estricta comprueba presencia, tipo y nulidad de los campos declarados en todas las rutas, además de mostrar que el ID numérico anterior falla. Los campos adicionales de respuesta quedan fuera del subconjunto que usa G038.

Comando: `node pruebas/contrato_cruzado.test.mjs` (también integrado en `node pruebas/verificar.mjs`).

SHA-256 de contrato_cruzado.test.mjs: 76b59506dedf21acc693d1e4751a119b2a0b13a784a69b799a9c3b09e97b27cc.
