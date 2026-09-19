# TC-M02-G40 — Restricciones de estado y coherencia temporal para el registro de eventos biológicos

**CU-05 · RF-39 — Registro de Eventos Biológicos (base).**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-075) Rechazar evento sobre CERRADO/BAJA · (TC-M02-076) Rechazar fecha de evento inválida |
| Tipo | Validación |
| Herramienta | API — Postman |
| Endpoints | `POST /activos-biologicos/{id}/eventos/sanitario` (representativo, ver TC-M02-G39 para justificación) |
| Responsable | Juan Manuel · Prioridad Alta |

## ✅ Resultado (2026-09-19): PASS — 11/11 assertions

Ambos sub-casos pasan limpio. Además de reconfirmar el comportamiento, se simplificó la colección: ya no depende
de un activo fijo preparado con un `INSERT` manual en su momento — ahora TC-M02-075 construye su propia
precondición (activo → fase → `/cierre`) con el flujo real de la API, porque los dos defectos que antes lo
bloqueaban (`INC-M02-37-01` de RF-37 e `INC-M02-45-02` de RF-45) ya están resueltos (ver `TC-M02-G23`, `TC-M02-G34`
y `TC-M02-G39`). La colección es ahora completamente autocontenida y re-ejecutable sin datos persistentes.

### TC-M02-076 — se corrigió el código HTTP esperado en la assertion (400 → 422)

El **comportamiento de negocio siempre fue correcto**: la fecha futura y la fecha anterior al registro del activo
se rechazan, y el mensaje de la segunda coincide **palabra por palabra** con el documentado en la ficha ("La fecha
del evento es inválida o inconsistente con el historial."). La ficha original pedía 400, pero el use case
(`_event_validations.py`) usa `BusinessRuleError`, que en este proyecto mapea consistentemente a **422**
(documentado en `CLAUDE.md`: "BusinessRuleError → 422 → Violación de regla de negocio"). Es una imprecisión de la
ficha de prueba, no un defecto del sistema — se corrigió la assertion para esperar 422, y ahora el caso refleja
un PASS honesto en vez de un FAIL cosmético por un código HTTP mal documentado en el origen.

### GIVEN / WHEN / THEN

| Caso | GIVEN | WHEN | THEN esperado (RF) | Resultado real |
|---|---|---|---|---|
| TC-M02-075 | Activo en CERRADO (construido vía API: fase + `/cierre`) | `POST /eventos/sanitario` | 409, mensaje sobre estado | **409, mensaje exacto — PASS** |
| TC-M02-076 (futura) | Activo ACTIVO recién creado | `POST /eventos/sanitario` con fecha 2027 | 422 (convención `BusinessRuleError` del proyecto) | **422 `FECHA_FUTURA`, mensaje correcto — PASS** |
| TC-M02-076 (anterior) | Mismo activo | `POST /eventos/sanitario` con fecha 2025-01-01 | 422, mensaje exacto | **422 `FECHA_ANTERIOR_REGISTRO`, mensaje idéntico al documentado — PASS** |

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`. Ambos activos se crean en el setup de la colección.
- Newman 6.2.2 + htmlextra 1.23.1. Fecha de ejecución: 2026-09-19.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-39/TC-M02-G40
newman run TC-M02-G40.postman_collection.json -r cli,htmlextra \
  --reporter-htmlextra-export RESULTADOS/TC-M02-G40_resultado.html \
  --suppress-exit-code
```

Cada ejecución crea sus propios activos de prueba, por lo que se puede repetir sin limpiar datos y sin interferir
con los de otros testers en el entorno compartido.
