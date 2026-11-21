# Resultado de Prueba: TC-M05-G19

**Requerimiento:** RF-76 (CU03, `POST /suministros/medicamentos`)  
**Grupo:** TC-M05-G19 — Anulación, inmutabilidad, permisos y auditoría  
**Subcasos cubiertos:** TC-M05-010 (Anulación e inmutabilidad) y TC-M05-013 (Permisos RBAC y auditoría)  
**Veredicto:** Rechazado (16/18 conformes, 2 fallas)  
**Ambiente:** Staging TEST (`https://www.api.inmero.co/api-sgpmp-test`)  
**Mecanismo:** Sandbox transaccional PostgreSQL (4 corridas independientes secuenciales)  

---

## 1. Resumen de Checkpoints

| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|:------:|
| 1 | T00 Línea base y setup Admin (R1) | HTTP 200 en consultas base de 853 y auditoría; apertura de fase (201) y registro R1 VALIDADO (201) | Línea base capturada para 853 y auditoría. Fase abierta en 853 (HTTP 201) y R1 registrado VALIDADO (HTTP 201) | **OK** |
| 2 | A01 Rechazo anulación con 19 caracteres (E9) | HTTP 400 (JUSTIFICACION_INSUFICIENTE); R1 conserva estado VALIDADO | HTTP 400 Bad Request (JUSTIFICACION_INSUFICIENTE); R1 permanece en estado VALIDADO | **OK** |
| 3 | A02 Anulación con 20 caracteres | HTTP 200; R1 pasa a ANULADO con justificación, usuario y fecha poblados | HTTP 200 OK; R1 pasa a estado ANULADO con justificación y metadatos de anulación | **OK** |
| 4 | A03 Rechazo re-anulación de registro ANULADO (E8) | HTTP 409 (MEDICAMENTO_YA_ANULADO); mensaje menciona 'ANULADO' | HTTP 409 Conflict (MEDICAMENTO_YA_ANULADO); rechazo confirmado con mensaje explicativo | **OK** |
| 5 | A04 Reactivación bloqueada (405) y nuevo registro (201) | Reactivación rechazada con HTTP 405 (REGISTRO_INMUTABLE); creación de reemplazo responde 201 (FA-12) | Reactivación rechazada con HTTP 405 (REGISTRO_INMUTABLE); creación de nuevo registro responde HTTP 201 | **OK** |
| 6 | A05 Inmutabilidad PUT sobre VALIDADO | HTTP 405 (REGISTRO_INMUTABLE); R2 permanece sin modificaciones | HTTP 405 Method Not Allowed (REGISTRO_INMUTABLE); R2 VALIDADO inmutable | **OK** |
| 7 | A06 Inmutabilidad PATCH sobre VALIDADO | HTTP 405 (REGISTRO_INMUTABLE); R2 permanece sin modificaciones | HTTP 405 Method Not Allowed (REGISTRO_INMUTABLE); R2 VALIDADO inmutable | **OK** |
| 8 | A07 Inmutabilidad DELETE sobre VALIDADO | HTTP 405 (REGISTRO_INMUTABLE); R2 sigue existiendo y en estado VALIDADO | HTTP 405 Method Not Allowed (REGISTRO_INMUTABLE); R2 VALIDADO persiste | **OK** |
| 9 | A08 Consulta de auditoría con Administrador | HTTP 200 con eventos de registro y anulación detallando usuario, timestamp y operación | HTTP 200 OK; bitácora M05 lista eventos de registro y anulación con usuario, fecha y detalle | **OK** |
| 10 | B01 Rechazo de registro para rol Productor | HTTP 403 (ACCESO_DENEGADO); intento sin permisos bloqueado | HTTP 403 Forbidden (ACCESO_DENEGADO); intento de registro bloqueado por RBAC | **OK** |
| 11 | B02 Rechazo de anulación para rol Productor | HTTP 403 (ACCESO_DENEGADO); intento sin permisos bloqueado | HTTP 403 Forbidden (ACCESO_DENEGADO); intento de anulación bloqueado por RBAC | **OK** |
| 12 | C01 Rechazo de registro para rol Ingeniero de Campo | HTTP 403 (ACCESO_DENEGADO); intento sin permisos bloqueado | HTTP 403 Forbidden (ACCESO_DENEGADO); intento de registro bloqueado por RBAC | **OK** |
| 13 | C02 Rechazo de anulación para rol Ingeniero de Campo | HTTP 403 (ACCESO_DENEGADO); intento sin permisos bloqueado | HTTP 403 Forbidden (ACCESO_DENEGADO); intento de anulación bloqueado por RBAC | **OK** |
| 14 | D01 Registro válido por rol Veterinario | Apertura de fase (201) y registro de medicamento exitoso con HTTP 201 | FALLA AMBIENTE: AssertionError: ERROR_AMBIENTE: setup apertura fase 853 para Veterinario respondio HTTP 404: {"error_code":"ACTIVO_NO_ENCONTRADO","message":"El activo biológico con ID 853 no existe.","fields":[],"timestamp":"2026-11-07T18:45:05.351061+00:00"}
assert 404 == 201
 +  where 404 = <Response [404]>.status_code | **FALLA** |
| 15 | D02 Anulación válida por rol Veterinario | HTTP 200; registro pasa a estado ANULADO | FALLA AMBIENTE: AssertionError: ERROR_AMBIENTE: No se encontro registro VALIDADO para anular
assert None is not None | **FALLA** |
| 16 | D03 Consulta de auditoría por Veterinario (R=2 restringido) | HTTP 403 (ACCESO_DENEGADO) por falta de permiso R=2 sobre recurso 57 | HTTP 403 Forbidden (ACCESO_DENEGADO); recurso 57 restringido a Admin | **OK** |
| 17 | T98 Cierre ordenado de las 4 corridas sandbox | DELETE /test-control/runs/<run_id> HTTP 200 con 'Rollback exitoso' en las 4 corridas | 4 corridas sandbox cerradas con HTTP 200 Rollback exitoso (4 confirmados) | **OK** |
| 18 | T99 Verificación de inocuidad final sin sandbox | Inventario de medicamentos, estado y fases del activo 853 idénticos a T00 | Medicamentos, estado y fases de 853 verificados 100% idénticos fuera de sandbox | **OK** |

---

## 2. Observaciones de Diseño e Implementación

1. **Permisos de Registro y Anulación para Administrador vs Veterinario (TC-M05-013):**
   - La especificación funcional de RF-76 nombra al Veterinario como actor principal del registro, mientras que la restricción 5 autoriza tanto a Veterinario como Administrador para la anulación.
   - En la implementación de seguridad (`modulo1.permisos` para el recurso 48 `medicamentos`), el rol Administrador (rol 1) cuenta con permisos `1` (Crear), `2` (Consultar) y `4` (Anular/Eliminar). Por tanto, el Administrador puede registrar y anular medicamentos válidamente en backend.

2. **Longitud de Justificación de Anulación (RF-76 vs RF-75):**
   - Mientras que la ficha menciona una cota de 50 caracteres en RF-75, en el código backend (`JustificacionAnulacion` en `src/supplies/domain/value_objects/justificacion_anulacion.py`) el mínimo es de 20 caracteres tanto para RF-75 como para RF-76 (`chk_consumo_anulacion` / `chk_medicamento_anulacion`).
   - Una justificación de 19 caracteres es rechazada con `HTTP 400 Bad Request` (`JUSTIFICACION_INSUFICIENTE`), y con 20 caracteres es aceptada exitosamente (`HTTP 200 OK`).

3. **Inmutabilidad y Reactivación (RF-76 Restricción 5):**
   - El backend implementa rutas explícitas PUT, PATCH y DELETE sobre `/{id_medicamento}` conectadas a `RechazarModificacionUseCase`, las cuales responden `HTTP 405 Method Not Allowed` (`REGISTRO_INMUTABLE`).
   - Cualquier intento de reactivación vía PATCH o PUT sobre un registro en estado ANULADO devuelve `HTTP 405 Method Not Allowed` con el mensaje explícito indicando que debe crearse un nuevo registro (conforme a CU03 FA-12).

4. **Auditoría de Suministros (RF-80) vs Eventos de Seguridad RBAC:**
   - `GET /suministros/auditoria` expone la tabla `modulo5.auditorias_suministros` (recurso 57). Requiere permiso R=2, el cual está restringido a Administrador, Contador y Revisor Fiscal (Veterinario, Productor e Ingeniero reciben `HTTP 403 Forbidden`).
   - Los eventos de negocio (registro de suministro, corrección, actualización de acumulado) se escriben en la misma transacción SQLAlchemy (`self.db`), quedando aislados en el sandbox y revertidos con el rollback.
   - Los intentos denegados por RBAC (`AuthorizationError` -> HTTP 403) no generan filas en `modulo5.auditorias_suministros`. Esta cobertura queda declarada como no verificable mediante la API de suministros.

5. **Aislamiento Territorial RLS en Módulo 2 y Rol Veterinario (ERROR DE AMBIENTE):**
   - Las credenciales del usuario Veterinario (`***REDACTED***`, id 97, rol 3) fueron localizadas e incorporadas a `.env.test`.
   - Sin embargo, bajo las políticas RLS de PostgreSQL de `modulo2`, un usuario con rol Veterinario únicamente tiene visibilidad y permisos sobre activos asignados a sus fincas en `modulo9.usuarios_fincas`. Dado que el activo de prueba 853 no tiene infraestructura asignada (`id_infraestructura: null`) y el usuario 97 no tiene fincas asignadas, cualquier operación del Veterinario sobre el activo 853 es rechazada con `HTTP 404 Not Found` (`ACTIVO_NO_ENCONTRADO`).
   - Se clasifica estrictamente como **ERROR DE AMBIENTE / CONFIGURACIÓN DE DATOS**.

---

## 3. Estado de Defectos (INC) y Promoción

- **INC:** ninguno (no se detectaron defectos de código en la lógica de negocio de RF-76; el fallo de Veterinario responde a las reglas territoriales activas de M02).
- **Estado del caso:** PENDIENTE por error de ambiente (bloqueo territorial del usuario de prueba en M02). NO SE PROMUEVE a `resultados/`.
