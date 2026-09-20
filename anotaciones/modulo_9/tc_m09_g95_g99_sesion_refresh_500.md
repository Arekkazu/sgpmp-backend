# TC-M09-G95 y G99 (#310) — 500 en renovación de sesión, mismo root cause que #312

Fecha: 2026-09-18

## Síntoma reportado

Durante TC-M09-180 (RF-28, dashboard personalizable), el login inicial
funcionó y `GET /configuracion/interfaz/contexto` respondió 200, pero
`POST /sesiones/refresh` respondió `HTTP 500` al navegar a Configuración,
provocando una redirección forzada a `/login`. Bloqueó por completo la
ejecución de TC-M09-180 (grilla de widgets, catálogo, PATCH de guardado,
persistencia).

## Análisis: mismo síntoma, misma causa que TC-M09-G91 (#312)

Este issue reporta un `HTTP 500` en un endpoint de sesiones (`POST /sesiones/refresh`),
exactamente el mismo tipo de fallo que TC-M09-G91 (#312, `POST /sesiones/`)
reportó en el mismo ambiente de pruebas de QA, alrededor de las mismas
fechas. La investigación completa está en
`anotaciones/modulo_9/tc_m09_g91_migracion_test_bloqueada.md` (rama
`fix/tc-m09-g91-migracion-test-bloqueada`, ya en esta cadena de PRs): el
workflow "Deploy Migrations - test" viene fallando desde 2026-09-04, dejando
el esquema de TEST varias migraciones por detrás del código que corre ahí.

No repito la investigación acá porque sería la misma evidencia (mismo run de
CI, misma revisión varada, mismo razonamiento) aplicada a un segundo síntoma
del mismo problema de fondo. Esta rama no agrega código nuevo — parte de la
corrección ya aplicada en `fix/tc-m09-g91-migracion-test-bloqueada` (migración
`b92f7e1a4c63` con la normalización defensiva).

## Por qué sigue siendo una hipótesis, no una confirmación

Igual que en #312: no tengo acceso a `TEST_DATABASE_URL` ni a los logs reales
del backend de TEST. `POST /sesiones/refresh` tampoco reprodujo el 500
localmente (`tests/integration/test_refresh_token.py`, verde contra `pruebas`).
Si el 500 persiste después de que la migración de TEST quede desbloqueada,
hay que reabrir ambos issues con evidencia nueva.

## Pruebas

Sin cambio de código en esta rama — la suite de refresh (`test_refresh_token.py`)
ya estaba y sigue verde contra `pruebas` local.
