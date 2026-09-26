# INC-M02-96-G94 — Rate limiting no verificable y contrato incompleto en datos-consolidados

**RF:** RF-50 — Disponibilidad de datos para módulos analíticos
**Endpoint:** `GET /activos-biologicos/{id_activo}/datos-consolidados`

## Causa raíz

El proyecto ya tenía un limitador de tasa reutilizable (`src/shared/rate_limit.py`,
introducido por INC-M09-21-G125-02) y otros routers lo usan (ej.
`POST /configuracion/dispositivos-iot`). El router de activos biológicos nunca lo
aplicó al endpoint de `datos-consolidados`: cero solicitudes de la ráfaga de QA
fueron rechazadas porque no había ningún límite configurado. El contrato OpenAPI
tampoco declaraba `429` en las respuestas posibles.

## Qué se corrigió

- `activo_biologico_router.py`: se agrega `_LIMITE_DATOS_CONSOLIDADOS =
  rate_limit(100, 60, alcance="activos_datos_consolidados")` y se conecta como
  dependencia de la ruta, junto con `429: {'model': ErrorResponse}` en `responses`.
  El límite numérico (100/min) usa el mismo valor que exige RF-50.
- Test nuevo `tests/biological_assets/test_inc_m02_96_g94_rate_limit_datos_consolidados.py`:
  verifica que la ruta declara la dependencia (para que una futura regresión de
  "se quitó el limitador" falle en CI, no solo en un pentest) y que el limitador
  corta en la solicitud 101.
- Documentado un nuevo caso de error (E-06) en
  `anotaciones/modulo_2/curls_m02_cu12_indicadores_datos.md`.

## Qué queda fuera de alcance (documentado, no resuelto aquí)

1. **Aislamiento por módulo, no por usuario** (Hallazgo BLOQ-G94-01 del QA). El RF-50
   define el límite como "100 solicitudes/minuto/**módulo**", pero el mecanismo de
   autenticación actual (`get_current_user`, JWT de usuario + rol) no tiene concepto
   de "módulo consumidor" (M04, M06, M08...) — el limitador aplicado aquí es por
   `id_usuario`, no por módulo. Definir una identidad de módulo autenticable es
   exactamente el alcance de **INC-M02-90-G92**, que se resuelve por separado en esta
   misma cadena de PRs. Una vez exista esa identidad, este mismo helper `rate_limit`
   puede recibir esa clave en vez de `id_usuario` sin cambiar su implementación.
2. **`securitySchemes`/`security` ausentes en el OpenAPI global** (Hallazgo OBS-G94-02,
   parte contractual). `get_current_user` valida el header `Authorization` manualmente
   (`Header(None)`) en vez de usar las clases de seguridad de FastAPI
   (`HTTPBearer`/`OAuth2PasswordBearer`), así que **ningún** endpoint autenticado de
   toda la API (no solo este) aparece con esquema de seguridad en el OpenAPI generado.
   Corregirlo requiere tocar `main.py` (registrar un `securityScheme` global) y
   verificar el contrato completo de la aplicación, no solo el de `datos-consolidados`
   — queda fuera del alcance de este issue puntual, se deja anotado para un ticket de
   hardening de OpenAPI a nivel de aplicación.

## Pruebas

`pytest tests/biological_assets/` — 76 passed (incluye el test nuevo).
