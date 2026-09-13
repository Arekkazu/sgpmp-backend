# TC-M02-G40 — Restricciones de estado y coherencia temporal para el registro de eventos biológicos

**CU-05 · RF-39 — Registro de Eventos Biológicos (base).**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-075) Rechazar evento sobre CERRADO/BAJA · (TC-M02-076) Rechazar fecha de evento inválida |
| Tipo | Validación |
| Herramienta | API — Postman |
| Endpoints | `POST /activos-biologicos/{id}/eventos/sanitario` (representativo, ver TC-M02-G39 para justificación) |
| Responsable | Juan Manuel · Prioridad Alta |

## Resultado: TC-M02-075 PASS · TC-M02-076 PASS en negocio, discrepancia menor de código HTTP

**9/11 assertions PASS.** Detalle completo en `RESULTADOS/TC-M02-G40_resultado.md`.

### Precondición de TC-M02-075 — cómo se preparó (autorizado explícitamente por el usuario)

Llevar un activo a CERRADO por la API normal está bloqueado por **dos defectos ya reportados**, ninguno relacionado
con RF-39: `POST /{id}/cierre` (RF-38) exige una fase productiva activa, imposible de crear hoy por
**INC-M02-37-01**; `POST /eventos/baja` (RF-45) falla por el bug de mayúsculas en un trigger, **INC-M02-45-02**.
Con autorización explícita del usuario, se insertó directamente (con `COMMIT` real, no de prueba) un registro en
`modulo2.historicos_estados_activos` (`id_estado_nuevo=5` CERRADO, `modulo_origen='RF-38'`), dejando que el propio
trigger `trg_fn_sincronizar_estado_activo` sincronizara `activos_biologicos.id_estado` — el mismo mecanismo que
usaría la aplicación si RF-38 funcionara. No se modificó código ni se corrigieron los bugs; es exclusivamente una
preparación de datos para poder ejecutar este caso.

### TC-M02-076 — discrepancia de código HTTP (400 documentado vs. 422 real)

El **comportamiento de negocio es correcto en los dos casos**: la fecha futura y la fecha anterior al registro del
activo se rechazan, y el segundo mensaje coincide **palabra por palabra** con el que documenta la ficha ("La fecha
del evento es inválida o inconsistente con el historial."). La única discrepancia es el código HTTP: el use case
(`_event_validations.py`) usa `BusinessRuleError`, que en este proyecto mapea a **422** (documentado así en
`CLAUDE.md`: "BusinessRuleError → 422 → Violación de regla de negocio"), no a 400 como dice la ficha del caso. No
se trata como incidente porque el código sigue de forma consistente su propia convención documentada — es una
imprecisión de la ficha de prueba (400 vs. 422 para "regla de negocio violada"), no una inconsistencia del sistema.
Se dejó la assertion codificando el 400 literal de la ficha para que quede visible en el reporte.

### GIVEN / WHEN / THEN

| Caso | GIVEN | WHEN | THEN esperado (RF) | Resultado real |
|---|---|---|---|---|
| TC-M02-075 | Activo en CERRADO (preparado vía BD, ver arriba) | `POST /eventos/sanitario` | 409, mensaje sobre estado | **409, mensaje exacto — PASS** |
| TC-M02-076 (futura) | Activo ACTIVO recién creado | `POST /eventos/sanitario` con fecha 2027 | 400 | **422 `FECHA_FUTURA`, mensaje correcto** |
| TC-M02-076 (anterior) | Mismo activo | `POST /eventos/sanitario` con fecha 2025-01-01 | 400, mensaje exacto | **422 `FECHA_ANTERIOR_REGISTRO`, mensaje idéntico al documentado** |

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`. Activos: `213` (CERRADO, preparado vía BD) · `215` (ACTIVO, fresco).
- Newman 6.2.2 + htmlextra 1.23.1. Fecha de ejecución: 2026-09-10.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-39/TC-M02-G40
newman run TC-M02-G40.postman_collection.json -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G40.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G40.html \
  --suppress-exit-code
```

El activo 213 (CERRADO) es un dato de precondición persistente en TEST, no se recrea en cada corrida — la
colección solo lo verifica (paso "0B"). El paso "2A" sí crea un activo nuevo en cada ejecución.
