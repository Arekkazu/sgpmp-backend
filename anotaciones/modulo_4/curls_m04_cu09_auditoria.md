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
| FA-08 | Fallo en persistencia (E2/E8). Desde DEV-37: 3 intentos (`AUDITORIA_M04_REINTENTOS`), cada uno en su savepoint; si todos fallan, el evento (de cualquier severidad, con `id_evento` y `fecha_evento` originales) y un `AUDITORIA_FALLA_PERSISTENCIA` CRITICAL van a `logs/audit_fallback_M04_YYYYMMDD.log`, y el flujo sigue. Solo si tampoco se puede escribir el respaldo se responde `500 AUDITORIA_M04_NO_PERSISTIDA` (DEV-03). Ver la sección DEV-37 |

### Eventos que emiten las consultas M04 (DEV-03)

Solo se usan valores de `enum_tipo_evento_auditoria_m04` y `resultado_operacion = EXITOSO`. Como varias consultas comparten `tipo_evento`, el payload dice cuál fue:

| Endpoint | `tipo_evento` | Discriminador en `payload_evento` |
|----------|---------------|-----------------------------------|
| `GET /prediccion/historial/{id}` | `HISTORIAL_CONSULTADO` | `consulta: HISTORIAL_DIAGNOSTICO` |
| `GET /prediccion/modelos/{id}/ota-status` | `HISTORIAL_CONSULTADO` | `consulta: OTA_STATUS` |
| `GET /prediccion/despliegues` | `HISTORIAL_CONSULTADO` | `consulta: DESPLIEGUES_OTA` |
| `GET /prediccion/auditoria` | `HISTORIAL_CONSULTADO` | `consulta: AUDITORIA_M04` |
| `GET /prediccion/auditoria/exportar` | `EXPORTACION_GENERADA` | `exportacion: AUDITORIA_M04` |

```bash
curl -X GET "http://localhost:8000/prediccion/auditoria?tipo_evento=HISTORIAL_CONSULTADO" \
  -H "Authorization: Bearer <token>"
```
| FA-10 | Payload > 64 KB → trunca, agrega `payload_truncado: true`, persiste con severidad WARNING |
| FA-12 | Inmutabilidad: la tabla es append-only; no existe endpoint DELETE/PATCH sobre eventos |
| FA-13 | Acceso no autorizado: RBAC rechaza con 403 antes de llegar al use case |

## RBAC — Recurso 46 (auditoria_m04)

| Permiso | id_permiso | Rol | Acción |
|---------|-----------|-----|--------|
| admin_leer_auditoria_m04 | 264 | Administrador | R=2 (consultar) |
| admin_ejecutar_auditoria_m04 | 265 | Administrador | E=5 (exportar) |
| vet_leer_auditoria_m04 | (DB-08) | Veterinario | R=2 (consultar) — RF-73 actores, DEV-37 |

---

## DEV-37 — Veterinario, reintentos y sincronización del respaldo (RF-73 actores, E2, E8)

### El Veterinario consulta la bitácora (200)

Con DB-08 aplicada, el Veterinario tiene R sobre el recurso 46. Exportar sigue siendo
solo del Administrador (E=5).

```bash
curl -s "http://localhost:8000/prediccion/auditoria?por_pagina=5"   -H "Authorization: Bearer <TOKEN_VET>"          # 200
curl -s -o /dev/null -w "%{http_code}
" "http://localhost:8000/prediccion/auditoria/exportar"   -H "Authorization: Bearer <TOKEN_VET>"          # 403
```

### Con la BD caída (E2)

No hay endpoint: lo hace el repositorio al registrar cualquier evento de M04.
1. 3 intentos (`AUDITORIA_M04_REINTENTOS`, pausa 0.2 s · intento), cada uno en un savepoint.
2. Si todos fallan, se escriben en `logs/audit_fallback_M04_YYYYMMDD.log` (o
   `AUDITORIA_M04_DIR_RESPALDO`), una línea JSON cada uno:
   - el evento completo, con su `id_evento`, `fecha_evento` y `hash_evento` originales;
   - `AUDITORIA_FALLA_PERSISTENCIA` (CRITICAL, actor SISTEMA `DESARROLLO_M04`), con
     `id_evento_original` e `intentos` en el payload.
3. Log `CRITICAL` para monitoreo. El flujo de negocio no se interrumpe por la auditoría.

### Al volver la BD (E8 / CA-14)

La tarea periódica de `main.py` revisa el respaldo cada 30 s (sin respaldo no toca la BD):
- inserta los eventos en orden FIFO con `origen_registro = FALLBACK`, `id_evento` y
  `fecha_evento` originales (idempotente por `id_evento`);
- registra `AUDITORIA_FALLBACK_ACTIVADO` (CRITICAL) con `inicio_contingencia`,
  `fin_contingencia`, `eventos_sincronizados` y `fallas_persistencia`;
- tras el commit, avisa por correo a quien tiene E=5 sobre el recurso 46 (Administrador).

Si la BD sigue caída, se revierte y el respaldo se conserva para la siguiente pasada.

```bash
curl -s "http://localhost:8000/prediccion/auditoria?tipo_evento=AUDITORIA_FALLBACK_ACTIVADO"   -H "Authorization: Bearer <TOKEN_ADMIN>"
```
