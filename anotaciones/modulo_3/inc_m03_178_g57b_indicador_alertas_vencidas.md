# INC-M03-178-G57B — Indicador `alertas_vencidas_sin_atencion` (RF-57, Salida 3)

**RF:** RF-57, "Salida — 3. Indicadores de Estado del Sistema de Alertas"; E10 y CA-12; TC-M03-N46.
**Issue:** #757. **Rama:** desde `dev`. **Sin migración.**

## Lo que reportó QA

- `GET /iot/monitoreo/dashboard` no trae ninguna clave con "vencid".
- Ninguna de las 237 rutas de `/openapi.json` expone indicadores de alertas.

## Lo que pide el RF

El RF-57 dice que el sistema "mantiene y expone métricas actualizadas" y lista seis:
`alertas_activas_total`, `alertas_criticas_activas`, `alertas_por_tipo`,
`alertas_vencidas_sin_atencion`, `tiempo_promedio_resolucion` y `tasa_falsos_positivos`.
El backend no calculaba ninguna.

**Decisión del equipo:**
- Exponer los seis en una ruta nueva, `GET /iot/alertas/indicadores`.
- Agregar además `alertas_vencidas_sin_atencion` al dashboard de monitoreo.
- Las vencidas cuentan **todas** por defecto, con un rango opcional `fecha_desde` /
  `fecha_hasta`.

## Definiciones

Todos los indicadores cuentan **solo alertas operativas**, porque las técnicas son de RF-60.
Usan el mismo alcance que `GET /iot/alertas`: las fincas del usuario, por el área de la alerta
o por la del activo biológico, y opcionalmente un área (`id_infraestructura`).

| Indicador | Cálculo | Rango de fechas |
|---|---|---|
| `alertas_activas_total` | Abiertas: `ACTIVA` o `EN_ATENCION` | No aplica (foto actual) |
| `alertas_criticas_activas` | Abiertas con severidad `CRITICO` | No aplica |
| `alertas_por_tipo` | Abiertas agrupadas por `tipo_alerta` | No aplica |
| `alertas_vencidas_sin_atencion` | `VENCIDA` con `fecha_atencion` nula (nunca reconocida: E10) | Sobre `fecha_resolucion`, la fecha en que venció |
| `tiempo_promedio_resolucion_min` | Promedio de `fecha_resolucion - fecha_generacion` de las `RESUELTA`, en minutos | Sobre `fecha_resolucion` |
| `tasa_falsos_positivos` | `DESCARTADA / (RESUELTA + DESCARTADA)`; `null` si no hay ninguna cerrada | Sobre `fecha_resolucion` |

También se devuelven `alertas_resueltas` y `alertas_descartadas`, que son la base de la tasa.

**Notas:**
- `VENCIDA` es un estado terminal, así que una vencida sigue contando "sin atención".
- El modelo permite `EN_ATENCION → VENCIDA`, pero esas sí fueron reconocidas y no cuentan.
- El trigger `fn_alerta_validar_transicion` fija `fecha_resolucion` al pasar a cualquier estado
  terminal.
- Los indicadores se calculan al consultar, no se guardan como contadores. Una alerta que vence
  con el worker de DEV-31 sube el indicador en la siguiente consulta, y no hay contadores que
  se puedan desincronizar.

## Cambios

- **Dominio:** `IndicadoresAlertas` y `FiltroIndicadoresAlertas` (entidad) y el puerto
  `IndicadoresAlertasRepository`.
- **Infraestructura:** `SqlAlchemyIndicadoresAlertasRepository`, con SQL agregado y el alcance
  de `GET /iot/alertas`.
- **`ConsultarIndicadoresAlertasUseCase`:** un rango invertido responde 400 `RANGO_FECHAS_INVALIDO`.
- **`alerta_router.py`:**
  - Ruta `GET /iot/alertas/indicadores`, con RBAC recurso 32 y acción R (los mismos roles que
    listan alertas operativas).
  - Va antes de `/{id_alerta}`; si no, "indicadores" se toma como un id.
- **`IndicadoresAlertasSchema`:** schema de respuesta de la ruta.
- **Dashboard:**
  - `DashboardResponseSchema.alertas_vencidas_sin_atencion`.
  - `ObtenerDashboardUseCase.contar_alertas_vencidas_sin_atencion`.
  - Los dos GET del dashboard lo calculan con el mismo puerto.

## Evidencia

**Pruebas unitarias:** `tests/telemetry/test_inc_m03_178_g57b_indicador_alertas_vencidas.py`.
- El contrato tiene los seis indicadores, y el dashboard trae la clave.
- La ruta va antes del detalle por id.
- El use case pasa el alcance y el rango.
- Un rango invertido responde 400.
- La tasa de falsos positivos se calcula bien (incluido `null` sin alertas cerradas).
- El dashboard usa el mismo alcance.

**Integración:** `tests/integration/test_inc_m03_178_g57b_indicador_alertas_vencidas.py`, con
PostgreSQL real, RLS (`sgpmp_app`), JWT de un Productor y el worker real de DEV-31.
- **TC-M03-N46:**
  - Una alerta CRITICO ACTIVA da `vencidas=0`, `activas=1` y `criticas=1`.
  - Al vencer, da `vencidas=1` y `activas=0`, en la ruta y en el dashboard del área.
- **No cuentan:**
  - una alerta de otra finca;
  - una técnica;
  - una que pasó `EN_ATENCION → VENCIDA`.
- **Históricos:**
  - 1 resuelta en 30 min y 3 descartadas dan una tasa de 0.75 y un promedio de ~30 min.
  - Con `fecha_desde` en el futuro, todo queda en 0 o `null`.
  - Un rango invertido responde 400.
- **Sobre `origin/dev`** (prueba copiada a un worktree): `/indicadores` responde 400
  `VAL_ENTRADA`, porque se interpreta como `id_alerta`, y el dashboard no trae la clave.

**Regresión:**
- Suite completa: 4 failed y 25 errors, los mismos de la base. Ninguno nuevo.
- `test_dev31_rf57_sla_vencida_bd` y la integración del dashboard de G87 pasan.

## Fuera de alcance

- **Consumo desde M08:** el RF dice que estos indicadores alimentan el dashboard gerencial de
  M08. Esa integración es de M08.
- **Indicador por unidad en `resumen_unidades`:** el dashboard expone el total del alcance (o
  del área filtrada). Para el detalle por unidad está `GET /iot/alertas/indicadores?id_infraestructura=`.
- **Conflicto con G57B #756** (`fix/m03-inc177-g57b-dashboard-rendimiento`): las dos ramas
  tocan las mismas líneas de `monitoreo_router.py` y `obtener_dashboard_use_case.py`. Al
  integrarlas se conservan ambos lados: el aviso en segundo plano y `indicadores_alertas`.
