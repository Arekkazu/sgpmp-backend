# INC-M02-38-G25 — Omisión de validación de densidad máxima por especie en eventos de crecimiento

**RF:** RF-36 (Gestión Poblacional de Activos Biológicos), aplicado desde CU06 (RF-40, `POST /{id_activo}/eventos/crecimiento`).

## Qué reportó QA

Al registrar un evento de crecimiento sobre un lote poblacional, el backend recalcula `densidad = cantidad_actual / superficie`, pero nunca la compara contra `densidad_maxima_por_especie`. En vez de rechazar con `409 Conflict` cuando la densidad excede el máximo, el sistema acepta el evento (`201 Created`) sin ninguna alerta.

`TC-M02-052`: lote `130` (Cachama, `cantidad_actual=5`, `superficie=500 m²`, densidad=0.01) — se esperaba `409` y se obtuvo `201`.

## Investigación del dato "densidad_maxima_por_especie" (Paso 0)

RF-36 dice literalmente: *"Las validaciones por especie deben definirse en M09 e incluyen: ... Densidad máxima por infraestructura"* y *"densidad no debe superar la densidad_maxima_por_especie definida en M09"*.

Una decisión previa (`cu03_gaps_bd_rf36.md`, D-01) ya había investigado esto y concluyó que el dato no existía — pero buscaba en el lugar equivocado (`ParametrosEspeciePort`, que solo tiene rangos de medición, no densidad). Se verificó contra `sgpmp_dev` real (vía MCP de postgres) antes de decidir dónde vive realmente:

- `modulo9.especies`: sin columna de densidad.
- `modulo9.metricas_produccion`: rangos de medición por tipo, no densidad.
- `modulo9.umbrales_ambientales` / `variables_ambientales`: umbrales físico-ambientales (temperatura, pH, oxígeno...), ninguna variable de densidad poblacional.
- `modulo4.configuraciones_motor_ia.densidad_maxima_config`: existe pero es un peso del motor de predicción de riesgo de M04 (ligado a `tipo_modelo`, no a `id_especie`), concepto distinto, y está en `NULL`.
- **`modulo9.infraestructuras.capacidad_maxima`** (integer, individuos) — **este es el dato**. Ya está declarado en el esquema, junto con `superficie` y `id_especie` (la infraestructura ya está pensada para alojar una especie). `densidad_maxima_por_especie` = `capacidad_maxima / superficie` de la infraestructura donde reside el lote.

Mejor aún: **el dato ya llegaba hasta el use case sin usarse**. `InfraestructuraConsulta` (`infraestructura_consulta_port.py`) ya declara `capacidad_maxima: Optional[int]`, `InfraestructuraM09Adapter.obtener_activa()` ya lo selecciona de la BD, y `RegistrarEventoCrecimientoUseCase` ya inyecta `infra_port` y ya llama `infra_port.obtener_activa(...)` para leer `superficie` — solo ignoraba `infra.capacidad_maxima`, presente en el mismo objeto.

## Fix

`RegistrarEventoCrecimientoUseCase._execute()`, rama `POBLACIONAL`, antes de mutar el detalle vía `activo.aplicar_evento_crecimiento(...)`:

```python
if infra and infra.capacidad_maxima and superficie and superficie > 0:
    cantidad_actual = Decimal(str(activo.detalle_poblacional.cantidad_actual or 0))
    densidad_actual = cantidad_actual / superficie
    densidad_maxima = Decimal(infra.capacidad_maxima) / superficie
    if densidad_actual > densidad_maxima:
        raise ConflictError(
            code='DENSIDAD_MAXIMA_SUPERADA',
            message='La densidad del lote supera el máximo permitido para la especie.',
        )
```

Puntos de diseño, confirmados con el texto exacto del RF-36 antes de implementar (para no adivinar):

- **La validación usa `cantidad_actual` sin modificarlo, nunca `cantidad_medida`.** RF-36 es explícito: `cantidad_actual` "se modifica únicamente mediante eventos de tipo BAJA o mediante registros de ingresos asociados a eventos" — un evento de crecimiento nunca la toca, solo actualiza `peso_promedio`/`biomasa_total`. `cantidad_medida` sigue siendo descriptivo del muestreo, como ya funcionaba.
- **Si `capacidad_maxima` no está configurada (`None`), no bloquea.** Es el estado real de las 12 infraestructuras en `sgpmp_dev` hoy — sin dato sembrado, sin restricción, mismo criterio que ya usa `es_tipo_compatible` en el mismo puerto ("si no hay ninguna regla configurada... es compatible por defecto").
- La validación corre **antes** de `aplicar_evento_crecimiento()` — rechaza sin mutar nada del detalle poblacional.
- `409` agregado a las respuestas documentadas del endpoint en el router (antes solo listaba 400/401/403/404/422).

## Hallazgo relacionado ya resuelto en `dev` (no forma parte de este fix)

El informe de QA también reportó un `TypeError`/500 en `POST /{id}/fases` por una llamada a `cerrar_gestion_activa(id_activo, fecha_fin, motivo)` con 3 argumentos en vez de 4 (`cambiar_fase_use_case.py`). Verificado en esta rama (basada en `dev` actual): la llamada ya pasa los 4 argumentos (`usuario.id_usuario` incluido) — ya estaba corregido antes de este fix, probablemente en el entorno de QA (`sgpmp_test`) por estar en una revisión más antigua que `dev`.

## Pruebas

`tests/biological_assets/test_registrar_evento_crecimiento_densidad_maxima.py` — 5 casos nuevos, fakes escritos a mano, sin BD:

- Densidad por encima del máximo → `409 DENSIDAD_MAXIMA_SUPERADA`, evento no persistido.
- Densidad exactamente igual al máximo (borde) → aceptada.
- Densidad por debajo del máximo → aceptada.
- `capacidad_maxima` sin configurar (`None`) → no bloquea, sin importar la cantidad.
- `cantidad_medida` grande no dispara el rechazo si `cantidad_actual` sigue bajo el máximo — confirma que no se usa para la validación.

Suite completa sin regresiones: 663 passed (658 previos + 5 nuevos), mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no relacionados, confirmados fallando igual en `origin/dev` sin este cambio).

## Alcance

No se tocó `ParametrosEspeciePort` ni ningún adaptador de M09 — el dato ya existía completo en `InfraestructuraConsultaPort`. Sembrar `capacidad_maxima` real por infraestructura (hoy `NULL` en todas) queda fuera de alcance: es una decisión operativa de datos, no de código.
