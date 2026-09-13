# TC-M02-G34 — Validación de fechas, secuencia y solapamiento en cambios de fase del ciclo productivo

**CU-02 · RF-37 — Gestión de Fases del Ciclo Productivo.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-040) Rechazar fecha inválida · (TC-M02-041) Rechazar transición no estándar sin confirmación · (TC-M02-043) Rechazar solapamiento de fases · (TC-M02-044) Rechazar cambio de fase en activo CERRADO/BAJA |
| Tipo | Validación |
| Herramienta | API — Postman |
| Endpoints | `POST /activos-biologicos/{id_activo}/fases` · `GET /activos-biologicos/{id_activo}/fases` |
| Responsable | Juan Manuel · Prioridad Alta |

## ⚠️ Resultado: BLOQUEADO en su totalidad — 5/8 assertions FAIL

**Los 4 sub-casos dependen de `POST /fases`, que está roto para cualquier entrada (INC-M02-37-01, ya reportado
desde TC-M02-G23).** Se re-confirmó con datos frescos y, además, se descubrió un **segundo defecto independiente**
que bloquea específicamente la precondición de TC-M02-044. Detalle completo con evidencia en
`RESULTADOS/TC-M02-G34_resultado.md` y causas raíz en `NOTA_BLOQUEO.md`.

### GIVEN / WHEN / THEN

| Caso | WHEN | THEN esperado (RF) | Resultado real |
|---|---|---|---|
| TC-M02-040 | `POST /fases` con `fecha_inicio` futura (2027) | 400 "Fecha de cambio de fase inválida" | **500** — y aunque se corrija el crash, no hay ninguna validación de fecha en el código (gap adicional) |
| TC-M02-041 | `POST /fases` con `fase_destino_id` fuera de secuencia, sin confirmación | 409 "La transición requiere confirmación explícita" | **500** — y el DTO no tiene ni `fase_destino_id` ni `confirmacion_no_estandar` (INC-M02-37-02, ya reportado) |
| TC-M02-043 | Crear una fase que se solape con una anterior | 409 "Solapamiento de fases detectado" | **Bloqueado en la precondición** — no se puede crear ni la primera fase |
| TC-M02-044 | `POST /fases` sobre un activo en BAJA | 409 "No se puede cambiar la fase de un activo inactivo" | **Bloqueado en la precondición** — llevar el activo a BAJA también falla (500, defecto nuevo, ver abajo) |

### El defecto nuevo (precondición de TC-M02-044)

Para no depender de RF-37 al preparar un activo en BAJA, se usó `POST /eventos/baja` (RF-45) sobre un activo **sin
fase previa** — así se evita por completo el código afectado por INC-M02-37-01. Aun así, la petición falla con
**500 "Error inesperado en base de datos"** — un mensaje que indica un error real de base de datos, no el
`TypeError` de Python de INC-M02-37-01. Evidencia comparativa fuerte (no una hipótesis al aire): el mismo tipo de
operación (registrar un cambio de estado) **sí funciona** cuando pasa `modulo_origen='MANUAL'` (RF-44, confirmado
en `TC-M02-G22`), pero **falla** cuando pasa `modulo_origen='RF-45'` (este caso) — sugiere fuertemente que el CHECK
de base de datos sobre esa columna no fue actualizado para aceptar todos los literales que el código ya usa tras
un refactor reciente (rama `fix/rf38-44-45-centralizar-cambio-estado`). Detalle completo en `NOTA_BLOQUEO.md`,
sección 2.

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`. Sin acceso a base de datos — toda la verificación es vía API.
- Activos de prueba: 204 (especie 2/Trucha, para 040/041/043), 205 (especie 2/Trucha, para 044).
- Newman 6.2.2 + htmlextra 1.23.1. Fecha de ejecución: 2026-09-10.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-37/TC-M02-G34
newman run TC-M02-G34.postman_collection.json -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G34.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G34.html \
  --suppress-exit-code
```
