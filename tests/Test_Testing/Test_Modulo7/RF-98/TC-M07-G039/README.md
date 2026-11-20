# TC-M07-G039 — preparación ORD-G039-005

Estado: automatización local preparada para revisión QA. Sin acceso a TEST, sin RUN oficial ni veredicto de producto. Casos TC-M07-13 a TC-M07-16, RF-98 v1.2. El ejecutor único es `g039.mjs`; la colección única es `G039.postman_collection.json` y contiene tres lecturas. Cypress no aplica.

## Flujo

El preflight lee permisos, anexos y contratos. Bloquea si falta un permiso, no hay exactamente una ACTIVO, hay más de dos vigentes, existe una PENDIENTE con `fecha_vigencia` alcanzada en UTC, anexo APROBADO, mapeadores no vacíos y cupo libre, o una DEPRECADO con `fecha_inactivacion` alcanzada. Las PENDIENTE vencidas sin cupo aparecen como observación no bloqueante `PENDIENTE_VENCIDA_SIN_CUPO` con sus ids. La ausencia de DEPRECADO, PENDIENTE o INACTIVO afecta solo al subcaso que la necesita. Las versiones se eligen en vivo por estado e id menor y se guardan en `resultado.json`.

Orden: 14 (activar DEPRECADO, activar ACTIVO, deprecar PENDIENTE), 15 (PATCH y PUT de ACTIVO), 13 (deprecar ACTIVO con 90 días si sigue activa), 16 (activar y deprecar INACTIVO). No se registra ninguna versión. Se conservan los oráculos originales: 14 exige rechazo 4xx, invariancia, WARNING nuevo y aviso nuevo; 15 exige `MODIFICACION_NO_PERMITIDA` e invariancia; 13 exige DEPRECADO, 90 días por instante y auditoría; 16 exige `REACTIVACION_NO_PERMITIDA` e invariancia. El código de cada rechazo de 14 se conserva en las observaciones. El rollback se verifica por igualdad de la firma completa con la base.

Presupuesto: 70 solicitudes y 600 segundos, en serie. El conforme simulado usa **49 solicitudes**, incluidas tres lecturas Newman, DELETE y lectura poscierre. Los 15 escenarios se ejecutan solo contra loopback.

## Validación local

```powershell
node g039.mjs --comprobar
node --check g039.mjs
node --check pruebas/simulador_g039.mjs
node --check pruebas/escenarios_g039.mjs
node --check pruebas/verificar.mjs
node pruebas/g039_local.test.mjs
node pruebas/contrato_cruzado.test.mjs
node pruebas/escenarios_g039.mjs
node pruebas/verificar.mjs
```

## SHA-256

| Archivo | SHA-256 |
|---|---|
| `g039.mjs` | `78e66da8d655318eb6b3a06c2c704d150701a8fc156f3b4c9207bc216ef2a7c5` |
| `pruebas/verificar.mjs` | `5b69deae4ec5cc7ffb0a48fdbb74c1640c763a56d3647a639a3acffde836f320` |
| `pruebas/simulador_g039.mjs` | `3484d6f1ff0946de92a8731de13ddaefe985b6c2a9908d67e94f45d87aec3b2a` |
| `pruebas/escenarios_g039.mjs` | `6397427ffcb781204adbc512e65aae10fb77f119f6c64a4bccd02e5fc0dad76e` |
| `pruebas/escenarios_g039.json` | `fa07356fbebdb9d323fb23a713812105f0c1af8d805b68ff9cd6df9df43167d1` |
| `pruebas/contrato_cruzado.test.mjs` | `3f4d19bfae0894431ba80a276a007787c27a3d6ff4b16f48faa375a0004b5dbb` |
| `pruebas/g039_dto_test.py` | `c5400673775323dbbdd85b899478e8f663993105986b50b8ce16a65485dea21a` |

SHA-256 esperado de `g039.mjs`: `78e66da8d655318eb6b3a06c2c704d150701a8fc156f3b4c9207bc216ef2a7c5`

SHA-256 esperado de `verificar.mjs`: `5b69deae4ec5cc7ffb0a48fdbb74c1640c763a56d3647a639a3acffde836f320`
