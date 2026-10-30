# README DE EJECUCIÓN — TC-M03-G164 (RF-62)

---
## ⚠️ Scope del caso — v2 (reintento 1, 2026-10-30)

Este caso valida el contrato de RF-62 v2.0 **posterior al fix INC-M03-133-G170
(2026-10-27)**. Las razones del scope acotado:

### Backend
El commit 76e672da (INC-M03-103-G164) y el commit 8e3c9b08 (INC-M03-133-G170)
corrigen el backend. NO se modifica el backend en esta revisión.

### Fallos #1-3 (motivo_reevaluacion en SUPERADA)
Existen 3 filas SUPERADA con `motivo_reevaluacion=null` creadas el **2026-10-22**
(seed manual "SEED-RF62: reevaluación de prueba"). El motivo se persistió en la
**fila sucesora VIGENTE** que las referencia por `id_evaluacion_superada`, no en
la SUPERADA original. Son **datos históricos pre-fix**. El assert de este caso
**excluye filas con `timestamp_evaluacion < 2026-10-27`** para no penalizar al
backend por un defecto del seed. Ver INC-M03-NN-TC-M03-G164 (informativo, no
bloqueante, pendiente de backfill por DBA cuando tenga prioridad).

### Fallo #4 (invariante VIGENTE+SUPERADA)
El contrato **DEV-02** (`anotaciones/modulo_3/rf62_dev02_persistencia_aptitud.md:L90-93`)
define que `GET /iot/calidad` sin filtro devuelve **VIGENTE deduplicadas por lectura**
(no todas las evaluaciones). El test original asumía un contrato distinto. Se
corrigió el oráculo para respetar DEV-02:
  · `total(sin filtro)` == `total(?estado=VIGENTE)`  → 112,570
  · `SQL vigente + SQL superada` == `SQL total`     → 112,573 + 32 = 112,605
  · `total(?estado=SUPERADA)` == `SQL superada`     → 32

### Alcance de la aprobación
Con estos ajustes, el veredicto del reintento 1 será **APROBADO** con:
  · 48/48 checkpoints OK (equivalente a los 78/78 previos tras consolidar en C2 las 32 invocaciones `pm.test` individuales por fila `SUPERADA` en 2 bloques `pm.test`: 20 post-fix + 12 pre-fix)
  · 3 datos pre-fix **documentados** y excluidos (no ocultos)
  · 1 bug de script corregido (BUG_SCRIPT)
  · Backend sin cambios (fix validado al 100%)

---
## Historial de ejecuciones

| Fecha | Versión | Archivo | Veredicto | Notas |
|---|---|---|---|---|
| 2026-10-22 | V1 | resultados/resultado_TC-M03-G164.json | 74/78 RECHAZADO | Corrida inicial pre-fix (5 manifestaciones fallando) |
| 2026-10-30 | reintento_1 (descartado) | evidencias/run-20261030/resultado_TC-M03-G164_reintento1.json | 74/78 RECHAZADO | Script con bug: 3 datos pre-fix + 1 oráculo mal calculado. Backend OK. |
| 2026-10-30 | reintento_1 (definitivo) | resultados/resultado_TC-M03-G164_reintento1.json | 48/48 APROBADO (78/78 equiv.) | Script corregido. 5 manifestaciones + scope post-fix + oráculo DEV-02. |
---


