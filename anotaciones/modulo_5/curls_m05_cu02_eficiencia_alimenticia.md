# CURLs — M05 CU02: Calcular y Consultar Eficiencia Alimenticia (ICA, RF-74)

Base URL (local, sin proxy): `http://localhost:8000`
(En producción el proxy antepone `/api`.)

Autenticación: header `Authorization: Bearer <TOKEN>`.
Roles en los ejemplos: `<ADMIN>` (rol 1), `<PROD>` (rol 2), `<VET>` (rol 3), `<CONT>` (rol 5).

RBAC:
- recurso `eficiencia_alimenticia` = **49** — E=5 (calcular), R=2 (consultar) → Admin/Productor/Veterinario.
- recurso `administracion_batch_ica` = **50** — E=5 (ejecutar/interrumpir/reintentar), R=2 (panel) → Admin/Productor.

Fórmula (RF-74): `CA = Alimento Total Consumido (kg) / Ganancia de Peso Total (kg)`.
Clasificación: `<2.0` EXCELENTE · `2.0–3.5` ACEPTABLE · `3.5–5.0` BAJA · `>5.0` CRITICA (genera alerta).

---

## Flujo A — Calcular ICA (manual) · Admin/Productor/Veterinario

```bash
curl -X POST http://localhost:8000/suministros/eficiencia-alimenticia/calcular \
  -H "Authorization: Bearer <ADMIN>" -H "Content-Type: application/json" \
  -d '{ "id_activo_biologico": 1, "periodo_evaluacion": "MENSUAL" }'
```
`periodo_evaluacion` ∈ `SEMANAL` | `MENSUAL` | `POR_CICLO`.

Respuesta `200` (CALCULADO, clasificación CRITICA → se generó alerta):
```json
{
  "id_resultado_ica": 4, "id_activo_biologico": 1, "periodo_evaluacion": "MENSUAL",
  "fecha_inicio_periodo": "2026-07-01", "fecha_fin_periodo": "2026-07-30",
  "estado_resultado": "CALCULADO", "es_vigente": true, "intento": 1,
  "alimento_consumido_total_kg": "400.0000", "ganancia_peso_kg": "59.5000",
  "ca_calculado": "6.7226", "clasificacion_ca": "CRITICA", "data_quality_score": 100,
  "causa_no_calculo": null, "tipo_calculo": "MANUAL", "id_usuario": 1
}
```

Respuesta `200` (CA_NO_CALCULABLE — sin datos suficientes; **no es error**, se persiste con causa):
```json
{
  "estado_resultado": "CA_NO_CALCULABLE", "es_vigente": true,
  "ca_calculado": null, "clasificacion_ca": null,
  "causa_no_calculo": "SIN_REGISTROS_CONSUMO", "data_quality_score": 75, ...
}
```
Jerarquía de causa (mayor a menor): `SIN_PESO_INICIAL` > `SIN_PESO_FINAL` >
`SIN_REGISTROS_CONSUMO` > `POBLACION_INVALIDA` > `PESO_INVALIDO` > `PESO_SIN_VARIACION_POSITIVA`.

Notas:
- Peso desde RF-40 (`modulo2.eventos_crecimeinto`): INDIVIDUAL usa `valor_medicion`,
  POBLACIONAL usa `nuevo_peso_promedio`. Peso inicial/final = pesaje más reciente ≤ fecha del borde.
- Al reemplazar un vigente, el anterior queda como histórico (`es_vigente=false`).
- La auditoría la escribe un trigger de BD en `modulo5.auditorias_suministros`.

Errores posibles:
- `404 ACTIVO_NO_ENCONTRADO` — el activo no existe.
- `422 ACTIVO_NO_ACTIVO` — el activo no está en estado ACTIVO (E1).
- `422 CICLO_SIN_FECHA_INICIO` — POR_CICLO sobre un activo sin ciclo/fase abierta.
- `403 ACCESO_DENEGADO` — rol sin permiso E sobre recurso 49 (p.ej. `<CONT>`).
- `401 TOKEN_REQUERIDO` — falta el Bearer.

---

## Flujo B — Consultar ICA vigente · Admin/Productor/Veterinario

```bash
curl "http://localhost:8000/suministros/eficiencia-alimenticia/activos/1/vigente?periodo=MENSUAL" \
  -H "Authorization: Bearer <VET>"
```
Respuesta `200` (con resultado):
```json
{ "id_activo_biologico": 1, "periodo_evaluacion": "MENSUAL", "tiene_resultado": true,
  "mensaje": null, "resultado": { "ca_calculado": "6.7226", "clasificacion_ca": "CRITICA", ... } }
```
Respuesta `200` (sin resultado — FA-03, **no** es 404):
```json
{ "id_activo_biologico": 99, "periodo_evaluacion": "SEMANAL", "tiene_resultado": false,
  "mensaje": "No hay un resultado ICA vigente para el activo y período indicados.", "resultado": null }
```

## Flujo B — Consultar historial ICA · Admin/Productor/Veterinario

```bash
curl "http://localhost:8000/suministros/eficiencia-alimenticia/activos/1/historial" \
  -H "Authorization: Bearer <VET>"
# opcional: ?periodo=MENSUAL
```
Respuesta `200`: `{ "id_activo_biologico": 1, "total": 3, "items": [ ... ] }`
(incluye vigentes e históricos; el reemplazo deja el anterior con `es_vigente=false`).

Errores (ambas consultas): `401 TOKEN_REQUERIDO`, `403 ACCESO_DENEGADO` (rol sin R sobre recurso 49).

---

## Flujo C — Motor batch (panel de administración) · recurso 50

### Ejecutar / reactivar el batch · Admin/Productor
```bash
curl -X POST http://localhost:8000/suministros/eficiencia-alimenticia/batch/ejecutar \
  -H "Authorization: Bearer <ADMIN>" -H "Content-Type: application/json" \
  -d '{ "solo_cola": false }'
```
`solo_cola: true` reactiva únicamente la cola pendiente (FA-07/reactivación) sin barrer todos los activos.

Respuesta `200` (corrida finalizada):
```json
{ "id_ejecucion": 1, "estado": "COMPLETADO", "tipo_disparo": "MANUAL",
  "cantidad_activos_total": 10, "cantidad_activos_procesados": 10, "cantidad_fallidos": 0,
  "cantidad_activos_pendientes": 0, "num_workers": 1, "causa_interrupcion": null }
```
Comportamiento: calcula los 3 períodos por activo ACTIVO; prioriza CRITICA del vigente y
antigüedad de ciclo; si `count > limite` encola el excedente (`LIMITE_SUPERADO`); paraleliza si
`count > umbral_paralelizacion`; reintenta fallos técnicos con backoff y, agotados, registra
`CA_FALLO_PERSISTENTE`; si excede la ventana → `INTERRUMPIDO` + preserva la cola (`VENTANA_EXCEDIDA`).

Errores: `409 BATCH_EN_CURSO` (ya hay una corrida), `422 BATCH_DESACTIVADO`, `403 ACCESO_DENEGADO`.

### Interrumpir una corrida (FA-12) · Admin/Productor
```bash
curl -X POST http://localhost:8000/suministros/eficiencia-alimenticia/batch/1/interrumpir \
  -H "Authorization: Bearer <ADMIN>" -H "Content-Type: application/json" \
  -d '{ "motivo": "mantenimiento" }'
```
Respuesta `200`: ejecución con `estado="INTERRUMPIDO"`, `causa_interrupcion`, `hora_corte`.
Errores: `404 EJECUCION_NO_ENCONTRADA`, `422 BATCH_NO_EN_EJECUCION` (ya finalizada).

### Reintento manual de un activo (E5) · Admin/Productor
```bash
curl -X POST http://localhost:8000/suministros/eficiencia-alimenticia/batch/activos/1/reintentar \
  -H "Authorization: Bearer <ADMIN>"
```
Recalcula los 3 períodos (`tipo_calculo=REINTENTO_MANUAL`) y, si había un
`CA_FALLO_PERSISTENTE` abierto, lo marca resuelto. Respuesta `200`: `{ id_activo_biologico, total, items }`.

### Panel de estado · Admin/Productor
```bash
curl http://localhost:8000/suministros/eficiencia-alimenticia/batch/estado \
  -H "Authorization: Bearer <ADMIN>"
```
Respuesta `200`: lista de corridas recientes (`EstadoBatchResponse[]`, más recientes primero).

### Cola pendiente · Admin/Productor
```bash
curl http://localhost:8000/suministros/eficiencia-alimenticia/batch/cola \
  -H "Authorization: Bearer <ADMIN>"
```
Respuesta `200`: `{ "total": 0, "items": [] }` (activos `EN_COLA` con prioridad y motivo).

### Fallos persistentes · Admin/Productor
```bash
curl http://localhost:8000/suministros/eficiencia-alimenticia/batch/fallos \
  -H "Authorization: Bearer <ADMIN>"
```
Respuesta `200`: `{ "total": 0, "items": [] }` (activos en `CA_FALLO_PERSISTENTE` no resueltos).

Errores (panel/cola/fallos): `401 TOKEN_REQUERIDO`, `403 ACCESO_DENEGADO` (rol sin R sobre recurso 50; p.ej. `<VET>`).

---

## Scheduler (sin endpoint)
El batch nocturno corre automáticamente a `hora_ejecucion` (por defecto **02:00** hora del servidor)
vía una tarea del `lifespan` en `main.py` (`_ejecutar_batch_ica_diario`). Los parámetros (límite,
workers, umbral, ventana, hora, reintentos/backoff) están en `modulo5.configuracion_batch_ica`.
