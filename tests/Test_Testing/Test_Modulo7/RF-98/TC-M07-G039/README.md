# TC-M07-G039 - reevaluacion V2 local (ORD-G039-010)

Estado: preparacion local. No se accedio a TEST, no se creo RUN oficial y no hay veredicto de producto. Casos TC-M07-13, 14, 15 y 16; RF-98 v1.2. Correcciones informadas: 04bddac4 y 20b5f701.

## Inventario

- Ejecutor canonico: g039.mjs.
- Coleccion Newman vigente: G039.postman_collection.json (tres lecturas dentro del sandbox).
- Cypress: no aplica a la matriz del grupo; no hay spec ni config.
- Contrato de respuestas y citas: lib/contrato.mjs y pruebas/contrato_g039.json.
- Simulador y validaciones locales: pruebas/simulador_g039.mjs, escenarios_g039.mjs/json, contrato_cruzado.test.mjs, g039_local.test.mjs, g039_dto_test.py y verificar.mjs.
- Lanzador Newman: pruebas/newman_hijo.mjs.
- Evidencia historica V1: Resultados/RUN-G039-V1-20261118-161622, solo lectura. Sin duplicados activos ni archivos de legado fuera de esa evidencia.

Fuentes de codigo consultadas en lectura: src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py; src/accounting_integration/infrastructure/routers/m07_router.py; src/accounting_integration/infrastructure/dto/m07_dto.py; src/accounting_integration/domain/entities/contrato.py y evento_integracion.py; src/accounting_integration/infrastructure/repositories/contrato_repository.py y auditoria_integracion_repository.py; src/accounting_integration/infrastructure/adapters/alerta_administrador_adapter.py; src/identity_access/infrastructure/repositories/notificacion_repository.py y schema/notificacion_schema.py; src/configuration/infrastructure/routers/parametros_integracion_contable_router.py. Se leyo la fila TC-M07-G039 de Casos_Prueba(Modulo7Agrup).csv y RF-98 en Especificacion-Requerimientos-Modulo7.md.

## Flujo V2

CAPACIDADES: reevaluar/reintentar, version 2. dirRun escribe exclusivamente en EvaluacionV2/Resultados/RUN-G039-V2-<timestamp>. El contexto exige version_anterior=1. El login se hace antes del RUN, con correo_electronico y contrasena, sin cabeceras de sandbox.

El preflight se ejecuta dentro del RUN y bloquea escrituras si no hay una unica vigente ACTIVO, PENDIENTE e INACTIVO, permisos de contratos R/U (acciones 2/3) y auditoria R (accion 2), gracia minima M09 <=90, alguna PENDIENTE vencida activable o aviso tipo 41 con menos de 11 minutos. Si bloquea, se ejecuta DELETE y se informa NO_CONCLUYENTE.

Orden: 14 repeticion (activar ACTIVO), lectura inmediata de bandeja y comprobacion de aviso nuevo o agrupado; 14 salto (deprecar PENDIENTE); 15 PATCH/PUT sobre ACTIVO con descripcion valida; 13 deprecar ACTIVO con 90 dias; 14 retroceso (activar ese DEPRECADO); 16 activar y deprecar INACTIVO. Cada rechazo se coteja con un evento WARNING nuevo por UUID y con el listado intacto. El aviso de CA-27 se exige al primer rechazo segun D3; los posteriores se observan bajo antispam. Los eventos y avisos pueden persistir fuera del sandbox. DELETE y lectura publica poscierre verifican la firma de contratos.

Limites: 70 solicitudes, 600 segundos, timeout por solicitud 120 segundos, peticiones en serie, sin reintentos de escritura. El conforme local usa 58 solicitudes, incluidas tres lecturas Newman, DELETE y lectura poscierre. El simulador conserva eventos y avisos fuera del sandbox y modela antispam y agrupacion. Hay 18 escenarios locales; la auditoria usa la primera pagina filtrada (ordenada por fecha descendente) y compara UUID nuevos.

## Validacion local

node --check para los .mjs, node g039.mjs --comprobar, node g039.mjs --capacidades, node pruebas/g039_local.test.mjs, node pruebas/contrato_cruzado.test.mjs, node pruebas/escenarios_g039.mjs, Pydantic con pytest y node pruebas/verificar.mjs. El verificador conserva pasos 1-10 y RED; los pasos que requieren spawn pueden devolver EPERM por el sandbox y se informan como SANDBOX.

## SHA-256

SHA-256 esperado de `g039.mjs`: `075929afc224ece83dae362eb8b0f25e1e83e6e3d653bbaf8bddac4a7e2f3cb1`

SHA-256 esperado de `verificar.mjs`: `5503fb83b1461e5f5b0bd1c57217b77ecf1e7cb258a1d0c6ae6acd91ed1b8be7`
