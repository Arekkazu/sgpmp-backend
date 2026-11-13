# TC-M06-G36 - preparacion V2, ORD-G36-007

Alcance: TC-M06-009 y TC-M06-010, RF-86 restriccion 5 y CA-12/CA-13. Esta preparacion es local. No crea RUN ni consulta TEST. El oraculo proviene de Casos_Prueba(Modulo6Agrup).csv:379 (Windows-1252) y Especificacion-Requerimientos-Modulo6.md:1290,1304,1454-1456. V1 en Resultados/RUN-G36-V1-20261108-161426/ permanece intacto.

## Fuente tecnica leida

Se leyo origin/test con git show, solo lectura:

- GET /finanzas/periodos/{p}/variaciones: m06_router.py:305-310; campos de historial en valoracion_repository.py:372-388.
- GET /finanzas/lineas?id_periodo_contable: m06_router.py:280-286.
- POST /finanzas/variaciones/{id}/correctivos: m06_router.py:319-324; SolicitarCorrectivoDTO.motivo en m06_dto.py:135-137; motivo minimo y respuesta pendiente en correctivo_variacion_use_case.py:28-37,64-90.
- GET /finanzas/correctivos: m06_router.py:327-332; permite comprobar solicitudes pendientes y su ausencia tras DELETE.
- POST /finanzas/correctivos/{id_solicitud}/aprobacion: m06_router.py:335-339; respuesta aprobada y lineas inversas en correctivo_variacion_use_case.py:94-119; doble control en :136-147.
- PUT/PATCH/DELETE en las dos rutas de variacion: m06_router.py:350-356, 409 VARIACION_INMUTABLE.
- PUT/PATCH/DELETE /finanzas/lineas/{id}: m06_router.py:359-366, 409 LINEA_ASIENTO_INMUTABLE.

El codigo revisado no acredita por si solo el despliegue TEST. Las rutas M02, login y sandbox se conservaron del ejecutor vigente. No se usa /openapi.json como oraculo.

## Flujo previsto

Tres logins antes del RUN: Contador QA solicita, usuario 169 aprueba, Administrador registra pesajes M02. Segun la orden, la cuenta 169 fue preparada por SQL con autorizacion del responsable QA y se necesita para el doble control. El preflight vivo exige periodo del titular que contiene hoy en America/Bogota y ABIERTO, dos bovinos, precio vigente, matriz TB/PM y acceso del Contador 2. Si falla, no hay escrituras y se hace DELETE.

Cada caso prepara su propia variacion y linea con pesaje +2 % y procesamiento M06. 009 hace nueve intentos y compara huellas SHA-256 canonicas. 010 comprueba solicitud pendiente, inefectividad antes de aprobar, aprobacion por otro Contador, historial y linea inversa. El 403 del solicitante es observacion. El cierre hace DELETE y lecturas poscierre sin cabeceras RUN para ambos activos. RF-52, notificaciones y backlog externo quedan fuera de la comprobacion de rollback.

Presupuesto: 150 solicitudes API del ejecutor y Newman dentro del RUN; tres logins fuera. Cota planeada: 3 catalogos + 2 precios + 6 detalles/fichas/accesos + 20 bases + 2 pesajes + 2 procesamientos + 20 lecturas tras pesajes + 9 intentos + 10 lecturas tras 009 + 1 solicitud + 10 lecturas pendientes + 2 aprobaciones + 10 lecturas finales + 4 Newman + 1 DELETE + 20 poscierre = 122; reserva 28 para paginacion y conciliacion. Peticiones en serie.

RUN V2: EvaluacionV2/Resultados/RUN-G36-V2-<timestamp>/ con preflight.json, resultado.json, Newman JSON/HTML y un solo TC-M06-G36_reevaluacion_V2.md. Coleccion vigente G36.postman_collection.json; no hay Cypress.

## Validacion local

node --check g36.mjs; node --check lib/g36_core.mjs; node g36.mjs --comprobar; node pruebas/g36_env.test.mjs; node pruebas/g36_ensayo.mjs. El ensayo usa fetcher local con guarda de URL y cero peticiones remotas. La sonda de proceso hijo dio EPERM en el entorno de Codex; el responsable QA debe repetirla antes de TEST.
