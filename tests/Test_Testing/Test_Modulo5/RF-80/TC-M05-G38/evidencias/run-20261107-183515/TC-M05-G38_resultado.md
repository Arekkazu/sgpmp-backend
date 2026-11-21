# Resultado de Prueba: TC-M05-G38
## Consulta de Bitácora y Cadena de Custodia (RF-80)

- **ID Caso:** TC-M05-G38 (TC-M05-032 y TC-M05-044)
- **Veredicto:** Rechazado (7/11 OK, 4 Fallas)
- **Fecha:** 2026-11-07 18:35:32 (America/Bogota)
- **Duración:** 15.39 s

### Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Admin Conteo inicial de eventos y creacion de activo con operaciones | HTTP 200 en auditoria base, HTTP 201 en activo QA y HTTP 200 en suministros | HTTP 200 en auditoria base, HTTP 201 en activo QA y HTTP 200 en suministros | OK |
| 2 | A01 Cadena de custodia cronologica con doble timestamp visible | Secuencia completa de eventos del activo ordenada cronologicamente con fecha_evento y fecha_emision visibles | Secuencia completa de eventos del activo ordenada cronologicamente con fecha_evento y fecha_emision visibles | OK |
| 3 | A02 Exportacion de bitacora en CSV, XLSX y PDF con filtro de activo | HTTP 200 con archivo valido segun formato (CSV, XLSX, PDF); HTTP 400 ante formato no soportado | AssertionError: assert 'VAL_ENTRADA' == 'FORMATO_EXPORTACION_INVALIDO' | FALLA |
| 4 | B01 Validacion de filtros invalidos (formato de fecha y rango invertido) | HTTP 4xx con mensaje explicativo ante formato invalido o fecha_desde > fecha_hasta | AssertionError: DEFECTO_PRODUCTO (TC-M05-044.1 / RNF Validacion): La especificacion requiere que la combinacion invalida fecha_desde > fecha_hasta retorne HTTP 4xx con mensaje explicativo. Obtenido HTTP 200 (el endpoint retorno 200 con lista vacia sin validar la coherencia temporal de los filtros). | FALLA |
| 5 | B02 Consulta sin coincidencias (200 lista vacia) y registro de consulta en bitacora | HTTP 200 con lista vacia y registro de la consulta (+1 evento) segun CU06 FA-02 | AssertionError: DEFECTO_PRODUCTO / CONFLICTO DE DISENO (CU06 FA-02 vs Catalogo / TC-M05-044.2): La especificacion CU06 FA-02 establece que la ejecucion de consultas a la bitacora debe auditarse (+1 evento). El conteo total se mantuvo en 52731 (sin incremento), ya que ConsultarAuditoriaSuministrosUseCase no implementa auto-auditoria al no haberse definido un evento de negocio para consultas a la bitacora de M05. | FALLA |
| 6 | T98 Admin Cierre ordenado de sandbox Administrador y rollback | HTTP 200 con confirmacion de rollback exitoso | HTTP 200 con confirmacion de rollback exitoso | OK |
| 7 | T99 Admin Verificacion de inocuidad y reversion de datos fuera de sandbox | Conteo final de auditoria identico al conteo inicial | Conteo final de auditoria identico al conteo inicial | OK |
| 8 | C01 Vet Restriccion de acceso RBAC a endpoints de auditoria para Veterinario | HTTP 403 ACCESO_DENEGADO en lista, detalle y exportar sin fuga de datos en la respuesta | HTTP 403 ACCESO_DENEGADO en lista, detalle y exportar sin fuga de datos en la respuesta | OK |
| 9 | C02 Vet Registro de evento de seguridad ante intento de acceso denegado | Incremento (+1) en eventos de seguridad/rechazo tras intentos denegados | AssertionError: DEFECTO_PRODUCTO (RF-80 / TC-M05-044.3): La especificacion de seguridad requiere que los intentos de acceso denegados a la bitacora de auditoria registren un evento de seguridad. El backend respondio HTTP 403 ACCESO_DENEGADO ante las 3 solicitudes del Veterinario pero registro 0 eventos con resultado RECHAZADO en modulo5.auditorias_suministros. | FALLA |
| 10 | C98 Vet Cierre ordenado de sandbox Veterinario y rollback | HTTP 200 con confirmacion de rollback exitoso | HTTP 200 con confirmacion de rollback exitoso | OK |
| 11 | C99 Vet Verificacion de inocuidad tras corrida Veterinario | Conteo final de auditoria identico al conteo inicial | Conteo final de auditoria identico al conteo inicial | OK |

### Diagnóstico de Fallas (Defectos de Producto)
- **Falla en B01 (RF-80 / TC-M05-044.1):**
  La combinación inválida `fecha_desde > fecha_hasta` retorna HTTP 200 con lista vacía en lugar de HTTP 4xx con mensaje explicativo de corrección. El endpoint no valida la coherencia temporal de los parámetros de fecha.
- **Falla en B02 (RF-80 CU06 FA-02 vs Catálogo / TC-M05-044.2):**
  La especificación CU06 FA-02 estipula que las consultas a la bitácora deben auto-auditarse (+1 evento). En la implementación actual, `ConsultarAuditoriaSuministrosUseCase` es de solo lectura y no audita la consulta por no existir un tipo de evento en el catálogo para "consulta de bitácora".
- **Falla en C02 (RF-80 / TC-M05-044.3):**
  Los intentos de acceso no autorizados denegados con HTTP 403 (Veterinario) no generan un evento de seguridad en `modulo5.auditorias_suministros` ni en `modulo1.eventos`. El middleware RBAC (`src/shared/rbac.py`) lanza `AuthorizationError` sin persistir trazas de seguridad.

### Cobertura No Ejecutada Declarada
- **B03 (044.4) Fallo forzado de M12:** No ejecutable en ambiente sandbox al no existir broker externo ni inyector de fallas en red/BD.
