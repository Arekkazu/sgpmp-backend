# CURLs — M09 CU01: Gestionar Catálogo de Especies Productivas

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT obtenido en `/sesiones/login`.

---

## Flujo A — Registrar especie (Admin)

```bash
curl -X POST http://localhost:8000/configuracion/especies \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Bovino",
    "descripcion": "Ganado vacuno para producción de carne y leche"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_especie": 1,
  "nombre": "Bovino",
  "descripcion": "Ganado vacuno para producción de carne y leche",
  "es_activo": true,
  "fecha_creacion": "2026-06-13T...",
  "fecha_actualizacion": null
}
```

Errores posibles:
- `409` — nombre duplicado (case-insensitive)
- `403` — rol sin permiso C sobre especies

---

## Flujo E — Consultar catálogo (autenticado)

### Todas las especies
```bash
curl -X GET http://localhost:8000/configuracion/especies \
  -H "Authorization: Bearer <TOKEN>"
```

### Solo activas
```bash
curl -X GET "http://localhost:8000/configuracion/especies?solo_activas=true" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 3,
  "items": [
    {
      "id_especie": 1,
      "nombre": "Bovino",
      "descripcion": "...",
      "es_activo": true,
      "fecha_creacion": "2026-06-13T...",
      "fecha_actualizacion": null
    }
  ]
}
```

---

## Flujo B — Editar especie (Admin o Ingeniero de Campo)

`fecha_actualizacion` debe ser el valor exacto que devolvió el sistema al
consultar la especie (control de concurrencia optimista).

```bash
curl -X PATCH http://localhost:8000/configuracion/especies/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Bovino Lechero",
    "descripcion": "Ganado vacuno especializado en producción de leche",
    "fecha_actualizacion": "2026-06-13T15:30:00+00:00"
  }'
```

Errores posibles:
- `404` — especie no existe
- `409` — nombre ya pertenece a otra especie
- `412` — concurrencia: la especie fue modificada por otro usuario
- `422` — especie inactiva (debe reactivarse primero)

---

## Flujo C — Desactivar especie (Admin)

```bash
curl -X PATCH http://localhost:8000/configuracion/especies/1/desactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — especie no existe
- `422` — especie ya inactiva
- `423` — especie con proceso crítico activo (bloqueada por M04)

---

## Flujo D — Reactivar especie (Admin)

```bash
curl -X PATCH http://localhost:8000/configuracion/especies/1/reactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — especie no existe
- `422` — especie ya activa

---

## Notas

- El campo `nombre` acepta letras (incluyendo tildes y ñ), entre 3 y 50 caracteres.
  No puede empezar con espacio. Se normaliza internamente a minúsculas para
  verificar duplicados, pero se guarda con el casing original.
- La unicidad del nombre es **case-insensitive**: "Bovino" y "bovino" se consideran duplicados.
- Para probar con Swagger: `http://localhost:8000/docs` → sección "Configuración - Especies".
