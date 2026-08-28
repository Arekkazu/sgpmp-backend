# CURLs — RF-10 archivo histórico de auditoría

Base local: `http://localhost:8000` (sin `/api`; ese prefijo lo agrega el proxy en
producción). Todos los endpoints requieren `Authorization: Bearer <access_token>`
de un usuario cuyo rol tenga el permiso `(recurso 6, acción 2)`.

Para obtener el token:

```bash
curl -X POST http://localhost:8000/sesiones/ \
  -H "Content-Type: application/json" \
  -d '{"correo_electronico":"admin@ejemplo.com","contrasena":"TuClave123*"}'
```

---

## 1. Consultar el archivo histórico

```bash
curl -X GET "http://localhost:8000/auditoria/archivado/?pagina=1&tamano=20" \
  -H "Authorization: Bearer $TOKEN"
```

**200 OK**

```json
{
  "total": 0,
  "pagina": 1,
  "tamano": 20,
  "items": []
}
```

En desarrollo el histórico está vacío: el evento más antiguo de `modulo1.eventos`
es de 2026-01-27, así que todavía no hay nada con más de 12 meses. Cada ítem, cuando
lo haya, trae la misma forma que `GET /auditoria/`, incluido `integridad_ok` con el
resultado de recalcular el hash SHA-256 del registro.

## 2. Filtrar el histórico

Mismos filtros que el log activo: `id_usuario`, `tipo_evento`, `categoria`,
`fecha_desde`, `fecha_hasta`.

```bash
curl -X GET "http://localhost:8000/auditoria/archivado/?id_usuario=1&categoria=AUTENTICACION&tamano=50" \
  -H "Authorization: Bearer $TOKEN"
```

```bash
curl -X GET "http://localhost:8000/auditoria/archivado/?fecha_desde=2025-01-01T00:00:00Z&fecha_hasta=2025-06-30T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

## 3. Paginación

`tamano` está acotado a 50 por el propio endpoint (`Query(20, ge=1, le=50)`), que es
como el sistema fuerza la paginación obligatoria del RNF de rendimiento.

```bash
curl -X GET "http://localhost:8000/auditoria/archivado/?pagina=2&tamano=50" \
  -H "Authorization: Bearer $TOKEN"
```

Pedir `tamano=100` devuelve **422** por validación de FastAPI antes de tocar la DB.

---

## Errores

### FA "Acceso denegado a la consulta de logs" — 403

Token de un rol sin el permiso `(6, 2)`, por ejemplo Veterinario:

```bash
curl -X GET "http://localhost:8000/auditoria/archivado/" \
  -H "Authorization: Bearer $TOKEN_VETERINARIO"
```

```json
{
  "error_code": "ACCESO_DENEGADO",
  "message": "Acceso denegado. Su rol no tiene permisos para realizar esta operación."
}
```

Si el rol sí tiene el permiso RBAC pero no es administrador, el use case devuelve el
403 con el mensaje del RF y **registra el intento** como evento tipo 16 con resultado
`fallido`.

### FA "Filtro de búsqueda inválido" — 400

```bash
curl -X GET "http://localhost:8000/auditoria/archivado/?fecha_desde=2026-08-01T00:00:00Z&fecha_hasta=2026-01-01T00:00:00Z" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "error_code": "RANGO_FECHAS_INVALIDO",
  "message": "Error de consulta: Los parámetros de filtrado son inconsistentes. Verifique el rango de fechas y los identificadores de usuario seleccionados."
}
```

### FA "Intento de modificación o eliminación" — sin endpoint

No existe `PUT`, `PATCH` ni `DELETE` sobre `/auditoria` ni `/auditoria/archivado`.
FastAPI responde **405 Method Not Allowed** por ruta no registrada:

```bash
curl -i -X DELETE "http://localhost:8000/auditoria/archivado/" \
  -H "Authorization: Bearer $TOKEN"
```

A nivel de base, el trigger `trg_proteger_eventos_archivados` bloquea `UPDATE` y
`DELETE` con `IMMUTABLE_RECORD`, igual que `trg_proteger_auditoria_*` sobre
`modulo1.eventos`.

### 401 sin token o con token vencido

```json
{ "error_code": "TOKEN_EXPIRADO", "message": "..." }
```

---

## Verificar la alerta del FA de archivado

No hay endpoint que dispare el fallo: lo emite la tarea diaria cuando el archivado
revienta. Para verlo desde la API, provocar el fallo y luego revisar la bandeja del
administrador:

```bash
curl -X GET "http://localhost:8000/notificaciones?solo_no_leidas=true" \
  -H "Authorization: Bearer $TOKEN"
```

El mensaje esperado empieza con
`"Fallo en política de retención: No se pudo completar el archivado de logs antiguos."`
y trae adjunta la excepción real. El evento asociado es de tipo 25
(`FALLO_ARCHIVADO_AUDITORIA`) con resultado `fallido`, visible en:

```bash
curl -X GET "http://localhost:8000/auditoria/?tipo_evento=25" \
  -H "Authorization: Bearer $TOKEN"
```
