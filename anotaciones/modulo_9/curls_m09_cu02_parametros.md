# CURLs — M09 CU02: Configurar Parámetros por Especie

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT obtenido en `/sesiones/login`.

---

## ETAPAS DEL CICLO PRODUCTIVO

### Flujo A — Registrar etapa

```bash
curl -X POST http://localhost:8000/configuracion/ciclos \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_especie": 1,
    "nombre": "Crecimiento",
    "descripcion": "Fase de crecimiento inicial del activo",
    "duracion_dias": 90
  }'
```

Respuesta esperada `201`:
```json
{
  "id_ciclo_biologico": 1,
  "nombre": "Crecimiento",
  "descripcion": "Fase de crecimiento inicial del activo",
  "duracion_dias": 90,
  "id_especie": 1,
  "es_activo": true,
  "fecha_actualizacion": null
}
```

Errores posibles:
- `404` — especie no existe o está inactiva
- `409` — nombre duplicado para esta especie (case-insensitive)
- `422` — duracion_dias <= 0
- `403` — sin permiso C sobre ciclos_biologicos

---

### Flujo D — Consultar etapas por especie

```bash
curl -X GET "http://localhost:8000/configuracion/ciclos?id_especie=1" \
  -H "Authorization: Bearer <TOKEN>"
```

Solo activas:
```bash
curl -X GET "http://localhost:8000/configuracion/ciclos?id_especie=1&solo_activas=true" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 2,
  "items": [
    {
      "id_ciclo_biologico": 1,
      "nombre": "Crecimiento",
      "descripcion": "...",
      "duracion_dias": 90,
      "id_especie": 1,
      "es_activo": true,
      "fecha_actualizacion": null
    }
  ]
}
```

---

### Flujo B — Editar etapa

`fecha_actualizacion` debe ser el valor exacto devuelto por el sistema (concurrencia optimista).
Enviar `null` si la etapa nunca ha sido editada.

```bash
curl -X PATCH http://localhost:8000/configuracion/ciclos/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Crecimiento Temprano",
    "descripcion": "Fase inicial ajustada",
    "duracion_dias": 75,
    "fecha_actualizacion": null
  }'
```

Errores posibles:
- `404` — etapa no existe
- `409` — nombre duplicado para esta especie
- `412` — conflicto de concurrencia (otra sesión modificó la etapa)
- `422` — etapa inactiva o duracion_dias <= 0

---

### Flujo C — Desactivar etapa

```bash
curl -X PATCH http://localhost:8000/configuracion/ciclos/1/desactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — etapa no existe
- `422` — etapa ya inactiva o tiene activos biológicos en esa fase

---

## PATOLOGÍAS POR ESPECIE

### Flujo E — Registrar patología para una especie

Crea una patología **propia de la especie** (entidad M09 en `especies_patologias`).
El nombre es único **por especie** (case-insensitive): el mismo nombre puede existir
en otra especie con datos propios. No escribe el catálogo clínico M04
(`id_patologia` queda `null`).

```bash
curl -X POST http://localhost:8000/configuracion/patologias \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_especie": 1,
    "nombre": "Enfermedad X",
    "descripcion": "Descripción opcional de la patología"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_especies_patologias": 11,
  "id_patologia": null,
  "id_especie": 1,
  "nombre": "Enfermedad X",
  "descripcion": "Descripción opcional de la patología",
  "es_activo": true,
  "fecha_actualizacion": null
}
```

Errores posibles:
- `404` — especie no existe o está inactiva
- `409` — ya existe una patología con ese nombre para esta especie (FA-02)
- `403` — sin permiso C sobre patologias

---

### Flujo H — Consultar patologías por especie

```bash
curl -X GET "http://localhost:8000/configuracion/patologias?id_especie=1" \
  -H "Authorization: Bearer <TOKEN>"
```

Solo activas:
```bash
curl -X GET "http://localhost:8000/configuracion/patologias?id_especie=1&solo_activas=true" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 3,
  "items": [
    {
      "id_especies_patologias": 1,
      "id_patologia": 1,
      "id_especie": 1,
      "nombre": "Ich (Ichthyophthirius)",
      "descripcion": null,
      "es_activo": true,
      "fecha_actualizacion": null
    }
  ]
}
```

---

### Flujo F — Editar patología de la especie

Edita **solo** la patología de esa especie (nombre/descripción propios). El path param
es `id_especies_patologias` (la identidad de la patología por especie), no el catálogo M04.

```bash
curl -X PATCH http://localhost:8000/configuracion/patologias/11 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Enfermedad X Actualizada",
    "descripcion": "Descripción corregida",
    "fecha_actualizacion": null
  }'
```

Errores posibles:
- `404` — patología no existe
- `409` — ya existe una patología con ese nombre para esta especie
- `412` — conflicto de concurrencia
- `422` — patología inactiva

---

### Flujo G — Desactivar patología de la especie

Desactiva (baja lógica) la patología de esa especie. El path param es
`id_especies_patologias`.

```bash
curl -X PATCH http://localhost:8000/configuracion/patologias/11/desactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — patología no existe
- `422` — patología ya inactiva o (si está vinculada a catálogo M04) tiene historial clínico asociado

---

---

## MÉTRICAS DE PRODUCCIÓN

### Flujo I — Registrar métrica para una especie

```bash
curl -X POST http://localhost:8000/configuracion/metricas \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_especie": 1,
    "nombre": "Peso promedio",
    "unidad_medida": "kg",
    "tipo_medicion": "PESO",
    "aplica_a_tipo_activo": "INDIVIDUAL"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_metrica_produccion": 1,
  "nombre": "Peso promedio",
  "unidad_medida": "kg",
  "tipo_medicion": "PESO",
  "aplica_a_tipo_activo": "INDIVIDUAL",
  "id_especie": 1,
  "es_activo": true,
  "fecha_actualizacion": null
}
```

Errores posibles:
- `404` — especie no existe o está inactiva
- `409` — nombre duplicado para esta especie (case-insensitive)
- `422` — unidad incoherente con tipo_medicion (FA-10) o tipo_medicion inválido
- `403` — sin permiso C sobre metricas_produccion

---

### Flujo L — Consultar métricas por especie

```bash
curl -X GET "http://localhost:8000/configuracion/metricas?id_especie=1" \
  -H "Authorization: Bearer <TOKEN>"
```

Solo activas:
```bash
curl -X GET "http://localhost:8000/configuracion/metricas?id_especie=1&solo_activas=true" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 2,
  "items": [
    {
      "id_metrica_produccion": 1,
      "nombre": "Peso promedio",
      "unidad_medida": "kg",
      "tipo_medicion": "PESO",
      "aplica_a_tipo_activo": "INDIVIDUAL",
      "id_especie": 1,
      "es_activo": true,
      "fecha_actualizacion": null
    }
  ]
}
```

---

### Flujo J — Editar métrica

`fecha_actualizacion` debe ser el valor exacto devuelto por el sistema. Enviar `null` si nunca fue editada.

```bash
curl -X PATCH http://localhost:8000/configuracion/metricas/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Peso promedio ajustado",
    "unidad_medida": "g",
    "tipo_medicion": "PESO",
    "aplica_a_tipo_activo": "AMBOS",
    "fecha_actualizacion": null
  }'
```

Errores posibles:
- `404` — métrica no existe
- `409` — nombre duplicado para esta especie
- `412` — conflicto de concurrencia (otra sesión modificó la métrica)
- `422` — métrica inactiva, unidad incoherente o tipo inválido

---

### Flujo K — Desactivar métrica

```bash
curl -X PATCH http://localhost:8000/configuracion/metricas/1/desactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — métrica no existe
- `422` — métrica ya inactiva o tiene registros productivos activos (FA-09)

---

## Tabla FA-10: coherencia unidad_medida / tipo_medicion

| tipo_medicion | unidades_permitidas |
|---------------|---------------------|
| PESO          | kg, g, lb           |
| VOLUMEN       | litros, ml          |
| LONGITUD      | cm, m               |
| CONTEO        | unidades            |
| OTRO          | cualquiera          |

---

## Notas

- El nombre de etapa acepta letras, números, espacios, guiones y paréntesis (3–50 chars).
- El nombre de patología acepta letras, números, espacios, guiones, paréntesis y puntos (3–60 chars).
- El nombre de métrica acepta letras, números, espacios, guiones, paréntesis y barras (3–60 chars).
- Unicidad de etapas: por especie (case-insensitive).
- Unicidad de patologías: **por especie** (case-insensitive), índice `uq_especie_patologia_nombre`. FA-02 se activa si ya existe ese nombre en la misma especie. `id_patologia` (vínculo al catálogo clínico M04) es opcional/`null` para las creadas por M09. (#1633)
- Unicidad de métricas: por especie (case-insensitive), mismo patrón que etapas.
- `duracion_dias` debe ser entero positivo mayor a 0.
- Para probar con Swagger: `http://localhost:8000/docs` → secciones "Configuración - Ciclos Productivos", "Configuración - Patologías" y "Configuración - Métricas de Producción".
