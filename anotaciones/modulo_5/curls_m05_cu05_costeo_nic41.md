# CURLs — M05 CU05: Acumular inversión y proveer costos a M06 (RF-78, RF-79)

Base URL (local, sin proxy): `http://localhost:8000`
(En producción el proxy antepone `/api`.)

Autenticación: header `Authorization: Bearer <TOKEN>` obtenido de `POST /sesiones/`
(`{"correo_electronico": "...", "contrasena": "..."}`). Sesión expira a los 30 min de
inactividad — reloguear si aparece `401 SESION_EXPIRADA_INACTIVIDAD`.

Roles en los ejemplos: `<ADMIN>` (1), `<PROD>` (2), `<VET>` (3), `<ING>` (4, sin permiso),
`<CONT>` (5).

RBAC:
- recurso `costeo_directo_suministros` = **55** — C=1 (registrar) → Admin/Productor/Veterinario;
  R=2 (consultar acumulado) → +Contador/Revisor Fiscal; U=3 (corrección) → solo Admin/Contador.
- recurso `provision_nic41` = **56** — E=5 (consolidar/corregir) → Admin/Contador;
  R=2 (consultar) → +Productor/Revisor Fiscal.

Todos los escenarios de este documento fueron ejecutados contra un servidor local real
(`uvicorn main:app`) y verificados end-to-end el 2026-07-31, usando como fixture el activo
biológico **57** (`id_gestion_fases=33`, `id_ciclo_productivo=1`) para los escenarios 1-14 y
el activo **5** (`id_gestion_fases=32`) para los escenarios 15-16 (33 quedó cerrado/consolidado
tras el escenario 11). Durante esta verificación se encontró y corrigió un bug real en el
trigger de acumulación (`fn_acumular_costo_ciclo`) — ver el detalle en
`cu05_gaps_bd_rf78_rf79.md`, sección "Bug encontrado y corregido durante la verificación E2E".

---

## RF-78 — Registro directo de costos (SERVICIO_VETERINARIO / INSEMINACION)

### Escenario 1 — Registrar SERVICIO_VETERINARIO (acumulado creado)

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{
    "id_activo_biologico": 57,
    "tipo_suministro": "SERVICIO_VETERINARIO",
    "cantidad": 1,
    "unidad_medida": "servicio",
    "precio_unitario": 150000,
    "fecha_aplicacion": "2026-07-31",
    "justificacion_precio": "Visita veterinaria de control rutinario mensual",
    "id_idempotencia": "<uuid>"
  }'
```

Respuesta `201`: crea el `registro_suministro` (`tipo_operacion=REGISTRO`) y, vía
`trg_acumular_costo_ciclo`, crea `acumulado_ciclo` con `acumulado_total_ciclo=150000.0000`,
`acumulado_por_categoria={"SERVICIO_VETERINARIO": 150000.0}`, `version_acumulado=0`.

### Escenario 2 — Registrar INSEMINACION sobre el mismo `id_gestion_fases`

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{
    "id_activo_biologico": 57,
    "tipo_suministro": "INSEMINACION",
    "cantidad": 1,
    "unidad_medida": "dosis",
    "precio_unitario": 80000,
    "fecha_aplicacion": "2026-07-31",
    "justificacion_precio": "Costo de dosis de semen sexado importado",
    "id_idempotencia": "<uuid>"
  }'
```

`201`. El acumulado suma: `acumulado_total_ciclo=230000.0000`,
`acumulado_por_categoria={"INSEMINACION": 80000.0, "SERVICIO_VETERINARIO": 150000.0}` — las
categorías se mantienen separadas dentro del mismo `id_gestion_fases`.

### Escenario 3 — Reenvío con el mismo `id_idempotencia` (E8, idempotencia)

Repetir exactamente el request del escenario 1 con el mismo `id_idempotencia`:

```bash
curl -i -X POST http://localhost:8000/suministros/costeo-directo \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{..., "id_idempotencia": "<mismo-uuid-del-escenario-1>"}'
```

`HTTP 200` (no 201) con el `id_registro_suministro`/`fecha_registro` originales sin cambios —
no se duplica el registro ni el acumulado. Bug encontrado y corregido durante la implementación:
la primera versión devolvía `201` en el reenvío; se agregó `response.status_code = 200` en el
router cuando `resultado.ya_procesado=True`.

### Escenario 4 — Mismo contenido con `id_idempotencia` distinto (E6, deduplicación)

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{..., "id_idempotencia": "<uuid-nuevo>"}'
```

Mismos `id_activo_biologico`/`tipo_suministro`/`fecha_aplicacion`/`cantidad`/`precio_unitario`
que el escenario 1, pero `id_idempotencia` diferente:

`409 SUMINISTRO_DUPLICADO` — `"Registro de suministro idéntico ya existe. Si es una
corrección, use tipo_operacion=CORRECCION con id_registro_original."`

### Escenario 5 — `justificacion_precio` demasiado corta (E2)

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{..., "justificacion_precio": "corta"}'
```

`400 VAL_ENTRADA`:
```json
{"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud",
 "fields":[{"field":"justificacion_precio","message":"String should have at least 20 characters"}]}
```

### Escenario 6 — Activo sin ciclo productivo activo (E1)

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{"id_activo_biologico": 999999, "tipo_suministro": "SERVICIO_VETERINARIO", ...}'
```

`422 CICLO_NO_ACTIVO`:
```json
{"error_code":"CICLO_NO_ACTIVO",
 "message":"No existe un ciclo productivo activo para el activo 999999. Verifique el estado del ciclo en M02 antes de registrar suministros."}
```

### Escenario 10 — RBAC negativo (Ingeniero de Campo sin permiso de creación)

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo \
  -H "Authorization: Bearer <ING>" -H "Content-Type: application/json" \
  -d '{...}'
```

`403 ACCESO_DENEGADO` — el rol Ingeniero de Campo no tiene permiso `C` sobre el recurso 55.

---

## RF-78 — Corrección de un registro existente

### Escenario 7 — Corrección válida (reduce el costo sin dejar el acumulado negativo)

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo/<id_registro_original>/correccion \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" \
  -d '{
    "cantidad_corregida": 1,
    "precio_unitario_corregido": 120000,
    "motivo_correccion": "Correccion de tarifa veterinaria tras revision de factura del proveedor",
    "justificacion_precio": "Precio ajustado segun factura definitiva recibida del proveedor veterinario",
    "id_idempotencia": "<uuid>"
  }'
```

Sobre el registro SERVICIO_VETERINARIO del escenario 1 (`costo_registro=150000`):
`201`, crea una fila `tipo_operacion=CORRECCION` con `costo_registro=120000` y
`id_registro_original` apuntando al original. El original **permanece intacto**
(`costo_registro=150000` sin cambios). El acumulado pasa de `230000` a `200000`
(`230000 + (120000 - 150000)`), `version_acumulado` incrementa.

Solo Admin/Contador tienen el permiso `U` sobre el recurso 55 — un intento con `<VET>`
devuelve `403 ACCESO_DENEGADO`.

### Escenario 8 — Corrección que dejaría el acumulado negativo (FA-09)

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo/<id_registro_original>/correccion \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" \
  -d '{
    "cantidad_corregida": 1,
    "precio_unitario_corregido": 1,
    "motivo_correccion": "Correccion drastica para forzar acumulado negativo en prueba deliberada",
    "justificacion_precio": "Prueba deliberada de rechazo por acumulado negativo en el ciclo dos",
    "id_idempotencia": "<uuid>"
  }'
```

`422 ACUMULADO_NEGATIVO`:
```json
{"error_code":"ACUMULADO_NEGATIVO",
 "message":"No es posible registrar la corrección: el acumulado del ciclo resultante sería -29998.990000 (negativo). El registro original permanece intacto.",
 "fields":[{"field":"cantidad_corregida","message":"..."}]}
```

Verificado que **no hay efecto colateral**: ni `registro_suministro` ni `acumulado_ciclo`
cambian (la validación ocurre en la app, vía `AcumuladoCiclo.validar_correccion_no_negativa()`,
**antes** de intentar persistir — nunca llega a la base de datos).

### Escenario 9 — Corrección con `id_registro_original` inexistente

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo/00000000-0000-0000-0000-000000000000/correccion \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" \
  -d '{...}'
```

`404 REGISTRO_ORIGINAL_NO_ENCONTRADO`.

### Bonus — Corrección sobre una corrección (rechazada)

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo/<id_de_una_correccion>/correccion \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" -d '{...}'
```

`422 CORRECCION_SOBRE_CORRECCION` — `"El registro <id> ya es una corrección; no se puede
corregir una corrección. Referencie el registro original."`

---

## RF-78 — Consultas de acumulado

```bash
curl http://localhost:8000/suministros/costeo-directo/acumulado/activo/57 -H "Authorization: Bearer <CONT>"
curl http://localhost:8000/suministros/costeo-directo/acumulado/ciclo/33   -H "Authorization: Bearer <CONT>"
```

Ambos devuelven `200` con el mismo `AcumuladoCicloResponse`; el primero resuelve el
`id_gestion_fases` a partir del ciclo abierto del activo, el segundo lo recibe directo
(uso típico de M06/Contador tras el cierre, cuando ya no hay ciclo "abierto").

---

## RF-79 — Consolidación NIC-41

### Escenario 11 — Consolidar sobre ciclo activo (rechazado) → cerrar → consolidar

```bash
# Con la fase todavía activa (es_activa=true):
curl -X POST http://localhost:8000/suministros/nic41/ciclo/33/consolidar \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" -d '{}'
```

`409 CICLO_ACTIVO` — `"El ciclo 33 está activo. El reporte consolidado solo está disponible
tras el cierre del ciclo."`

Tras cerrar la fase (RF-41 no tiene hook de app; se cierra directo en BD para la prueba —
`UPDATE modulo2.gestiones_fases SET es_activa=false, fecha_finalizacion=now() WHERE
id_gestion_fases=33`):

```bash
curl -X POST http://localhost:8000/suministros/nic41/ciclo/33/consolidar \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" -d '{}'
```

`201`:
```json
{
  "id_provision": 1, "id_activo_biologico": 57, "id_gestion_fases": 33,
  "modalidad": "CONSOLIDADO",
  "monto_provision": "120010.0100",
  "desglose_categoria": {"ALIMENTO": "10.0000", "INSEMINACION": "0.0100", "SERVICIO_VETERINARIO": "120000.0000"},
  "total_registros": 5, "version_reporte": 1, "id_reporte_anterior": null,
  "es_reporte_potencialmente_incompleto": true,
  "estado": "GENERADO",
  "hash_integridad": "cbde3757047e3eeb11e4b0d965afe29944d15779ef79a9c769e1ccb125d7a27a"
}
```

`es_reporte_potencialmente_incompleto=true` aquí es correcto y esperado — el fixture tiene un
registro ALIMENTO (`costo=10`) insertado **antes** de que existiera `trg_acumular_costo_ciclo`
(dato heredado de pruebas de CU-01 previas), así que nunca se sumó a `acumulado_ciclo`
(`acumulado_total_ciclo=120000.01`) pero el consolidador sí lo incluye al recomputar desde
`registro_suministro` (`120010.01`) — la discrepancia entre ambos números es justamente lo que
la bandera está diseñada para detectar.

### Escenario 12 — `consolidar-manual` (fuerza incompleto, no exige cierre)

```bash
curl -X POST http://localhost:8000/suministros/nic41/ciclo/33/consolidar-manual \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" -d '{}'
```

`201`, `version_reporte=2`, `id_reporte_anterior=1` (comparte la cadena de versiones con
`consolidar`), `es_reporte_potencialmente_incompleto=true` siempre, sin importar el estado del
ciclo.

### Escenario 13 — Corregir una provisión + listar versiones

```bash
curl -X POST http://localhost:8000/suministros/nic41/2/correccion \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" \
  -d '{"motivo_correccion": "Correccion de la provision para incluir revision del contador tras auditoria interna"}'
```

`201`, `version_reporte=3`, `id_reporte_anterior=2`, `motivo_correccion` poblado. El monto se
**recalcula** desde el estado actual (`construir_consolidado()`), no copia el valor anterior.

```bash
curl http://localhost:8000/suministros/nic41/ciclo/33/versiones -H "Authorization: Bearer <CONT>"
```

`200`, devuelve las 3 versiones (`version_reporte` 1→2→3, cadena `id_reporte_anterior`
correcta). Las 3 versiones conservan `estado="GENERADO"` de forma independiente — el use case
de corrección **no** muta el `estado` de la versión anterior (evita disparar
`trg_provision_hash` sobre una fila que debe permanecer como evidencia congelada).

### Escenario 14 — Estabilidad del `hash_integridad`

```bash
curl http://localhost:8000/suministros/nic41/3 -H "Authorization: Bearer <CONT>"
curl http://localhost:8000/suministros/nic41/3 -H "Authorization: Bearer <CONT>"
```

Mismo `hash_integridad` en ambas respuestas — el trigger genérico de hash solo recalcula en
`INSERT`/`UPDATE`, nunca en `SELECT`.

---

## RF-78 — Concurrencia y cascada desde CU-01

### Escenario 15 — 2 requests concurrentes sobre el mismo `id_gestion_fases` nuevo

```bash
curl -X POST http://localhost:8000/suministros/costeo-directo -H "Authorization: Bearer <VET>" \
  -d '{"id_activo_biologico": 5, "tipo_suministro": "SERVICIO_VETERINARIO", "precio_unitario": 50000, ...}' &
curl -X POST http://localhost:8000/suministros/costeo-directo -H "Authorization: Bearer <VET>" \
  -d '{"id_activo_biologico": 5, "tipo_suministro": "INSEMINACION", "precio_unitario": 30000, ...}' &
wait
```

Ambas `201`. `acumulado_ciclo` resultante: `acumulado_total_ciclo=80000.0000`
(`50000+30000`, exacto, sin pérdida), `version_acumulado=1` (la primera petición en llegar crea
la fila vía el fallback `INSERT ... ON CONFLICT`, `version=0`; la segunda encuentra la fila con
el `UPDATE` normal, que la incrementa a `1` — el lock de fila de Postgres serializa
correctamente la carrera).

### Escenario 16 — Registro de ALIMENTO vía CU-01 también actualiza `acumulado_ciclo`

```bash
curl -X POST http://localhost:8000/suministros/consumo-alimentos \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{"id_activo_biologico": 5, "id_tipo_alimento": 1, "fecha_consumo": "2026-07-31", "cantidad_alimento": 5}'
```

`201` (endpoint de CU-01, RF-75). Verificado en BD: se creó automáticamente una fila en
`modulo5.registro_suministro` (`tipo_suministro='ALIMENTO'`, `costo_registro=5.0000`,
`id_gestion_fases` poblado) vía `fn_trg_poblar_registro_suministro_alimento`, y
`acumulado_ciclo.acumulado_por_categoria` ganó la clave `"ALIMENTO": 5.0` — confirma que la
extensión del Gap 6 a los triggers de CU-04 dispara la cascada completa (ledger → acumulado)
sin tocar el código Python de CU-01.

---

## Resumen de códigos de error verificados

| Código | HTTP | Escenario |
|---|---|---|
| `VAL_ENTRADA` | 400 | justificación de precio < 20 caracteres |
| `ACCESO_DENEGADO` | 403 | rol sin permiso RBAC |
| `REGISTRO_ORIGINAL_NO_ENCONTRADO` | 404 | corrección sobre UUID inexistente |
| `SUMINISTRO_DUPLICADO` | 409 | duplicado por contenido (mismo `id_idempotencia` distinto) |
| `CICLO_ACTIVO` | 409 | consolidar sobre ciclo aún abierto |
| `CICLO_NO_ACTIVO` | 422 | activo sin ciclo productivo activo |
| `CORRECCION_SOBRE_CORRECCION` | 422 | corregir una fila que ya es CORRECCION |
| `ACUMULADO_NEGATIVO` | 422 | corrección dejaría el acumulado en negativo (FA-09) |
