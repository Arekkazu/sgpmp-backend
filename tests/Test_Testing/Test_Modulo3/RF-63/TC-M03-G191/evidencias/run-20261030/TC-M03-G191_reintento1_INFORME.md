# TC-M03-G191 — Reintento 1

## Ambiente
- **BD:** PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`)
- **Usuario:** `member_qa`
- **Fecha:** 2026-10-30 08:59 (America/Bogota)

## Resultado general
- **Checkpoints evaluados:** 5
- **PASSED:** 1
- **FAILED:** 3
- **SKIPPED:** 1
- **Veredicto:** RECHAZADO (Bloqueo de Infraestructura / Privilegios RLS)

## Resultado por subcaso
- **`test_367a_sin_tipo_evento_se_registra_incompleto`:** FAILED
  - **Detalle:** Error de base de datos durante la consulta de verificación (`buscar_evento_por_descripcion`).
  - **Excepción:** `sqlalchemy.exc.ProgrammingError: (psycopg2.errors.InsufficientPrivilege) permission denied for function fn_es_usuario_servicio`
  - **Línea:** `test_tc_m03_g191.py:49` -> `helpers_tc_m03_g191.py:46` -> `query.py:2766`
- **`test_367b_sin_componente_origen_se_registra_incompleto`:** FAILED
  - **Detalle:** Error de base de datos durante la consulta de verificación (`buscar_evento_por_descripcion`).
  - **Excepción:** `sqlalchemy.exc.ProgrammingError: (psycopg2.errors.InsufficientPrivilege) permission denied for function fn_es_usuario_servicio`
  - **Línea:** `test_tc_m03_g191.py:82` -> `helpers_tc_m03_g191.py:46` -> `query.py:2766`
- **`test_367c_sin_timestamp_se_registra_incompleto`:** SKIPPED
  - **Razón del skip:** Decisión de diseño de Desarrollo (commit `79075257a4`, 2026-10-25): `fecha_evento` es opcional con fallback a `now(timezone.utc)`. No se considera campo faltante ni activa `registro_incompleto=True`. Caso no evaluable como incompleto.
- **`test_367d_evento_completo_registra_incompleto_false`:** FAILED
  - **Detalle:** Error de base de datos durante la consulta de verificación (`buscar_evento_por_descripcion`).
  - **Excepción:** `sqlalchemy.exc.ProgrammingError: (psycopg2.errors.InsufficientPrivilege) permission denied for function fn_es_usuario_servicio`
  - **Línea:** `test_tc_m03_g191.py:117` -> `helpers_tc_m03_g191.py:46` -> `query.py:2766`
- **`test_367e_post_manual_rechazado`:** PASSED
  - **Detalle:** Verificación de Restricción 4.4 vía HTTP (`sandbox_client.post('/iot/auditoria')`). El backend responde correctamente `405 Method Not Allowed`, impidiendo la inserción manual directa de eventos por parte de usuarios externos.

## Hallazgos
1. **Bloqueo RLS por Privilegio Faltante en PostgreSQL TEST (CRÍTICO):**
   - Los subcasos `367a`, `367b` y `367d` fallan de manera uniforme al intentar leer el registro persistido en `modulo3.bitacora_auditoria_iot`.
   - **Causa Raíz:** Las políticas RLS (Row Level Security) activadas en `modulo3.bitacora_auditoria_iot` evalúan `modulo1.fn_es_usuario_servicio()`. El usuario de prueba `member_qa` carece de permisos `EXECUTE` sobre dicha función en PostgreSQL TEST:
     ```text
     psycopg2.errors.InsufficientPrivilege: permission denied for function fn_es_usuario_servicio
     [SQL: SELECT modulo3.bitacora_auditoria_iot.id_evento AS ... FROM modulo3.bitacora_auditoria_iot WHERE ...]
     [SQLSTATE: 42501]
     ```
   - **Acción Requerida:** Aplicar la solicitud formal generada en `SOLICITUD_GRANT_DBA.md` ejecutando:
     ```sql
     GRANT EXECUTE ON FUNCTION modulo1.fn_es_usuario_servicio() TO member_qa;
     ```
2. **Cumplimiento de Restricción 4.4 Confirmado:**
   - El subcaso `367e` validó exitosamente que no existe endpoint expuesto para inyección manual no autorizada de eventos de auditoría IoT.
3. **Decisión de Diseño en Subcaso 367c:**
   - Subcaso documentado y omitido según el diseño de Dev (commit `79075257a4`).

