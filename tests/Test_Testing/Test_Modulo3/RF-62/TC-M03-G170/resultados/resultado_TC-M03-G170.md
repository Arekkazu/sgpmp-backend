# TC-M03-G170 — Resultado

**Veredicto**: RECHAZADO
**Fecha**: 2026-10-23
**Camino**: sensor 91 preexistente (Camino 2)
**Nota**: Esta es la corrida canónica del caso. La corrida V1 (bloqueada por `INC-M03-123-G167` en `00.07-Crear-Sensor`) se conserva como evidencia histórica en `evidencias/run-20261023/`.

## Resumen ejecutivo

La suite se ejecutó con `--no-bail` (para saltar el fallo del preflight) y
probó los 3 subcasos sobre el sensor 91, que tiene 6 evaluaciones VIGENTE.

- **TC-324 (reevaluación exitosa)**: PARCIAL. HTTP 200, 6 superadas, 0 creadas.
  **FALLA** porque el criterio de aceptación exige crear nuevas evaluaciones.
- **TC-325 (rechazos por causa)**: PASSED (4/4). 400/422 documentados.
- **TC-326 (rechazos por fechas)**: PASSED (2/2). 422 en ambas.

## INC / Hallazgo bloqueante

**INC-M03-G170** (nuevo): `POST /iot/calidad/reevaluar` invalida las
evaluaciones previas (`evaluaciones_superadas=6`) pero **no regenera
evaluaciones nuevas** (`evaluaciones_creadas=0`). El CSV de G170 exige
crear nuevas ACTIVA con motivo_reevaluacion y parametros_calibracion_aplicados.

Categoría: FLUJO. Severidad: Severo. Equipo: Desarrollo.
Ubicación probable: `SolicitarReevaluacionUseCase`.

## Hallazgo secundario (no blocking)

**TC-326b**: `fecha_desde == fecha_hasta` retorna 422. El CSV dice
"(supuesto, el requerimiento no lo define)". Se documenta como observación
de requerimiento, no como fallo del caso.

## INC relacionado (heredado)

**INC-M03-G167-SENSOR-500**: `00.07-Crear-Sensor` falla. En V1 de G170
retornó 500; en V2 retornó 400. **Verificar si el código cambió entre
hoy y ayer.** No afecta TC-324/325/326 porque se usó `--no-bail` y
sensor preexistente.

## Evidencia

- Reporte HTML: `resultados/resultado_TC-M03-G170.html`
- JSON: `resultados/resultado_TC-M03-G170.json`
- Consola: `evidencias/console_run.log`
- Histórico V1 (bloqueado): `evidencias/run-20261023/`
- Sandbox: cerrado 200 OK

## Próximos pasos

Cuando Desarrollo corrija el hallazgo de `evaluaciones_creadas=0`:
- Re-ejecutar como `resultado_TC-M03-G170_reintento1.{html,json,md}` (V2, cuando se corrija el INC-M03-133-G170)
- Veredicto esperado: APROBADO
