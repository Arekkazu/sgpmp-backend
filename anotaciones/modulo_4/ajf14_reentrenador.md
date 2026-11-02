# AJF-14 — Reentrenador real: gaps de BD, contrato y pendientes

Fecha: 2026-11-02 · Autor: Arekkazu · Plan: «ajustes de frontend M02/M03/M04», ítem AJF-14 (16).

## Gaps de BD (Paso 0)

No hubo acceso a `sgpmp_dev` desde el entorno donde se hizo el cambio (la red no deja salir al
puerto 5447), así que el análisis se hizo contra el baseline (`alembic/baseline/esquema_baseline.sql`)
y las migraciones del repo. **Antes de desplegar, verificar en DEV con SamuelPR21.** Los gaps de los demás ítems (AJF-04, AJF-07) van en la migración `bb5526687aae`.

| Gap | Decisión | Dónde |
|-----|----------|-------|
| No hay tabla de procesos de reentrenamiento en `modulo4` | Tabla nueva `modulo4.procesos_reentrenamiento` + 3 ENUM (`enum_proceso_reentrenamiento_disparador`, `_modo_generacion`, `_estado`) | Migración `21fe51f2aea1` (DB-1) |
| Un animal podía tener dos procesos abiertos | Índice único parcial `uq_proceso_reentrenamiento_id_activo_biologico` (PENDIENTE/EN_CURSO) | `21fe51f2aea1` |
| Valores de bitácora `REENTRENAMIENTO_INICIADO/_COMPLETADO/_FALLIDO/_INTERRUMPIDO` | **Ya existen** en `modulo4.enum_tipo_evento_auditoria_m04` (baseline): DB-2 no requiere DDL | — |
| Grants y RLS | `SELECT, INSERT, UPDATE` a los roles de la app; RLS forzada: `pol_proceso_reentrenamiento_select` (animal en las infraestructuras del usuario), `_insert` (permiso E de `version_modelo`, a su nombre), `_servicio` (ALL para el usuario de servicio, que usa el motor) | `21fe51f2aea1` (DB-3) |
| RBAC | Sin recursos nuevos: listar procesos usa `version_modelo` R (43·2); solicitar, E (43·5), como hoy | — |
| Contar días de lecturas con la sesión del usuario | La RLS de `telemetrias` pide monitoreo/historial R: el conteo va con una sesión de sistema aparte (código, sin DDL) | `version_modelo_router.py` |

La migración **no se aplicó**: necesita la autorización de SamuelPR21. Inventario completo de gaps de todos los ítems: `anotaciones/ajustes_m02_m03_m04_gaps_bd.md`.

## Flujo

```
Usuario (43·E) ── POST /prediccion/modelos/reentrenamiento/solicitudes {id_activo_biologico}
                   → proceso PENDIENTE + REENTRENAMIENTO_SOLICITADO
motor-ia (hilo reentrenador, token de servicio)
  POST  /prediccion/motor/reentrenamientos/tomar        → EN_CURSO, fase 1 (204 si no hay)
  GET   /prediccion/motor/activos/{id}/lecturas?horas=336
  GET   /prediccion/motor/activos/{id}/retroalimentaciones
  PATCH /prediccion/motor/reentrenamientos/{id} {fase, progreso, cpu, ram_mb}   ← latido
  POST  /prediccion/modelos (X-RF71-Internal-Key, id_proceso_rf71 = id del proceso)
  PATCH /prediccion/motor/reentrenamientos/{id} {estado: COMPLETADO | FALLIDO, codigo_error, motivos}
backend: cada 5 min, EN_CURSO sin latido > 15 min → INTERRUMPIDO (BE-5)
Pantalla: GET /prediccion/modelos/reentrenamiento/procesos (43·R)
```

Fases (`FASES` en `proceso_reentrenamiento.py`): 1 ACTIVACION · 2 DATASET · 3 PREPROCESAMIENTO ·
4 ENTRENAMIENTO · 5 METRICAS · 6 ENTREGA · 7 CIERRE.

## Decisiones

- **Sin mínimo de retroalimentaciones por animal.** La solicitud por animal no exige las 200 de la
  solicitud por tipo de modelo: el pipeline de ET-02 entrena con lecturas + generador sintético y
  la procedencia (SINTETICA / MIXTA / REAL) la decide el entrenamiento; SINTETICA y MIXTA quedan en
  sombra (regla de RF-69 existente). La solicitud por tipo de modelo sigue igual.
- **Lecturas mínimas:** 7 días (`dias_minimos` de ET-02). En DEV se baja con
  `REENTRENAMIENTO_DIAS_MINIMOS_LECTURAS` (backend) y `MOTOR_IA_ENTRENAMIENTO_DIAS_CALIBRACION` (motor).
- **BE-3 sin tocar el registro:** al cerrar COMPLETADO sin `id_version_modelo`, el backend toma la
  versión registrada con `id_proceso_rf71` = id del proceso.
- **BE-6 (disparador PROGRAMADO) no se hizo** en v1: depende de P-9.

## Pendientes (abiertos en el plan)

- **P-6** El script de entrenamiento `modelos_individuales_ET02_v5.py` no está en ningún repositorio:
  vive en `anotaciones/M04-M03 MODELOS/` de una máquina local. El motor ya tiene el reentrenador
  (`motor_ia/reentrenador.py`) y el adaptador (`motor_ia/entrenamiento.py`), pero la copia literal
  `motor_ia/entrenamiento_et02.py` (M-1) hay que generarla desde ese archivo, como se hizo con
  `et02.py`. Sin ella, cada proceso termina FALLIDO con `ENTRENAMIENTO_NO_DISPONIBLE`, sin inventar
  resultados.
- **P-7** Contenedor propio para el reentrenador (recomendado) — lo decide Implementación.
- **P-8** Quién solicita: hoy, quien tenga 43·E (Administrador y Veterinario).
- **P-9** Disparador PROGRAMADO.

## CURLs

Base local: `http://localhost:8000`. `<TOKEN_VET>`: JWT con 43·E. `<TOKEN_MOTOR>`: `IOT_INFERENCIA_M04_TOKEN`.

### Solicitar el reentrenamiento de un animal (BE-1)

```bash
curl -X POST "http://localhost:8000/prediccion/modelos/reentrenamiento/solicitudes" \
  -H "Authorization: Bearer <TOKEN_VET>" -H "Content-Type: application/json" \
  -d '{"id_activo_biologico": 4, "motivo": "Prueba E2E con BOV-003"}'
```

`201`: `{"id_evento": "...", "estado": {...}, "id_proceso_reentrenamiento": "..."}`.
Errores: `404 ACTIVO_NO_ENCONTRADO` · `409 REENTRENAMIENTO_EN_CURSO` · `422 ACTIVO_SIN_MODELO_INDIVIDUAL` ·
`422 LECTURAS_INSUFICIENTES` · `400` sin `tipo_modelo` ni `id_activo_biologico` · `403` sin 43·E.

### Listar procesos (BE-4)

```bash
curl "http://localhost:8000/prediccion/modelos/reentrenamiento/procesos?estado=EN_CURSO&pagina=1&por_pagina=20" \
  -H "Authorization: Bearer <TOKEN_VET>"
```

`200`: `{"items": [{"id_proceso_reentrenamiento": "...", "estado": "EN_CURSO", "fase_actual": 4,
"fases": [{"fase": 1, "nombre": "ACTIVACION", "fecha_inicio": "...", "fecha_fin": "...", "resultado": "OK"}, …],
"porcentaje_progreso": 55, "porcentaje_cpu": "68.50", "memoria_ram_mb": 900, …}], "total": 1, "pagina": 1, "por_pagina": 20}`.
Errores: `400 ESTADO_INVALIDO | PAGINACION_INVALIDA | RANGO_FECHAS_INVALIDO` · `403`.
Detalle: `GET /prediccion/modelos/reentrenamiento/procesos/{id}` (`404 PROCESO_NO_ENCONTRADO`).

### Motor: tomar, latido, cierre (BE-2)

```bash
curl -X POST "http://localhost:8000/prediccion/motor/reentrenamientos/tomar" -H "Authorization: Bearer <TOKEN_MOTOR>"
curl -X PATCH "http://localhost:8000/prediccion/motor/reentrenamientos/<ID>" -H "Authorization: Bearer <TOKEN_MOTOR>" \
  -H "Content-Type: application/json" -d '{"fase": 4, "progreso": 55, "cpu": 68.5, "ram_mb": 900}'
curl -X PATCH "http://localhost:8000/prediccion/motor/reentrenamientos/<ID>" -H "Authorization: Bearer <TOKEN_MOTOR>" \
  -H "Content-Type: application/json" -d '{"estado": "FALLIDO", "codigo_error": "CALIBRACION_INCOMPLETA", "motivos": ["2 días de lecturas"]}'
curl "http://localhost:8000/prediccion/motor/activos/4/retroalimentaciones" -H "Authorization: Bearer <TOKEN_MOTOR>"
```

`tomar`: `200` con el proceso EN_CURSO o `204`. `PATCH`: `200`; `404 PROCESO_NO_ENCONTRADO` ·
`422 FASE_RETROCEDE | PROCESO_NO_EN_CURSO | PROCESO_CERRADO | VERSION_NO_REGISTRADA` · `400` cuerpo inválido · `401` sin token.
