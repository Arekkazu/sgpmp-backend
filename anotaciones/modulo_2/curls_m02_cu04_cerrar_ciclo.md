# CURLs — M02 CU04 — Cerrar Ciclo Productivo (RF-38, RF-44)

> Base URL: `http://localhost:8000`
> Recurso RBAC: 29 (`activos_biologicos`)
> Actores RF-44 (E=5): Administrador (id_rol=1), Productor (id_rol=2), Veterinario (id_rol=3), Ingeniero (id_rol=4)
> Actores RF-38 (D=4): Administrador (id_rol=1), Productor (id_rol=2), Veterinario (id_rol=3)

Reemplazar `{TOKEN}` con JWT válido y `{ID_ACTIVO}` con el id del activo.

---

## Flujo A — Cambiar estado del activo (RF-44)

**Endpoint:** `PATCH /activos-biologicos/{id_activo}/estado`
**Permiso:** E(5) sobre recurso 29

### A1 — Happy path: ACTIVO → INACTIVO

```bash
curl -X PATCH http://localhost:8000/activos-biologicos/{ID_ACTIVO}/estado \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "estado_nuevo": "INACTIVO",
    "fecha_cambio_estado": "2026-06-28",
    "motivo_cambio": "Activo en cuarentena preventiva."
  }'
```

**Respuesta esperada (200):**
```json
{
  "id_activo_biologico": 1,
  "estado_anterior": 1,
  "estado_nuevo": 2,
  "historial": {
    "id_historico": 1,
    "id_activo_biologico": 1,
    "id_estado_anterior": 1,
    "nombre_estado_anterior": null,
    "id_estado_nuevo": 2,
    "nombre_estado_nuevo": null,
    "fecha_cambio": "2026-06-28T00:00:00+00:00",
    "motivo_cambio": "Activo en cuarentena preventiva.",
    "modulo_origen": "modulo2",
    "id_usuario": 3
  }
}
```

### A2 — Error: transición no permitida (CERRADO → ACTIVO)

**Código:** `422`
```json
{
  "code": "TRANSICION_INVALIDA",
  "message": "La transición CERRADO → ACTIVO no está permitida. Transiciones válidas desde CERRADO: BAJA."
}
```
**FA:** FA-07

### A3 — Error: activo en BAJA (irreversible)

**Código:** `409`
```json
{
  "code": "ESTADO_BAJA_IRREVERSIBLE",
  "message": "El activo se encuentra en estado BAJA. No se permite modificar el estado de activos dados de baja definitivamente."
}
```
**FA:** FA-07

### A4 — Error: estado redundante

**Código:** `409`
```json
{
  "code": "ESTADO_REDUNDANTE",
  "message": "El activo ya se encuentra en el estado solicitado. No se realizó ningún cambio."
}
```
**FA:** FA-07

### A5 — Error: fecha futura

**Código:** `422` (validación Pydantic)
```json
{
  "code": "VALIDATION_ERROR",
  "message": "La fecha del cambio de estado no puede ser futura."
}
```
**FA:** FA-04

### A6 — Error: motivo vacío

**Código:** `422` (validación Pydantic)
```json
{
  "code": "VALIDATION_ERROR",
  "message": "El motivo del cambio de estado es obligatorio."
}
```
**FA:** FA-03

### A7 — Error: activo no encontrado

**Código:** `404`
```json
{
  "code": "ACTIVO_NO_ENCONTRADO",
  "message": "El activo biológico con ID 9999 no existe."
}
```
**FA:** FA-01

---

## Flujo B — Cerrar ciclo productivo (RF-38)

**Endpoint:** `POST /activos-biologicos/{id_activo}/cierre`
**Permiso:** D(4) sobre recurso 29

### B1 — Happy path: cierre exitoso de activo ACTIVO

Requisitos previos: activo en estado ACTIVO, con fase productiva activa y sin sensores IoT asociados vigentes.

```bash
curl -X POST http://localhost:8000/activos-biologicos/{ID_ACTIVO}/cierre \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "fecha_cierre": "2026-06-28",
    "motivo_cierre": "sacrificio",
    "descripcion_cierre": "Lote completó ciclo productivo. Cosecha realizada."
  }'
```

**Respuesta esperada (200):**
```json
{
  "id_activo_biologico": 1,
  "estado": "CERRADO",
  "fecha_cierre": "2026-06-28",
  "motivo_cierre": "sacrificio",
  "fase_finalizada": true
}
```

**Efectos en DB:**
- `modulo2.activos_biologicos.id_estado` → 5 (CERRADO)
- `modulo2.historicos_estados_activos` → nuevo registro con modulo_origen='modulo2'
- `modulo2.gestiones_fases` → fila activa marcada `es_activa=false`, `fecha_finalizacion=fecha_cierre`

### B2 — Error: activo ya cerrado o en BAJA

**Código:** `409`
```json
{
  "code": "ESTADO_INVALIDO_PARA_CIERRE",
  "message": "El activo biológico ya se encuentra en estado CERRADO. No es posible realizar un nuevo cierre de ciclo."
}
```
**FA:** FA-02

### B3 — Error: sensores IoT activos vinculados

**Código:** `422`
```json
{
  "code": "SENSORES_ACTIVOS",
  "message": "El activo tiene sensores IoT vinculados activos. Desvincule los sensores antes de cerrar el ciclo productivo."
}
```
**FA:** FA-06

### B4 — Error: sin fase productiva activa

**Código:** `422`
```json
{
  "code": "SIN_FASE_ACTIVA",
  "message": "El activo no presenta una fase productiva activa. Verifique la integridad del ciclo de vida antes de cerrar."
}
```
**FA:** FA-05

### B5 — Error: fecha de cierre anterior al último evento

**Código:** `400`
```json
{
  "code": "FECHA_CIERRE_ANTERIOR_ULTIMO_EVENTO",
  "message": "La fecha de cierre no puede ser anterior al último registro de actividad del activo (2026-06-25).",
  "field": "fecha_cierre"
}
```
**FA:** FA-04

### B6 — Error: fecha futura

**Código:** `422` (validación Pydantic)
```json
{
  "code": "VALIDATION_ERROR",
  "message": "La fecha de cierre no puede ser futura."
}
```
**FA:** FA-04

### B7 — Error: motivo vacío

**Código:** `422` (validación Pydantic)
```json
{
  "code": "VALIDATION_ERROR",
  "message": "Debe indicar un motivo de cierre."
}
```
**FA:** FA-03

### B8 — Error: activo no encontrado

**Código:** `404`
```json
{
  "code": "ACTIVO_NO_ENCONTRADO",
  "message": "El activo biológico con ID 9999 no existe."
}
```
**FA:** FA-01

### B9 — Error: sin permisos (rol sin D=4)

**Código:** `403`
```json
{
  "code": "AUTHORIZATION_ERROR",
  "message": "No tienes permiso para realizar esta acción."
}
```
**FA:** FA-08
