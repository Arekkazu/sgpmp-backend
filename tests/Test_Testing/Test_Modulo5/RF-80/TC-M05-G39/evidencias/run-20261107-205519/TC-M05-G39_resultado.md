# Resultado de Prueba: TC-M05-G39
## Campos Mínimos, Inmutabilidad, Hash e Idempotencia (RF-80)

- **ID Caso:** TC-M05-G39 (TC-M05-092, TC-M05-093 y TC-M05-094 / Agrupados: 028, 029 y 030)
- **Veredicto:** Rechazado (4/8 OK, 4 Fallas)
- **Fecha:** 2026-11-07 20:55:41 (America/Bogota)
- **Duración:** 19.82 s

### Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Admin Conteo inicial de eventos y creacion de activo con operacion RF-78 | HTTP 200 en auditoria base, HTTP 201 en activo QA y HTTP 200 en suministro registrado | HTTP 200 en auditoria base, HTTP 201 en activo QA y HTTP 200 en suministro registrado | OK |
| 2 | A02 Consulta de evento incompleto y presencia de detalle_causa (TC-M05-092 / 028) | HTTP 200 con registro_incompleto=true y detalle_causa no nulo detallando campos faltantes (CA-12 / CU06 FA-05) | AssertionError: DEFECTO_PRODUCTO (RF-80 CA-12 / CU06 FA-05 / TC-M05-092 / 028): La especificacion requiere que los eventos con registro_incompleto=true incluyan en detalle_causa la lista de campos faltantes (ej. 'Campos faltantes: ...'). El evento 87 tiene registro_incompleto=true pero detalle_causa es null. | FALLA |
| 3 | B01 Superficie de escritura exclusiva GET en OpenAPI (TC-M05-093 / 029) | 0 metodos de modificacion (POST/PUT/PATCH/DELETE) expuestos bajo /suministros/auditoria* en OpenAPI | 0 metodos de modificacion (POST/PUT/PATCH/DELETE) expuestos bajo /suministros/auditoria* en OpenAPI | OK |
| 4 | B02 Inmutabilidad rechazo 405 y registro de evento de seguridad (TC-M05-093 / 029) | HTTP 405 Method Not Allowed en PUT/PATCH/DELETE, hash inalterado y registro de evento de seguridad | AssertionError: DEFECTO_PRODUCTO (RF-80 Restr. 1 / CA-2 / RNF-05 / TC-M05-093 / 029): La especificacion de inmutabilidad exige que todo intento de modificacion no permitido (PUT/PATCH/DELETE) sea rechazado y registrado como evento de seguridad en la bitacora. El sistema respondio HTTP 405 pero registro 0 eventos con resultado RECHAZADO en modulo5.auditorias_suministros (conteo=0) y 0 eventos en modulo1.eventos (conteo=0). | FALLA |
| 5 | B03 Verificacion de formula y cobertura del hash SHA-256 (TC-M05-093 / 029) | La formula de calculo debe cubrir todas las columnas excluyendo unicamente 'hash_integridad' | AssertionError: DEFECTO_PRODUCTO (RF-80 CA-6 / Restr. 5 / TC-M05-093 / 029): La especificación exige que el hash de integridad cubra la totalidad de columnas del registro excluyendo ÚNICAMENTE 'hash_integridad'. La función en base de datos excluye indebidamente columnas ajenas/muertas: ['hash_integridad', 'creado_en', 'id_registro_suministro']. | FALLA |
| 6 | C01 Presencia de id_evento_m05 para deduplicacion at-least-once (TC-M05-094 / 030) | Campo 'id_evento_m05' (UUID unico) presente en la entidad de auditoria para deduplicacion | AssertionError: DEFECTO_PRODUCTO (RF-80 Restr. 9 / CA-14 / RNF-09 / TC-M05-094 / 030): La especificacion de deduplicacion exige que cada registro de auditoria contenga el campo 'id_evento_m05' (UUID unico emitido por el componente de M05 antes de publicar). La API y la tabla modulo5.auditorias_suministros carecen de esta columna/propiedad (solo disponen de id_auditoria_suministro de tipo entero). | FALLA |
| 7 | T98 Admin Cierre ordenado de sandbox Administrador y rollback | HTTP 200 con confirmacion de rollback exitoso | HTTP 200 con confirmacion de rollback exitoso | OK |
| 8 | T99 Admin Verificacion de inocuidad tras corrida Administrador | Conteo final de auditoria identico al conteo inicial | Conteo final de auditoria identico al conteo inicial | OK |

### Diagnóstico de Fallas (Defectos de Producto)
- **Falla en A02 (TC-M05-092 / 028 - RF-80 CA-12 / CU06 FA-05):**
  Los eventos con `registro_incompleto=true` (ej. evento 87 `CICLO_CONSOLIDADO`, 88, 89 en `modulo5.auditorias_suministros`) tienen `detalle_causa = null` en lugar de listar los campos faltantes (ej. 'Campos faltantes: ...').
- **Falla en B02 (TC-M05-093 / 029 - RF-80 Restr. 1 / CA-2 / RNF-05):**
  Los intentos de modificación indebida (PUT, PATCH, DELETE) retornan correctamente HTTP 405 Method Not Allowed y el hash_integridad permanece intacto, pero el router no genera ni persiste un evento de seguridad con resultado 'RECHAZADO' en `modulo5.auditorias_suministros` (conteo=0) ni en `modulo1.eventos` (conteo=0).
- **Falla en B03 (TC-M05-093 / 029 - RF-80 CA-6 / Restr. 5):**
  La función `modulo5.calcular_hash_integridad()` excluye indebidamente las columnas `creado_en` e `id_registro_suministro` además de `hash_integridad`. Dichas columnas ni siquiera existen en el esquema de `modulo5.auditorias_suministros` (código muerto heredado de otro trigger) violando el principio normativo de cubrir la totalidad de columnas.
- **Falla en C01 (TC-M05-094 / 030 - RF-80 Restr. 9 / CA-14 / RNF-09):**
  La entidad y tabla de auditoría carecen de la columna/propiedad `id_evento_m05` (UUID único emitido antes de publicar para deduplicación at-least-once). Solo existe la clave primaria serial `id_auditoria_suministro`.

### Cobertura No Ejecutada Declarada
- **A01 (TC-M05-092 / 028):** Invocación unitaria de función pura de validación de campos mínimos. No ejecutable al no existir validador unitario puro en backend (la validación la ejercen constraints de Postgres en repositorio).
