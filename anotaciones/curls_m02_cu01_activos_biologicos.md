# CURLs — M02 CU01: Registrar y Asociar Activo Biológico (RF-33 + RF-34)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa.

---

## RF-33 — Registrar Activo Biológico

### POST /activos-biologicos — Activo INDIVIDUAL

```bash
curl -X POST http://localhost:8000/activos-biologicos \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "INDIVIDUAL",
    "id_especie": 2,
    "fecha_inicio_ciclo": "2026-01-15",
    "origen_financiero": "compra",
    "costo_adquisicion": 1500.00,
    "soporte_documental": "factura-trucha-001.pdf",
    "id_infraestructura": 1,
    "identificador": "TRU-002",
    "raza": "Arcoíris Atlántica",
    "sexo": "Hembra",
    "fecha_nacimiento": "2025-03-01T00:00:00Z",
    "peso_inicial": 0.25,
    "detalles_procedencia": "Piscicultura Valle del Cauca"
  }'
```

Respuesta esperada `201`:
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
- `400 ESPECIE_INVALIDA` — `id_especie` no existe o está inactiva (FA-05)
- `400 INFRAESTRUCTURA_INVALIDA` — `id_infraestructura` no existe o está inactiva (FA-06)
- `400 ATRIBUTO_INVALIDO` — clave en `atributos_dinamicos` no corresponde a métrica de la especie (FA-07)
- `400` (validación Pydantic) — `fecha_inicio_ciclo` futura o anterior a 1970 (FA-04)
- `400` (validación Pydantic) — INDIVIDUAL sin `identificador` / con `cantidad_inicial` (FA-02)
- `400` (validación Pydantic) — `compra`/`donacion` sin `costo_adquisicion` o `soporte_documental` (FA-08)
- `403 ACCESO_DENEGADO` — rol sin permiso C sobre `activos_biologicos` (Contador, Veterinario)
- `409 IDENTIFICADOR_DUPLICADO` — `identificador` ya registrado (FA-03)

---

### POST /activos-biologicos — Activo POBLACIONAL (nacimiento)

```bash
curl -X POST http://localhost:8000/activos-biologicos \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "POBLACIONAL",
    "id_especie": 2,
    "fecha_inicio_ciclo": "2026-03-01",
    "origen_financiero": "nacimiento",
    "id_infraestructura": 1,
    "cantidad_inicial": 500,
    "peso_promedio_inicial": 0.12
  }'
```

Respuesta esperada `201`:
```json
{
  "id_activo_biologico": 53,
  "tipo": "POBLACIONAL",
  "identificador": null,
  "nombre_estado": "ACTIVO",
  "detalle_individual": null,
  "detalle_poblacional": {
    "cantidad_inicial": 500,
    "cantidad_actual": 500,
    "peso_promedio_inicial": "0.1200",
    "peso_promedio": null,
    "biomasa_total": null,
    "densidad": null
  }
}
```

---

### POST /activos-biologicos — Activo POBLACIONAL (compra)

```bash
curl -X POST http://localhost:8000/activos-biologicos \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "POBLACIONAL",
    "id_especie": 2,
    "fecha_inicio_ciclo": "2026-04-01",
    "origen_financiero": "compra",
    "costo_adquisicion": 3200.00,
    "soporte_documental": "compra-lote-04-2026.pdf",
    "id_infraestructura": 1,
    "cantidad_inicial": 1000,
    "peso_promedio_inicial": 0.08
  }'
```

---

## RF-34 — Consultar Asociación a Infraestructura

### GET /activos-biologicos/{id}/infraestructura — Asociación activa

```bash
curl -X GET "http://localhost:8000/activos-biologicos/51/infraestructura?tipo_consulta=ACTIVA" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "tipo_consulta": "ACTIVA",
  "id_activo_biologico": 51,
  "asociacion_activa": {
    "id_historial": 1,
    "id_activo_biologico": 51,
    "id_infraestructura": 1,
    "nombre_infraestructura": "Estanque-01",
    "tipo_infraestructura": "estanque",
    "fecha_inicio": "2026-06-27T...",
    "fecha_fin": null
  },
  "historial": null
}
```

### GET /activos-biologicos/{id}/infraestructura — Historial completo

```bash
curl -X GET "http://localhost:8000/activos-biologicos/51/infraestructura?tipo_consulta=HISTORIAL" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "tipo_consulta": "HISTORIAL",
  "id_activo_biologico": 51,
  "asociacion_activa": null,
  "historial": [
    {
      "id_historial": 1,
      "id_infraestructura": 1,
      "nombre_infraestructura": "Estanque-01",
      "tipo_infraestructura": "estanque",
      "fecha_inicio": "2026-06-27T...",
      "fecha_fin": null
    }
  ]
}
```

Errores posibles:
- `404 ACTIVO_NO_ENCONTRADO` — el activo biológico no existe
- `400 TIPO_CONSULTA_INVALIDO` — `tipo_consulta` no es 'ACTIVA' ni 'HISTORIAL'
- `403 ACCESO_DENEGADO` — sin permiso R sobre `activos_biologicos`

---

## Casos de validación (FA)

### FA-02: INDIVIDUAL con cantidad_inicial → 400

```bash
curl -X POST http://localhost:8000/activos-biologicos \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "INDIVIDUAL",
    "id_especie": 2,
    "fecha_inicio_ciclo": "2026-01-15",
    "origen_financiero": "compra",
    "costo_adquisicion": 500,
    "soporte_documental": "doc.pdf",
    "id_infraestructura": 1,
    "identificador": "TRU-999",
    "raza": "Arcoíris",
    "sexo": "Hembra",
    "fecha_nacimiento": "2025-01-01T00:00:00Z",
    "cantidad_inicial": 5
  }'
```
Respuesta esperada `400`: `cantidad_inicial no aplica para activos de tipo INDIVIDUAL.`

### FA-03: Identificador duplicado → 409

```bash
# Segundo intento con el mismo identificador que ya existe
curl -X POST http://localhost:8000/activos-biologicos \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{ ..., "identificador": "TRU-001" }'
```
Respuesta esperada `409 IDENTIFICADOR_DUPLICADO`.

### FA-08: origen=compra sin soporte_documental → 400

```bash
curl -X POST http://localhost:8000/activos-biologicos \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_activo": "INDIVIDUAL",
    "id_especie": 2,
    "fecha_inicio_ciclo": "2026-01-15",
    "origen_financiero": "compra",
    "id_infraestructura": 1,
    "identificador": "TRU-X",
    "raza": "Arcoíris",
    "sexo": "Hembra",
    "fecha_nacimiento": "2025-01-01T00:00:00Z"
  }'
```
Respuesta esperada `400`: `costo_adquisicion mayor a 0 es requerido cuando origen_financiero es 'compra'.`
