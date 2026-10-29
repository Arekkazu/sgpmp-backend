# TC-M03-G169 — Cierre V1 RECHAZADO (primera corrida)

**Fecha**: 2026-10-28
**Veredicto**: RECHAZADO
**Causa**: INC-M03-G168-BROKER-RLS (defecto del producto — RLS en modulo9.sensores)
**Corrida**: V1 (primera ejecución con resultados computables)
**Nota histórica**: el caso estuvo bloqueado desde su diseño por el INC de RLS.
  El estado "Fallido" en la lista original del caso NO provenía de una corrida
  previa con resultados computables, sino de la imposibilidad de ejecutarlo.
  Por tanto esta corrida es V1, no reintento.

**Subcasos afectados**:
- TC-M03-321 (FUERA_DE_RANGO → índice 0 / NO_APTO)
- TC-M03-322 (ERROR_CALIBRACION → índice 70 / APTO_CON_RESERVA)

## Resultado de la ejecución V1

- Duración: 6.6s
- Requests: 25
- Assertions: total=27 · passed=18 · failed=9

## Cascada observada

1. `POST /iot/telemetria` → 401 ERROR_AUTENTICACION (RLS bloquea al servicio)
2. `id_telemetria` queda vacío
3. `POST /iot/calidad/{id}/evaluar` degrada a `POST /iot/calidad` → 405
4. Aserciones de TC-321 y TC-322 → fail (9 en total)

## Evidencia computable

- `resultados/resultado_TC-M03-G169.html`
- `resultados/resultado_TC-M03-G169.json`

## Evidencia no computable

- `evidencias/run-20261028/console_run.log`
- `evidencias/run-20261028/INC-M03-G168-BROKER-RLS.md`

## Correcciones de infraestructura aplicadas antes de la corrida V1

- ✅ Reporter escribe .html y .json (sin sufijo, primera corrida)
- ✅ `.md` fuera de `resultados/`
- ✅ Assert teardown valida "Rollback exitoso"
- ✅ Pre-check `modulo9.calibraciones` en TC-322
- ✅ Assert `gap_temporal_anomalo.activo === true` en TC-322
- ✅ Verificación de inmutabilidad de RF-53 post-evaluación

## Próximos pasos

1. **Desarrollo/DBA**: fix del RLS (ver INC-M03-G168-BROKER-RLS).
2. **QA**: cuando se desbloquee → **reintento 1** (`_reintento1`), sin tocar
   aserciones de negocio. El runner ya está configurado para esa nomenclatura.
3. **QA**: crear issue en Taiga con formato:
   `[INC-M03-G168-BROKER-RLS][RF-62] Error 401 en ingesta de telemetría por RLS en sensores de sandbox`
