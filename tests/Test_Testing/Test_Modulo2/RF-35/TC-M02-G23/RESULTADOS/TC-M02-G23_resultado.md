# TC-M02-G23 — Resultado de ejecución

**Estado general: TC-M02-045 FAIL (BOLA crítico confirmado) · TC-M02-046 PASS · TC-M02-047 BLOQUEADO en precondición
(bug independiente de RF-37).** Postman/Newman: 9/12 assertions PASS. Pytest: 5/7 PASS. Ambos contra el backend
TEST desplegado, con datos reales.

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G23 (agrupa TC-M02-045, TC-M02-046, TC-M02-047) |
| RF / CU | RF-35 / RF-37 / CU-02 |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuentas | Admin (`id_usuario=47`) · Productor A (`id_usuario=71`, Finca 36) · Veterinario (`id_usuario=73`, sin fincas) |
| Fecha de ejecución | 2026-09-09, ~23:55–00:05 UTC |
| Herramientas | Newman 6.2.2 + htmlextra 1.23.1 · Pytest 9.0.3 + `requests` |

## Preparación del entorno de prueba

Documentado en detalle en `README.md`. Resumen de las acciones administrativas realizadas (todas reversibles,
todas sobre cuentas/datos de prueba, ninguna sobre código):

1. `POST /usuarios/71/gestionar {"accion_cuenta":"activar"}` y `POST /usuarios/73/gestionar {"accion_cuenta":"activar"}`
   — reactivación de 2 cuentas QA `PENDIENTE` preexistentes (creadas por pruebas de RF-01 anteriores, nunca
   activadas ni usadas por nadie más).
2. `PATCH /usuarios/73 {"id_rol":3}` — asignación del rol Veterinario a la segunda cuenta (nace Productor por
   defecto).
3. `POST /configuracion/fincas` × 2 — Finca 36 (`id_usuario=71`, Productor A) y Finca 37 (`id_usuario=47`, admin).
4. `POST /configuracion/infraestructuras` × 2 — una por finca.
5. `POST /activos-biologicos` × 2 — activo 199 (propio de Productor A, Finca 36) y activo 200 (víctima controlada,
   Finca 37).

## TC-M02-045 — BOLA al actualizar activo de otra finca

### Control positivo: Productor A edita su propio activo

`PATCH /activos-biologicos/199` (Productor A) → **200 OK**, `raza` actualizada. Confirma que la cuenta y el permiso
de escritura funcionan — el resto de los resultados no se explican por una cuenta mal configurada.

### GET sobre activo ajeno

`GET /activos-biologicos/200` (Productor A, Finca 37 no es la suya) → **404** `ACTIVO_NO_ENCONTRADO`. Correcto: el
alcance por finca (RF-25) sí se aplica en la consulta — confirmado en código:
`ConsultarActivoUseCase.execute(..., ids_fincas_permitidas=...)` filtra por finca antes de responder.

### PATCH sobre activo ajeno — BOLA confirmado

```json
// PATCH /activos-biologicos/200 (Productor A)
// {"raza": "MODIFICADO por Productor A via BOLA - finca ajena"}
// HTTP 200 -- el RF exige 403 aqui
{
  "id_activo_biologico": 200, "id_infraestructura": 15, "id_usuario": 47,
  "detalle_individual": { "raza": "MODIFICADO por Productor A via BOLA - finca ajena", ... }
}
```

**Confirmado en 3 ejecuciones independientes** (curl manual con dos activos ajenos distintos — incluyendo, en la
exploración inicial, un activo perteneciente a un usuario real del sistema no relacionado con esta prueba,
restaurado a su valor original inmediatamente después con autorización explícita del usuario — más la colección
Postman formal y la suite pytest, ambas contra el activo víctima controlado 200).

**Causa raíz confirmada por lectura de código:**
`ActualizarActivoIndividualUseCase.execute()` (`actualizar_activo_individual_use_case.py`) llama
`self.repo.obtener_por_id(id_activo)` **sin el parámetro `ids_fincas_permitidas`** que sí usa
`ConsultarActivoUseCase` (RF-35 GET) y `ListarActivosUseCase`. El router (`activo_biologico_router.py`,
`actualizar_activo_individual`) tampoco calcula ni pasa `_ids_fincas_alcance(db, usuario_actual)` al use case, a
diferencia de todos los endpoints `GET` del mismo archivo. El resultado: `PATCH /activos-biologicos/{id}` **nunca
aplica ningún filtro de finca**, sin importar el rol o la asignación del usuario que hace la petición — cualquier
usuario con el permiso genérico de actualización sobre el recurso 29 (Admin, Productor, Ingeniero) puede modificar
el activo de cualquier finca del sistema.

### Verificación posterior

`GET /activos-biologicos/200` (admin) confirma que la `raza` quedó con el valor de la modificación no autorizada,
no con el original — el efecto de negocio del BOLA es real y persistente, no solo un código de respuesta incorrecto.

## TC-M02-046 — Función restringida por rol

**PASS.** `PATCH /activos-biologicos/199` (Veterinario, sin permiso `U` sobre el recurso 29) → **403**
`ACCESO_DENEGADO` ("Su rol no tiene permisos para realizar esta operación"). Verificado que la `raza` del activo no
cambió tras el intento. El control de acceso a nivel de función (OWASP API5) sí funciona correctamente para este
camino — el RBAC estándar del proyecto (`require_permission` en el router) bloquea la operación antes de que llegue
al use case.

## TC-M02-047 — Intento de alterar historial inmutable de fases

**BLOQUEADO en la precondición** — ver `NOTA_BLOQUEO.md` para el detalle completo y la causa raíz exacta (confirmada
por lectura de código, sin necesitar acceso a base de datos): `cambiar_fase_use_case.py` llama a
`repo.cerrar_gestion_activa()` con 3 argumentos cuando el método exige 4 (falta `usuario_id`), lo que produce un
`TypeError` no controlado → 500 en **cualquier** intento de cambio de fase, para **cualquier** activo, con
**cualquier** ciclo productivo válido. Confirmado en 9 combinaciones distintas de activo/ciclo (incluyendo el
ejemplo exacto documentado en `anotaciones/modulo_2/curls_m02_cu02_activo_individual.md`, que tampoco funciona en
TEST hoy).

Sin poder crear la primera fase, es imposible construir "un registro histórico de fase ya cerrado". Se dejó como
verificación parcial válida:

```json
// PATCH /activos-biologicos/199/fases/1
// HTTP 404 {"detail": "Not Found"}
```

No existe ninguna ruta HTTP para editar una fase existente — el router (`activo_biologico_router.py`) solo define
`POST` (crear/avanzar) y `GET` (listar) bajo `/fases`, nunca un `PATCH`/`PUT` sobre una fase individual. Esto
demuestra que el historial es append-only **por ausencia total de vía de edición**, aunque no permite verificar el
comportamiento específico de "rechazar el intento de alterar una fase ya cerrada" que pide el RF, porque no se pudo
generar ese registro para intentarlo.

## Resumen de assertions

### Postman/Newman (12 assertions, 9 PASS / 3 FAIL)

| # | Assertion | Resultado |
|---|---|---|
| 1–3 | Login admin / Productor A / Veterinario | PASS |
| 4 | Control positivo: Productor A edita su propio activo (200) | PASS |
| 5 | GET activo ajeno → 404 | PASS |
| 6 | **PATCH activo ajeno → 403 (BOLA)** | **FAIL — obtuvo 200** |
| 7 | Verificación admin: GET responde 200 | PASS |
| 8 | **Verificación admin: raza del activo ajeno sin cambios** | **FAIL — sí cambió** |
| 9 | Veterinario PATCH → 403 | PASS |
| 10 | Veterinario PATCH → `error_code=ACCESO_DENEGADO` | PASS |
| 11 | **Cambiar fase → 201** | **FAIL — obtuvo 500 (bloqueo RF-37)** |
| 12 | No existe ruta de edición directa de fase (404/405) | PASS |

### Pytest (7 tests, 5 PASS / 2 FAIL)

| Test | Resultado |
|---|---|
| `test_control_positivo_productor_edita_su_propio_activo` | PASS |
| `test_get_activo_de_otra_finca_no_lo_revela` | PASS |
| `test_patch_activo_de_otra_finca_debe_rechazarse_con_403` | **FAIL — BOLA confirmado** |
| `test_activo_ajeno_no_debio_cambiar` | **FAIL — el dato sí cambió** |
| `test_rol_sin_permiso_escritura_no_puede_actualizar` | PASS |
| `test_no_existe_endpoint_de_edicion_directa_de_fase` | PASS |
| `test_precondicion_bloqueada_cambiar_fase_falla_para_cualquier_activo` | PASS (documenta el bloqueo intencionalmente) |

## Evidencia

- [Colección Postman](../TC-M02-G23.postman_collection.json)
- [Suite Pytest](../test_tc_m02_g23_control_acceso.py)
- [Nota de bloqueo — RF-37](../NOTA_BLOQUEO.md)
- [Reporte Newman HTML](newman-TC-M02-G23.html)
- [Reporte Newman JSON](newman-TC-M02-G23.json)

## Conclusión y recomendación

**TC-M02-045 (BOLA) es el hallazgo más grave detectado hasta ahora en la auditoría en vivo de RF-35**: cualquier
usuario con permiso de escritura sobre activos biológicos (Administrador, Productor, Ingeniero de Campo) puede
modificar datos de activos que pertenecen a fincas ajenas, sin ninguna restricción, simplemente conociendo o
adivinando el ID del activo. Esto es explotable en producción tal como está desplegado hoy en TEST, y contradice
directamente el control de acceso por finca (RF-25) que sí está correctamente implementado para las operaciones de
lectura del mismo módulo. Se recomienda tratarlo como incidente de seguridad crítico (ver formulación en el formato
de incidentes de este proyecto) y priorizarlo por encima de los hallazgos funcionales de TC-M02-G20/G21/G22.

TC-M02-046 confirma que el resto del modelo RBAC (autorización a nivel de función) funciona correctamente — el
problema de TC-M02-045 es específicamente de autorización a nivel de objeto (BOLA), no un fallo general de RBAC.

TC-M02-047 quedó bloqueado por un defecto de RF-37 no relacionado con RF-35, ya diagnosticado con causa raíz exacta
en `NOTA_BLOQUEO.md` — una vez corregido (cambio de una línea), el caso puede completarse íntegramente reutilizando
la infraestructura de prueba ya creada (activo 199, Finca 36).
