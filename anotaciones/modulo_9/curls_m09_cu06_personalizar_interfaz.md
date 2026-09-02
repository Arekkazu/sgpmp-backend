# CURLs — M09 CU06: Personalizar Interfaz del Sistema

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT obtenido en `/sesiones/login`.

---

## RF-25 — Contexto adaptativo de interfaz (`/configuracion/interfaz/contexto`)

Todos los roles con permiso R sobre `contexto_interfaz` (`id_recurso=22`).

### Obtener contexto del usuario autenticado (Flujo A)

```bash
curl -X GET http://localhost:8000/configuracion/interfaz/contexto \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_usuario": 3,
  "nombre_completo": "Ana García",
  "id_rol": 2,
  "nombre_rol": "Productor",
  "id_finca": 1,
  "finca_activa": "Finca El Paraíso",
  "departamento": "Cundinamarca",
  "especies_configuradas": ["Tilapia", "Trucha"],
  "modulos_autorizados": ["especies", "ciclos_biologicos", "fincas"]
}
```

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre `contexto_interfaz` (FA-22)

---

## RF-26 — Identidad visual institucional (`/configuracion/identidad-visual/{id_finca}`)

Solo el rol **Administrador** puede operar sobre este recurso (`id_recurso=23`).

### Consultar identidad visual activa de una finca (Flujo A)

```bash
curl -X GET http://localhost:8000/configuracion/identidad-visual/1 \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_identidad_visual": 1,
  "id_finca": 1,
  "id_usuario": 1,
  "logo_path": "uploads/logos/abc123.png",
  "primary_color": "#1E90FF",
  "secondary_color": "#FF6347",
  "org_display_name": "AcuaColombia S.A.S.",
  "version": 2,
  "fecha_creacion": "2026-06-01T10:00:00Z"
}
```

Sin identidad visual registrada devuelve `null` (200).

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre `identidad_visual` (FA-22)

---

### Crear identidad visual de una finca (Flujo B)

Retorna `409` si ya existe una identidad visual para esa finca (FA-23).
Logo opcional; debe ser PNG, JPEG o SVG; máximo 2 MB (FA-24, FA-25).

```bash
curl -X POST http://localhost:8000/configuracion/identidad-visual \
  -H "Authorization: Bearer <TOKEN>" \
  -F "id_finca=1" \
  -F "primary_color=#1E90FF" \
  -F "secondary_color=#FF6347" \
  -F "org_display_name=AcuaColombia S.A.S." \
  -F "logo=@/ruta/al/logo.png;type=image/png"
```

Respuesta esperada `201`:
```json
{
  "id_identidad_visual": 1,
  "id_finca": 1,
  "id_usuario": 1,
  "logo_path": "uploads/logos/uuid-generado.png",
  "primary_color": "#1E90FF",
  "secondary_color": "#FF6347",
  "org_display_name": "AcuaColombia S.A.S.",
  "version": 1,
  "fecha_creacion": "2026-06-21T12:00:00Z"
}
```

Errores posibles:
- `400` — color con formato inválido, nombre vacío o mayor de 50 chars (FA-24)
- `400` — formato de imagen no permitido (gif, bmp, etc.) (FA-25)
- `400` — imagen supera 2 MB (FA-26)
- `403` — rol sin permiso C sobre `identidad_visual` (sin RBAC)
- `409` — ya existe identidad visual para esa finca (FA-23)

---

### Actualizar identidad visual de una finca (Flujo C)

`version` debe coincidir con el valor actual en BD; de lo contrario retorna `412` (FA-27).

```bash
curl -X PATCH http://localhost:8000/configuracion/identidad-visual/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -F "primary_color=#2E8B57" \
  -F "secondary_color=#FFD700" \
  -F "org_display_name=AcuaColombia Actualizada" \
  -F "version=1"
```

Respuesta esperada `200` con campos actualizados y `version=2`.

Sin logo nuevo (omitir `-F "logo=..."`): se conserva el logo anterior.

Errores posibles:
- `400` — color con formato inválido o nombre inválido (FA-24)
- `403` — rol sin permiso U sobre `identidad_visual`
- `404` — finca sin identidad visual registrada
- `412` — versión enviada no coincide con la actual en BD (FA-27)

---

## RF-27 — Tema visual (`/configuracion/personalizacion/tema`)

Todos los usuarios con permiso R/U sobre `tema_visual` (`id_recurso=24`).
Admin gestiona tema global con permiso sobre `configuracion_ui_global` (`id_recurso=27`).

### Obtener tema resuelto del usuario (Flujo A)

Jerarquía: preferencia individual → tema global → CLARO (1).

```bash
curl -X GET http://localhost:8000/configuracion/personalizacion/tema \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "theme_mode": 2,
  "fuente": "personal",
  "id_tema_visual": 5
}
```

`fuente` puede ser `"personal"`, `"global"` o `"defecto"`.

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre `tema_visual`

---

### Guardar preferencia de tema personal (Flujo B)

```bash
curl -X PATCH http://localhost:8000/configuracion/personalizacion/tema \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"theme_mode": 2}'
```

Respuesta esperada `200`:
```json
{
  "id_tema_visual": 5,
  "id_usuario": 3,
  "theme_mode": 2,
  "es_global": false,
  "fecha_actualizacion": "2026-06-21T12:30:00Z"
}
```

Errores posibles:
- `400` — `theme_mode` no es 1, 2 o 3
- `403` — rol sin permiso U sobre `tema_visual`

---

### Obtener tema global (Flujo C — Admin)

```bash
curl -X GET http://localhost:8000/configuracion/personalizacion/tema/global \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

Respuesta `200` con objeto `TemaVisual` donde `es_global=true`, o `null` si no configurado.

Errores posibles:
- `403` — rol sin permiso R sobre `configuracion_ui_global`

---

### Actualizar tema global del sistema (Flujo D — Admin)

```bash
curl -X PATCH http://localhost:8000/configuracion/personalizacion/tema/global \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -H "Content-Type: application/json" \
  -d '{"theme_mode": 1}'
```

Respuesta esperada `200` con `es_global=true` y el nuevo `theme_mode`.

Errores posibles:
- `400` — `theme_mode` no es 1, 2 o 3
- `403` — rol sin permiso U sobre `configuracion_ui_global`

---

## RF-28 — Layout del dashboard (`/configuracion/personalizacion/dashboard`)

Todos los usuarios con permiso sobre `dashboard_layout` (`id_recurso=25`).

El catálogo de widgets vive en `modulo9.widgets`. Cada widget declara el `id_recurso` cuyo permiso
`R` lo habilita, así que dos roles con el mismo permiso sobre el dashboard ven catálogos distintos.

### Catálogo de widgets disponibles para el rol

```bash
curl -X GET http://localhost:8000/configuracion/personalizacion/dashboard/widgets \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
[
  {"id_widget": 1, "clave": "temp_galpon", "nombre": "Temperatura Galpon",
   "grupo": "Ambiental", "span_predeterminado": 1},
  {"id_widget": 6, "clave": "estado_iot", "nombre": "Estado Dispositivos IoT",
   "grupo": "IoT", "span_predeterminado": 2}
]
```

Verificado en dev: el Productor (rol 2) recibe los ids `[1,2,3,4,5,6,7,8,9,10,11,14,15]` y el
Veterinario (rol 3) `[1,2,3,4,5,6,8,9,10,11,12,13,14]` — el 12/13 (producción) solo para el
veterinario, el 7/15 (dispositivos IoT) solo para el productor.

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre `dashboard_layout`

---

### Obtener layout actual (Flujo A)

Si el usuario no tiene layout guardado, devuelve el predeterminado de su rol
(`modulo9.dashboard_layouts_default`); si su rol tampoco tiene uno, una grilla vacía.

```bash
curl -X GET http://localhost:8000/configuracion/personalizacion/dashboard \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_dashboard_layout": 2,
  "id_usuario": 3,
  "grid": [
    {
      "id_widget": 1,
      "posicion_fila": 1,
      "posicion_columna": 1,
      "span_columnas": 2,
      "visible": true,
      "orden": 0
    }
  ],
  "active_widget": ["temp_galpon", "alertas"],
  "fecha_actualizacion": "2026-09-02T12:00:00Z",
  "version_perfil": 3
}
```

`version_perfil` es la versión del perfil del usuario al momento de la lectura. Devolverla en el
`PATCH` permite que el backend detecte que un administrador cambió el rol o la finca del usuario
mientras editaba (FA-34).

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre `dashboard_layout`

---

### Guardar configuración del dashboard (Flujo B)

Valida, en este orden y **antes de tocar la base**: perfil vigente, widget existente, widget
permitido para el rol, indicador existente, máximo 12 widgets activos, coordenadas y span dentro de
la grilla, y ausencia de solapamiento. Una configuración inválida no persiste nada parcial.

```bash
curl -X PATCH http://localhost:8000/configuracion/personalizacion/dashboard \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "layout_config": [
      {
        "id_widget": 6,
        "posicion_fila": 1,
        "posicion_columna": 1,
        "span_columnas": 2,
        "visible": true,
        "orden": 0
      },
      {
        "id_widget": 9,
        "posicion_fila": 1,
        "posicion_columna": 3,
        "span_columnas": 1,
        "visible": true,
        "orden": 1
      }
    ],
    "active_widget": ["estado_iot", "alertas_crit"],
    "version_perfil": 3
  }'
```

Respuesta esperada `200` con el layout guardado.

`version_perfil` es opcional: si se omite, el chequeo de concurrencia no se aplica.
Poner `visible: false` en un widget **libera su celda** — es la forma de "desactivar un widget antes
de agregar uno nuevo" que sugiere el propio RF.

Errores posibles:
- `400` — `posicion_fila` fuera de rango 1–3 (FA-30)
- `400` — `posicion_columna` fuera de rango 1–4 (FA-30)
- `400` — `span_columnas` no es 1 o 2 (FA-30)
- `400` `DESBORDE_HORIZONTAL` — widget con span 2 en la columna 4 (FA-30)
- `400` `LIMITE_WIDGETS_ALCANZADO` — más de 12 widgets activos, en `layout_config` o en
  `active_widget` (FA-32)
- `400` `ACTIVE_WIDGET_DUPLICADO` — `active_widget` repite un identificador
- `400` `WIDGET_INEXISTENTE` — `id_widget` que no está en `modulo9.widgets`
- `400` `ACTIVE_WIDGET_INEXISTENTE` — clave de `active_widget` fuera del catálogo
- `403` `ACCESO_DENEGADO` — rol sin permiso U sobre `dashboard_layout`
- `403` `WIDGET_NO_AUTORIZADO` — widget de un módulo que el rol no puede leer (FA-33)
- `409` `SOLAPAMIENTO_WIDGETS` — dos widgets en la misma celda, o uno dentro del rango de
  expansión de otro (FA-31)
- `409` `CONFLICTO_PERFIL_MODIFICADO` — el perfil del usuario cambió durante la edición (FA-34)

---

### Restaurar layout predeterminado del rol (Flujo C)

```bash
curl -X POST http://localhost:8000/configuracion/personalizacion/dashboard/restaurar \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200` con el layout base del rol. Verificado en dev para el rol 2:
`grid` con los widgets `[1, 2, 8, 9, 14]` y `active_widget`
`["temp_galpon","hum_galpon","alertas","alertas_crit","fincas_estado"]`.

Errores posibles:
- `403` — rol sin permiso U sobre `dashboard_layout`
- `500` `RESTAURACION_SIN_DEFAULT` — el rol no tiene fila en
  `modulo9.dashboard_layouts_default` (FA-35). Pasa con roles creados después de la migración
  `a7f3c92e4d18`; se corrige insertando su layout base. **No se escribe nada**: la configuración
  actual del usuario queda intacta.

---

### Datos de los widgets visibles

```bash
curl -X GET http://localhost:8000/configuracion/personalizacion/dashboard/datos \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`, una entrada por widget visible, ordenada por `orden`:
```json
[
  {
    "id_widget": 6, "clave": "estado_iot", "nombre": "Estado Dispositivos IoT",
    "posicion_fila": 1, "posicion_columna": 1, "span_columnas": 2, "orden": 0,
    "sin_datos": false, "mensaje": null,
    "datos": [{"serial": "IOT-001", "es_activo": true, "finca": "La Esperanza"}]
  },
  {
    "id_widget": 1, "clave": "temp_galpon", "nombre": "Temperatura Galpon",
    "posicion_fila": 2, "posicion_columna": 1, "span_columnas": 1, "orden": 1,
    "sin_datos": true,
    "mensaje": "Sin datos disponibles para el sensor o periodo seleccionado.",
    "datos": []
  }
]
```

Un widget sin fuente configurada, o cuya fuente no devolvió filas, llega con `sin_datos: true` y
**conserva su posición en la grilla** — no se omite ni afecta a los demás (FA-36).

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre `dashboard_layout`

---

## RF-29 — Preferencia de idioma (`/configuracion/personalizacion/idioma`)

Todos los usuarios con permiso sobre `preferencia_idioma` (`id_recurso=26`).
Admin gestiona idioma global con permiso sobre `configuracion_ui_global` (`id_recurso=27`).

Locales válidos: `"es-CO"`, `"en-US"`.

### Obtener idioma resuelto del usuario (Flujo A)

Jerarquía: preferencia individual → idioma global → `"es-CO"`.

```bash
curl -X GET http://localhost:8000/configuracion/personalizacion/idioma \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "locale_code": "en-US",
  "fuente": "personal",
  "id_preferencia_idioma": 7
}
```

`fuente` puede ser `"personal"`, `"global"` o `"defecto"`.

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre `preferencia_idioma`

---

### Guardar preferencia de idioma personal (Flujo B)

```bash
curl -X PATCH http://localhost:8000/configuracion/personalizacion/idioma \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"locale_code": "en-US"}'
```

Respuesta esperada `200`:
```json
{
  "id_preferencia_idioma": 7,
  "id_usuario": 3,
  "locale_code": "en-US",
  "es_por_defecto": false,
  "fecha_actualizacion": "2026-06-21T13:00:00Z"
}
```

Errores posibles:
- `400` — `locale_code` no está entre `es-CO` / `en-US` (FA-33)
- `403` — rol sin permiso U sobre `preferencia_idioma`

---

### Obtener idioma global (Flujo C — Admin)

```bash
curl -X GET http://localhost:8000/configuracion/personalizacion/idioma/global \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

Respuesta `200` con objeto `PreferenciaIdioma` donde `es_por_defecto=true`, o `null` si no configurado.

Errores posibles:
- `403` — rol sin permiso R sobre `configuracion_ui_global`

---

### Actualizar idioma global del sistema (Flujo D — Admin)

```bash
curl -X PATCH http://localhost:8000/configuracion/personalizacion/idioma/global \
  -H "Authorization: Bearer <TOKEN_ADMIN>" \
  -H "Content-Type: application/json" \
  -d '{"locale_code": "es-CO"}'
```

Respuesta esperada `200` con `es_por_defecto=true` y el nuevo `locale_code`.

Errores posibles:
- `400` — `locale_code` no válido (FA-33)
- `403` — rol sin permiso U sobre `configuracion_ui_global`
