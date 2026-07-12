# CURLs — M04 CU-04: Consultar Historial Diagnóstico del Activo (RF-67)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa (rol Veterinario, Productor o Administrador).

---

## Flujo principal — consulta con rango de fechas

### GET /prediccion/historial/{id_activo_biologico}

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2025-01-01&fecha_fin=2026-07-11&incluir_alertas=true" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "eventos": [
    {
      "id_evento": "550e8400-e29b-41d4-a716-446655440000",
      "tipo_evento": "INFERENCIA",
      "id_activo_biologico": 1,
      "fecha_evento": "2026-07-10T14:32:00+00:00",
      "id_resultado_inferencia": "7f3a9b1c-2d4e-5f6a-8b9c-0d1e2f3a4b5c",
      "payload": {
        "nivel_riesgo": 2,
        "id_patologia": 3,
        "nombre_patologia": "Leptospirosis",
        "probabilidad_riesgo": {"bajo": 0.10, "medio": 0.25, "alto": 0.65},
        "probabilidad_enfermedad": {"3": 0.72, "5": 0.18},
        "confianza_global": 0.87,
        "tipo_modelo": "ESPECIES_PEQUEÑAS",
        "id_version_modelo": 4,
        "modo_ejecucion": "SERVIDOR",
        "contexto_incompleto": false,
        "latencia_excedida": false,
        "latencia_ms": 342,
        "fecha_inicio_ventana": "2026-07-10T14:22:00+00:00",
        "fecha_fin_ventana": "2026-07-10T14:32:00+00:00",
        "tiene_alerta_generada": true,
        "id_alerta_generada": 7
      }
    },
    {
      "id_evento": "661f9511-f30c-52e5-b827-557766551111",
      "tipo_evento": "ALERTA",
      "id_activo_biologico": 1,
      "fecha_evento": "2026-07-10T14:32:01+00:00",
      "id_resultado_inferencia": "7f3a9b1c-2d4e-5f6a-8b9c-0d1e2f3a4b5c",
      "payload": {
        "id_alerta_patologica": 7,
        "id_patologia": 3,
        "nombre_patologia": "Leptospirosis",
        "probabilidad_pct": 65.0,
        "nivel_criticidad": "ALTO",
        "estado_alerta": "PENDIENTE"
      }
    }
  ],
  "cursor_siguiente": "eyJ0cyI6ICIyMDI2LTA3LTEwVDE0OjMyOjAwKzAwOjAwIiwgImlkIjogIjdmM2E5YjFjLTJkNGUtNWY2YS04YjljLTBkMWUyZjNhNGI1YyJ9",
  "total_pagina": 2
}
```

---

## FA-01 — Sin datos en el rango seleccionado

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2020-01-01&fecha_fin=2020-12-31" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "eventos": [],
  "cursor_siguiente": null,
  "total_pagina": 0
}
```

---

## Filtros opcionales

### Filtrar por nivel de riesgo (0=sin riesgo, 1=bajo, 2=medio, 3=alto)

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2025-01-01&fecha_fin=2026-07-11&nivel_riesgo=3" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200` con solo inferencias de nivel 3 (crítico).

### Filtrar por patología

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2025-01-01&fecha_fin=2026-07-11&id_patologia=3" \
  -H "Authorization: Bearer <TOKEN>"
```

---

## FA-02 — Activo no encontrado o inaccesible (cuando stub M02 se reemplace)

```bash
curl -X GET "http://localhost:8000/prediccion/historial/9999?fecha_inicio=2025-01-01&fecha_fin=2026-07-11" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `404`:
```json
{
  "code": "ACTIVO_NO_ENCONTRADO",
  "message": "El activo biológico no existe o no está disponible.",
  "field": null
}
```

---

## FA-03 — Rango de fechas inválido

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2026-07-11&fecha_fin=2025-01-01" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `400`:
```json
{
  "code": "RANGO_FECHAS_INVALIDO",
  "message": "La fecha de inicio no puede ser posterior a la fecha de fin.",
  "field": "fecha_inicio"
}
```

---

## FA-03b — Fecha futura

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2025-01-01&fecha_fin=2099-12-31" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `400`:
```json
{
  "code": "RANGO_FECHAS_INVALIDO",
  "message": "No se pueden consultar rangos de fecha futuros.",
  "field": "fecha_fin"
}
```

---

## FA-05 — Cursor de paginación inválido

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2025-01-01&fecha_fin=2026-07-11&cursor_paginacion=cursor_corrupto_xxxx" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `400`:
```json
{
  "code": "CURSOR_INVALIDO",
  "message": "El cursor de paginación es inválido. Reinicia la consulta desde la primera página.",
  "field": "cursor_paginacion"
}
```

---

## Paginación — segunda página con cursor

Tomar el valor de `cursor_siguiente` de la respuesta anterior e incluirlo en la siguiente llamada:

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2025-01-01&fecha_fin=2026-07-11&cursor_paginacion=eyJ0cyI6ICIyMDI2LTA3LTEwVDE0OjMyOjAwKzAwOjAwIiwgImlkIjogIjdmM2E5YjFjLTJkNGUtNWY2YS04YjljLTBkMWUyZjNhNGI1YyJ9" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200` con los siguientes 50 eventos (o menos si es la última página, con `cursor_siguiente: null`).

---

## FA sin token / sin permiso

```bash
curl -X GET "http://localhost:8000/prediccion/historial/1?fecha_inicio=2025-01-01&fecha_fin=2026-07-11"
```

Respuesta `401`:
```json
{
  "code": "TOKEN_AUSENTE",
  "message": "Se requiere autenticación."
}
```

Con token de rol sin permiso (ej. Contador):
```json
{
  "code": "PERMISO_DENEGADO",
  "message": "No tienes permiso para realizar esta acción."
}
```
