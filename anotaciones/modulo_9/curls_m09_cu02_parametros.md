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
    "aplica_a_tipo_activo": "INDIVIDUAL",
    "tipo_dato": "NUMERICO",
    "valor_min": 20,
    "valor_max": 40
  }'
```

`valor_min` / `valor_max` (RFC-004, **TC-M02-G12 #460**) son opcionales y definen el rango válido del
atributo dinámico que RF-33 valida al registrar un activo. Solo aplican a `tipo_dato` `NUMERICO` o
`ENTERO`; si ambos vienen, `valor_min <= valor_max`. Hasta 10 dígitos con 4 decimales (`NUMERIC(10,4)`).

Respuesta esperada `201`:
```json
{
  "id_metrica_produccion": 1,
  "nombre": "Peso promedio",
  "unidad_medida": "kg",
  "tipo_medicion": "PESO",
  "aplica_a_tipo_activo": "INDIVIDUAL",
  "tipo_dato": "NUMERICO",
  "es_obligatorio": false,
  "valor_min": "20.0000",
  "valor_max": "40.0000",
  "id_especie": 1,
  "es_activo": true,
  "fecha_actualizacion": null
}
```

Los `Decimal` viajan como cadena (`"20.0000"`), igual que en el resto de la API de configuración.

Errores posibles:
- `400` — `RANGO_METRICA_INVALIDO` (`valor_min` > `valor_max`, campo `valor_min`) o `RANGO_METRICA_NO_APLICA`
  (rango con `tipo_dato` `TEXTO`/`BOOLEANO`, campo `valor_min` o `valor_max`)
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
      "tipo_dato": "NUMERICO",
      "es_obligatorio": false,
      "valor_min": "20.0000",
      "valor_max": "40.0000",
      "id_especie": 1,
      "es_activo": true,
      "fecha_actualizacion": null
    }
  ]
}
```

`valor_min`/`valor_max` son `null` cuando la métrica no tiene rango. Es la forma oficial de que QA consulte los
límites configurados (TC-M02-014: comprobar por API que un valor queda fuera de rango).

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

**Rango en la edición (RFC-004):** omitir `valor_min`/`valor_max` **conserva** el rango guardado; enviarlos con un
número lo reemplaza; enviarlos como `null` lo **elimina**. Se valida ya fusionado con lo guardado (enviar solo
`valor_max: 10` con un `valor_min` guardado de 20 da `400 RANGO_METRICA_INVALIDO`). Si la edición cambia
`tipo_dato` a `TEXTO`/`BOOLEANO` sin enviar rango, el rango previo se limpia; enviarlo explícitamente da
`400 RANGO_METRICA_NO_APLICA`.

```bash
curl -X PATCH http://localhost:8000/configuracion/metricas/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"nombre": "Peso promedio ajustado", "unidad_medida": "kg", "tipo_medicion": "PESO",
       "aplica_a_tipo_activo": "AMBOS", "fecha_actualizacion": "<valor devuelto>",
       "valor_min": 25, "valor_max": null}'
```

El nombre acepta guion bajo (`peso_destete`), igual que el dominio: antes el DTO lo rechazaba y una métrica
creada así no se podía editar.

Errores posibles:
- `400` — `RANGO_METRICA_INVALIDO` / `RANGO_METRICA_NO_APLICA`
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

Los valores históricos `manual`, `calculada` y `TALLA` no forman parte de
`tipo_medicion`: describían el método o una denominación anterior, no la magnitud RF-16.
La migración `v5.3.0_rf16_normalizar_tipos_medicion_legacy` los convierte al catálogo
vigente, corrige `tipo_dato` y valida `chk_metricas_tipo_medicion`. Esto permite que el
endpoint evalúe FA-09 y responda `METRICA_CON_REGISTROS` en vez de fallar durante la
hidratación ORM.

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
