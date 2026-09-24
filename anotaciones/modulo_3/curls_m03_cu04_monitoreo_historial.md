# CURLs — M03 CU04 — Monitorear y consultar telemetría (RF-58, RF-59)

Base URL local: `http://localhost:8000`  
Auth: `Authorization: Bearer <jwt>`

---

## RF-58 — Dashboard de monitoreo en tiempo real

### 1. Dashboard completo (todas las unidades del usuario)

```bash
curl -s -X GET "http://localhost:8000/iot/monitoreo/dashboard" \
  -H "Authorization: Bearer <jwt>" | python -m json.tool
```

**Respuesta esperada 200:**
```json
{
  "total": 12,
  "pagina": 1,
  "por_pagina": 50,
  "resumen_unidades": [
    {
      "id_infraestructura": 1,
      "nombre_infraestructura": "Galpón A",
      "id_finca": 1,
      "nombre_finca": "Finca El Pinar",
      "total_sensores": 4,
      "sensores_online": 3,
      "sensores_sin_senal": 1,
      "sensores_con_error": 0,
      "estado_general": "AMARILLO",
      "alertas_activas_count": 2,
      "ultimo_dato_recibido": "2026-07-06T23:59:00Z"
    }
  ],
  "sensores": [
    {
      "id_sensor": 101,
      "id_dispositivo_iot": 5,
      "nombre_sensor": "Sensor Temp A1",
      "tipo_variable": "TEMPERATURA_AMBIENTAL",
      "categoria_variable": "AMBIENTAL",
      "ultimo_valor": "25.3000",
      "ultima_unidad": "°C",
      "ultimo_timestamp_captura": "2026-07-06T23:59:00Z",
      "estado_semaforo": "VERDE",
      "estado_calidad": "LECTURA_VALIDA",
      "estado_conectividad": "ACTIVO",
      "tiempo_sin_reporte_min": 0,
      "dato_desactualizado": false,
      "id_alerta": null,
      "severidad_alerta": null,
      "tendencia": "→",
      "id_infraestructura": 1,
      "nombre_infraestructura": "Galpón A",
      "id_finca": 1,
      "nombre_finca": "Finca El Pinar",
      "nivel_bateria_pct": null,
      "calidad_senal_rssi": null,
      "calidad_senal_snr": null
    }
  ]
}
```

**Errores:**
- `401 TOKEN_INVALIDO` — JWT ausente o expirado (FA-01)
- `403 PERMISO_DENEGADO` — rol sin permiso sobre recurso 33

---

### 2. Dashboard filtrado por unidad productiva

```bash
curl -s -X GET "http://localhost:8000/iot/monitoreo/dashboard/1?pagina=1&por_pagina=50" \
  -H "Authorization: Bearer <jwt>" | python -m json.tool
```

**Paginación con más de 50 sensores (FA-07, CA-17):**
```bash
# Página 2 de sensores de la unidad
curl -s "http://localhost:8000/iot/monitoreo/dashboard/1?pagina=2&por_pagina=50" \
  -H "Authorization: Bearer <jwt>"
```

**Nota:** `por_pagina` máximo es 50 — el sistema segmenta automáticamente para cumplir FA-07.

---

### 3. Dashboard — Ingeniero de Campo (incluye campos técnicos)

Con JWT de Ingeniero de Campo (id_rol=4), la respuesta incluye:
```json
{
  "nivel_bateria_pct": "87.50",
  "calidad_senal_rssi": "-72.00",
  "calidad_senal_snr": "9.50"
}
```

Con JWT de Productor (id_rol=2), estos campos son `null` (CA-8).

---

## RF-59 — Historial de lecturas

### 4. Consulta básica por rango de fechas y variable

```bash
curl -s -X GET "http://localhost:8000/iot/monitoreo/historial?\
fecha_inicio=2026-07-01&fecha_fin=2026-07-06&tipo_variable=TEMPERATURA_AMBIENTAL" \
  -H "Authorization: Bearer <jwt>" | python -m json.tool
```

**Respuesta esperada 200:**
```json
{
  "total": 288,
  "pagina": 1,
  "por_pagina": 100,
  "paginas_totales": 3,
  "filtros_aplicados": {
    "fecha_inicio": "2026-07-01",
    "fecha_fin": "2026-07-06",
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "sensor_id": null,
    "estado_dato": null,
    "origen_dato": null,
    "incluir_alertas": false
  },
  "rango_real_datos": {
    "primer_timestamp": "2026-07-01T00:00:05Z",
    "ultimo_timestamp": "2026-07-06T23:59:55Z"
  },
  "items": [
    {
      "id_telemetria": 5001,
      "id_sensor": 101,
      "nombre_sensor": "Sensor Temp A1",
      "id_variable": 1,
      "tipo_variable": "TEMPERATURA_AMBIENTAL",
      "categoria_variable": "AMBIENTAL",
      "valor": "25.3000",
      "valor_ajustado": "25.1500",
      "unidad_medida": "°C",
      "timestamp_captura": "2026-07-06T23:59:55Z",
      "estado_calidad": "LECTURA_VALIDA",
      "estado_semaforo_historico": "GRIS",
      "origen_dato": "TIEMPO_REAL",
      "id_infraestructura": 1,
      "infraestructura": "Galpón A",
      "finca": "Finca El Pinar",
      "id_activo_biologico": 55,
      "especie": "Tilapia Roja",
      "id_especie": 39,
      "id_alerta": null,
      "id_umbral_ambiental": 39,
      "valor_min_umbral": "18.00",
      "valor_max_umbral": "27.00",
      "version_umbral": "2026-09-10T12:00:00Z"
    }
  ],
  "estadisticas": [
    {
      "tipo_variable": "TEMPERATURA_AMBIENTAL",
      "valor_minimo": "18.2000",
      "valor_maximo": "31.7000",
      "valor_promedio": "24.8500",
      "total_lecturas": 288,
      "pct_dentro_rango": null,
      "pct_fuera_rango": null,
      "total_alertas_en_periodo": 0
    }
  ]
}
```

**Nota (INC-M09-107-G32 / #298):** `estado_semaforo_historico` ahora se calcula contra el
umbral RF-17 activo de la especie/variable de la lectura (`id_umbral_ambiental`,
`valor_min_umbral`, `valor_max_umbral`, `version_umbral` identifican qué configuración se usó).
Sigue en `"GRIS"` cuando no se pudo resolver la especie de la lectura (sin
`vinculaciones_lecturas`/`activos_biologicos` asociado) o no existe un umbral activo para esa
combinación especie+variable. M09 aún no versiona umbrales por vigencia temporal (RF-59
Restricción 16): se usa el umbral activo actual, no el vigente histórico en `timestamp_captura`.

---

### 5. Consulta con múltiples filtros y datos de buffer

```bash
curl -s "http://localhost:8000/iot/monitoreo/historial?\
fecha_inicio=2026-07-01&fecha_fin=2026-07-06\
&sensor_id=101&estado_dato=LECTURA_VALIDA\
&origen_dato=BUFFER_LOCAL&orden=ASC&pagina=1&por_pagina=50" \
  -H "Authorization: Bearer <jwt>"
```

---

### 6. Consulta con alertas correlacionadas

```bash
curl -s "http://localhost:8000/iot/monitoreo/historial?\
fecha_inicio=2026-07-01&fecha_fin=2026-07-06\
&tipo_variable=TEMPERATURA_AMBIENTAL&incluir_alertas=true" \
  -H "Authorization: Bearer <jwt>"
```

Las lecturas que tienen una alerta asociada incluirán `id_alerta` no nulo.

---

### 7. Error — rango > 90 días sin filtros adicionales (FA-09, CA-12)

```bash
curl -s "http://localhost:8000/iot/monitoreo/historial?\
fecha_inicio=2026-01-01&fecha_fin=2026-07-06" \
  -H "Authorization: Bearer <jwt>"
```

**Respuesta esperada 422:**
```json
{
  "error_code": "RANGO_MAXIMO_EXCEDIDO",
  "message": "El rango máximo sin filtros adicionales es 90 días. Agregue al menos un filtro de variable, sensor, unidad productiva o especie.",
  "fields": [],
  "timestamp": "..."
}
```

---

### 8. Error — fecha_fin en el futuro

```bash
curl -s "http://localhost:8000/iot/monitoreo/historial?\
fecha_inicio=2026-07-01&fecha_fin=2026-12-31\
&tipo_variable=TEMPERATURA_AMBIENTAL" \
  -H "Authorization: Bearer <jwt>"
```

**Respuesta esperada 400:**
```json
{
  "error_code": "FECHA_FIN_FUTURA",
  "message": "fecha_fin no puede ser posterior a la fecha actual.",
  "fields": [{"field": "fecha_fin"}]
}
```

---

### 9. Exportar historial — stub M08 (503)

```bash
curl -s "http://localhost:8000/iot/monitoreo/historial/exportar?\
formato=PDF&fecha_inicio=2026-07-01&fecha_fin=2026-07-06\
&tipo_variable=TEMPERATURA_AMBIENTAL" \
  -H "Authorization: Bearer <jwt>"
```

**Respuesta esperada 503:**
```json
{
  "error_code": "M08_NO_DISPONIBLE",
  "message": "El módulo de exportación (M08) no está disponible en este entorno. Reintente más tarde.",
  "fields": []
}
```

---

### 10. Error — exportar sin filtros activos (FA-11)

```bash
curl -s "http://localhost:8000/iot/monitoreo/historial/exportar?\
formato=PDF&fecha_inicio=2026-07-01&fecha_fin=2026-07-06" \
  -H "Authorization: Bearer <jwt>"
```

**Respuesta esperada 400:**
```json
{
  "error_code": "EXPORTAR_SIN_FILTROS",
  "message": "Debe aplicar al menos un filtro adicional antes de exportar.",
  "fields": []
}
```

---

## Referencias de FA

| FA | Endpoint | Comportamiento |
|----|----------|----------------|
| FA-01 | dashboard, historial | 403 si sin permisos RBAC |
| FA-07 | dashboard | por_pagina max=50, paginación obligatoria |
| FA-08 | historial | 400 COMBINACION_FILTROS_INVALIDA |
| FA-09 | historial | 422 RANGO_MAXIMO_EXCEDIDO (>90 días sin filtros) |
| FA-10 | historial | 422 VOLUMEN_EXCESIVO (>10.000 registros) |
| FA-11 | historial/exportar | 400 EXPORTAR_SIN_FILTROS |
| FA-13 | historial | semáforo GRIS si no hay especie resuelta o umbral RF-17 activo (INC-M09-107-G32) |
