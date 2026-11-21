# Resultado de Prueba: TC-M05-G37
## Persistencia y Clasificación de Eventos (RF-80)

- **ID Caso:** TC-M05-G37 (TC-M05-026 y TC-M05-027)
- **Veredicto:** Rechazado (9/10 OK, 1 Fallas)
- **Fecha:** 2026-11-07 18:31:10 (America/Bogota)
- **Duración:** 10.51 s

### Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Conteo inicial de eventos y creacion de activo con ciclo | HTTP 200 en auditoria base, HTTP 201 en activo QA y apertura de fase productiva | HTTP 200 en auditoria base, HTTP 201 en activo QA y apertura de fase productiva | OK |
| 2 | A01 Registro de suministro directo RF-78 y persistencia <= 2 s | HTTP 200, evento SUMINISTRO_REGISTRADO persistido <= 2 s con campos base RF-10 y de extension M05 | HTTP 200, evento SUMINISTRO_REGISTRADO persistido <= 2 s con campos base RF-10 y de extension M05 | OK |
| 3 | A01 Cierre de ciclo productivo RF-79 y eventos de consolidacion <= 2 s | HTTP 200, eventos CICLO_CONSOLIDADO y REPORTE_COSTOS_GENERADO en auditoria <= 2 s | HTTP 200, eventos CICLO_CONSOLIDADO y REPORTE_COSTOS_GENERADO en auditoria <= 2 s | OK |
| 4 | A01 Consulta de historial de suministros RF-81 y persistencia <= 2 s | HTTP 200, evento CONSULTA_HISTORIAL_EJECUTADA en auditoria <= 2 s | HTTP 200, evento CONSULTA_HISTORIAL_EJECUTADA en auditoria <= 2 s | OK |
| 5 | A02 Registro de evento con resultado FALLIDO o RECHAZADO ante operacion invalida | Evento en auditoria con resultado FALLIDO/RECHAZADO persistido <= 2 s ante operacion rechazada | AssertionError: DEFECTO_PRODUCTO (RF-80 CA-1 / TC-M05-026.1): La especificacion exige que las operaciones fallidas se registren en la bitacora con resultado FALLIDO o RECHAZADO en <= 2 s. El backend respondio HTTP 409 (CICLO_NO_ACTIVO) pero registro 0 eventos fallidos en modulo5.auditorias_suministros para el activo 984. | FALLA |
| 6 | A03 Consistencia entre consulta por filtros en lista y consulta por detalle /{id} | HTTP 200 en ambos endpoints, identidad de campos entre lista y detalle | HTTP 200 en ambos endpoints, identidad de campos entre lista y detalle | OK |
| 7 | B01 Clasificacion y retencion diferenciada (NIC41 / 5 años vs TECNICO / 1 año) | Eventos contables clasificados como NIC41 con 5 años de retencion; operativos como TECNICO con 1 año | Eventos contables clasificados como NIC41 con 5 años de retencion; operativos como TECNICO con 1 año | OK |
| 8 | B02 Clasificacion por defecto de tipo no catalogado como NIC41 / 5 años (nivel unidad) | Funcion de clasificacion asigna ('NIC41', '5 años') ante tipo desconocido | Funcion de clasificacion asigna ('NIC41', '5 años') ante tipo desconocido | OK |
| 9 | T98 Cierre ordenado de sandbox Administrador y rollback | HTTP 200 con confirmacion de rollback exitoso | HTTP 200 con confirmacion de rollback exitoso | OK |
| 10 | T99 Verificacion de inocuidad y reversion de datos fuera de sandbox | Conteo final de auditoria identico al conteo base antes de la prueba | Conteo final de auditoria identico al conteo base antes de la prueba | OK |

### Diagnóstico de Fallas
- **Defecto de Producto en A02 (RF-80 CA-1 / TC-M05-026.1):**
  La especificación estipula que toda operación de suministro debe auditarse, y si la operación falla, debe registrarse un evento con resultado FALLIDO o RECHAZADO en <= 2 s.
  En la implementación actual, los rechazos de validación de negocio (HTTP 4xx como `FECHA_FUERA_DE_RANGO` o `VAL_ENTRADA`) retornan el error HTTP inmediatamente sin escribir en `modulo5.auditorias_suministros`. El mecanismo `_registrar_fallo` en `RegistrarSuministroDirectoUseCase` solo se activa tras agotar 3 reintentos de errores transitorios de infraestructura (`InfrastructureError`, `ServiceUnavailableError`), dejando sin auditar los rechazos de negocio de la API.
