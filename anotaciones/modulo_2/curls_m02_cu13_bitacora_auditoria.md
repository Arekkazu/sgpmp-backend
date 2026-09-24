# CURLs — M02 CU13: Auditoría y Trazabilidad (RF-52)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa (rol con permiso READ sobre recurso 31).

---

## RF-52 — Consultar Bitácora de Auditoría

### GET /activos-biologicos/auditoria — Sin filtros (paginación por defecto)

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total_registros": 47,
  "pagina_actual": 1,
  "total_paginas": 3,
  "registros_por_pagina": 20,
  "registros": [
    {
      "id_bitacora": 47,
      "id_evento": "a3f1c2d4-8b9e-4f0a-bcde-1234567890ab",
      "rf_origen": "RF33",
      "tipo_evento": "ACTIVO_REGISTRADO",
      "clasificacion_biologica": "GESTION_OPERATIVA",
      "id_activo_biologico": 15,
      "tipo_activo": "INDIVIDUAL",
      "timestamp_evento": "2026-06-10T14:30:00Z",
      "timestamp_registro": "2026-06-10T14:30:01Z",
      "resultado": "EXITOSO",
      "descripcion": "Activo biológico registrado: TRU-015",
      "detalle_tecnico": null,
      "id_usuario_responsable": 3,
      "modulo_consumidor": "modulo2",
      "severidad_log": "INFO",
      "id_evento_correlacionado": null,
      "hash_integridad": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "registro_incompleto": false
    }
  ]
}
```

---

### GET /activos-biologicos/auditoria — Filtrar por rf_origen

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?rf_origen=RF40" \
  -H "Authorization: Bearer <TOKEN>"
```

---

### GET /activos-biologicos/auditoria — Filtrar por clasificacion_biologica

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?clasificacion_biologica=TRANSFORMACION_BIOLOGICA" \
  -H "Authorization: Bearer <TOKEN>"
```

Valores válidos de `clasificacion_biologica`:
- `TRANSFORMACION_BIOLOGICA` — eventos de crecimiento, reproductivos, productivos, cambios de fase
- `GESTION_OPERATIVA` — registro, actualización, transferencia, asociación IoT, indicadores
- `SANITARIO` — eventos sanitarios
- `CONTROL_ESTADO` — cambios de estado, bajas, cierre de ciclo
- `ACCESO_DATOS` — consultas de activo, historial, ficha integral, datos consolidados, infraestructura

---

### GET /activos-biologicos/auditoria — Filtrar por resultado

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?resultado=FALLIDO" \
  -H "Authorization: Bearer <TOKEN>"
```

Valores de `resultado`: `EXITOSO` | `FALLIDO` | `RECHAZADO` | `ADVERTENCIA`

---

### GET /activos-biologicos/auditoria — Filtrar por activo específico

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?id_activo_biologico=15" \
  -H "Authorization: Bearer <TOKEN>"
```

---

### GET /activos-biologicos/auditoria — Filtrar por rango de fechas

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?fecha_inicio=2026-06-01T00:00:00Z&fecha_fin=2026-06-30T23:59:59Z" \
  -H "Authorization: Bearer <TOKEN>"
```

---

### GET /activos-biologicos/auditoria — Filtros combinados con paginación

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?rf_origen=RF45&resultado=EXITOSO&pagina=1&page_size=10" \
  -H "Authorization: Bearer <TOKEN>"
```

---

### GET /activos-biologicos/auditoria — Filtrar por tipo_evento

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?tipo_evento=BAJA_REGISTRADA" \
  -H "Authorization: Bearer <TOKEN>"
```

---

### GET /activos-biologicos/auditoria — Filtrar por severidad_log

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?severidad_log=ERROR" \
  -H "Authorization: Bearer <TOKEN>"
```

Valores de `severidad_log`: `INFO` | `WARNING` | `ERROR` | `CRITICAL`

---

## Errores posibles

| HTTP | code | Causa |
|------|------|-------|
| 401 | UNAUTHORIZED | Token ausente o inválido |
| 403 | AUTHORIZATION_ERROR | El rol del usuario no tiene permiso READ (acción 2) sobre recurso 31 (`bitacora_auditoria_m02`) |
| 422 | PARAMETROS_INVALIDOS | `fecha_inicio` o `fecha_fin` no son ISO 8601 válidas |

---

## RF-52 E5 — Reconciliación con el historial RF-46 y registro correctivo

Una tarea diaria (05:00 UTC, `main.py`) cruza el historial RF-46 con la bitácora.
Cada fila del historial sin su registro de auditoría queda en un evento
`INCONSISTENCIA_RF46_RF52` (`CRITICAL`), y quien tenga permiso de crear sobre el
recurso 31 recibe una notificación interna. Para ver las inconsistencias:

```bash
curl -X GET "http://localhost:8000/activos-biologicos/auditoria?tipo_evento=INCONSISTENCIA_RF46_RF52" \
  -H "Authorization: Bearer <TOKEN>"
```

Cada una trae en `detalle_tecnico.registros_rf46` la `tabla` y el `id` de las filas
sin registro. Con eso, el administrador crea el registro correctivo:

### POST /activos-biologicos/auditoria/registros-correctivos

Requiere permiso CREATE (acción 1) sobre el recurso 31 (`bitacora_auditoria_m02`),
que solo tiene Administrador (migración `094d4799c3ca`).

```bash
curl -X POST "http://localhost:8000/activos-biologicos/auditoria/registros-correctivos" \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -H "Content-Type: application/json" \
  -d '{
    "tabla": "eventos_activos",
    "id_registro": 109,
    "motivo": "El worker se reinició antes de registrar la auditoría del evento."
  }'
```

`tabla` admite: `eventos_activos`, `historicos_estados_activos`, `gestiones_fases`,
`movimientos`, `historial_activos`.

Respuesta esperada `201`:
```json
{
  "tabla": "eventos_activos",
  "id_registro": 109,
  "id_activo_biologico": 53,
  "motivo": "El worker se reinició antes de registrar la auditoría del evento.",
  "timestamp_evento": "2026-09-23T18:40:00Z"
}
```

Queda en la bitácora como `REGISTRO_CORRECTIVO_AUDITORIA` (`WARNING`), con el motivo y
la llave `registros_rf46`. El historial RF-46 no se modifica.

| HTTP | code | Causa | FA |
|------|------|-------|----|
| 400 | VAL_ENTRADA | `tabla` fuera de la lista, `id_registro` ≤ 0 o `motivo` vacío | — |
| 403 | AUTHORIZATION_ERROR | El rol no tiene CREATE sobre el recurso 31 | E4 |
| 404 | REGISTRO_RF46_NO_ENCONTRADO | La fila no existe o no forma parte del historial RF-46 | E5 |
| 409 | REGISTRO_YA_AUDITADO | La fila ya tiene su registro en la bitácora (original o correctivo previo) | E5 |

---

## Tabla de tipos de evento por RF

| rf_origen | tipo_evento (éxito) | tipo_evento (fallo) | clasificacion_biologica |
|-----------|---------------------|---------------------|-------------------------|
| RF33 | ACTIVO_REGISTRADO | ACTIVO_REGISTRO_FALLIDO | GESTION_OPERATIVA |
| RF34 | INFRAESTRUCTURA_CONSULTADA | — | ACCESO_DATOS |
| RF35 (read, activo INDIVIDUAL) | ACTIVO_INDIVIDUAL_CONSULTA | — | ACCESO_DATOS |
| RF35 (write) | ACTIVO_INDIVIDUAL_ACTUALIZADO | ACTIVO_ACTUALIZACION_FALLIDA | GESTION_OPERATIVA |
| RF36 (read, activo POBLACIONAL) | ACTIVO_POBLACIONAL_CONSULTA | — | ACCESO_DATOS |
| RF37 | FASE_CAMBIADA | FASE_CAMBIO_FALLIDO | TRANSFORMACION_BIOLOGICA |
| RF38 | CICLO_CERRADO | CICLO_CIERRE_FALLIDO | CONTROL_ESTADO |
| RF40 | EVENTO_CRECIMIENTO_REGISTRADO | EVENTO_CRECIMIENTO_FALLIDO | TRANSFORMACION_BIOLOGICA |
| RF41 | EVENTO_SANITARIO_REGISTRADO | EVENTO_SANITARIO_FALLIDO | SANITARIO |
| RF42 | EVENTO_REPRODUCTIVO_REGISTRADO | EVENTO_REPRODUCTIVO_FALLIDO | TRANSFORMACION_BIOLOGICA |
| RF43 | EVENTO_PRODUCTIVO_REGISTRADO | EVENTO_PRODUCTIVO_FALLIDO | TRANSFORMACION_BIOLOGICA |
| RF44 | ESTADO_CAMBIADO | ESTADO_CAMBIO_FALLIDO | CONTROL_ESTADO |
| RF45 | BAJA_REGISTRADA | BAJA_REGISTRO_FALLIDO | CONTROL_ESTADO |
| RF46 | HISTORIAL_CONSULTADO | — | ACCESO_DATOS |
| RF47 | FICHA_CONSULTADA | — | ACCESO_DATOS |
| RF48 | TRANSFERENCIA_REGISTRADA | TRANSFERENCIA_FALLIDA | GESTION_OPERATIVA |
| RF49 | ASOCIACION_IOT_CREADA | ASOCIACION_IOT_FALLIDA | GESTION_OPERATIVA |
| RF50 | DATOS_ANALITICOS_CONSULTADOS | — | ACCESO_DATOS |
| RF51 | INDICADOR_CALCULADO | — | GESTION_OPERATIVA |
| RF37 (avance automático desde RF-40) | FASE_AVANZADA_AUTOMATICAMENTE | — | TRANSFORMACION_BIOLOGICA |
| RF52 (E1) | INDISPONIBILIDAD_AUDITORIA | — | GESTION_OPERATIVA |
| RF52 (E3) | ALTA_CARGA_AUDITORIA_INICIO / ALTA_CARGA_AUDITORIA_FIN | — | GESTION_OPERATIVA |
| RF52 (E5) | RECONCILIACION_RF46_RF52 / REGISTRO_CORRECTIVO_AUDITORIA | INCONSISTENCIA_RF46_RF52 | GESTION_OPERATIVA |
