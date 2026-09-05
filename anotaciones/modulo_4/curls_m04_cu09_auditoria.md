# CURLs — M04 CU-09: Auditoría y Trazabilidad del Motor (RF-73)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN_ADMIN>` por el JWT de sesión activa con **rol Administrador** (id_rol=1).

---

## Flujo 1 — Listar bitácora de auditoría con filtros

### GET /prediccion/auditoria

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

Respuesta esperada `200`:
```json
{
  "total": 87,
  "pagina": 1,
  "por_pagina": 50,
  "items": [
    {
      "id_evento": "uuid-1234",
      "tipo_evento": "VERSION_ACTIVADA",
      "modulo": "MODULO4",
      "fecha_evento": "2026-07-12T14:22:10+00:00",
      "tipo_actor": "USUARIO",
      "correlacion_id": "uuid-corr",
      "payload_evento": {"tipo_modelo": "BOVINO_ADULTO", "id_version_nueva": 3},
      "es_payload_truncado": false,
      "severidad_evento": "INFO",
      "origen_registro": "DESARROLLO_M04",
      "id_usuario": 1,
      "id_sistema": null,
      "id_referencia": "3",
      "entidad_referencia": "version_modelo",
      "resultado_operacion": "EXITOSO",
      "codigo_error": null,
      "descripcion_error": null,
      "origen_dato": null,
      "version_modelo": null,
      "latencia_ms": null,
      "hash_evento": "abc123...64chars"
    }
  ]
}
```

### Con filtros por tipo de evento

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria?tipo_evento=VERSION_ACTIVADA&pagina=1&por_pagina=10" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

### Con filtro por rango de fechas

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria?fecha_desde=2026-07-01T00:00:00Z&fecha_hasta=2026-07-12T23:59:59Z" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

### Con filtro por actor

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria?id_usuario=5&severidad_evento=WARNING" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

### Con filtro por entidad referenciada

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria?id_referencia=3" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

Errores posibles:
- `401 UNAUTHORIZED` — token ausente o inválido (FA-13)
- `403 FORBIDDEN` — rol sin permiso R sobre recurso 46 (FA-13)

---

## Flujo 2 — Obtener detalle de un evento

### GET /prediccion/auditoria/{id_evento}

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria/550e8400-e29b-41d4-a716-446655440001" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

Respuesta esperada `200`:
```json
{
  "id_evento": "550e8400-e29b-41d4-a716-446655440001",
  "tipo_evento": "RETROALIMENTACION_REGISTRADA",
  "modulo": "MODULO4",
  "fecha_evento": "2026-07-12T10:15:30+00:00",
  "tipo_actor": "USUARIO",
  "correlacion_id": "uuid-corr-999",
  "payload_evento": {
    "id_resultado_inferencia": "uuid-inf",
    "estado_retroalimentacion": "INCORRECTO",
    "id_usuario_veterinario": 5,
    "conflicto_retroalimentacion": false
  },
  "es_payload_truncado": false,
  "severidad_evento": "INFO",
  "origen_registro": "DESARROLLO_M04",
  "id_usuario": 5,
  "id_referencia": "uuid-retro",
  "entidad_referencia": "retroalimentacion_clinica",
  "resultado_operacion": "EXITOSO",
  "hash_evento": "abc123...64chars"
}
```

Errores posibles:
- `401 UNAUTHORIZED` — token ausente o inválido
- `403 FORBIDDEN` — rol sin permiso R sobre recurso 46
- `404 EVENTO_AUDITORIA_NO_ENCONTRADO` — UUID no existe en la tabla

---

## Flujo 3 — Exportar bitácora en JSON

### GET /prediccion/auditoria/exportar

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria/exportar?formato=json" \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -o auditoria_m04.json
```

Respuesta: descarga de archivo `auditoria_m04.json` (Content-Type: application/json).

---

## Flujo 4 — Exportar bitácora en CSV

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria/exportar?formato=csv&tipo_evento=VERSION_ACTIVADA" \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -o auditoria_m04.csv
```

Respuesta: descarga de archivo `auditoria_m04.csv` (Content-Type: text/csv). Compatible con Excel.

Errores posibles en exportar:
- `401 UNAUTHORIZED` — token ausente o inválido
- `403 FORBIDDEN` — rol sin permiso E=5 sobre recurso 46 (solo Admin puede exportar)

---

## Notas de implementación (FA relevantes)

| FA | Comportamiento implementado |
|----|---------------------------|
| FA-01 | Payload inválido (campos mínimos faltantes) → persiste evento `AUDITORIA_EVENTO_INVALIDO` con severidad ERROR, flujo principal continúa |
| FA-08 | Fallo en persistencia de evento CRITICAL/ERROR → escribe en `logs/audit_fallback_M04_YYYYMMDD.log` (JSON por línea); no interrumpe flujo |
| FA-10 | Payload > 64 KB → trunca, agrega `payload_truncado: true`, persiste con severidad WARNING |
| FA-12 | Inmutabilidad: la tabla es append-only; no existe endpoint DELETE/PATCH sobre eventos |
| FA-13 | Acceso no autorizado: RBAC rechaza con 403 antes de llegar al use case |

## RBAC — Recurso 46 (auditoria_m04)

| Permiso | id_permiso | Rol | Acción |
|---------|-----------|-----|--------|
| admin_leer_auditoria_m04 | 264 | Administrador | R=2 (consultar) |
| admin_ejecutar_auditoria_m04 | 265 | Administrador | E=5 (exportar) |
