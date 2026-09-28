# Impacto de F3 (`usuarios_fincas` M:N) sobre el RLS de F1/F4/F5, por schema

**Punto de partida verificado contra `sgpmp_dev`:** F3 del plan de control de
acceso (`modulo9.usuarios_fincas`, migración `1b9536d4411c`, INC-M02-61-G52)
**ya está implementada y en `dev`** — mergeada el 2026-09-23, antes incluso de
que se mergearan las migraciones de RLS de F1 (modulo1/modulo9, mergeadas el
2026-09-27). `AlcanceFincaAdapter` (`src/shared/alcance_finca_adapter.py`) ya
resuelve el alcance por finca contra esa tabla, no contra el viejo
`fincas.id_usuario` 1:1.

**Consecuencia central de este documento:** las políticas RLS de F1 para
`modulo9.fincas` y `modulo9.infraestructuras` se escribieron usando el modelo
**viejo** (`id_usuario = current_user_id()`), y **no** se actualizaron para
usar `usuarios_fincas`. Hoy es inofensivo porque nada llama `set_config`
todavía (ver `control_acceso_f2_contexto_sesion.md`). En cuanto la identidad
viaje de verdad, la fila de RLS quedaría **más restrictiva** que el
RBAC + alcance de la aplicación: un Veterinario o Ingeniero de Campo con
acceso M:N asignado seguiría viendo listados vacíos de fincas ajenas, el
mismo síntoma que F3 se creó para resolver, pero reintroducido un nivel más
abajo, en la base de datos.

Este documento no aplica ningún DDL — es análisis. La corrección propuesta se
deja lista para una migración de F4/F5, previa autorización del DBA.

---

## Función única de pertenencia (recomendada, no aplicada)

Toda política que necesite "¿qué fincas ve este usuario?" debe llamar a una
única función, para que un cambio de modelo futuro toque un solo objeto:

```sql
-- PROPUESTA, no ejecutada. Columnas verificadas contra modulo9.usuarios_fincas.
CREATE OR REPLACE FUNCTION modulo9.fn_fincas_del_usuario(p_id_usuario integer)
RETURNS SETOF integer
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT id_finca FROM modulo9.usuarios_fincas
    WHERE id_usuario = p_id_usuario AND es_activo IS TRUE;
$$;
```

`SECURITY DEFINER` para no tener que otorgarle a `sgpmp_app` un `SELECT`
directo sobre `usuarios_fincas` que podría usar para otro fin. Mismo patrón
ya usado por `app_ctx.current_user_id()`/`current_role()`, salvo que estas sí
necesitan `SECURITY DEFINER` porque leen una tabla, no solo un GUC — **ojo**:
si se crea así, hay que darle a `sgpmp_app` `GRANT USAGE ON SCHEMA modulo9` (ya
lo tiene) y no hace falta `GRANT` sobre `usuarios_fincas` en sí.

---

## `modulo9` — impacto directo, ya viva

`modulo9` es donde vive `fincas`, y donde ya hay RLS parcial (migración
`5243bbbb28de`). Es el único schema con deuda **ya escrita e incorrecta**, no
solo pendiente de escribir.

| Tabla | Política actual | Problema | Corrección propuesta |
|---|---|---|---|
| `fincas` | `pol_fincas_select`: `id_usuario = current_user_id() OR admin` | Ignora `usuarios_fincas`; un usuario con acceso M:N (no dueño) no ve la fila de la finca | `id_finca IN (SELECT modulo9.fn_fincas_del_usuario(current_user_id())) OR id_usuario = current_user_id() OR admin` (se conserva la rama de dueño porque `fincas.id_usuario` se sigue mostrando como "propietario", ver `anotaciones/modulo_1/rf46...` / INC-M02-61-G52) |
| `infraestructuras` | `pol_infraestructuras_select`: `id_finca IN (SELECT id_finca FROM fincas WHERE id_usuario = current_user_id()) OR admin` | Misma raíz: solo mira `fincas.id_usuario`, nunca `usuarios_fincas` | `id_finca IN (SELECT modulo9.fn_fincas_del_usuario(current_user_id())) OR admin` |

Otros tres hallazgos de `modulo9`, de la misma familia (RLS activo desde F1,
sin política — deny-all), verificados por consulta directa a
`pg_policy`/`pg_class`:

- **`compatibilidad_sensores_especies`** — deny-all hoy, **y se usa en
  producción**: `src/biological_assets/infrastructure/adapters/sensor_m09_adapter.py`
  y `src/biological_assets/domain/repositories/sensor_consulta_port.py` la
  consultan para RF-49 (compatibilidad sensor↔especie). El comentario de la
  propia migración ya lo anticipa ("RF-49, no incluido en este lote"), pero
  conviene que quede explícito aquí: es deuda viva, no solo teórica.
- **`compatibilidades_tipo_area_especie`** — deny-all, sin verificar uso
  activo en esta pasada (candidato a la misma revisión).
- **`intentos_fallidos`** — deny-all, mismo tratamiento pendiente.

Ninguna de las tres es responsabilidad de F3; se anotan aquí porque son la
misma clase de deuda ("migración de F1 dejó la tabla sin política") y
conviene resolverlas en el mismo lote que el fix de fincas/infraestructuras.

---

## `modulo1` — sin impacto de F3

No tiene `id_finca` ni ninguna tabla que llegue a `fincas` por FK (verificado
contra `information_schema` — cero resultados para `modulo1` en la búsqueda
de cadenas hacia `modulo9.fincas`). Su control es RBAC + auto-acceso
(`id_usuario = current_user_id()`); no necesita `fn_fincas_del_usuario()`.

---

## Resto de schemas — impacto futuro (F4/F5), cadenas de FK verificadas

Ninguno de estos schemas tiene RLS activo todavía. Esto es lo que hay que
tener en cuenta **cuando** F4/F5 les llegue, para no repetir el error de
`modulo9`: toda política de estos schemas debe llamar
`fn_fincas_del_usuario()`, nunca `fincas.id_usuario` directo, porque para
cuando se escriban esas políticas F3 ya estará asumido como el modelo
vigente (no habrá "migración vieja" que arrastrar, a diferencia de `modulo9`).

Cadenas de FK obtenidas con una consulta recursiva contra
`information_schema` (hasta 4 saltos, sin ciclos), no copiadas del análisis
original.

### `modulo2` (activos biológicos) — cadena dominante: 2-3 saltos vía infraestructura

`activos_biologicos.id_infraestructura → modulo9.infraestructuras.id_finca`
(2 saltos). El resto de las ~20 tablas del schema cuelga de
`activos_biologicos` (3 saltos): `eventos_activos`, `gestiones_fases`,
`historial_activos`, `historicos_estados_activos`, `movimientos`,
`detalles_activos_*`, `indicadores_zootecnicos`, `auditoria_activos_biologicos`,
`asociaciones_activos_sensores`. Ninguna tabla de `modulo2` tiene `id_finca`
propio — es el patrón 3 (cadena) casi puro, tal como ya anticipaba el
análisis original.

### `modulo3` (telemetría) — mixto: 1, 2 y 3-4 saltos

- **1 salto directo:** `reglas_alertas.id_finca`.
- **2 saltos:** `alertas.id_infraestructura`, `vinculaciones_lecturas.id_infraestructura`.
- **3-4 saltos:** el resto cuelga de `dispositivos_iot` (que a su vez cuelga
  de `infraestructuras`, 2 saltos): `sensores`, `estados_dispositivos_iot`,
  `telemetrias`, `heartbeats`, `calibraciones`, `bitacora_ingest`, `buffers`,
  `eventos_edge_computing`, `paquetes_inferencia`, `historico_transiciones_dispositivos`,
  `transmisiones_mqtt`, `periodos_inactividad`.

### `modulo4` (predicción) — mixto: 1, 3 y 4 saltos

- **1 salto directo:** `alertas_patologicas.id_finca` (nota: esta misma tabla
  también llega a `activos_biologicos` en 3 saltos vía `id_activo_biologico`
  — dos caminos distintos a la misma finca, hay que decidir cuál usa la
  política, o si valida ambos).
- **3 saltos:** la mayoría, vía `activos_biologicos`: `observaciones_clinicas`,
  `resultados_inferencia`, `resultados_riesgo_contagio`,
  `retroalimentaciones_clinicas`, `historial_diagnostico_eventos`.
- Dispositivos edge (`despliegues_ota`, `metricas_fallback_motor`,
  `sincronizacion_nodos_edge`) llegan en 3 saltos vía `dispositivos_iot`.

### `modulo5` (suministros) — cadena dominante: 3-4 saltos vía activo biológico

Ninguna tabla con `id_finca` propio. Todo cuelga de `activos_biologicos` (3
saltos: `registro_suministro`, `registros_medicamentos`,
`registros_consumo_alimentos`, `resultado_ica`, `costos_productivos`,
`mediciones_inventarios`, `mediciones_incrementales`, `provision_nic41`,
`auditorias_suministros`, `cola_calculo_ica`, `fallos_calculo_ica`,
`historial_suministros_activos`, `reporte_gastos_acumulados`) o de
`gestiones_fases` (4 saltos: `acumulado_ciclo`, `provision_nic41`,
`registro_suministro`, `auditorias_suministros` — algunas llegan por ambos
caminos). Es la cadena más larga y más cara de todo el sistema, tal como ya
anticipaba el análisis original — candidato fuerte a función auxiliar propia
o desnormalización de `id_finca`, decisión que corresponde al piloto de F4,
no a este documento.

### `modulo6` (NIC-41 contable) — 3-4 saltos, siempre vía activo biológico

Sin `id_finca` propio en ninguna tabla. 3 saltos:
`reconocimientos_iniciales`, `mediciones_posteriores`,
`calculos_valor_razonable`, `valoraciones_por_costos`,
`variaciones_valor_razonable`, `reconocimientos_productos_agricolas`,
`registros_costos`, `auditorias_financieras`. 4 saltos: el resto
(`cadenas_trazabilidad_contable`, `cotizaciones`, `deterorios_activos`,
`revisiones_reconocimiento`).

### `modulo7` (integraciones) — 4 saltos, vía modulo6

Las tres tablas relevantes (`auditoria_peticiones`,
`documentos_generados_aaef` x2) cuelgan de `modulo6` (que a su vez cuelga de
`activos_biologicos`) — 4 saltos totales. El más largo del sistema.

### `modulo8` (reportes) — mixto: 1, 2 y 3-4 saltos

- **1 salto directo:** `reportes_regulatorios.id_finca` (además llega
  también en 3 saltos vía `activos_biologicos` — mismo caso que
  `alertas_patologicas` en modulo4, dos caminos a la misma finca).
- **2 saltos:** `configuraciones_semaforo.id_infraestructura`,
  `snapshots_kpi.id_infraestructura`.
- **3-4 saltos:** `historiales_clinicos`, `auditorias_reportes`,
  `retroalimentacion_feedback`.

---

## Qué es deuda ya viva vs. qué es trabajo futuro

**Ya viva (corregir antes de activar RLS de verdad en `modulo9`, junto con
los fixes de `control_acceso_f2_contexto_sesion.md`):**
- `pol_fincas_select` y `pol_infraestructuras_select` ignoran `usuarios_fincas`.
- `compatibilidad_sensores_especies` deny-all con uso activo en producción (RF-49).

**Trabajo futuro (F4/F5, ningún DDL pendiente hoy):**
- Todas las cadenas de `modulo2`–`modulo8` de arriba: no tienen RLS todavía,
  así que no hay nada "roto" — solo hay que escribirlas ya contra
  `fn_fincas_del_usuario()` desde el primer día, no contra `fincas.id_usuario`.
- Las tablas con **dos caminos distintos** hacia `fincas`
  (`alertas_patologicas`, `reportes_regulatorios`) necesitan una decisión
  explícita de cuál camino manda en la política — no se puede automatizar.
- La cadena de `modulo5`/`modulo7` (3-4 saltos) es la más cara: candidata a
  medirse primero en el piloto de F4 antes de decidir función auxiliar vs.
  desnormalización de `id_finca`.
