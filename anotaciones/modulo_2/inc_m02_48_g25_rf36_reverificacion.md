# INC-M02-48-G25 [RF-36] — Reverificación de la validación de densidad máxima

**Issue:** [#394](https://github.com/Arekkazu/sgpmp-backend/issues/394)
**Relacionado:** INC-M02-38-G25 / issue #198, ya corregido por el commit
`9cbb4418` (`fix(m02): validar densidad maxima por especie en eventos de
crecimiento (RF-36)`), presente en `fix/m02-fixes`.

## Qué reportó QA (2026-09-19)

Reverificando el fix de #198 en el ambiente de TEST, encontraron que un lote
de 50.000 individuos en 500 m² (100 ind/m²) fue aceptado con `201 Created` en
vez de rechazado con `409 DENSIDAD_MAXIMA_SUPERADA`, y señalaron tres causas
candidatas (H-A, H-B, H-D) más una discrepancia contractual (H-C).

## Investigación

Se revisó el código real en `fix/m02-fixes`
(`registrar_evento_crecimiento_use_case.py:159-182`) y la suite de pruebas
existente (`tests/biological_assets/test_registrar_evento_crecimiento_densidad_maxima.py`,
5 casos, ya cubre la lógica con fakes) contra cada hipótesis:

- **H-B ("la lógica nunca dispara el 409")** — **descartada, con evidencia
  nueva.** Se agregó
  `tests/integration/test_inc_m02_48_g25_rf36_densidad_maxima_e2e.py`, que
  ejercita el camino completo (HTTP-equivalente → `RegistrarEventoCrecimientoUseCase`
  → `InfraestructuraM09Adapter` real → Postgres real, sin fakes) con un lote
  de 100 individuos en 500 m² contra una infraestructura con
  `capacidad_maxima=1`: el evento se rechaza con `409 DENSIDAD_MAXIMA_SUPERADA`,
  tal como exige RF-36. Un segundo caso con `capacidad_maxima=1000` confirma
  que un lote dentro del límite sigue aceptándose. La lógica es correcta de
  punta a punta cuando la infraestructura tiene `capacidad_maxima` configurada.
- **H-D ("los seeds de TEST tienen `capacidad_maxima = NULL`")** —
  **confirmada como causa raíz real del repro de QA.** Verificado en vivo
  contra `sgpmp` (dev) vía MCP de postgres: las 12 infraestructuras reales
  tienen `capacidad_maxima IS NULL`. El propio commit `9cbb4418` ya documentó
  esto como el estado conocido en dev al momento del fix, y hay una prueba
  unitaria dedicada (`test_sin_capacidad_maxima_configurada_no_bloquea`) que
  prueba deliberadamente que, sin límite configurado, el sistema no bloquea —
  mismo criterio que otras validaciones opcionales por infraestructura en
  este módulo (ej. `es_tipo_compatible`). **No se cambia este comportamiento
  en este PR**: es una decisión de diseño ya tomada y probada, no un bug — la
  ausencia total de un lote "correctamente configurado" en los datos de TEST
  es lo que hace que la validación nunca se ejerza ahí, no un defecto de la
  validación en sí.
- **H-A ("el fix no está desplegado en TEST")** — **fuera del alcance de un
  PR de backend.** El código de la validación ya existe en `fix/m02-fixes`
  (commit `9cbb4418`) y en este PR se demuestra con una prueba real que
  funciona correctamente. Si TEST corre una imagen anterior a ese commit, es
  un problema de despliegue de quien administra ese ambiente, no algo que un
  cambio de código pueda resolver — una vez esta rama llegue a `dev` y se
  redepliegue TEST, el fix queda activo ahí también.
- **H-C ("la densidad máxima debería salir de M09 por especie, no de
  `infraestructuras.capacidad_maxima`")** — **sigue pendiente de decisión de
  Análisis, no se resuelve en este PR.** No existe hoy ninguna tabla de
  configuración de densidad por especie en M09 (verificado: `modulo9.especies`
  no tiene columnas relacionadas). Construir esa tabla y su UI de
  configuración es una funcionalidad nueva, no un bug fix puntual sobre
  RF-36/RF-40 — excede el alcance de INC-M02-48-G25. Se deja documentado aquí,
  de nuevo, para que no se pierda como ya había pasado una vez con #198.

## Qué cambia en este PR

- Prueba de integración nueva
  (`tests/integration/test_inc_m02_48_g25_rf36_densidad_maxima_e2e.py`) que
  cierra la brecha entre "la lógica es correcta" (unitario con fakes) y
  "funciona de punta a punta" (adapter real + Postgres real) — evidencia
  reproducible que refuta H-B de forma concluyente.
- Ningún cambio de comportamiento en el código de aplicación: la validación
  ya era correcta: el gap real era falta de evidencia end-to-end (ahora
  cerrado) y falta de datos de prueba con `capacidad_maxima` configurado en
  el ambiente de TEST (fuera del alcance de este repositorio de backend).

## Pendientes explícitos (no se resuelven aquí)

1. **Ops/QA-TEST:** confirmar que TEST corre una imagen que incluye el commit
   `9cbb4418` (o esta rama una vez mergeada a `dev`), y poblar
   `capacidad_maxima` en al menos una infraestructura de prueba para poder
   reejecutar el escenario original con datos que sí activen la validación.
2. **Análisis:** decidir si `densidad_maxima_por_especie` debe migrar a una
   configuración propia de M09 por especie (como dice el texto literal de
   RF-36) en vez de derivarse de `infraestructuras.capacidad_maxima` (como
   implementa hoy el código). Mientras no haya decisión, el comportamiento
   actual se mantiene.
