# CURLs — M02 CU12: Consultar Indicadores y Exponer Datos (RF-50, RF-51)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa.

Recurso RBAC: 29 (`activos_biologicos`) | Acción: 2 (R — Leer)
Actores: Administrador, Productor, Veterinario, Ingeniero de campo

---

## GET /activos-biologicos/{id_activo}/indicadores

Calcula y expone indicadores zootécnicos on-demand a partir de eventos registrados
(RF-51). El cálculo siempre es fresco desde las tablas de eventos.

Query params opcionales:
- `fecha_inicio` / `fecha_fin`: formato `YYYY-MM-DD` — limitan el período de cálculo
- `tipo_indicador`: `CRECIMIENTO` | `PRODUCCION` | `SANITARIO` | `EFICIENCIA` | `TODOS` (default)

---

### Flujo A — Todos los indicadores (activo INDIVIDUAL con mediciones de peso)

```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/indicadores" \
  -H "Authorization: Bearer <TOKEN>"
```

**Respuesta esperada (200 OK):**
```json
{
  "id_activo_biologico": 1,
  "tipo_activo": "INDIVIDUAL",
  "indicadores": [
    {
      "tipo": "ganancia_peso",
      "valor": 0.2778,
      "unidad": "kg/dia",
      "periodo_inicio": "2024-01-01",
      "periodo_fin": "2024-04-01",
      "variables_usadas": {
        "peso_inicial_kg": 260.0,
        "peso_final_kg": 285.0,
        "dias": 90,
        "total_mediciones": 2
      },
      "fecha_calculo": "2026-06-29T12:00:00Z",
      "disponible": true
    },
    {
      "tipo": "produccion_promedio",
      "valor": null,
      "unidad": "unidades/dia",
      "periodo_inicio": null,
      "periodo_fin": null,
      "variables_usadas": {"registros_disponibles": 0},
      "fecha_calculo": "2026-06-29T12:00:00Z",
      "disponible": false
    },
    {
      "tipo": "tasa_morbilidad",
      "valor": null,
      "unidad": "%",
      "periodo_inicio": null,
      "periodo_fin": null,
      "variables_usadas": {},
      "fecha_calculo": "2026-06-29T12:00:00Z",
      "disponible": false
    },
    {
      "tipo": "tasa_mortalidad",
      "valor": null,
      "unidad": "%",
      "periodo_inicio": null,
      "periodo_fin": null,
      "variables_usadas": {},
      "fecha_calculo": "2026-06-29T12:00:00Z",
      "disponible": false
    },
    {
      "tipo": "conversion_alimenticia",
      "valor": null,
      "unidad": "kg_alimento/kg_ganancia",
      "periodo_inicio": null,
      "periodo_fin": null,
      "variables_usadas": {},
      "fecha_calculo": "2026-06-29T12:00:00Z",
      "disponible": false
    }
  ],
  "advertencias": [
    "DATOS_INSUFICIENTES: no hay eventos productivos en el período solicitado.",
    "NO_APLICA_INDIVIDUAL: tasa_morbilidad solo aplica a activos POBLACIONALES.",
    "NO_APLICA_INDIVIDUAL: tasa_mortalidad solo aplica a activos POBLACIONALES.",
    "REQUIERE_M05: El indicador conversion_alimenticia requiere datos de consumo de alimento del módulo M05, que aún no está implementado."
  ]
}
```

---

### Flujo B — Solo indicador de crecimiento con rango de fechas

```bash
curl -X GET "http://localhost:8000/activos-biologicos/5/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2024-01-01&fecha_fin=2024-12-31" \
  -H "Authorization: Bearer <TOKEN>"
```

**Respuesta esperada (200 OK):**
```json
{
  "id_activo_biologico": 5,
  "tipo_activo": "INDIVIDUAL",
  "indicadores": [
    {
      "tipo": "ganancia_peso",
      "valor": 0.0421,
      "unidad": "kg/dia",
      "periodo_inicio": "2024-01-15",
      "periodo_fin": "2024-06-01",
      "variables_usadas": {
        "peso_inicial_kg": 1.2,
        "peso_final_kg": 8.7,
        "dias": 138,
        "total_mediciones": 5
      },
      "fecha_calculo": "2026-06-29T12:00:00Z",
      "disponible": true
    }
  ],
  "advertencias": []
}
```

---

### Errores posibles

#### E-01 — Activo inexistente (FA-01)
```bash
curl -X GET "http://localhost:8000/activos-biologicos/9999/indicadores" \
  -H "Authorization: Bearer <TOKEN>"
```
**HTTP 404:**
```json
{
  "code": "ACTIVO_NO_ENCONTRADO",
  "message": "El activo biológico con ID 9999 no existe en los registros del sistema."
}
```

#### E-02 — Fecha inicio posterior a fecha fin (FA-02)
```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/indicadores?fecha_inicio=2024-12-31&fecha_fin=2024-01-01" \
  -H "Authorization: Bearer <TOKEN>"
```
**HTTP 400:**
```json
{
  "code": "PARAMETROS_INVALIDOS",
  "message": "La fecha de inicio (2024-12-31) no puede ser posterior a la fecha de fin (2024-01-01)."
}
```

#### E-03 — Tipo de indicador inválido
```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/indicadores?tipo_indicador=INVALIDO" \
  -H "Authorization: Bearer <TOKEN>"
```
**HTTP 400:**
```json
{
  "code": "PARAMETROS_INVALIDOS",
  "message": "Tipo de indicador inválido. Valores permitidos: CRECIMIENTO, EFICIENCIA, PRODUCCION, SANITARIO, TODOS."
}
```

#### E-04 — Sin permisos (FA-05)
**HTTP 403:** Lanzado automáticamente por `require_permission(29, 2)` si el rol no tiene permiso.

---

## GET /activos-biologicos/{id_activo}/datos-consolidados

Expone datos estructurados del activo para consumo por módulos analíticos internos
(M03, M04, M06, M08) en formato JSON estandarizado (RF-50).

Query params opcionales:
- `tipo_dato`: `eventos` | `fases` | `estado` | `metricas` | `todos` (default)
- `fecha_inicio` / `fecha_fin`: filtro temporal sobre eventos (solo aplica a `tipo_dato=eventos` o `todos`)
- `pagina` / `page_size`: paginación (default: 1 / 20, máximo page_size: 100)

---

### Flujo A — Datos completos del activo

```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/datos-consolidados" \
  -H "Authorization: Bearer <TOKEN>"
```

**Respuesta esperada (200 OK):**
```json
{
  "id_activo_biologico": 1,
  "identificador": "BOV-001",
  "tipo_activo": "INDIVIDUAL",
  "especie": "Bovino",
  "estado_actual": "ACTIVO",
  "infraestructura_asociada": "Potrero Norte",
  "fase_productiva_activa": "Engorde",
  "historial_eventos": [
    {
      "categoria": "CRECIMIENTO",
      "fecha": "2024-04-01T00:00:00+00:00",
      "detalle_1": "PESO",
      "detalle_2": "285 kg",
      "observacion": null,
      "usuario": "Juan Pérez"
    }
  ],
  "historial_fases": [
    {
      "categoria": "FASE_PRODUCTIVA",
      "fecha": "2024-01-01T00:00:00+00:00",
      "nombre_fase": "Engorde",
      "estado": "Activa",
      "observacion": "duracion_dias=120, es_activa=true, fecha_finalizacion=NULL",
      "usuario": "Admin"
    }
  ],
  "historico_estados": [],
  "metricas_actuales": {
    "peso_actual": 285.0,
    "unidad_peso": "kg",
    "fecha_ultimo_peso": "2024-04-01",
    "cantidad_actual": null,
    "biomasa_total": null,
    "indicadores_historicos": [
      {
        "tipo": "ganancia_peso",
        "fecha_inicio": "2024-01-01",
        "fecha_fin": "2024-04-01",
        "resultado": {"gpd_kg": 0.278, "dias": 90, "peso_inicial_kg": 260.0, "peso_final_kg": 285.0}
      }
    ]
  },
  "total_registros": 2,
  "pagina_actual": 1,
  "total_paginas": 1,
  "registros_por_pagina": 20,
  "fecha_generacion": "2026-06-29T12:00:00Z"
}
```

---

### Flujo B — Solo métricas actuales

```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/datos-consolidados?tipo_dato=metricas" \
  -H "Authorization: Bearer <TOKEN>"
```

**Respuesta esperada (200 OK):**
Mismo formato pero `historial_eventos`, `historial_fases` y `historico_estados` vacíos.
`metricas_actuales` contiene peso actual, cantidad actual e indicadores históricos almacenados.

---

### Flujo C — Filtrar solo eventos en un período

```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/datos-consolidados?tipo_dato=eventos&fecha_inicio=2024-01-01&fecha_fin=2024-06-30" \
  -H "Authorization: Bearer <TOKEN>"
```

---

### Flujo D — Paginación de histórico completo

```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/datos-consolidados?tipo_dato=todos&pagina=2&page_size=10" \
  -H "Authorization: Bearer <TOKEN>"
```

---

### Errores posibles

#### E-01 — Activo inexistente (FA-01)
```bash
curl -X GET "http://localhost:8000/activos-biologicos/9999/datos-consolidados" \
  -H "Authorization: Bearer <TOKEN>"
```
**HTTP 404:**
```json
{
  "code": "ACTIVO_NO_ENCONTRADO",
  "message": "El activo biológico con ID 9999 no existe en los registros del sistema."
}
```

#### E-02 — Tipo de dato inválido
```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/datos-consolidados?tipo_dato=invalido" \
  -H "Authorization: Bearer <TOKEN>"
```
**HTTP 400:**
```json
{
  "code": "PARAMETROS_INVALIDOS",
  "message": "Tipo de dato inválido. Valores permitidos: estado, eventos, fases, metricas, todos."
}
```

#### E-03 — Rango de fechas inválido
```bash
curl -X GET "http://localhost:8000/activos-biologicos/1/datos-consolidados?fecha_inicio=2024-13-01" \
  -H "Authorization: Bearer <TOKEN>"
```
**HTTP 400:**
```json
{
  "code": "PARAMETROS_INVALIDOS",
  "message": "Parámetro inválido: Invalid isoformat string: '2024-13-01'"
}
```

#### E-04 — Sin permisos (FA-05)
**HTTP 403:** Lanzado automáticamente por `require_permission(29, 2)` si el rol no tiene permiso.
