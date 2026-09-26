# TC-M02-G33 — Transiciones de fase válidas: secuencia estándar y no estándar con confirmación explícita

**CU-02 · RF-37 — Gestión de Fases del Ciclo Productivo.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-039) Registrar cambio de fase estándar válido · (TC-M02-042) Aceptar transición no estándar con confirmación explícita |
| Tipo | Funcional |
| Herramienta | API — Postman |
| Precondiciones | 1. Activo ACTIVO con fase actual definida; fase destino es la siguiente en la secuencia RF-16. 2. Mismas condiciones |
| Datos de entrada | 1. Transición a la siguiente fase de la secuencia definida en RF-16. 2. Salto de fase fuera de secuencia CON `confirmacion_no_estandar=true` → aceptado |
| Resultado esperado | 1. La fase actual se cierra (`fecha_fin`), se crea la nueva fase ACTIVA, queda en historial y auditoría. 2. La transición no estándar se registra exitosamente, con evidencia de la confirmación en el historial |
| Responsable | Juan Manuel |
| Prioridad | Alta |
| Endpoints | `POST /activos-biologicos/{id_activo}/fases` · `GET /activos-biologicos/{id_activo}/fases` |

## Resultado vigente (2026-09-26): TC-M02-039 PASS — TC-M02-042 FAIL parcial (11/12 assertions)

**El gap estructural del 2026-09-19 está implementado** (`15c4611e feat(m02): fase_destino/confirmacion_no_estandar
... (RF-37)`, llegó con el merge de `dev`): el salto confirmado se acepta y respeta el destino pedido. Queda **un
defecto residual real**: la marca de transición no estándar no se guarda en el historial de fases.

Cambios en la colección (sin alterar lo que exige el RF):

- `fase_destino_id` es el **id de la fase dentro del ciclo** (`id_ciclos_productivo_biologico`), no el número de
  paso. La colección enviaba `3` (paso) y el sistema respondía `400 FASE_DESTINO_INVALIDA`, correctamente: en TEST el
  ciclo 2 tiene las fases `4` (paso 1), `5` (paso 2) y `6` (paso 3, "Fase engorde trucha") — verificado en la BD de
  TEST (solo lectura), ya que ningún endpoint expone esos ids. Nueva variable `id_fase_destino=6`.
- Nuevo paso 4: `GET .../fases` tras el salto, para verificar el resultado esperado de la ficha ("fase actual se
  cierra con `fecha_fin`" y "evidencia de la confirmación en el historial"), que antes no se comprobaba.

| Caso | WHEN | Resultado real (2026-09-26) |
|---|---|---|
| TC-M02-039 | `POST /fases` con `id_ciclo_productiva=2` | **201**, fase 1 activa, visible en el historial — PASS |
| TC-M02-042 (salto) | `POST /fases` con `fase_destino_id=6` + `confirmacion_no_estandar=true` | **201**, `paso_actual=3`, respuesta con `es_transicion_no_estandar=true` — PASS |
| TC-M02-042 (cierre) | `GET /fases` | Fase 1 con `es_activa=false` y `fecha_finalizacion` = inicio de la fase 3 — PASS |
| TC-M02-042 (evidencia) | `GET /fases` | **FAIL**: la fase 3 aparece con `es_transicion_no_estandar=false` |

### Defecto: `es_transicion_no_estandar` no se persiste en el historial de fases

- `POST /activos-biologicos/{id}/fases` responde `es_transicion_no_estandar: true`, pero `GET
  /activos-biologicos/{id}/fases` devuelve esa **misma** fase (`id_gestion_fases`) con `false`.
- Causa: `modulo2.gestiones_fases` no tiene columna para ese dato (verificado en la BD de TEST, solo lectura) y el
  `INSERT` de `crear_gestion_fase` (`activo_biologico_repository.py`) no lo guarda: el POST solo devuelve el valor que
  tenía en memoria y la lectura del historial siempre cae al valor por defecto (`False`).
- La única evidencia persistida está en la bitácora de auditoría (`modulo2.bitacora_auditoria_m02`, evento
  `FASE_CAMBIADA`, `detalle_tecnico.es_transicion_no_estandar = true`), que no es el historial de fases que consulta
  el usuario.

Activo propio creado por la corrida (`id_activo_biologico=618`). Evidencia:
`RESULTADOS/TC-M02-G33_resultado.html` (Newman htmlextra, 2026-09-26).

---

## Histórico (2026-09-19): TC-M02-039 PASS — TC-M02-042 FAIL (gap real, no de entorno)

**INC-M02-37-01 (el bug que bloqueaba TC-M02-039) está resuelto.** `POST /activos-biologicos/{id}/fases` ya
responde `201`: la fase se crea, queda activa, y el historial la refleja correctamente. Ver
`RESULTADOS/TC-M02-G33_resultado.html` para la evidencia: **7/8 assertions PASS**, la única que falla es la de
TC-M02-042 (esperado — ver abajo).

**TC-M02-042 sigue sin poder pasar — no por un bloqueo de precondición, sino porque la funcionalidad que pide el
RF no está implementada.** `CambiarFaseDTO`
(`src/biological_assets/infrastructure/dto/cambiar_fase_dto.py`) solo declara `id_ciclo_productiva`,
`motivo_cambio` y `fecha_inicio` — **no existe ningún campo `confirmacion_no_estandar` ni `fase_destino_id`** en el
contrato de la API. Enviarlos (como se hizo en esta prueba) no produce ningún error de validación: Pydantic los
descarta en silencio (`extra='ignore'` por defecto de `BaseDTO`), y el use case (`CambiarFaseUseCase.execute()`)
**siempre** avanza automáticamente a la siguiente fase de la secuencia — no hay ninguna rama de código que
contemple "saltar" a una fase específica ni "confirmar" nada. Es decir: el propio concepto que pide el sub-caso
("transición fuera de secuencia con confirmación explícita") **no existe en la implementación actual**, sin
importar si el bug de INC-M02-37-01 se corrige o no.

Esto ya estaba señalado en la auditoría del módulo (`anotaciones/modulo_2/estado.md`, sección RF-37): *"El modelo de
'fase destino + confirmación de transición no estándar' del RF no está implementado (...) el flujo alterno
'transición no estándar sin confirmación' (409) es inalcanzable"*. Esta ejecución lo confirma en vivo, contra TEST,
con evidencia real de request/response.

### GIVEN / WHEN / THEN

| Caso | GIVEN | WHEN | THEN esperado (RF) | Resultado real |
|---|---|---|---|---|
| TC-M02-039 | Activo ACTIVO, sin fase previa, ciclo productivo válido y de su misma especie | `POST /fases` con `id_ciclo_productiva` | 201, fase creada, `paso_actual=1` | **201 — correcto** |
| TC-M02-042 | Mismo activo, con fase 1 ya activa | `POST /fases` con `confirmacion_no_estandar=true` + `fase_destino_id=3` (saltar la fase 2) | 201, y `paso_actual=3` (respeta el destino pedido) | **201, pero `paso_actual=2` — FAIL.** El campo `fase_destino_id` se ignora; el sistema siempre avanza a la siguiente fase secuencial, sin importar qué destino se pida |

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`.
- Activo de prueba: creado en el setup de la colección, especie 2 (Trucha Arcoíris) — misma especie que el ciclo
  productivo `id_ciclo_productiva=2` ("Ciclo completo trucha 2025-A", 3 fases), documentado en
  `anotaciones/modulo_2/curls_m02_cu02_activo_individual.md`.
- Newman 6.2.2 + htmlextra 1.23.1. Sin acceso a base de datos — toda la verificación es vía API.
- Fecha de ejecución: 2026-09-19.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-37/TC-M02-G33
newman run TC-M02-G33.postman_collection.json -r cli,htmlextra \
  --reporter-htmlextra-export RESULTADOS/TC-M02-G33_resultado.html \
  --suppress-exit-code
```

`--suppress-exit-code` es intencional: mientras el gap de TC-M02-042 exista, Newman termina con código de salida
distinto de 0 (1 assertion fallida) — el `FAIL` real queda igual registrado en el reporte HTML. Ver `NOTA_BLOQUEO.md`
para lo que falta implementar (`confirmacion_no_estandar`/`fase_destino_id` en el DTO y su lógica en el use case).
