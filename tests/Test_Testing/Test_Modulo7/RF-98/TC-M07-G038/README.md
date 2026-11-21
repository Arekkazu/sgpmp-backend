# TC-M07-G038 — preparación local de reevaluación V2

Orden ORD-G038-013. RF-98 v1.2, casos TC-M07-09 a TC-M07-12. Antecedente oficial: V1 del 2026-11-18, 09/10/12 APROBADO y 11 RECHAZADO por INC-M07-G038-01. Corrección informada: 0553cefd (#1168). V2 oficial: 09, 10 y 12 APROBADO; 11 RECHAZADO solo en aviso_administrador. Esta preparaci?n no consulta TEST ni crea un RUN V3.

## Inventario y ejecución

- `g038.mjs`: ejecutor canónico V2, operaciones `reevaluar` y `reintentar`.
- `G038.postman_collection.json`: única colección Newman; `pruebas/newman_hijo.mjs` genera JSON y HTML dentro del RUN.
- `lib/contrato.mjs` y `pruebas/contrato_g038.json`: contrato de respuestas y comprobación estricta.
- `pruebas/simulador_g038.mjs`, `escenarios_g038.mjs`, `escenarios_g038.json`, `g038_local.test.mjs`, `contrato_cruzado.test.mjs`, `g038_dto_test.py` y `verificar.mjs`: verificación local. No hay UI obligatoria ni spec Cypress activo.
- `Resultados/RUN-G038-V1-20261118-092544/`: evidencia histórica oficial, intacta. No hay duplicados activos del ejecutor ni de la colección.

El lanzador autorizado prepara `EvaluacionV3/Resultados/RUN-G038-V3-<timestamp>/contexto_operacion.json`, con `version=3`, `version_anterior=2`, `operacion=REEVALUAR` o `REINTENTAR`, intento, autorización, run_id y los cuatro casos. El ejecutor exige esa ruta en producción y escribe el único informe `TC-M07-G038_reevaluacion_V3.md` en el RUN. Rechaza rutas V1 y V2. El login usa LoginDTO antes de abrir el sandbox. En el RUN verifica permisos, una sola ACTIVO, anexo APROBADO, fixture PENDIENTE con anexo no utilizable, altas libres y ausencia de PENDIENTE vencida activable. Si falla, cierra el sandbox sin escribir contratos. La bandeja se lee con `pagina=1&tamano=50&modulo=integracion&nivel=CRITICA`. Un aviso tipo 41 con fecha_envio de menos de 11 minutos impide el intento 11; un filtro rechazado (4xx) deja el aviso NO_CONCLUYENTE sin reintento. El aviso se acepta por ID nuevo o por mayor ocurrencias o fecha_ultima_ocurrencia posterior al intento en el mismo ID. El motivo exige anexo y mapeo junto con una negaci?n de su aprobaci?n; admite expresiones como ?anexo de mapeo no aprobado? y ?no tiene un anexo de mapeo aprobado?. La consulta ya filtra el m?dulo y el nivel; el ?tem no necesita `modulo`, pero su valor se conserva en el resumen y la evidencia cuando existe. El escenario del aviso 20902 usa una fecha local de m?s de 11 minutos para permitir comprobar la agrupaci?n sin saltarse el corte antispam.

Orden: 11 → 09 → 12 → DELETE y comprobación de base → 10 → DELETE. La gracia de MAJOR se lee de M09, sin fijarla en el alta. La versión para cada alta se elige del listado. Las líneas base y comparaciones de avisos y auditoría se guardan saneadas en `resultado.json`. Máximo 70 solicitudes y 600 s; timeout de 120 s por petición. El escenario conforme simulado empleó **39 solicitudes**.

El aviso de activación bloqueada persiste fuera del sandbox según la revisión del adaptador; el DELETE no lo revierte. Las lecturas públicas posteriores a DELETE se usan para comprobar la base sin reabrir el sandbox. Estas lecturas sin cabeceras del sandbox son intencionales: verifican la base tras DELETE sin reabrir la transaccion, igual que en G036 y G037.

## Validación local

```powershell
node --check g038.mjs
node --check pruebas/verificar.mjs
node g038.mjs --comprobar
node g038.mjs --capacidades
node pruebas/g038_local.test.mjs
node pruebas/contrato_cruzado.test.mjs
node pruebas/escenarios_g038.mjs
node pruebas/verificar.mjs
& '..\..\..\..\..\.venv\Scripts\python.exe' -m pytest -p no:cacheprovider pruebas/g038_dto_test.py -q
```

Los 20 escenarios de `escenarios_g038.json` incluyen conforme, aviso agrupado, aviso de otro modulo o nivel, filtro 4xx, falta o supresión del aviso, aviso ajeno o sin motivo, cupo lleno, PENDIENTE vencida activable, discrepancias de 09/10/12, rollback y DELETE fallidos, login inválido y privacidad. Todos indican `oficial`. `verificar.mjs` conserva pasos 1–10 y RED; en este entorno los pasos que crean procesos hijos informan `spawn EPERM`, mientras las invocaciones directas funcionan. No interpretar una simulación local como veredicto de TEST.

## SHA-256 esperado

SHA-256 esperado de `g038.mjs`: `456bdbe41a5635508598a89ec956d0664492ece7a55d826887bee111525923cb`

SHA-256 esperado de `verificar.mjs`: `8ebf03dc1dbe7e1ce8bcdc0d3f0e0969f4c2a7e508dca278c2853ee840964fc1`

SHA-256 de `simulador_g038.mjs`: `7a029018f51eae98d9f7857b12f3ba4edb307339c2892e4a1a20ff5590695a5c`

SHA-256 de `escenarios_g038.json`: `91714073b2eade7fcb572945574cbd88586b6bd4789d1167e1d63ff816d2d51f`

SHA-256 de `contrato_g038.json`: `848045c37dd2ff62307be3f4f2b2d5d9d48f6a450a415d30060d075544866462`

## Lecturas de código

Se consultaron realmente `src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py`, `domain/entities/contrato.py`, `infrastructure/adapters/alerta_administrador_adapter.py`, `infrastructure/repositories/auditoria_integracion_repository.py`, `src/configuration/infrastructure/routers/parametros_integracion_contable_router.py`, `src/configuration/infrastructure/schema/parametros_alertas_schema.py`, `src/identity_access/infrastructure/schema/notificacion_schema.py` y los DTO/rutas citados en `contrato_g038.json`. Las fuentes del oráculo son la fila G038 de la matriz y RF-98, no la implementación.
