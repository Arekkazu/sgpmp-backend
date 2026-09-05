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
- `404 ACTIVO_NO_ENCONTRADO` — el activo biológico no existe
- `403 ACCESO_DENEGADO` — sin permiso R sobre `activos_biologicos`

---

### PATCH /activos-biologicos/{id} — Actualizar atributos del individuo

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/51 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "raza": "Arcoíris Premium",
    "peso_inicial": 0.30
  }'
```

Respuesta esperada `200` con los campos actualizados en `detalle_individual`.

Errores posibles:
- `400 TIPO_INVALIDO` — el activo es POBLACIONAL (no tiene detalle individual)
- `404 ACTIVO_NO_ENCONTRADO` — el activo biológico no existe
- `422` (validación Pydantic) — ningún campo enviado en el body
- `403 ACCESO_DENEGADO` — sin permiso U sobre `activos_biologicos`

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
  "nombre_ciclo": "Ciclo completo trucha 2025-A",
  "nombre_fase_actual": "Fase larval trucha",
  "paso_actual": 1,
  "total_pasos": 3,
  "fecha_inicio": "2026-06-27T...",
  "fecha_finalizacion": null,
  "es_activa": true,
  "motivo_cambio": "Inicio de ciclo completo trucha"
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
