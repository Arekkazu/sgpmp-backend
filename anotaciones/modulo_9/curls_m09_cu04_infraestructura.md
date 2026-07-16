# CURLs — M09 CU04: Gestionar Infraestructura Productiva

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT obtenido en `/sesiones/login`.

---

## RF-18 — Parámetros operativos del sistema (`/configuracion/parametros`)

Solo el rol **Administrador** puede operar sobre este recurso (`id_recurso=21`).

### Consultar configuración activa

```bash
curl -X GET http://localhost:8000/configuracion/parametros \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_configuracion_global": 1,
  "frecuencia_muestreo": 60,
  "heartbeat": 120,
  "fecha_actualizacion": "2026-04-28T14:42:28.213141Z",
  "id_usuario": 1,
  "es_activo": true
}
```

---

### Crear configuración operativa

Retorna `409` si ya existe una configuración activa en el sistema (FA-13).

```bash
curl -X POST http://localhost:8000/configuracion/parametros \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "frecuencia_muestreo": 60,
    "heartbeat": 120
  }'
```

Errores posibles:
- `409` — ya existe una configuración activa (FA-13)
- `400` — heartbeat menor que frecuencia de muestreo (FA-12)
- `400` — valores no son enteros positivos (FA-12)
- `403` — rol sin permiso C sobre `configuraciones_globales`

---

### Actualizar configuración operativa

`fecha_actualizacion` debe ser el valor exacto devuelto por la última consulta (FA-14).

```bash
curl -X PATCH http://localhost:8000/configuracion/parametros/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "frecuencia_muestreo": 30,
    "heartbeat": 90,
    "fecha_actualizacion": "2026-04-28T14:42:28.213141Z"
  }'
```

Errores posibles:
- `404` — configuración no existe
- `412` — concurrencia: otro administrador modificó los parámetros antes (FA-14)
- `400` — heartbeat menor que frecuencia de muestreo (FA-12)

---

## RF-19 — Fincas (`/configuracion/fincas`)

Recurso `id_recurso=9`. Admin: C/R/U/D. Productor: solo R (sus fincas).

### Registrar finca (Admin)

El campo `nombre` solo acepta letras, espacios, tildes y ñ (FA-10). Las coordenadas
deben estar en rango: latitud −90 a 90, longitud −180 a 180 (FA-09).

```bash
curl -X POST http://localhost:8000/configuracion/fincas \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Finca El Paraiso",
    "ubicacion": {
      "departamento": "Antioquia",
      "municipio": "Medellin",
      "vereda": "La Estrella",
      "latitud": "6.25",
      "longitud": "-75.56"
    },
    "tamano_h": "100.5",
    "id_usuario": 2
  }'
```

Respuesta esperada `201`:
```json
{
  "id_finca": 1,
  "nombre": "Finca El Paraiso",
  "ubicacion": {
    "departamento": "Antioquia",
    "municipio": "Medellin",
    "vereda": "La Estrella",
    "latitud": "6.25",
    "longitud": "-75.56"
  },
  "tamano_h": "100.50",
  "es_activo": true,
  "fecha_creacion": "2026-06-21T16:13:31Z",
  "fecha_actualizacion": "2026-06-21T16:13:31.413509Z",
  "id_usuario": 2
}
```

Errores posibles:
- `409` — nombre duplicado (case-insensitive, global) (FA-07)
- `400` — nombre/ubicación con caracteres no permitidos (FA-10)
- `400` — coordenadas fuera de rango (FA-09)
- `400` — `tamano_h` cero, negativo o no numérico (FA-11)
- `403` — rol sin permiso C sobre fincas (FA-01)

---

### Listar fincas

Admin recibe todas las fincas; Productor recibe solo las asignadas a él (FA-06).

```bash
# Todas (Admin) o las propias (Productor)
curl -X GET http://localhost:8000/configuracion/fincas \
  -H "Authorization: Bearer <TOKEN>"

# Solo activas
curl -X GET "http://localhost:8000/configuracion/fincas?solo_activas=true" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 1,
  "items": [
    {
      "id_finca": 1,
      "nombre": "Finca El Paraiso",
      "ubicacion": { "departamento": "Antioquia", "municipio": "Medellin", "vereda": "La Estrella", "latitud": "6.25", "longitud": "-75.56" },
      "tamano_h": "100.50",
      "es_activo": true,
      "fecha_creacion": "2026-06-21T...",
      "fecha_actualizacion": "2026-06-21T...",
      "id_usuario": 2
    }
  ]
}
```

---

### Detalle de finca

```bash
curl -X GET http://localhost:8000/configuracion/fincas/1 \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — finca no existe
- `403` — productor accediendo a una finca no asignada (FA-01)

---

### Editar finca (Admin)

`fecha_actualizacion` debe ser el valor exacto de la última respuesta (FA-14).

```bash
curl -X PATCH http://localhost:8000/configuracion/fincas/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Finca El Paraiso Norte",
    "ubicacion": {
      "departamento": "Antioquia",
      "municipio": "Medellin",
      "vereda": "La Estrella",
      "latitud": "6.30",
      "longitud": "-75.60"
    },
    "tamano_h": "120.0",
    "fecha_actualizacion": "2026-06-21T16:13:31.413509Z"
  }'
```

Errores posibles:
- `404` — finca no existe
- `409` — nombre ya pertenece a otra finca (FA-07)
- `412` — concurrencia: la finca fue modificada por otro usuario (FA-14)
- `400` — caracteres inválidos / coordenadas fuera de rango (FA-10, FA-09)

---

### Desactivar finca (Admin)

```bash
curl -X PATCH http://localhost:8000/configuracion/fincas/1/desactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — finca no existe
- `422` — finca ya inactiva
- `422` — finca con áreas productivas u otros registros activos (FA-04)

---

## RF-20 — Áreas productivas (`/configuracion/infraestructuras`)

Recurso `id_recurso=10`. Admin: C/R/U/D. Productor/Vet/Ing: solo R.

Valores válidos para `tipo_area`: `galpon`, `corral`, `potrero`, `estanque`, `invernadero`.

### Registrar área productiva (Admin)

La finca debe existir y estar activa (FA-03).

```bash
curl -X POST http://localhost:8000/configuracion/infraestructuras \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_infraestructura": "Galpon Principal",
    "tipo_area": "galpon",
    "superficie": "2500.00",
    "finca_id": 1,
    "descripcion_infraestructura": "Galpon principal de engorde"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_infraestructura": 1,
  "nombre_infraestructura": "Galpon Principal",
  "tipo_area": "galpon",
  "superficie": "2500.00",
  "id_finca": 1,
  "descripcion_infraestructura": "Galpon principal de engorde",
  "es_activo": true,
  "fecha_actualizacion": null
}
```

Errores posibles:
- `404` — finca no existe (FA-03)
- `422` — finca inactiva (FA-03)
- `409` — nombre duplicado dentro de la misma finca (FA-08)
- `400` — superficie cero, negativa o no numérica (FA-11)
- `403` — rol sin permiso C sobre infraestructuras (FA-01)

---

### Listar áreas de una finca

El parámetro `finca_id` es obligatorio.

```bash
# Todas las áreas de la finca
curl -X GET "http://localhost:8000/configuracion/infraestructuras?finca_id=1" \
  -H "Authorization: Bearer <TOKEN>"

# Solo activas
curl -X GET "http://localhost:8000/configuracion/infraestructuras?finca_id=1&solo_activas=true" \
  -H "Authorization: Bearer <TOKEN>"
```

---

### Detalle de área productiva

```bash
curl -X GET http://localhost:8000/configuracion/infraestructuras/1 \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — área no existe

---

### Editar área productiva (Admin)

`fecha_actualizacion` es `null` si el área nunca ha sido editada; en ediciones
posteriores enviar el timestamp exacto de la última respuesta (FA-14).

```bash
# Primera edición (fecha_actualizacion nunca se ha asignado)
curl -X PATCH http://localhost:8000/configuracion/infraestructuras/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_infraestructura": "Galpon Principal Ampliado",
    "tipo_area": "galpon",
    "superficie": "3000.00",
    "descripcion_infraestructura": "Galpon ampliado tras remodelacion",
    "fecha_actualizacion": null
  }'

# Ediciones siguientes (usar el timestamp de la respuesta anterior)
curl -X PATCH http://localhost:8000/configuracion/infraestructuras/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_infraestructura": "Galpon Principal Ampliado",
    "tipo_area": "galpon",
    "superficie": "3500.00",
    "descripcion_infraestructura": "Galpon ampliado fase dos",
    "fecha_actualizacion": "2026-06-21T17:00:00.000000Z"
  }'
```

Errores posibles:
- `404` — área no existe
- `409` — nombre duplicado dentro de la misma finca (FA-08)
- `412` — concurrencia: el área fue modificada por otro usuario (FA-14)
- `400` — superficie inválida (FA-11)

---

### Desactivar área productiva (Admin)

```bash
curl -X PATCH http://localhost:8000/configuracion/infraestructuras/1/desactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — área no existe
- `422` — área ya inactiva
- `422` — área con dispositivos IoT o activos biológicos activos (FA-04)

---

## Notas

- El `nombre` de finca acepta letras (con tildes y ñ) y espacios; entre 1 y 55 caracteres. No se permiten números ni caracteres especiales (FA-10).
- Los campos de ubicación (`departamento`, `municipio`, `vereda`) siguen la misma restricción de caracteres que el nombre de finca.
- La unicidad del nombre de finca es **global y case-insensitive** (FA-07).
- La unicidad del nombre de área es **por finca y case-sensitive** vía constraint de DB (FA-08).
- El control de concurrencia (FA-14) requiere enviar `fecha_actualizacion` con el valor exacto obtenido de la última lectura. Un timestamp desactualizado retorna `412`.
- Tipos de área válidos (enum DB): `galpon`, `corral`, `potrero`, `estanque`, `invernadero`.
- Para probar con Swagger: `http://localhost:8000/docs` → secciones "Configuración - Parámetros Operativos", "Configuración - Fincas", "Configuración - Infraestructura Productiva".
