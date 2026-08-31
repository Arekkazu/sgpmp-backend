# CURLs — RF-10 exportación del historial de auditoría

Base local: `http://localhost:8000` (sin `/api`; ese prefijo lo agrega el proxy en
producción). Requiere `Authorization: Bearer <access_token>` de un usuario cuyo rol
tenga el permiso `(recurso 6, acción 2)` — el mismo que `GET /auditoria/`.

Para obtener el token:

```bash
curl -X POST http://localhost:8000/sesiones/ \
  -H "Content-Type: application/json" \
  -d '{"correo_electronico":"admin@ejemplo.com","contrasena":"TuClave123*"}'
```

---

## Por qué existe este endpoint

Exportar el log paginando costaba **una petición por página**: con el tope de
`tamano ≤ 50`, un conjunto de 10.000 registros eran 200 peticiones, cada una con su
`COUNT(*)`, su verificación de hashes y **su propio evento `CONSULTA_AUDITORIA`**.
Una sola descarga dejaba 200 registros de haber leído la auditoría. Aquí todo eso
ocurre una vez y deja un único evento `EXPORTACION_AUDITORIA` (tipo 26).

## 1. Exportar el historial completo

```bash
curl -X GET "http://localhost:8000/auditoria/exportar" \
  -H "Authorization: Bearer $TOKEN" -o auditoria.csv
```

**200 OK** — `Content-Type: text/csv; charset=utf-8`

```
Content-Disposition: attachment; filename="auditoria-2026-08-31.csv"
X-Total-Registros: 938
X-Registros-Exportados: 938
```

```csv
ID,Usuario,Tipo evento,Módulo,Descripción,Resultado,IP,Fecha/Hora,Integridad
945,Carlos Rodríguez Pérez,ACTIVACION_CUENTA,MODULO1,,exitoso,10.0.0.7,2026-08-26T03:38:08.288496+00:00,INTEGRO
```

La columna `Usuario` trae `nombre_usuario` y cae al `id_usuario` cuando el evento no
lo guardó. `Tipo evento` sale de `modulo1.tipos_eventos` vía
`nombre_para_tipo_evento()`, no de una tabla del cliente. `Integridad` es
`INTEGRO` | `LEGADO` | `MANIPULADO`.

El archivo empieza con BOM UTF-8 y usa CRLF para que Excel lo abra sin romper los
acentos de «Módulo» y «Descripción».

### Cabeceras de conteo

`X-Total-Registros` es cuántos cumplen el filtro; `X-Registros-Exportados` cuántos
trae el archivo. Si el segundo es menor, la exportación se truncó en el límite de
10.000 (`UMBRAL_SATURACION`) y el cliente debe avisar que hay que refinar los filtros.

> Ambas cabeceras están en `expose_headers` del CORS en `main.py`. Sin eso el
> navegador se las oculta al frontend y el aviso de truncado nunca aparece.

## 2. Exportar con filtros

Los mismos que `GET /auditoria/`: `id_usuario`, `tipo_evento`, `categoria`,
`fecha_desde`, `fecha_hasta`.

```bash
curl -X GET "http://localhost:8000/auditoria/exportar?tipo_evento=16&fecha_desde=2026-01-01T00:00:00Z" \
  -H "Authorization: Bearer $TOKEN" -o auditoria_consultas.csv
```

Las fechas se comparan contra `fecha_evento`, que es `timestamptz`. Enviarlas con
zona explícita (`...Z` o `±HH:MM`) evita que una fecha sin zona se interprete en la
del servidor en vez de la del usuario.

## 3. Exportar el archivo histórico

```bash
curl -X GET "http://localhost:8000/auditoria/exportar?archivados=true" \
  -H "Authorization: Bearer $TOKEN" -o auditoria_historico.csv
```

Mismos filtros y mismo permiso, sobre `modulo1.eventos_archivados`.

---

## Errores

| HTTP | `error_code` | Cuándo | FA |
|------|--------------|--------|-----|
| 400 | `FILTROS_INCONSISTENTES` | `fecha_desde > fecha_hasta`, o `id_usuario` que no existe | Filtros inconsistentes |
| 403 | `ACCESO_DENEGADO` | El rol no tiene `(recurso 6, acción 2)`. **El intento queda auditado** | Acceso no autorizado |
| 500 | `INTEGRIDAD_AUDITORIA_VIOLADA` | Algún registro del conjunto fue alterado en la tabla | Fallo de integridad del registro |

```bash
# 400 — rango invertido
curl -X GET "http://localhost:8000/auditoria/exportar?fecha_desde=2026-06-01T00:00:00Z&fecha_hasta=2026-01-01T00:00:00Z" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "error_code": "FILTROS_INCONSISTENTES",
  "message": "Error de consulta: Los parámetros de filtrado son inconsistentes. Verifique el rango de fechas y los identificadores de usuario seleccionados.",
  "fields": null,
  "timestamp": "2026-08-31T15:04:05.000000+00:00"
}
```

El 500 por integridad se levanta **antes** de emitir el primer byte: la verificación
recorre todo el conjunto en una primera pasada y solo entonces empieza a transmitirse
el CSV. Una vez enviadas las cabeceras del 200 ya no habría forma de convertir la
respuesta en un error.

## 4. Comprobar que quedó un solo evento

```sql
SELECT count(*) FROM modulo1.eventos WHERE tipo_evento = 26;  -- 1 por descarga
SELECT detalle FROM modulo1.eventos WHERE tipo_evento = 26 ORDER BY id_evento DESC LIMIT 1;
```

El `detalle` guarda los filtros aplicados, `total_disponible`, `total_exportado` y
`truncado`.

---

## 5. Catálogo de tipos de evento

El cliente necesita traducir el `tipo_evento` numérico de cada registro a una
etiqueta. Mantener esa tabla a mano en el frontend ya provocó que las 25 etiquetas
se desincronizaran y el CSV saliera con el evento equivocado en cada fila.

```bash
curl -X GET "http://localhost:8000/auditoria/catalogo/tipos-evento" \
  -H "Authorization: Bearer $TOKEN"
```

**200 OK**

```json
[
  {"id_tipo_evento": 1, "nombre": "REGISTRO_USUARIO", "accion": "Creación cuenta usuario", "categoria": "AUTENTICACION"},
  {"id_tipo_evento": 26, "nombre": "EXPORTACION_AUDITORIA", "accion": "Exportacion del historial de auditoria", "categoria": "CONSULTA"}
]
```

`categoria` es `AUTENTICACION` | `MODIFICACION` | `CONSULTA`, y sale de
`categoria_para_tipo_evento()`. Permite agrupar o colorear por 3 valores en vez de
mantener un mapa de 25 ids en el cliente. Es `null` si la DB tuviera un tipo sin
clasificar en el dominio.

A diferencia del resto del router, este endpoint usa `require_permission(6, 2)` y no
`verificar_acceso_auditoria`: esa dependencia audita el intento denegado, y el
catálogo se pide cada vez que se pinta el desplegable de filtros — no puede dejar un
evento por carga.

| HTTP | `error_code` | Cuándo |
|------|--------------|--------|
| 403 | `ACCESO_DENEGADO` | El rol no tiene `(recurso 6, acción 2)` |
