# CU-01 RF-64 — CURLs Catálogo de Patologías M04

Base URL local: `http://localhost:8000`  
Autenticación: `Authorization: Bearer <JWT>`  
Roles autorizados: Administrador (id_rol=1), Veterinario (id_rol=3)

---

## POST /prediccion/patologias — Registrar patología

**RBAC**: C sobre recurso `patologias` (id=18)  
**Respuesta exitosa**: 201

```bash
curl -s -X POST http://localhost:8000/prediccion/patologias \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_patologia": "Neumonía por micoplasma",
    "especie_aplicable": "TODAS",
    "variables_sensoricas_asociadas": [13, 15, 12],
    "descripcion_clinica": "Temperatura corporal elevada junto con frecuencia respiratoria alta y aumento de CO2 en el ambiente indican cuadro de neumonía por micoplasma en el activo biológico."
  }' | python3 -m json.tool
```

**Respuesta esperada (201)**:
```json
{
  "id_patologia": 15,
  "nombre_patologia": "Neumonía por micoplasma",
  "especie_aplicable": "TODAS",
  "descripcion_clinica": "...",
  "es_base": false,
  "es_activo": true,
  "version_catalogo": 1,
  "variables_sensoricas_asociadas": [
    {"id_variable_ambiental": 13, "peso_evidencia": "1.000", "es_variable_critica": false},
    {"id_variable_ambiental": 15, "peso_evidencia": "1.000", "es_variable_critica": false},
    {"id_variable_ambiental": 12, "peso_evidencia": "1.000", "es_variable_critica": false}
  ],
  "fecha_creacion_m04": "2026-07-10T...",
  "fecha_actualizacion": null
}
```

**Errores posibles**:

| FA | HTTP | code | Condición |
|----|------|------|-----------|
| FA-01 | 404 | `ESPECIE_NO_ACTIVA` | `especie_aplicable` no existe o no está activa |
| FA-02 | 422 | `CANTIDAD_VARIABLES_INVALIDA` | Menos de 2 o más de 6 variables (E5) |
| FA-02 | 422 | `DESCRIPCION_CLINICA_INSUFICIENTE` | `descripcion_clinica` < 50 chars |
| FA-03 | 422 | `VARIABLE_NO_EN_I3P1` | Variable no existe en catálogo I3P-1 (E1) |
| FA-04 | 409 | `NOMBRE_PATOLOGIA_DUPLICADO` | Nombre duplicado (case-insensitive) (E4) |
| FA-05 | 409 | `COMBINACION_VARIABLES_DUPLICADA` | Misma combinación de variables (E6) |
| — | 401 | `AUTENTICACION_REQUERIDA` | Token ausente o inválido |
| — | 403 | `PERMISO_DENEGADO` | Rol sin permiso C sobre patologias |

---

## GET /prediccion/patologias — Listar catálogo

**RBAC**: R sobre recurso `patologias` (id=18)  
**Respuesta exitosa**: 200

```bash
# Todas las patologías
curl -s http://localhost:8000/prediccion/patologias \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Solo activas
curl -s "http://localhost:8000/prediccion/patologias?solo_activas=true" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Solo base
curl -s "http://localhost:8000/prediccion/patologias?solo_base=true" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Por especie (TODAS)
curl -s "http://localhost:8000/prediccion/patologias?especie_aplicable=TODAS" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Respuesta esperada (200)**:
```json
{
  "total": 8,
  "items": [...]
}
```

---

## GET /prediccion/patologias/{id} — Detalle de patología

**RBAC**: R sobre recurso `patologias` (id=18)  
**Respuesta exitosa**: 200

```bash
curl -s http://localhost:8000/prediccion/patologias/7 \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Respuesta esperada (200)**: objeto `PatologiaM04Response` con la patología base `Ninguna (estado normal)`.

**Errores posibles**:

| HTTP | code | Condición |
|------|------|-----------|
| 404 | `PATOLOGIA_NO_ENCONTRADA` | ID no existe |

---

## PATCH /prediccion/patologias/{id} — Editar patología

**RBAC**: U sobre recurso `patologias` (id=18)  
**Respuesta exitosa**: 200

```bash
curl -s -X PATCH http://localhost:8000/prediccion/patologias/15 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_patologia": "Neumonía por micoplasma aviar",
    "descripcion_clinica": "Temperatura corporal elevada junto con frecuencia respiratoria alta y aumento de CO2 en el ambiente son indicadores de neumonía por micoplasma en aves de producción.",
    "variables_sensoricas_asociadas": [13, 15, 12, 11],
    "fecha_actualizacion": "2026-07-10T12:00:00Z"
  }' | python3 -m json.tool
```

**Errores posibles**:

| FA | HTTP | code | Condición |
|----|------|------|-----------|
| FA-06 | 422 | `PATOLOGIA_BASE_INMUTABLE` | `es_base = true` (E2) |
| FA-07 | 409 | `PATOLOGIA_EN_USO_POR_MODELO` | Modelo en EN_VALIDACION o ACTIVO usa la patología (E7) |
| — | 412 | `CONFLICTO_CONCURRENCIA` | `fecha_actualizacion` no coincide con la BD |
| FA-03 | 422 | `VARIABLE_NO_EN_I3P1` | Variable inválida |
| FA-02 | 422 | `CANTIDAD_VARIABLES_INVALIDA` | <2 o >6 variables |
| FA-04 | 409 | `NOMBRE_PATOLOGIA_DUPLICADO` | Nombre ya existe en otra patología |
| FA-05 | 409 | `COMBINACION_VARIABLES_DUPLICADA` | Combinación duplicada |
| — | 404 | `PATOLOGIA_NO_ENCONTRADA` | ID no existe |

---

## PATCH /prediccion/patologias/{id}/desactivar — Desactivar patología

**RBAC**: D sobre recurso `patologias` (id=18)  
**Respuesta exitosa**: 200

```bash
curl -s -X PATCH http://localhost:8000/prediccion/patologias/15/desactivar \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Respuesta esperada (200)**: objeto `PatologiaM04Response` con `es_activo: false`.

**Errores posibles**:

| FA | HTTP | code | Condición |
|----|------|------|-----------|
| FA-07 | 409 | `PATOLOGIA_EN_USO_POR_MODELO` | Modelo activo usa la patología (E3) |
| FA-08 | 409 | `PATOLOGIA_EN_USO_POR_MODELO` | Patología base con modelo entrenado |
| — | 404 | `PATOLOGIA_NO_ENCONTRADA` | ID no existe |

---

## Verificación de datos en BD

```bash
# Verificar patologías base insertadas
# (via MCP postgres)
SELECT id_patologia, nombre, es_base, es_activo, version_catalogo
FROM modulo9.patologias WHERE es_base = true ORDER BY id_patologia;

# Verificar variables asociadas
SELECT p.nombre, va.nombre AS variable
FROM modulo9.patologias p
JOIN modulo4.patologias_variables_sensoricas pvs ON pvs.id_patologia = p.id_patologia
JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = pvs.id_variable_ambiental
WHERE p.es_base = true ORDER BY p.id_patologia, pvs.id_variable_ambiental;

# Verificar historial
SELECT * FROM modulo4.historial_catalogo_patologias ORDER BY timestamp_cambio DESC LIMIT 5;

# Verificar auditoría
SELECT tipo_evento, fecha_evento, id_referencia, resultado_operacion
FROM modulo4.eventos_auditoria_m04 ORDER BY fecha_evento DESC LIMIT 5;
```
