# CURLs — M09 CU07: Gestionar Plantillas de Configuración

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT obtenido en `/sesiones/login`.
Roles con acceso: **Administrador** (id_rol=1) e **Ingeniero de Campo** (id_rol=4).
Recurso RBAC: `id_recurso=28` (plantillas).

---

## RF-30 — Listar plantillas disponibles (Flujo A)

### GET /configuracion/plantillas

```bash
curl -X GET http://localhost:8000/configuracion/plantillas \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 2,
  "items": [
    {
      "id_plantilla": 1,
      "id_especie": 3,
      "id_usuario": 1,
      "template_name": "Tilapia Estándar",
      "version": 2,
      "fecha_creacion": "2026-06-21T10:00:00Z",
      "params_snapshot": {
        "schema_version": 1,
        "ciclos_biologicos": [...],
        "metricas_produccion": [...],
        "umbrales_ambientales": [...],
        "patologias": [{"nombre": "Estreptococosis"}]
      }
    }
  ]
}
```

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre recurso 28 (FA-05)

---

## RF-30 — Detalle de plantilla (Flujo C)

### GET /configuracion/plantillas/{id_plantilla}

```bash
curl -X GET http://localhost:8000/configuracion/plantillas/1 \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`: misma estructura que un item de la lista.

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre recurso 28 (FA-05)
- `404` — plantilla no existe

---

## RF-30 — Historial de aplicaciones (Flujo E)

### GET /configuracion/plantillas/historial

```bash
curl -X GET http://localhost:8000/configuracion/plantillas/historial \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 1,
  "items": [
    {
      "id_aplicacion_plantilla": 1,
      "id_plantilla": 1,
      "id_usuario": 1,
      "target_config": {"id_especie": 5},
      "before_snapshot": {...},
      "after_snapshot": {...},
      "fecha_aplicacion": "2026-06-21T11:30:00Z"
    }
  ]
}
```

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre recurso 28 (FA-05)

---

## RF-30 — Esquema vigente y changelog de versiones (Flujo F)

### GET /configuracion/plantillas/esquema

Publica el esquema al que debe ajustarse `params_snapshot` y el changelog de
versiones que exige el RNF de mantenibilidad del RF-30. El frontend lo usa para
saber qué categorías y campos enviar; RF-32 usa `compatible_con` para decidir si
una plantilla antigua todavía se puede aplicar.

```bash
curl -X GET http://localhost:8000/configuracion/plantillas/esquema \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "schema_version_actual": 1,
  "categorias": [
    "ciclos_biologicos",
    "patologias",
    "metricas_produccion",
    "umbrales_ambientales"
  ],
  "campos_requeridos": {
    "ciclos_biologicos": {
      "nombre": "texto no vacío",
      "duracion_dias": "entero positivo"
    },
    "patologias": {"nombre": "texto no vacío"},
    "metricas_produccion": {
      "nombre": "texto no vacío",
      "unidad_medida": "texto no vacío",
      "tipo_medicion": "uno de ['PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO']",
      "aplica_a_tipo_activo": "uno de ['INDIVIDUAL', 'LOTE', 'AMBOS']"
    },
    "umbrales_ambientales": {
      "id_variable_ambiental": "entero positivo",
      "unidad_medida": "texto no vacío",
      "valor_min": "número",
      "valor_max": "número"
    }
  },
  "campos_nivel_alerta": {
    "nivel": "uno de ['normal', 'precaucion', 'critico']",
    "limite_inferior": "número",
    "limite_superior": "número"
  },
  "changelog": [
    {
      "version": 1,
      "fecha": "2026-06-21",
      "compatible_con": [1],
      "cambios": [
        "Versión inicial del esquema de params_snapshot.",
        "..."
      ]
    }
  ]
}
```

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso R sobre recurso 28 (FA-05)

---

## RF-31 — Crear plantilla de configuración (Flujo B)

### POST /configuracion/plantillas

Crea una plantilla **nueva**. El `params_snapshot` debe tener al menos una
categoría con elementos y el `template_name` debe estar libre: un nombre ya
registrado se rechaza con `409`. Para actualizar una plantilla existente hay
que generar una versión (Flujo G), no repetir el nombre aquí.

```bash
curl -X POST http://localhost:8000/configuracion/plantillas \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "Tilapia Estándar",
    "id_especie": 3,
    "params_snapshot": {
      "ciclos_biologicos": [
        {"nombre": "Alevín", "duracion_dias": 30, "descripcion": "Fase inicial"},
        {"nombre": "Juvenil", "duracion_dias": 60}
      ],
      "metricas_produccion": [
        {
          "nombre": "Peso promedio",
          "unidad_medida": "kg",
          "tipo_medicion": "PESO",
          "aplica_a_tipo_activo": "INDIVIDUAL"
        }
      ],
      "umbrales_ambientales": [
        {
          "id_variable_ambiental": 1,
          "unidad_medida": "°C",
          "valor_min": "22.0",
          "valor_max": "30.0",
          "niveles": [
            {"nivel": "normal", "limite_inferior": "22.0", "limite_superior": "30.0"},
            {"nivel": "precaucion", "limite_inferior": "20.0", "limite_superior": "32.0"},
            {"nivel": "critico", "limite_inferior": "15.0", "limite_superior": "38.0"}
          ]
        }
      ],
      "patologias": [
        {"nombre": "Estreptococosis", "descripcion": "Infección bacteriana"},
        {"nombre": "Saprolegniasis"}
      ]
    }
  }'
```

Respuesta esperada `201`:
```json
{
  "id_plantilla": 1,
  "id_especie": 3,
  "id_usuario": 1,
  "template_name": "Tilapia Estándar",
  "version": 1,
  "fecha_creacion": "2026-06-21T10:00:00Z",
  "params_snapshot": {
    "schema_version": 1,
    "ciclos_biologicos": [...],
    "metricas_produccion": [...],
    "umbrales_ambientales": [...],
    "patologias": [...]
  }
}
```

Errores posibles:
- `400` — template_name fuera del rango 3-50 chars (FA-07)
- `400` — params_snapshot sin ningún elemento en ninguna categoría (FA-10),
  mensaje `Plantilla vacía: debe seleccionar al menos un parámetro (...)`
- `400` — un ítem sin sus campos obligatorios; el mensaje nombra la categoría,
  la posición y los campos que faltan, p. ej.
  `ciclos_biologicos[0]: faltan los campos ['duracion_dias'].` (FA-09 del RF-31)
- `400` — un campo obligatorio con el tipo equivocado, p. ej.
  `ciclos_biologicos[0].duracion_dias debe ser entero positivo; llegó 'muchos'.`
  o `metricas_produccion[0].tipo_medicion debe ser uno de ['PESO', ...]; llegó 'continua'.`
  Sin esta validación el dato quedaba guardado en una plantilla inmutable y
  reventaba al aplicarla en RF-32 (`int()`/`Decimal()` → `500`)
- `401` — token ausente o inválido
- `403` — rol sin permiso C sobre recurso 28 (FA-05)
- `404` — especie origen no existe
- `409` — `template_name` ya registrado (`NOMBRE_PLANTILLA_DUPLICADO`, FA
  "Nombre de plantilla duplicado"). La comparación ignora mayúsculas y espacios,
  igual que el trigger de la BD
- `422` — params_snapshot con claves de dispositivos IoT, infraestructura,
  dashboard o identidad visual (`ALCANCE_NO_PERMITIDO`, FA "Scope Creep" del RF-30)
- `422` — especie origen inactiva (FA-08)

Segunda llamada con el mismo `template_name` → `409`. Versionar es el Flujo G.

---

## RF-30 / RF-31 — Generar nueva versión de una plantilla (Flujo G)

### POST /configuracion/plantillas/{id_plantilla}/versiones

Las plantillas son inmutables: actualizar una es crear su versión siguiente.
La versión nueva hereda `template_name` e `id_especie` de la anterior — solo
cambian los parámetros. El número lo asigna el trigger
`trg_fn_plantilla_version_incremental` dentro de la transacción, así dos
versionados simultáneos no pueden reclamar el mismo.

```bash
curl -X POST http://localhost:8000/configuracion/plantillas/1/versiones \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "params_snapshot": {
      "ciclos_biologicos": [
        {"nombre": "Alevín", "duracion_dias": 35, "descripcion": "Fase inicial ajustada"}
      ],
      "patologias": [{"nombre": "Estreptococosis"}]
    }
  }'
```

Respuesta esperada `201`:
```json
{
  "id_plantilla": 4,
  "id_especie": 3,
  "id_usuario": 1,
  "template_name": "Tilapia Estándar",
  "version": 2,
  "fecha_creacion": "2026-09-03T10:00:00Z",
  "params_snapshot": {"schema_version": 1, "ciclos_biologicos": [...], "patologias": [...]}
}
```

La v1 sigue intacta en el listado: el criterio de aceptación pide que una
actualización *genere* una versión, no que sobreescriba la original.

Errores posibles:
- `400` — params_snapshot vacío o que no cumple el esquema
- `401` — token ausente o inválido
- `403` — rol sin permiso C sobre recurso 28
- `404` — la plantilla base no existe
- `422` — params_snapshot con claves fuera de alcance (`ALCANCE_NO_PERMITIDO`)
- `422` — la especie asociada fue desactivada entre una versión y la siguiente

### Verificación en DB

```sql
SELECT id_plantilla, template_name, version, fecha_creacion
FROM modulo9.plantillas
WHERE LOWER(TRIM(template_name)) = 'tilapia estándar'
ORDER BY version;
```

---

## RF-32 — Aplicar plantilla a especie destino (Flujo D)

### POST /configuracion/plantillas/{id_plantilla}/aplicar

```bash
curl -X POST http://localhost:8000/configuracion/plantillas/1/aplicar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_especie_destino": 5,
    "fecha_actualizacion_especie_destino": "2026-05-10T08:00:00Z"
  }'
```

Respuesta esperada `200`:
```json
{
  "id_aplicacion_plantilla": 1,
  "id_plantilla": 1,
  "id_usuario": 1,
  "target_config": {"id_especie": 5},
  "before_snapshot": {
    "ciclos_biologicos": [...],
    "metricas_produccion": [...],
    "umbrales_ambientales": [...],
    "patologias": [{"nombre": "Ictioftiriasis", "es_activo": true}]
  },
  "after_snapshot": {
    "ciclos_biologicos": [...],
    "metricas_produccion": [...],
    "umbrales_ambientales": [...],
    "patologias": [{"nombre": "Estreptococosis", "es_activo": true}]
  },
  "fecha_aplicacion": "2026-06-21T11:30:00Z"
}
```

Errores posibles:
- `401` — token ausente o inválido
- `403` — rol sin permiso E sobre recurso 28 (FA-05)
- `404` — plantilla no existe
- `404` — especie destino no existe (FA-03)
- `412` — schema_version del snapshot incompatible con la versión actual (FA-02)
- `412` — `fecha_actualizacion_especie_destino` no coincide con la especie en DB, conflicto de concurrencia (FA-11)
- `422` — especie destino inactiva

### Verificación en DB tras aplicar

```sql
-- Confirmar que las metricas del destino cambiaron
SELECT nombre, es_activo FROM modulo9.metricas_produccion WHERE id_especie = 5 ORDER BY es_activo DESC;

-- Ver el registro de aplicacion con before/after
SELECT id_aplicacion_plantilla, before_snapshot, after_snapshot, fecha_aplicacion
FROM modulo9.aplicaciones_plantillas
ORDER BY fecha_aplicacion DESC LIMIT 5;
```
