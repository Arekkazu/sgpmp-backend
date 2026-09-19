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

## Resultado (2026-09-19): TC-M02-039 PASS — TC-M02-042 FAIL (gap real, no de entorno)

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
