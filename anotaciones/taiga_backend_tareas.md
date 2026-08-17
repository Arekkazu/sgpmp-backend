# Tareas [Back-end] — Taiga

- **Proyecto:** SGPMP DESARROLLO (`arekkazu-sgpmp-desarrollo`, id `1802172`)
- **Criterio:** user stories con etiqueta `back-end`
- **Total:** 30 tareas
- **Generado:** 2026-08-15

> Los campos siguientes reproducen los datos tal como están en Taiga (sin interpretación).

---

# Módulo 1 — Identity & Access: cierre de gaps

## Sprint 1 — Crítico y fundacional

### #6 — [Back-end] RF-11: Bloquear/eliminar endpoint legacy GET /usuarios/ sin auth

| Campo | Valor |
|---|---|
| Ref / ID | 6 / 9463904 |
| Estado | Done |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p0-critico |
| Módulo | m1 |
| Etiquetas | p0-critico, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 2 |
| Creado | 2026-08-07T18:45:40.527Z |
| Modificado | 2026-08-14T03:50:13.278Z |
| Terminado | 2026-08-15T05:44:30.309Z |
| Bloqueada | No |

**Descripción:** Estimación: 2 pts. Existe un endpoint más viejo (GET /usuarios/) sin autenticación ni control de acceso que devuelve todos los usuarios con todos sus campos sin enmascarar (identificación, teléfono, dirección, género). Fuga de datos personales real si queda expuesto en producción. Fix: eliminarlo o protegerlo con require_permission. Ref: anotaciones/modulo_1/estado.md (RF-11, hallazgo transversal #4).

### #7 — [Back-end] RF-01/08/09: Hashear tokens de un solo uso

| Campo | Valor |
|---|---|
| Ref / ID | 7 / 9463905 |
| Estado | Done |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p0-critico |
| Módulo | m1 |
| Etiquetas | p0-critico, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:45:41.606Z |
| Modificado | 2026-08-14T03:50:23.528Z |
| Terminado | 2026-08-15T05:44:32.457Z |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. Los tokens de activación de cuenta y de recuperación/restablecimiento de contraseña se guardan y comparan en texto plano. El RF exige almacenamiento como hash. Si alguien lee la tabla, puede usar los tokens directamente. Ref: anotaciones/modulo_1/estado.md (RF-01, RF-08, RF-09, hallazgo transversal #2).

### #8 — [Back-end] RF-05/06: Unificar RBAC en router y quitar id_rol hardcodeado en gestión de cuenta/perfil

| Campo | Valor |
|---|---|
| Ref / ID | 8 / 9463906 |
| Estado | Done |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m1 |
| Etiquetas | p1-alto, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 5 |
| Creado | 2026-08-07T18:45:42.608Z |
| Modificado | 2026-08-14T21:03:58.046Z |
| Terminado | 2026-08-15T05:44:37.029Z |
| Bloqueada | No |

**Descripción:** Estimación: 5 pts. editar_perfil_use_case.py y gestionar_cuenta_use_case.py hardcodean ROL_ADMINISTRADOR=1 en el use case, y el router de editar_perfil no tiene require_permission. Contradice la regla de CLAUDE.md de que la autorización va siempre en el router. Además existen dos caminos distintos para cambiar el estado de una cuenta con distinto rigor (motivo_accion, protección de último admin, tabla de auditoría dedicada) — evaluar unificarlos en uno solo. Ref: anotaciones/modulo_1/estado.md (RF-05, RF-06, hallazgo transversal #1).

### #9 — [Back-end] RF-02: JWT a 8h y declarar JWT_EXPIRE_HOURS en .env.example

| Campo | Valor |
|---|---|
| Ref / ID | 9 / 9463907 |
| Estado | Done |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m1 |
| Etiquetas | p1-alto, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 1 |
| Creado | 2026-08-07T18:45:43.613Z |
| Modificado | 2026-08-13T18:34:39.335Z |
| Terminado | 2026-08-15T05:44:53.703Z |
| Bloqueada | No |

**Descripción:** Estimación: 1 pt. El JWT dura 24h por defecto en vez de las 8h que pide el RF, y la variable JWT_EXPIRE_HOURS no está declarada en .env.example, por lo que cualquier ambiente nuevo corre silenciosamente con el default. Ref: anotaciones/modulo_1/estado.md (RF-02, hallazgo transversal #5).

### #10 — [Back-end] RF-01/10: Auditoría de registro y activación de cuenta

| Campo | Valor |
|---|---|
| Ref / ID | 10 / 9463908 |
| Estado | Ready for test |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m1 |
| Etiquetas | p1-alto, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 2 |
| Creado | 2026-08-07T18:45:44.613Z |
| Modificado | 2026-08-15T05:45:18.787Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 2 pts. CrearUsuarioUseCase y ActivarCuentaUseCase no escriben en la tabla de eventos de auditoría, pese a que RF-10 exige que 'registro de nuevo usuario' sea un evento auditable. Ref: anotaciones/modulo_1/estado.md (RF-01, RF-10).

## Sprint 2 — Funcional

### #11 — [Back-end] RF-04/06: Cambio de rol de usuario debe aplicarse sin esperar relogin

| Campo | Valor |
|---|---|
| Ref / ID | 11 / 9463909 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m1 |
| Etiquetas | p1-alto, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 5 |
| Creado | 2026-08-07T18:45:45.601Z |
| Modificado | 2026-08-07T23:23:56.150Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 5 pts. El id_rol viaja fijo dentro del JWT desde el login y nunca se revalida contra la DB. Si un admin cambia el rol de un usuario puntual, ese usuario sigue operando con permisos del rol anterior hasta que expire el token o cierre sesión manualmente. Evaluar alcance con el equipo — ya existe una propuesta documentada en anotaciones/modulo_1/plan_access_refresh_tokens.md (no implementada). Ref: anotaciones/modulo_1/estado.md (RF-04, RF-06, hallazgo transversal #3).

### #12 — [Back-end] RF-01: Agregar CAPTCHA en registro

| Campo | Valor |
|---|---|
| Ref / ID | 12 / 9463910 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m1 |
| Etiquetas | p1-alto, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:45:46.635Z |
| Modificado | 2026-08-07T23:23:56.273Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. El RF pide explícitamente CAPTCHA (Google reCAPTCHA v2 o v3) como requisito de seguridad y como flujo alterno HTTP 400. Hoy no existe ninguna referencia a CAPTCHA en el código. Implementar como adaptador en infrastructure/adapters/ siguiendo el patrón de stub/adapter del proyecto, con RECAPTCHA_SECRET_KEY en .env.example. Ref: anotaciones/modulo_1/estado.md (sección 'Si se agrega CAPTCHA').

### #13 — [Back-end] RF-01: confirmar_contraseña, numero_identificacion numérico, envío asíncrono

| Campo | Valor |
|---|---|
| Ref / ID | 13 / 9463911 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m1 |
| Etiquetas | p2-medio, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:45:47.913Z |
| Modificado | 2026-08-07T23:24:00.518Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. Faltan: campo confirmar_contraseña en el registro; validación de que numero_identificacion sea solo numérico; el reintento de envío de correo (hasta 3 veces, 5s de pausa) es síncrono dentro del request y puede demorar al usuario hasta ~15s. Ref: anotaciones/modulo_1/estado.md (RF-01).

### #14 — [Back-end] RF-02: Estado SUSPENDIDO o documentar uso de Eliminado

| Campo | Valor |
|---|---|
| Ref / ID | 14 / 9463913 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m1 |
| Etiquetas | p2-medio, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 2 |
| Creado | 2026-08-07T18:45:50.080Z |
| Modificado | 2026-08-07T23:24:00.972Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 2 pts. El RF-02 menciona un estado SUSPENDIDO que impide login, pero el catálogo real es Pendiente/Activo/Inactivo/Bloqueado/Eliminado — se usa Eliminado en su lugar. Decidir con el equipo de análisis si se agrega el estado o se documenta oficialmente la equivalencia. Ref: anotaciones/modulo_1/estado.md (RF-02).

### #15 — [Back-end] RF-10: Corregir categoría de eventos de auditoría

| Campo | Valor |
|---|---|
| Ref / ID | 15 / 9463914 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m1 |
| Etiquetas | p2-medio, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 2 |
| Creado | 2026-08-07T18:45:52.304Z |
| Modificado | 2026-08-07T23:24:01.475Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 2 pts. El campo 'categoría' del evento de auditoría siempre se guarda como AUTENTICACION sin importar el tipo real de evento (edición de rol, consulta de listado, etc.), lo que impide filtrar por categoría real. Ref: anotaciones/modulo_1/estado.md (RF-10).

### #16 — [Back-end] RF-11: Ordenar listado de usuarios por fecha de registro descendente

| Campo | Valor |
|---|---|
| Ref / ID | 16 / 9463915 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m1 |
| Etiquetas | p2-medio, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 1 |
| Creado | 2026-08-07T18:45:53.346Z |
| Modificado | 2026-08-07T23:24:05.337Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 1 pt. El endpoint de listado de usuarios para administradores no tiene ORDER BY explícito; el RF pide orden descendente por fecha de registro. Ref: anotaciones/modulo_1/estado.md (RF-11).

### #17 — [Back-end] RF-12: Sembrar permiso para ver identificación completa

| Campo | Valor |
|---|---|
| Ref / ID | 17 / 9463916 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m1 |
| Etiquetas | p2-medio, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 1 |
| Creado | 2026-08-07T18:45:55.550Z |
| Modificado | 2026-08-07T23:24:05.794Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 1 pt. El código que decide si un admin puede ver el número de identificación completo (sin enmascarar) está listo, pero no existe ninguna fila en modulo1.permisos que otorgue esa capacidad — hoy nadie puede verlo. Sembrar el permiso en modulo1.permisos. Ref: anotaciones/modulo_1/estado.md (RF-12).

### #18 — [Back-end] RF-14: Notificaciones de registro/activación + bandeja de notificaciones internas

| Campo | Valor |
|---|---|
| Ref / ID | 18 / 9463917 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m1 |
| Etiquetas | p2-medio, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 5 |
| Creado | 2026-08-07T18:45:57.740Z |
| Modificado | 2026-08-07T23:24:06.363Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 5 pts. El registro de usuario y la activación de cuenta no pasan por el sistema centralizado de notificaciones (solo correo directo, sin control anti-spam ni registro). Además, no existe ningún endpoint para que el usuario vea o marque como leídas sus notificaciones internas, pese a que el modelo de datos ya tiene la columna. Ref: anotaciones/modulo_1/estado.md (RF-14).

## Sprint 3 — Cierre

### #19 — [Back-end] [DBA] RF-06: Traducir errores de trigger de gestión de cuenta a error de dominio

| Campo | Valor |
|---|---|
| Ref / ID | 19 / 9463918 |
| Estado | New |
| Sprint | Sprint 3 — Cierre |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m1 |
| Etiquetas | p2-medio, m1, dba, back-end |
| Asignado | SamuelPR21 (Samuel Alexander Perdomo Fajardo) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 2 |
| Creado | 2026-08-07T18:45:59.904Z |
| Modificado | 2026-08-07T23:25:50.838Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 2 pts. Si un trigger de protección de DB (ej. sobre el último administrador) rechaza una operación de gestión de cuenta, el error no siempre se traduce a un mensaje limpio — en algunos casos llega al cliente como 500 genérico en vez de 403/422 con mensaje claro. Ampliar raise_from_db_error o el manejo de excepción específico. Ref: anotaciones/modulo_1/estado.md (RF-06).

### #20 — [Back-end] RF-10: Política de retención de auditoría (12 meses)

| Campo | Valor |
|---|---|
| Ref / ID | 20 / 9463919 |
| Estado | New |
| Sprint | Sprint 3 — Cierre |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p3-bajo |
| Módulo | m1 |
| Etiquetas | p3-bajo, m1, back-end |
| Asignado | leandroEstiven (Leandro Estiven Ramírez Molina) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:46:02.143Z |
| Modificado | 2026-08-08T01:30:22.218Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. No existe política de retención de 12 meses ni archivado automático de registros antiguos de auditoría — no hay ningún proceso programado. Evaluar si entra en este ciclo o queda documentado como pendiente futuro. Ref: anotaciones/modulo_1/estado.md (RF-10).

### #21 — [Back-end] Doc: Actualizar CLAUDE.md con hallazgos confirmados de Módulo 1

| Campo | Valor |
|---|---|
| Ref / ID | 21 / 9463921 |
| Estado | New |
| Sprint | Sprint 3 — Cierre |
| Epic | Módulo 1 — Identity & Access: cierre de gaps |
| Prioridad | p3-bajo |
| Módulo | m1 |
| Etiquetas | p3-bajo, m1, back-end |
| Asignado | arekkazu (Alexander Lozada Caviedes) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 1 |
| Creado | 2026-08-07T18:46:04.297Z |
| Modificado | 2026-08-07T23:48:34.195Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 1 pt. CLAUDE.md describe la gestión de roles/permisos como catálogo fijo (ya no es así, hay CRUD dinámico real) y dice que audit_sdk se inicializa en main.py (en realidad se importa pero nunca se registra, es código muerto). Actualizar la documentación de arquitectura para que no induzca a error. Ref: anotaciones/modulo_1/estado.md (hallazgo transversal #7).

---

# Módulo 2 — Biological Assets: cierre de gaps

## Sprint 1 — Crítico y fundacional

### #22 — [Back-end] [DBA] RF-52: Bitácora de auditoría append-only a nivel de DB

| Campo | Valor |
|---|---|
| Ref / ID | 22 / 9463922 |
| Estado | New |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p0-critico |
| Módulo | m2 |
| Etiquetas | p0-critico, m2, dba, back-end |
| Asignado | SamuelPR21 (Samuel Alexander Perdomo Fajardo) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:46:24.112Z |
| Modificado | 2026-08-07T23:29:32.276Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. La tabla bitacora_auditoria_m02 no tiene ningún trigger que bloquee UPDATE/DELETE, a diferencia de eventos_activos e historicos_estados_activos que sí lo tienen. Hoy cualquiera con acceso de escritura puede modificar o borrar registros de auditoría sin rastro. Es el gap más grave del módulo: RF-52 es la fuente de evidencia para valoración NIC 41 (M06) y auditorías ICA/UPRA. Crear triggers trg_fn_*_inmutable equivalentes. Ref: anotaciones/modulo_2/estado.md (RF-52, hallazgo transversal #6).

### #23 — [Back-end] RF-38/44/45: Cerrar segundo camino de cambio de estado (PATCH /{id}/estado)

| Campo | Valor |
|---|---|
| Ref / ID | 23 / 9463923 |
| Estado | Ready for test |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p0-critico |
| Módulo | m2 |
| Etiquetas | p0-critico, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 5 |
| Creado | 2026-08-07T18:46:26.947Z |
| Modificado | 2026-08-14T21:22:38.362Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 5 pts. PATCH /{id}/estado permite fijar CERRADO o BAJA sin las reglas ni efectos secundarios de RF-38/RF-45: no valida fase activa ni sensores IoT, no cierra la fase productiva, no descuenta cantidad_actual ni recalcula biomasa/densidad en lotes, no crea fila en eventos_bajas. Contradice el 'Principio de Centralización Obligatoria' de RF-44. Unificar en un único componente de cambio de estado invocado por los tres flujos (manual, cierre de ciclo, baja). Ref: anotaciones/modulo_2/estado.md (RF-38, RF-44, RF-45, hallazgo transversal #1).

### #24 — [Back-end] [DBA] RF-39/40/41/42: Traducir errores de trigger PL/pgSQL a error de dominio

| Campo | Valor |
|---|---|
| Ref / ID | 24 / 9463924 |
| Estado | New |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m2 |
| Etiquetas | p1-alto, m2, dba, back-end |
| Asignado | SamuelPR21 (Samuel Alexander Perdomo Fajardo) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:46:30.200Z |
| Modificado | 2026-08-07T23:29:32.607Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. raise_from_db_error solo traduce IntegrityError/DataError/OperationalError de SQLAlchemy, no reconoce los RAISE EXCEPTION ... USING ERRCODE='P02xx' que usan los triggers de este módulo. Cualquier violación que solo el trigger detecte cae en HTTP 500 genérico en vez del código documentado por el RF (400/409/422). Confirmado reproducible en RF-40 y RF-42. Resuelve 4 RFs de una vez. Ref: anotaciones/modulo_2/estado.md (RF-39, hallazgo transversal #4).

### #25 — [Back-end] RF-40: Corregir bug de unidad 'gr' vs 'g' en evento de crecimiento

| Campo | Valor |
|---|---|
| Ref / ID | 25 / 9463925 |
| Estado | New |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m2 |
| Etiquetas | p1-alto, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 2 |
| Creado | 2026-08-07T18:46:33.491Z |
| Modificado | 2026-08-07T23:29:32.705Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 2 pts. El DTO acepta 'gr' como unidad válida para PESO, pero el trigger trg_fn_evento_crecimiento_tipo_activo solo acepta ('kg','g','lb') — 'g', no 'gr'. Un request válido según el propio contrato del sistema es rechazado por el trigger, y por el gap de traducción de errores se convierte en HTTP 500. Además: el trigger no valida ninguna unidad para BIOMASA, y compara tipo_activo='poblacional' (minúscula) contra un enum que solo tiene 'POBLACIONAL' (esa rama nunca se ejecuta). Ref: anotaciones/modulo_2/estado.md (RF-40).

### #26 — [Back-end] RF-42: Corregir bug de restricción LOTE en evento reproductivo

| Campo | Valor |
|---|---|
| Ref / ID | 26 / 9463926 |
| Estado | New |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m2 |
| Etiquetas | p1-alto, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 2 |
| Creado | 2026-08-07T18:46:36.214Z |
| Modificado | 2026-08-07T23:29:37.548Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 2 pts. registrar_evento_reproductivo_use_case.py compara activo.tipo == 'LOTE', pero TipoActivo solo define INDIVIDUAL y POBLACIONAL — la condición nunca es verdadera. Un activo POBLACIONAL puede hoy registrar servicio/inseminación/diagnóstico/parto/aborto sin que el use case lo impida, violando la restricción del RF de que LOTE solo puede registrar NACIMIENTO. El trigger de DB sí compara correctamente, pero por el gap de traducción de errores el cliente recibe 500 en vez de 422. Ref: anotaciones/modulo_2/estado.md (RF-42).

### #27 — [Back-end] [DBA] RF-38/44/45: Unificar valores de modulo_origen en historicos_estados_activos

| Campo | Valor |
|---|---|
| Ref / ID | 27 / 9463928 |
| Estado | New |
| Sprint | Sprint 1 — Crítico y fundacional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m2 |
| Etiquetas | p1-alto, m2, dba, back-end |
| Asignado | SamuelPR21 (Samuel Alexander Perdomo Fajardo) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 2 |
| Creado | 2026-08-07T18:46:38.905Z |
| Modificado | 2026-08-07T23:29:45.821Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 2 pts. Todos los cambios de estado quedan grabados con modulo_origen='modulo2' (o 'modulo5'), nunca 'MANUAL'/'RF-38'/'RF-45' como exige RF-44 — imposible reconstruir el origen real de un cambio de estado desde esta tabla. Causa raíz: el CHECK chk_historico_modulo_origen_valido solo acepta literales 'modulo1'..'modulo9'. Ampliar el CHECK para aceptar los valores de origen reales. Ref: anotaciones/modulo_2/estado.md (RF-38, RF-44, RF-45, hallazgo transversal #2).

## Sprint 2 — Funcional

### #28 — [Back-end] RF-33: Snapshot inicial (Evento 0), CHECK soporte_documental, código HTTP

| Campo | Valor |
|---|---|
| Ref / ID | 28 / 9463929 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m2 |
| Etiquetas | p1-alto, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 5 |
| Creado | 2026-08-07T18:46:42.217Z |
| Modificado | 2026-08-07T23:40:55.125Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 5 pts. No existe el mecanismo de snapshot inicial que el RF exige explícitamente: no hay tabla historial_activos, y ActivoBiologico._snapshot() nunca se invoca desde el registro. Además falta un CHECK a nivel de DB para 'soporte_documental obligatorio si costo_adquisicion no es nulo' (confirmado con datos reales inconsistentes), y el flujo alterno de costo inválido para el origen responde 400 en vez del 422 que exige el RF (viene de un model_validator de Pydantic). Ref: anotaciones/modulo_2/estado.md (RF-33).

### #29 — [Back-end] RF-34: fecha_referencia, 404 sin asociación activa, sensores_en_infraestructura

| Campo | Valor |
|---|---|
| Ref / ID | 29 / 9463930 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m2 |
| Etiquetas | p2-medio, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:46:45.459Z |
| Modificado | 2026-08-07T23:25:05.709Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. Falta el parámetro fecha_referencia que el RF exige explícitamente (útil para RF-61) — sin él, CA-3 es inalcanzable. Cuando no hay asociación activa, el endpoint responde 200 con asociacion_activa=None en vez del 404 con alerta técnica que exige el flujo alterno E2. Faltan también sensores_en_infraestructura (enriquecimiento vía RF-22) y advertencia_integridad (verificación de solapamiento de periodos). Ref: anotaciones/modulo_2/estado.md (RF-34).

### #30 — [Back-end] RF-35: RBAC Veterinario, validar eventos pendientes, concurrencia optimista

| Campo | Valor |
|---|---|
| Ref / ID | 30 / 9463931 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m2 |
| Etiquetas | p1-alto, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:46:48.172Z |
| Modificado | 2026-08-07T23:25:06.190Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. Veterinario está listado explícitamente como actor de RF-35 pero no tiene permiso de actualización (PATCH) sobre el recurso 29 — confirmado contra modulo1.permisos. Tampoco se valida 'eventos pendientes sin cerrar' ni inconsistencias en el historial antes de aceptar una edición, pese a que el RF lo exige. Falta concurrencia optimista (412) en el PATCH, a diferencia del patrón estándar del proyecto. Ref: anotaciones/modulo_2/estado.md (RF-35).

### #31 — [Back-end] RF-36: Ficha de gestión de lote, densidad máxima, ingreso de individuos

| Campo | Valor |
|---|---|
| Ref / ID | 31 / 9463932 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m2 |
| Etiquetas | p1-alto, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 8 |
| Creado | 2026-08-07T18:46:50.902Z |
| Modificado | 2026-08-07T23:25:12.391Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 8 pts. El RF más bajo del módulo (~40%). No existe un endpoint/caso de uso propio de 'gestión de lote' con la ficha operativa completa (cantidad_actual + peso_promedio + biomasa_total + densidad + estado + historial). No se valida densidad_maxima_por_especie en absoluto (flujo alterno 409 inalcanzable). No hay ningún mecanismo de ingreso/alta de individuos al lote, solo el flujo de BAJA. Ref: anotaciones/modulo_2/estado.md (RF-36).

### #32 — [Back-end] RF-37: fase_destino/confirmacion_no_estandar, fecha no futura, RBAC

| Campo | Valor |
|---|---|
| Ref / ID | 32 / 9463933 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m2 |
| Etiquetas | p2-medio, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 5 |
| Creado | 2026-08-07T18:46:53.610Z |
| Modificado | 2026-08-07T23:25:18.173Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 5 pts. El DTO real (cambiar_fase_dto.py) solo tiene id_ciclo_productiva, motivo_cambio y fecha_inicio — no existe fase_destino_id ni confirmacion_no_estandar, así que el flujo alterno de 'transición no estándar sin confirmación' (409) es inalcanzable. Tampoco se valida que la fecha no sea futura. RBAC más amplio que el RF (Ingeniero de Campo incluido cuando el RF solo lista Productor/Veterinario/Administrador) — ajustar o documentar decisión. Ref: anotaciones/modulo_2/estado.md (RF-37).

### #33 — [Back-end] RF-48: Regla C2 (compatibilidad tipo infraestructura), formato de error

| Campo | Valor |
|---|---|
| Ref / ID | 33 / 9463934 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m2 |
| Etiquetas | p2-medio, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:46:56.376Z |
| Modificado | 2026-08-07T23:25:19.584Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. La Regla C2 (tipo de infraestructura destino adecuado para el tipo de activo) no está implementada — el campo tipo de la infraestructura está disponible pero nunca se usa para esta validación; una transferencia de un activo avícola a un estanque no sería rechazada. Además el error de fecha futura se traduce a HTTP 400 con formato {error_code, fields[]} en vez del 422 con formato {code, message, field} estándar de CLAUDE.md. Ref: anotaciones/modulo_2/estado.md (RF-48).

### #34 — [Back-end] RF-49: Compatibilidad de especie sensor-activo y ciclo de vida completo

| Campo | Valor |
|---|---|
| Ref / ID | 34 / 9463935 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p1-alto |
| Módulo | m2 |
| Etiquetas | p1-alto, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 5 |
| Creado | 2026-08-07T18:46:59.095Z |
| Modificado | 2026-08-07T23:25:18.718Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 5 pts. No existe validación de compatibilidad de especie (Restricción 3 del RF: el sensor debe ser compatible con la especie del activo según catálogo I3P-1) — un sensor de aves podría asociarse hoy a un bovino sin rechazo. Además solo existe POST /{id}/sensores: no hay endpoint para desactivar manualmente una asociación, reactivarla, ni listar/consultar las asociaciones activas — el RF exige gestionar el ciclo de vida completo. Ref: anotaciones/modulo_2/estado.md (RF-49).

### #35 — [Back-end] RF-50: modulo_consumidor real y rate limiting (429)

| Campo | Valor |
|---|---|
| Ref / ID | 35 / 9463936 |
| Estado | New |
| Sprint | Sprint 2 — Funcional |
| Epic | Módulo 2 — Biological Assets: cierre de gaps |
| Prioridad | p2-medio |
| Módulo | m2 |
| Etiquetas | p2-medio, m2, back-end |
| Asignado | Danielsxanti (Daniel Santiago rivera) |
| Owner | arekkazu (Alexander Lozada Caviedes) |
| Puntos (estimación) | 3 |
| Creado | 2026-08-07T18:47:01.311Z |
| Modificado | 2026-08-07T23:25:25.293Z |
| Terminado | — |
| Bloqueada | No |

**Descripción:** Estimación: 3 pts. El campo modulo_consumidor en EventoAuditoria tiene default 'modulo2' y ningún use case lo sobre-escribe, por lo que es inútil para identificar qué módulo externo consultó. Tampoco hay rate limiting: TooManyRequestsError existe en src/shared/errors.py pero no se usa en src/biological_assets/, pese a que el RF exige límite de solicitudes por módulo con 429. Ref: anotaciones/modulo_2/estado.md (RF-50).
