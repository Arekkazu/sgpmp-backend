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

## ⚠️ Resultado: BLOQUEADO — ambos sub-casos, mismo defecto ya identificado en TC-M02-G23 (RF-37)

**Estado general: FAIL/BLOQUEADO. 3/6 assertions PASS en Postman/Newman.** Ver `NOTA_BLOQUEO.md` para la causa raíz
(confirmada por código, no una hipótesis) y `RESULTADOS/TC-M02-G33_resultado.md` para el detalle completo.

`POST /activos-biologicos/{id}/fases` devuelve **500** para cualquier activo y cualquier ciclo productivo válido —
el mismo defecto **INC-M02-37-01** ya documentado al intentar armar la precondición de TC-M02-047
(`tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/NOTA_BLOQUEO.md`). Esto bloquea **TC-M02-039 directamente**: no
se puede verificar "la fase actual se cierra y se crea la nueva ACTIVA" porque ninguna fase, estándar o no, se
llega a crear.

### TC-M02-042 tiene además un segundo bloqueo, estructural e independiente

Incluso si INC-M02-37-01 se corrigiera hoy, **TC-M02-042 seguiría sin poder pasar**: `CambiarFaseDTO`
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
| TC-M02-039 | Activo ACTIVO, sin fase previa, ciclo productivo válido y de su misma especie | `POST /fases` con `id_ciclo_productiva` | 201, fase creada, `paso_actual=1` | **500 — bloqueado por INC-M02-37-01** |
| TC-M02-042 | Mismo activo | `POST /fases` con `confirmacion_no_estandar=true` + `fase_destino_id` | 201, transición no estándar registrada con evidencia de la confirmación | **500 — bloqueado por INC-M02-37-01, y aunque se corrigiera, los campos de confirmación no existen en el DTO (gap estructural adicional)** |

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`.
- Activo de prueba: `id_activo_biologico=201`, especie 2 (Trucha Arcoíris) — misma especie que el ciclo productivo
  `id_ciclo_productiva=2` ("Ciclo completo trucha 2025-A", documentado en
  `anotaciones/modulo_2/curls_m02_cu02_activo_individual.md`), para eliminar cualquier duda de que el 500 se deba a
  un descalce de especie en vez de al bug real.
- Newman 6.2.2 + htmlextra 1.23.1. Sin acceso a base de datos — toda la verificación es vía API.
- Fecha de ejecución: 2026-09-09/10.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-37/TC-M02-G33
newman run TC-M02-G33.postman_collection.json -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G33.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G33.html \
  --suppress-exit-code
```

Tras corregir INC-M02-37-01, el paso "1" (TC-M02-039) debería pasar de 500 a 201. El paso "3" (TC-M02-042) seguirá
fallando hasta que además se agreguen `confirmacion_no_estandar`/`fase_destino_id` al DTO y su lógica en el use
case — ver `NOTA_BLOQUEO.md`.
