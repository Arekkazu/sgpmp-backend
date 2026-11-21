# TC-M07-G040 — preparación ORD-G040-009

Estado: automatización local preparada para revisión QA. Sin acceso a TEST, sin RUN oficial y sin veredicto de producto. Casos TC-M07-17 a TC-M07-21, RF-98 v1.2. Un ejecutor (`g040.mjs`) y una colección Newman (`G040.postman_collection.json`, dos lecturas de contraste); Cypress no aplica.

## Flujo

Login web antes del RUN; preflight de permisos, anexos, contratos, titular de finca 463 y período cerrado; un POST de token de canal; ocho GET AAEF en serie con al menos 13 s entre peticiones; dos GET Newman; DELETE único y lectura de contratos sin cabeceras de sandbox. Máximo 40 solicitudes y 600 s. El token dura 300 s. Ni el NIT ni los secretos se fijan en el código; el NIT sale de `GET /configuracion/fincas/463/titular`. La ruta `GET /finanzas/periodos` verifica el período cerrado.

La reevaluación V2 acepta `VERSION_NO_ENCONTRADA` y `VERSION_NO_REGISTRADA` para TC-M07-19 por decisión del responsable QA, pendiente del cambio de RF-98 FA-7. Exige HTTP 404 y mensaje de no existencia o indisponibilidad (CA-15). El resultado conserva el código observado y registra la decisión cuando llega `VERSION_NO_REGISTRADA`. La V1 permanece intacta.

## Validación local

```powershell
node --check g040.mjs
node --check pruebas/verificar.mjs
node g040.mjs --comprobar
node pruebas/g040_local.test.mjs
node pruebas/contrato_cruzado.test.mjs
node pruebas/escenarios_g040.mjs
node pruebas/verificar.mjs
& 'C:\Users\yoloh\OneDrive\Escritorio\pruebas\sgpmp-backend\.venv\Scripts\python.exe' -m pytest -p no:cacheprovider pruebas\g040_dto_test.py -q
```

El verificador intenta ejecutar los hijos con `spawn` y clasifica cualquier `EPERM` como fallo `SANDBOX`. Los 19 escenarios locales ejecutan Newman mediante su biblioteca en el mismo proceso. El verificador comprueba cierre, rollback, evidencia y clasificación sobre salidas temporales. El responsable QA debe repetir los pasos afectados antes de TEST. No usar `--prueba-cli-local` fuera del directorio temporal.

El detalle de preparación se conserva en SIGAB_QA_ORQUESTACION/informes/ y SIGAB_QA_ORQUESTACION/estado/preparaciones/M07/TC-M07-G040/.

## SHA-256

SHA-256 esperado de `g040.mjs`: `df7155da3175fe71e2780c7fae80b36fb8b73b25f0627727d971160db4649bec`

SHA-256 esperado de `verificar.mjs`: `3078200e820a18af15c4eb5f49b113166142454b9317da1425484269532e3465`
