# CURLs — M05 CU04: Reporte de Gastos e Historial de Suministros (RF-77, RF-81)

Base URL (local, sin proxy): `http://localhost:8000`
(En producción el proxy antepone `/api`.)

Autenticación: header `Authorization: Bearer <TOKEN>` obtenido de `POST /sesiones/`
(`{"correo_electronico": "...", "contrasena": "..."}`). Sesión expira a los 30 min de
inactividad — reloguear si aparece `401 SESION_EXPIRADA_INACTIVIDAD`.

Roles en los ejemplos: `<ADMIN>` (1), `<PROD>` (2), `<VET>` (3), `<ING>` (4, sin permiso),
`<CONT>` (5), `<GESTOR>` (7, Gestor de Granja), `<REVFISCAL>` (8, Revisor Fiscal).

RBAC:
- recurso `reporte_gastos_suministros` = **51** — E=5 (generar) → Admin/Productor; R=2 (consultar) → + Contador.
- recurso `historial_suministros` = **52** — R=2, E=5 → Admin/Productor/Veterinario/Contador/Gestor de Granja/Revisor Fiscal.
- recurso `administracion_batch_reportes_gastos` = **53** — E=5, R=2 → Admin/Productor.
- recurso `administracion_batch_historial_suministros` = **54** — E=5, R=2 → solo Admin.

Todos los escenarios de este documento fueron ejecutados contra un servidor local real
(`uvicorn main:app`) y verificados end-to-end el 2026-07-31, incluyendo la transición de
estado de los trabajos async en BD (`PENDIENTE → EN_PROCESO → COMPLETADO`/`FALLIDO`).

---

## RF-77 — Reporte de Gastos Acumulados

### Flujo principal — Generación síncrona (activo individual)

```bash
curl -X POST http://localhost:8000/suministros/reportes-gastos \
  -H "Authorization: Bearer <PROD>" -H "Content-Type: application/json" \
  -d '{
    "fecha_inicio_reporte": "2026-01-01",
    "fecha_fin_reporte": "2026-07-31",
    "activo_biologico_id": 57,
    "tipo_periodo": "MENSUAL"
  }'
```

Respuesta `200`:
```json
{
  "id_reporte_gasto_acumulado": 7, "id_activo_biologico": 57,
  "fecha_inicio": "2026-01-01", "fecha_fin": "2026-07-31", "tipo_periodo": "MENSUAL",
  "gasto_total_acumulado": "10.0000",
  "desglose_categorias": [{"categoria": "ALIMENTACION", "subtotal": "10.0000", "num_registros": 1, "porcentaje": "100"}],
  "desglose_temporal": [{"etiqueta": "2026-07", "fecha_inicio": "2026-07-31", "fecha_fin": "2026-07-31", "monto": "10.0000"}],
  "registros_sin_costo": [],
  "tendencia": {
    "gasto_periodo_actual": "10.0000", "gasto_periodo_anterior": "0",
    "variacion_porcentual": null, "estado": "SIN_BASE_COMPARATIVA",
    "nota": "No existen gastos registrados en el período anterior equivalente. No es posible calcular variación porcentual."
  },
  "fecha_generacion": "2026-07-31T05:18:54Z"
}
```

### E7 — Activo sin ciclo productivo registrado

```bash
curl -X POST http://localhost:8000/suministros/reportes-gastos \
  -H "Authorization: Bearer <PROD>" -H "Content-Type: application/json" \
  -d '{"fecha_inicio_reporte":"2026-05-01","fecha_fin_reporte":"2026-07-31","activo_biologico_id":1}'
```
`422 ACTIVO_SIN_CICLO` — el activo no tiene `fecha_inicio_ciclo` definida (dato real del
entorno dev; distinto de tener una fase abierta en `gestiones_fases`, que es un concepto
separado usado por RF-37/38).

### E3 — Fecha de inicio anterior al ciclo productivo

```bash
curl -X POST http://localhost:8000/suministros/reportes-gastos \
  -H "Authorization: Bearer <PROD>" -H "Content-Type: application/json" \
  -d '{"fecha_inicio_reporte":"2024-01-01","fecha_fin_reporte":"2026-07-31","activo_biologico_id":57}'
```
`400 FECHA_INICIO_ANTERIOR_CICLO`.

### RBAC — rol sin permiso de generación

```bash
curl -X POST http://localhost:8000/suministros/reportes-gastos \
  -H "Authorization: Bearer <VET>" -H "Content-Type: application/json" \
  -d '{"fecha_inicio_reporte":"2026-01-01","fecha_fin_reporte":"2026-07-31","activo_biologico_id":57}'
```
`403 ACCESO_DENEGADO`.

### Flujo alterno — Generación asíncrona (reporte agregado por infraestructura, >6 meses)

```bash
curl -X POST http://localhost:8000/suministros/reportes-gastos \
  -H "Authorization: Bearer <PROD>" -H "Content-Type: application/json" \
  -d '{
    "fecha_inicio_reporte": "2025-01-01",
    "fecha_fin_reporte": "2026-07-31",
    "id_infraestructura": 2,
    "tipo_periodo": "MENSUAL"
  }'
```
`202 Accepted`:
```json
{"id_cola": 2, "estado": "PENDIENTE", "fecha_solicitud": "...",
 "mensaje": "El reporte solicitado se generará de forma asíncrona (id_cola=2). Consulte GET .../trabajos/{id_cola}..."}
```

Poll (el poller corre cada `intervalo_poll_segundos`, 15s por defecto):
```bash
curl http://localhost:8000/suministros/reportes-gastos/trabajos/2 -H "Authorization: Bearer <PROD>"
```
`200`, `estado: COMPLETADO`, con el `reporte` completo (desglose/tendencia reconstruidos desde
`resultado_json` — ver Gap 9 del doc de gaps, corregido tras encontrar este bug en esta misma
verificación).

### Panel admin (recurso 53)

```bash
curl -X POST http://localhost:8000/suministros/reportes-gastos/batch/ejecutar -H "Authorization: Bearer <ADMIN>"
curl http://localhost:8000/suministros/reportes-gastos/batch/cola -H "Authorization: Bearer <ADMIN>"
curl http://localhost:8000/suministros/reportes-gastos/batch/fallos -H "Authorization: Bearer <ADMIN>"
```

---

## RF-81 — Historial/Trazabilidad de Suministros

### Flujo principal — Consulta síncrona (nivel 1)

```bash
curl "http://localhost:8000/suministros/historial?id_activo_biologico=1&fecha_inicio_filtro=2020-01-01&fecha_fin_filtro=2026-12-31" \
  -H "Authorization: Bearer <CONT>"
```
`200` con `items` (11 registros: 8 ALIMENTO + 3 MEDICAMENTO) y `resumen` con
`monto_total_filtrado`, `desglose_por_tipo_suministro`, `desglose_por_ciclo`,
`datos_actualizados_hasta`, `nivel_volumen: 1`.

### FA-04 — Restricción de alcance del Gestor de Granja

```bash
# Activo que NO registró el Gestor -> 403
curl "http://localhost:8000/suministros/historial?id_activo_biologico=1" -H "Authorization: Bearer <GESTOR>"
# 403 ACCESO_DENEGADO

# Activo que SÍ registró el Gestor -> 200, solo sus datos
curl "http://localhost:8000/suministros/historial?id_activo_biologico=57" -H "Authorization: Bearer <GESTOR>"
# 200, 1 registro (el que el propio Gestor registró vía RF-75)
```
Regla interina verificada: `activos_biologicos.id_usuario = usuario_actual.id_usuario`
(`AlcanceActivoM02Adapter`).

### Revisor Fiscal — lectura total sin restricción

```bash
curl "http://localhost:8000/suministros/historial?id_activo_biologico=1" -H "Authorization: Bearer <REVFISCAL>"
```
`200` — mismo resultado que Contador/Admin (sin restricción de alcance).

### RBAC — rol sin permiso (Ingeniero de Campo)

```bash
curl "http://localhost:8000/suministros/historial?id_activo_biologico=1" -H "Authorization: Bearer <ING>"
```
`403 ACCESO_DENEGADO`.

### Exportación síncrona CSV

```bash
curl -o historial.csv -D - "http://localhost:8000/suministros/historial/exportar?id_activo_biologico=1" \
  -H "Authorization: Bearer <CONT>"
```
`200`, `Content-Type: text/csv`, columnas:
`id_registro_suministro,tipo_suministro,descripcion,fecha_aplicacion,cantidad,unidad_medida,precio_unitario,costo_registro,origen_precio,nombre_activo,especie,nombre_ciclo,estado_ciclo`.

### Flujo alterno — Trabajo async: EXPORTACION

```bash
curl -X POST http://localhost:8000/suministros/historial/trabajos \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" \
  -d '{"tipo_trabajo":"EXPORTACION","id_activo_biologico":1}'
# 202 { "id_cola": 1, "tipo_trabajo": "EXPORTACION", "estado": "PENDIENTE", ... }

curl http://localhost:8000/suministros/historial/trabajos/1 -H "Authorization: Bearer <CONT>"
# 200, estado COMPLETADO, total_registros: 11 (tras el poller)

curl -D - http://localhost:8000/suministros/historial/trabajos/1/descargar -H "Authorization: Bearer <CONT>"
# 200, CSV completo (idéntico al de exportación síncrona)
```

### E10/FA-10 — Límite de exportaciones concurrentes (429)

5 solicitudes `EXPORTACION` en paralelo con `limite_concurrencia_exportaciones=3`:
```bash
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/suministros/historial/trabajos \
    -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" \
    -d '{"tipo_trabajo":"EXPORTACION","id_activo_biologico":1}' &
done; wait
```
Resultado verificado: exactamente 3 `202` y 2 `429 LIMITE_EXPORTACIONES_EXCEDIDO`
(`"Límite de exportaciones concurrentes alcanzado. Espere a que alguna exportación finalice antes de solicitar otra."`).

### Nivel de volumen 3/4 — Consulta requiere modo asíncrono

Verificado bajando temporalmente `umbral_nivel3` a 5 (config real: 10.000):
```bash
curl "http://localhost:8000/suministros/historial?id_activo_biologico=1" -H "Authorization: Bearer <CONT>"
# 422 CONSULTA_REQUIERE_MODO_ASINCRONO
# "El activo 1 tiene 11 registros históricos (Nivel 3), que supera el límite de
#  procesamiento síncrono. Solicite la consulta vía POST .../trabajos (tipo CONSULTA_PESADA)."

curl -X POST http://localhost:8000/suministros/historial/trabajos \
  -H "Authorization: Bearer <CONT>" -H "Content-Type: application/json" \
  -d '{"tipo_trabajo":"CONSULTA_PESADA","id_activo_biologico":1}'
# 202 -> tras el poller, estado COMPLETADO, total_registros: 11
```

### Panel admin (recurso 54, solo Admin)

```bash
curl -X POST http://localhost:8000/suministros/historial/batch/ejecutar -H "Authorization: Bearer <ADMIN>"
curl http://localhost:8000/suministros/historial/batch/cola -H "Authorization: Bearer <ADMIN>"
curl http://localhost:8000/suministros/historial/batch/fallos -H "Authorization: Bearer <ADMIN>"
```

---

## Notas de verificación

- **Bug real encontrado y corregido durante esta verificación**: `reporte_gastos_acumulados.id_activo_biologico`
  era `NOT NULL` en BD, lo que rompía el flujo async de reportes agregados (por infraestructura/especie,
  explícitamente soportado por RF-77). Corregido con `ALTER TABLE ... DROP NOT NULL` + fix del modelo ORM.
  Documentado como Gap 9 en `cu04_gaps_bd_rf77_rf81.md`.
- **Bug real encontrado y corregido**: el endpoint de estado de trabajo async de RF-77
  (`GET .../trabajos/{id_cola}`) solo devolvía el snapshot persistido (sin desglose/tendencia)
  en vez de reconstruir la respuesta completa desde `resultado_json`. Corregido agregando
  `ReporteGastoResponse.desde_snapshot_y_resultado_json`.
- Usuarios de prueba creados en BD dev para verificar RBAC/alcance: `gestor.granja.test@pecuaria.co`
  (id_usuario=30, rol 7) y `revisor.fiscal.test@pecuaria.co` (id_usuario=31, rol 8). Activo de
  prueba `id_activo_biologico=57` (`TEST-GESTOR-ACTIVO-1`), registrado por el usuario Gestor,
  usado para validar la restricción de alcance de forma positiva (no solo el rechazo).
- Todas las transiciones de trabajos (`cola_generacion_reportes_gastos`,
  `cola_trabajos_historial_suministros`) se verificaron vía MCP postgres: ningún trabajo quedó
  huérfano en `EN_PROCESO` al finalizar la sesión de pruebas.
