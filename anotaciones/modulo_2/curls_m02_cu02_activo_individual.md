# CURLs — M02 CU02: Gestionar Activo Individual y Fases (RF-35 + RF-37)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa.

---

## RF-35 — Gestionar Activo Individual

### GET /activos-biologicos/{id} — Consultar activo

```bash
curl -X GET http://localhost:8000/activos-biologicos/51 \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_activo_biologico": 51,
  "id_especie": 2,
  "tipo": "INDIVIDUAL",
  "identificador": "TRU-002",
  "fecha_inicio_ciclo": "2026-01-15",
  "origen_financiero": "compra",
  "costo_adquisicion": "1500.0000",
  "soporte_documental": "factura-trucha-001.pdf",
  "id_infraestructura": 1,
  "id_estado": 1,
  "nombre_estado": "ACTIVO",
  "id_usuario": 1,
  "fecha_creacion": "2026-06-27T...",
  "fecha_actualizacion": null,
  "detalle_individual": {
    "raza": "Arcoíris Atlántica",
    "sexo": "Hembra",
    "fecha_nacimiento": "2025-03-01T00:00:00Z",
    "peso_inicial": "0.2500"
  },
  "detalle_poblacional": null
}
```

Errores posibles:
- `404 ACTIVO_NO_ENCONTRADO` — el activo biológico no existe, **o pertenece a
  una finca fuera del alcance del usuario** (RF-25, INC-M02-39-G27: se
  responde igual que "no existe" para no revelar la existencia de activos
  ajenos — BOLA, OWASP API1)
- `403 ACCESO_DENEGADO` — sin permiso R sobre `activos_biologicos`

---

### PATCH /activos-biologicos/{id} — Actualizar atributos del individuo

RBAC: Administrador, Productor, Ingeniero de Campo y **Veterinario** (tarea
Taiga "RF-35 RBAC Veterinario, eventos pendientes, concurrencia optimista"
— `vet_actualizar_activo_biologico`, ver
`anotaciones/modulo_2/cu02_gaps_bd_rf35_fix_rbac_concurrencia.md`).

`fecha_actualizacion` implementa concurrencia optimista (RF-35): enviar el
valor obtenido en el último `GET`. Si el activo nunca fue editado, el valor
es `null` y puede omitirse del body.

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/51 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "raza": "Arcoíris Premium",
    "peso_inicial": 0.30,
    "fecha_actualizacion": null
  }'
```

Respuesta esperada `200` con los campos actualizados en `detalle_individual`
y `fecha_actualizacion` con el nuevo timestamp.

Errores posibles:
- `400 TIPO_INVALIDO` — el activo es POBLACIONAL (no tiene detalle individual)
- `404 ACTIVO_NO_ENCONTRADO` — el activo biológico no existe
- `412 CONFLICTO_CONCURRENCIA` — `fecha_actualizacion` no coincide con el valor actual en BD (el activo fue modificado por otro usuario desde el último `GET`)
- `422 EVENTO_PENDIENTE_SIN_CERRAR` — el activo está en estado `EN_TRATAMIENTO`/`AISLADO` (evento sanitario sin cerrar)
- `422 HISTORIAL_INCONSISTENTE` — el último registro de `historicos_estados_activos` no coincide con el `id_estado` actual del activo
- `422` (validación Pydantic) — ningún campo enviado en el body
- `403 ACCESO_DENEGADO` — sin permiso U sobre `activos_biologicos`

#### Caso FA: PATCH con fecha_actualizacion desactualizada → 412

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/51 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"raza": "XYZ", "fecha_actualizacion": "2026-01-01T00:00:00Z"}'
```

Respuesta esperada `412`:
```json
{
  "code": "CONFLICTO_CONCURRENCIA",
  "message": "El activo fue modificado por otro usuario. Recarga y reintenta."
}
```

#### Caso FA: PATCH sobre activo con evento sanitario pendiente → 422

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/51 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"raza": "XYZ"}'
```

Respuesta esperada `422` (activo en estado `EN_TRATAMIENTO` o `AISLADO`):
```json
{
  "code": "EVENTO_PENDIENTE_SIN_CERRAR",
  "message": "No se puede editar el activo mientras tenga un evento sanitario pendiente sin cerrar (estado actual: EN_TRATAMIENTO). Cambie el estado de vuelta a ACTIVO, INACTIVO o CERRADO antes de editar sus datos."
}
```

#### Caso FA: PATCH en activo POBLACIONAL → 400

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/53 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"raza": "XYZ"}'
```

Respuesta esperada `400 TIPO_INVALIDO`.

#### Caso FA: PATCH sin campos → 422

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/51 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Respuesta esperada `422`: `Al menos un campo debe estar presente para actualizar.`

---

## RF-37 — Gestión de Fases del Ciclo Productivo

### POST /activos-biologicos/{id}/fases — Cambiar fase

`fase_destino_id` (opcional, tarea Taiga fase_destino/confirmacion_no_estandar):
`id_ciclos_productivo_biologico` de la fase a la que se quiere transicionar.
Si se omite, se avanza a la fase estándar siguiente (comportamiento
histórico, sin cambios). Si se especifica una fase que **no** es la estándar
siguiente (salto hacia adelante, retroceso, o re-entrar tras completar el
ciclo), se exige `confirmacion_no_estandar: true` o se rechaza con `409`.
`fecha_inicio` no puede ser futura.

#### Primera fase (iniciar ciclo)

```bash
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_ciclo_productiva": 2,
    "motivo_cambio": "Inicio de ciclo completo trucha"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_gestion_fases": 20,
  "id_activo_biologico": 51,
  "id_ciclo_productiva": 2,
  "id_ciclos_productivo_biologico": 5,
  "nombre_ciclo": "Ciclo completo trucha 2025-A",
  "nombre_fase_actual": "Fase larval trucha",
  "paso_actual": 1,
  "total_pasos": 3,
  "fecha_inicio": "2026-06-27T...",
  "fecha_finalizacion": null,
  "es_activa": true,
  "motivo_cambio": "Inicio de ciclo completo trucha",
  "es_transicion_no_estandar": false
}
```

#### Segunda fase (avanzar ciclo)

```bash
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_ciclo_productiva": 2,
    "motivo_cambio": "Transición a fase juvenil — peso alcanzado"
  }'
```

Respuesta esperada `201` con `paso_actual: 2`, `nombre_fase_actual: "Fase juvenil trucha"`.

#### Caso FA: ciclo inexistente → 400

```bash
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 9999}'
```

Respuesta esperada `400 CICLO_INVALIDO`.

#### Caso FA: ciclo completado → 422

```bash
# Después de completar las 3 fases del ciclo 2
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 2}'
```

Respuesta esperada `422 CICLO_COMPLETADO`.

#### Caso FA: transición no estándar sin confirmar → 409

```bash
# El activo está en la fase 1 (Alevinaje); fase_destino_id=3 salta la fase 2
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 2, "fase_destino_id": 7}'
```

Respuesta esperada `409`:
```json
{
  "code": "TRANSICION_NO_ESTANDAR_SIN_CONFIRMAR",
  "message": "La transición a \"Fase adulta trucha\" no es la siguiente fase estándar de la secuencia del ciclo \"Ciclo completo trucha 2025-A\". Si esta transición es intencional (salto de fase o retroceso), reenvíe la solicitud con confirmacion_no_estandar=true."
}
```

#### Caso FA: transición no estándar confirmada → 201

```bash
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 2, "fase_destino_id": 7, "confirmacion_no_estandar": true, "motivo_cambio": "Salto por crecimiento acelerado, autorizado por veterinario"}'
```

Respuesta esperada `201` con `"es_transicion_no_estandar": true`.

#### Caso FA: fase_destino_id inexistente en el ciclo → 400

```bash
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 2, "fase_destino_id": 9999}'
```

Respuesta esperada `400 FASE_DESTINO_INVALIDA`.

#### Caso FA: fecha_inicio futura → 400

```bash
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 2, "fecha_inicio": "2099-01-01T00:00:00Z"}'
```

Respuesta esperada `400`: `La fecha de inicio de la fase no puede ser futura.`

#### Caso FA: fase destino igual a la actual → 409 (INC-M02-G33, #428)

```bash
# El activo ya está en la fase 5; confirmar no cambia nada (RF-37: "la fase destino debe ser distinta a la actual")
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 2, "fase_destino_id": 5, "confirmacion_no_estandar": true}'
```

Respuesta esperada `409 FASE_DESTINO_IGUAL_ACTUAL` (`field: fase_destino_id`).

#### Caso FA: fecha que se solapa con el historial → 409 (INC-M02-G34, #429)

```bash
# fecha_inicio anterior al inicio de la fase activa o al fin de la última fase cerrada
curl -X POST http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 2, "fecha_inicio": "2020-01-01T00:00:00Z"}'
```

Respuesta esperada `409 FASE_SOLAPADA` (`field: fecha_inicio`). Antes: `500 ERROR_INTERNO`
(trigger `trg_fase_solapamiento`, SQLSTATE `P0227`, sin traducir).

#### Caso FA: activo CERRADO o en BAJA → 409 (INC-M02-G34, #429)

```bash
curl -X POST http://localhost:8000/activos-biologicos/8/fases \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"id_ciclo_productiva": 5}'
```

Respuesta esperada `409 ACTIVO_NO_OPERATIVO`. Antes: `500 ERROR_INTERNO`
(trigger `trg_fase_activo_estado_valido`, SQLSTATE `P0228`, sin traducir).

---

### GET /activos-biologicos/{id}/fases — Historial de fases

```bash
curl -X GET http://localhost:8000/activos-biologicos/51/fases \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_activo_biologico": 51,
  "fases": [
    {
      "id_gestion_fases": 20,
      "id_ciclo_productiva": 2,
      "nombre_ciclo": "Ciclo completo trucha 2025-A",
      "nombre_fase_actual": "Fase larval trucha",
      "paso_actual": 1,
      "total_pasos": 3,
      "fecha_inicio": "2026-06-27T...",
      "fecha_finalizacion": "2026-06-27T...",
      "es_activa": false,
      "motivo_cambio": "Transición a fase juvenil — peso alcanzado"
    },
    {
      "id_gestion_fases": 21,
      "id_ciclo_productiva": 2,
      "nombre_ciclo": "Ciclo completo trucha 2025-A",
      "nombre_fase_actual": "Fase juvenil trucha",
      "paso_actual": 2,
      "total_pasos": 3,
      "fecha_inicio": "2026-06-27T...",
      "fecha_finalizacion": null,
      "es_activa": true,
      "motivo_cambio": null
    }
  ]
}
```

Errores posibles:
- `404 ACTIVO_NO_ENCONTRADO` — el activo biológico no existe
- `403 ACCESO_DENEGADO` — sin permiso R sobre `activos_biologicos`
