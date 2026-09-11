# CURLs — M02 CU10: Gestionar Transferencias y Consultar Historial (RF-46, RF-47, RF-48)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT de sesión activa.

---

## Autenticación

```bash
curl -X POST http://localhost:8000/sesiones/ \
  -H "Content-Type: application/json" \
  -d '{"correo_electronico":"admin@pecuaria.co","contrasena":"Admin1234!"}'
```

Extraer el campo `token` de la respuesta.

---

## CU10A — RF-46: Consultar historial consolidado del activo

### GET /activos-biologicos/{id_activo}/historial — Sin filtros (paginación por defecto)

```bash
curl http://localhost:8000/activos-biologicos/5/historial \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_activo_biologico": 5,
  "total_registros": 12,
  "pagina_actual": 1,
  "total_paginas": 1,
  "registros_por_pagina": 20,
  "registros": [
    {
      "categoria": "TRANSFERENCIA",
      "fecha_evento": "2024-04-15T06:00:00Z",
      "descripcion": "",
      "detalle_especifico": {
        "infraestructura_origen": "Canal-Trucha-01",
        "infraestructura_destino": "Estanque-02"
      },
      "usuario_responsable": "Carlos Rodríguez Pérez",
      "modulo_origen": "modulo2"
    },
    {
      "categoria": "ESTADO",
      "fecha_evento": "2026-05-02T00:00:00Z",
      "descripcion": "Cambio de estado: ACTIVO",
      "detalle_especifico": {},
      "usuario_responsable": "Carlos Rodríguez Pérez",
      "modulo_origen": "modulo2"
    }
  ]
}
```

### GET /activos-biologicos/{id_activo}/historial — Con filtro por categoría

```bash
curl "http://localhost:8000/activos-biologicos/5/historial?categoria_evento=TRANSFERENCIA" \
  -H "Authorization: Bearer <TOKEN>"
```

Categorías válidas: `ESTADO`, `FASE_PRODUCTIVA`, `EVENTO_BIOLOGICO`, `CRECIMIENTO`, `SANITARIO`, `REPRODUCTIVO`, `PRODUCTIVO`, `BAJA`, `TRANSFERENCIA`

### GET /activos-biologicos/{id_activo}/historial — Con filtro por rango de fechas

```bash
curl "http://localhost:8000/activos-biologicos/5/historial?fecha_inicio=2026-01-01&fecha_fin=2026-06-30&pagina=1&page_size=10" \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `400 PARAMETROS_INVALIDOS` — fecha_inicio posterior a fecha_fin (FA-02)
- `404 ACTIVO_NO_ENCONTRADO` — el activo no existe (FA-01)
- `401 TOKEN_REQUERIDO` — sin token o token inválido
- `403` — rol sin permiso de lectura sobre activos biológicos

---

## CU10B — RF-47: Consultar ficha integral del activo

### GET /activos-biologicos/{id_activo}/ficha-integral

```bash
curl http://localhost:8000/activos-biologicos/5/ficha-integral \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "id_activo_biologico": 5,
  "identificador": "BOV-0852",
  "tipo": "INDIVIDUAL",
  "especie": "Tilapia Roja",
  "fecha_registro": "2026-05-02",
  "dias_en_sistema": 58,
  "estado_actual": "ACTIVO",
  "infraestructura_asociada": "Estanque-01",
  "fase_productiva_activa": "Ciclo completo tilapia 2025-A",
  "raza": "Brahman",
  "sexo": "Macho",
  "fecha_nacimiento": "2021-09-01",
  "peso_actual": "2.50",
  "unidad_peso": "kg",
  "fecha_ultimo_peso": "2026-06-28",
  "cantidad_actual": null,
  "biomasa_total": null,
  "densidad": null,
  "eventos_sanitarios": [
    {
      "tipo_evento": "SANITARIO",
      "medicamento": null,
      "diagnostico": "Evaluación estado corporal",
      "fecha": "2024-04-16T10:00:00+00:00"
    }
  ],
  "eventos_productivos": [],
  "eventos_crecimiento": [
    {"variable": "PESO", "valor": "2.50", "unidad": "kg", "fecha": "2026-06-28T14:00:00+00:00"}
  ],
  "eventos_reproductivos": [],
  "indicadores": [],
  "advertencias": []
}
```

Comportamiento especial:
- Si el activo está en estado `CERRADO` o `BAJA` pero tiene fase productiva activa, `advertencias` contendrá un mensaje de inconsistencia detectada.
- Si la vista no devuelve datos (activo sin ciclo activo), se retornan las secciones vacías con `advertencias: ["No se pudo cargar la información completa del activo."]`.

Errores posibles:
- `404 ACTIVO_NO_ENCONTRADO` — el activo no existe (FA-01)
- `401 TOKEN_REQUERIDO` — sin token o token inválido
- `403` — rol sin permiso de lectura sobre activos biológicos

---

## CU10C — RF-48: Registrar transferencia interna

### GET /activos-biologicos/{id_activo}/transferencias/disponibles — Listar infraestructuras destino compatibles

```bash
curl http://localhost:8000/activos-biologicos/5/transferencias/disponibles \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
[
  {"id_infraestructura": 1, "nombre": "Estanque-01", "tipo": "estanque", "capacidad_maxima": null, "id_especie": null},
  {"id_infraestructura": 3, "nombre": "Alevinera-01", "tipo": "estanque", "capacidad_maxima": null, "id_especie": null}
]
```

Nota: excluye la infraestructura actual del activo. Incluye sólo infraestructuras activas.

### POST /activos-biologicos/{id_activo}/transferencias — Registrar transferencia

```bash
curl -X POST http://localhost:8000/activos-biologicos/5/transferencias \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "infraestructura_origen_id": 2,
    "infraestructura_destino_id": 1,
    "fecha_transferencia": "2026-06-29",
    "motivo_transferencia": "Traslado por sobrepoblación en Estanque-02"
  }'
```

Respuesta esperada `201`:
```json
{
  "id_movimiento": 17,
  "id_activo_biologico": 5,
  "infraestructura_origen": "Estanque-02",
  "infraestructura_destino": "Estanque-01",
  "fecha_transferencia": "2026-06-29T00:00:00Z",
  "motivo_transferencia": "Traslado por sobrepoblación en Estanque-02",
  "mensaje": "Transferencia registrada exitosamente. El activo fue transferido a Estanque-01 en fecha 2026-06-29."
}
```

Errores posibles:
- `404 ACTIVO_NO_ENCONTRADO` — el activo no existe (FA-01)
- `409 ACTIVO_NO_ACTIVO` — el activo no está en estado ACTIVO (FA-03)
- `409 TRANSFERENCIA_CONCURRENTE` — hay una transferencia en progreso para el mismo activo (FA-07)
- `422 SIN_INFRAESTRUCTURA_ORIGEN` — el activo no tiene asociación activa en historial (FA-04)
- `422 INFRAESTRUCTURA_ORIGEN_INCORRECTA` — la infra origen del DTO no coincide con la del activo (FA-04)
- `422 INFRAESTRUCTURA_DESTINO_INVALIDA` — la infra destino no existe o está inactiva (FA-05)
- `422 DESTINO_IGUAL_ORIGEN` — origen y destino son la misma infraestructura (FA-06)
- `422 INCOMPATIBILIDAD_ESPECIE` — la infra destino no está habilitada para la especie del activo (C1)
- `422 CAPACIDAD_EXCEDIDA` — la infra destino no tiene capacidad suficiente (C3)
- `422 FECHA_FUTURA` — fecha_transferencia es posterior al día actual
- `401 TOKEN_REQUERIDO` — sin token o token inválido
- `403` — rol sin permiso de ejecución sobre activos biológicos (solo admin y productor)
