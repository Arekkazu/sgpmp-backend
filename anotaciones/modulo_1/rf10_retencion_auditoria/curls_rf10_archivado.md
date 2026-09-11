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
  "message": "Acceso denegado: No posee privilegios de administrador para consultar el historial de auditoría. Este incidente ha sido registrado."
}
```

El intento queda registrado como evento tipo 16 con resultado `fallido`, tal como
exige el flujo alterno. La decisión de acceso sigue saliendo de `modulo1.permisos`
(recurso 6, acción 2), no de un `id_rol` en código.

### FA "Filtro de búsqueda inválido" — 400

```bash
curl -X GET "http://localhost:8000/auditoria/archivado/?fecha_desde=2026-08-01T00:00:00Z&fecha_hasta=2026-01-01T00:00:00Z" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "error_code": "FILTROS_INCONSISTENTES",
  "message": "Error de consulta: Los parámetros de filtrado son inconsistentes. Verifique el rango de fechas y los identificadores de usuario seleccionados."
}
```

El mismo 400 se produce con un `id_usuario` que no existe:

```bash
curl -X GET "http://localhost:8000/auditoria/archivado/?id_usuario=99999999" \
  -H "Authorization: Bearer $TOKEN"
```

### FA "Intento de modificación o eliminación" — 405

```bash
curl -i -X DELETE "http://localhost:8000/auditoria/archivado/" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "error_code": "AUDITORIA_INMUTABLE",
  "message": "Operación no permitida: Los registros de auditoría son inmutables por diseño y no pueden ser modificados ni eliminados bajo ninguna circunstancia."
}
```

Igual con `PUT` y `PATCH`, sobre `/auditoria/` y sobre cualquier subruta. A nivel
de base, los triggers `trg_proteger_auditoria_*`,
`trg_proteger_eventos_archivados` y `trg_proteger_integridad_baseline` bloquean
`UPDATE` y `DELETE` con `IMMUTABLE_RECORD`.

### FA "Fallo de integridad del registro" — 500

Si un registro de la página consultada fue manipulado:

```json
{
  "error_code": "INTEGRIDAD_AUDITORIA_VIOLADA",
  "message": "Alerta de seguridad: Se ha detectado una violación de integridad en el registro de auditoría 568. Los datos han sido manipulados o están corruptos. Se ha notificado al oficial de seguridad."
}
```

Cada ítem trae además el campo `integridad`:

- `INTEGRO` — el hash almacenado coincide con el recalculado.
- `LEGADO` — no verificable desde antes de la política y sin cambios desde
  entonces. Se reporta pero no escala a 500.
- `MANIPULADO` — dispara el 500 anterior.

`integridad_ok` se mantiene como booleano y es `true` sólo cuando es `INTEGRO`.

### FA "Exceso de resultados en consulta" — 206

Cuando el total supera 10.000 registros la respuesta viaja con **HTTP 206**:

```json
{
  "total": 12500,
  "pagina": 1,
  "tamano": 50,
  "items": [],
  "mensaje": "Consulta extensa: Se muestran los primeros 50 resultados. Utilice los parámetros de paginación o filtros adicionales para refinar la búsqueda."
}
```

Por debajo del umbral responde 200 con `mensaje: null`.

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
