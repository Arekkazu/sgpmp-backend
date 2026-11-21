# Resultado de Prueba: TC-M05-G19

- **Requerimiento:** RF-76 (CU03) - Gestión de Medicamentos
- **Subcasos:** TC-M05-010 (Anulación e Inmutabilidad) y TC-M05-013 (Permisos RBAC y Auditoría)
- **Veredicto:** **Aprobado** (18/18 checkpoints OK, 0 fallas)
- **Ambiente:** TEST (`https://www.api.inmero.co/api-sgpmp-test`)
- **Staging de Evidencias:** `run-20261107-144439`

---

## 1. Matriz de Checkpoints

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
| 14 | D01 Registro válido por rol Veterinario | Apertura de fase (201) y registro de medicamento exitoso con HTTP 201 | HTTP 201 Created registrado exitosamente por Veterinario | **OK** |
| 15 | D02 Anulación válida por rol Veterinario | HTTP 200; registro pasa a estado ANULADO | HTTP 200 OK anulado exitosamente por Veterinario | **OK** |
| 16 | D03 Consulta de auditoría por Veterinario (R=2 restringido) | HTTP 403 (ACCESO_DENEGADO) por falta de permiso R=2 sobre recurso 57 | HTTP 403 Forbidden (ACCESO_DENEGADO); recurso 57 restringido a Admin | **OK** |
| 17 | T98 Cierre ordenado de las 4 corridas sandbox | DELETE /test-control/runs/<run_id> HTTP 200 con 'Rollback exitoso' en las 4 corridas | 4 corridas sandbox cerradas con HTTP 200 Rollback exitoso (4 confirmados) | **OK** |
| 18 | T99 Verificación de inocuidad final sin sandbox | Inventario de medicamentos, estado y fases del activo 853 idénticos a T00 | Medicamentos, estado y fases de 853 verificados 100% idénticos fuera de sandbox | **OK** |

---

## 2. Observaciones de Diseño e Implementación

1. **Causa Real del 404 Original del Veterinario (Hechos Observados):**
   - El activo 853 tiene `id_infraestructura: 389` (perteneciente a la Finca 1).
   - En la consulta a `GET /usuarios/me`, el usuario Veterinario (`***REDACTED***`, id 97, rol 3) tenía originalmente asignadas únicamente las fincas 84 (*Finca Juan Carlos*) y 184 (*Finca Prueba Alfa*). No tenía asignada la Finca 1.
   - En la arquitectura de seguridad (`src/shared/alcance_finca_adapter.py:30-45`), el Administrador es el único rol con alcance global (`es_global`). Todo rol operativo (como Veterinario) está estrictamente restringido a las fincas asignadas en `modulo9.usuarios_fincas`. Por ello, el activo 853 resultaba inaccesible (HTTP 404 `ACTIVO_NO_ENCONTRADO`) para el Veterinario.
   - **Asignación temporal (Opción A):** Para posibilitar la ejecución del rol Veterinario sobre el activo 853, se ejecutó un `PUT /usuarios/97/fincas` con token de Administrador asignando temporalmente `[1, 84, 184]`.
   - **Restauración:** Al finalizar la corrida, se restauró la lista original exacta `[84, 184]` mediante un login nuevo de Administrador, verificando por lectura que el usuario 97 retornó a su estado original.

2. **Permisos de Registro y Anulación para Administrador vs Veterinario (TC-M05-013):**
   - La especificación funcional de RF-76 nombra al Veterinario como actor principal del registro, mientras que la restricción 5 autoriza tanto a Veterinario como Administrador para la anulación.
   - En la implementación de seguridad (`modulo1.permisos` para el recurso 48 `medicamentos`), el rol Administrador (rol 1) cuenta con permisos `1` (Crear), `2` (Consultar) y `4` (Anular/Eliminar). Por tanto, el Administrador puede registrar y anular medicamentos válidamente en backend.

3. **Longitud de Justificación de Anulación (RF-76 vs RF-75):**
   - Mientras que la ficha menciona una cota de 50 caracteres en RF-75, en el código backend (`JustificacionAnulacion` en `src/supplies/domain/value_objects/justificacion_anulacion.py`) el mínimo es de 20 caracteres tanto para RF-75 como para RF-76 (`chk_consumo_anulacion` / `chk_medicamento_anulacion`).
   - Una justificación de 19 caracteres es rechazada con `HTTP 400 Bad Request` (`JUSTIFICACION_INSUFICIENTE`), y con 20 caracteres es aceptada exitosamente (`HTTP 200 OK`).

4. **Inmutabilidad y Reactivación (RF-76 Restricción 5):**
   - El backend implementa rutas explícitas PUT, PATCH y DELETE sobre `/{id_medicamento}` conectadas a `RechazarModificacionUseCase`, las cuales responden `HTTP 405 Method Not Allowed` (`REGISTRO_INMUTABLE`).
   - Cualquier intento de reactivación vía PATCH o PUT sobre un registro en estado ANULADO devuelve `HTTP 405 Method Not Allowed` con el mensaje explícito indicando que debe crearse un nuevo registro (conforme a CU03 FA-12).

5. **Auditoría de Suministros (RF-80) vs Eventos de Seguridad RBAC (T3 / Paso 4):**
   - `GET /suministros/auditoria` expone la tabla `modulo5.auditorias_suministros` (recurso 57). Requiere permiso R=2, el cual está restringido a Administrador, Contador y Revisor Fiscal (Veterinario, Productor e Ingeniero reciben `HTTP 403 Forbidden`).
   - Los eventos de negocio (registro de suministro, corrección, actualización de acumulado) se escriben en la misma transacción SQLAlchemy (`self.db`), quedando aislados en el sandbox y revertidos con el rollback.
   - Los intentos denegados por RBAC (`AuthorizationError` -> HTTP 403) provienen de la dependencia genérica `require_permission` de `src/shared/rbac.py`, la cual no posee adaptador de auditoría (a diferencia de M02 con `require_permission_m02`). Por tanto, no generan filas en `modulo5.auditorias_suministros` ni en `modulo1.eventos_auditoria`.
   - Conforme a la regla T3, se declara como cobertura no verificable mediante la API de suministros, sin agregarse checkpoints B03/C03.

---

## 3. Estado de Defectos (INC) y Promoción

- **INC:** ninguno (no se detectaron defectos de código en la lógica de negocio de RF-76; el flujo completo de validaciones, anulación, inmutabilidad y permisos opera conforme a especificación).
- **Estado de Promoción:** PROMOVIDO a resultados/.

---

## 4. Análisis de Código sobre Auditoría RBAC y Accesos Denegados (Tarea Anexa)

*(Inferencia por análisis estático de código)*
1. `src/biological_assets/infrastructure/rbac_auditoria.py` define `require_permission_m02`, que audita rechazos 403 (RF-52) invocando `RegistrarAccesoNoAutorizadoUseCase` para persistir en la tabla `modulo2.bitacora_auditoria_m02` (modelo `BitacoraAuditoriaM02Model`).
2. En cambio, `src/shared/rbac.py` (`require_permission`) y el manejador global de `AuthorizationError` solo lanzan y transforman la excepción a HTTP 403; no escriben en ninguna tabla de auditoría de seguridad (RF-10 no está implementado de forma transversal en el RBAC compartido ni en M05).
3. Cuando `require_permission_m02` audita en M02, lo hace usando la misma sesión/transacción de la petición (`db: Session = Depends(get_db)`), por lo que si la transacción hiciera rollback, el registro se revertiría.
4. En M05, el endpoint de lectura de auditoría es `GET /suministros/auditoria` (recurso 57 `bitacora_auditoria_suministros`), que consulta `modulo5.auditoria_suministros` y está restringido a los roles Administrador, Contador y Revisor Fiscal (acción 2); no expone intentos de acceso denegados de seguridad.

