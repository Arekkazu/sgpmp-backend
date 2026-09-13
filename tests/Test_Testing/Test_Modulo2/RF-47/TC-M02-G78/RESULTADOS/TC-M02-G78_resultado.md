# TC-M02-G78 — Resultado de ejecución

**Estado general: PASS — 4/4 tests vía Pytest contra el backend TEST desplegado.** TC-M02-131 es un PASS de
seguridad genuino; TC-M02-132 queda documentado como bloqueado por un gap ya conocido, no como una verificación
completa del sub-caso.

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G78 (TC-M02-131, TC-M02-132) |
| RF / CU | RF-47 / CU-10B |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuentas | Contador (`id_usuario=72`, re-rolado) · Veterinario (`id_usuario=73`, reutilizado de TC-M02-G23) |
| Fecha de ejecución | 2026-09-10, ~02:15 UTC |

## TC-M02-131 — Rechazar consulta de ficha sin permisos

**PASS completo.**

```json
// GET /activos-biologicos/5/ficha-integral  (token: Contador, id_rol=5)
// HTTP 403
{"error_code":"ACCESO_DENEGADO","message":"Acceso denegado. Su rol no tiene permisos para realizar esta operación.","fields":[]}
```

Verificado explícitamente que la respuesta no contiene ninguno de los campos propios del activo
(`identificador`, `especie`, `raza`, `sexo`, `peso_actual`, `eventos_sanitarios`, `indicadores`,
`fase_productiva_activa`) — solo el sobre de error estándar. El RBAC del recurso `activos_biologicos` (acción R)
funciona correctamente para un rol sin ningún permiso asignado.

## TC-M02-132 — Accesos directos visibles solo según permisos del rol

**Bloqueado — no evaluable con la API actual.**

Control positivo: `GET /activos-biologicos/222/ficha-integral` (token: Veterinario) → **200**, la cuenta y el
permiso de lectura funcionan, y el alcance por finca (RF-25) permite el acceso porque el activo 222 se creó
específicamente dentro de una finca asignada a este Veterinario.

```json
{"id_activo_biologico":222,"identificador":"G78-06591", ..., "advertencias":[]}
// Sin ningun campo "accesos_directos"
```

La respuesta **no tiene el campo `accesos_directos`** — la Sección 8 que describe este sub-caso no existe en la
API. Este mismo hallazgo ya se documentó en `tests/Test_Testing/Test_Modulo2/RF-47/TC-M02-G77/` (TC-M02-127): no
es un defecto nuevo de control de acceso, es la ausencia de la sección completa que impide evaluar si su
visibilidad se filtra correctamente por rol.

## Resumen de tests (Pytest, 4/4 PASS)

| Test | Resultado |
|---|---|
| `TestTCM02131SinPermisos::test_ficha_integral_rechazada_con_403` | PASS |
| `TestTCM02131SinPermisos::test_ningun_dato_del_activo_se_expone` | PASS |
| `TestTCM02132AccesosDirectosPorRol::test_veterinario_si_puede_leer_su_ficha` | PASS |
| `TestTCM02132AccesosDirectosPorRol::test_seccion_accesos_directos_no_existe_bloqueado` | PASS (documenta el bloqueo) |

## Evidencia

- [Suite Pytest](../test_tc_m02_g78_control_acceso_ficha_integral.py)

## Conclusión

El control de acceso de RF-47 sobre lo que la API expone hoy funciona correctamente (RBAC por rol + alcance por
finca). TC-M02-132 no se puede completar hasta que se implemente la Sección 8 (accesos directos) — el mismo gap ya
reportado en TC-M02-G77 — momento en el cual este test debe reemplazarse por una verificación real de qué acciones
se muestran habilitadas/deshabilitadas para cada rol.
