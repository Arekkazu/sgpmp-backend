# TC-M07-G027 — Rango alineado a períodos cerrados (5.1, CA-2, CA-3, FA-1, FA-2)

**Estado:** Ejecutado en vivo, confirmado correcto, sin hallazgos.
**Fecha:** 2026-11-17/18. **Entorno:** TEST.
**Evidencia completa:** colección compartida
`RF-97-Verificacion-Live/tc_m07_rf97_live.postman_collection.json` (carpeta "TC-M07-G027 - Rango
y periodos (negativos)"), reporte HTML en
`RF-97-Verificacion-Live/resultados/resultado_live_rf97.html`.

## Casos ejecutados contra NIT real 901444215

### Caso 1 — CA-2: `desde` a mitad de mes

```
GET .../vista-previa/productores/901444215?desde=2026-10-05&hasta=2026-10-31
```
**Respuesta real:** `422 Unprocessable Entity`
```json
{"error_code": "RANGO_NO_ALINEADO", "message": "..."}
```
✅ Confirmado: `422` con `RANGO_NO_ALINEADO`.

### Caso 2 — CA-3: rango con un período abierto al final

```
GET .../vista-previa/productores/901444215?desde=2026-10-01&hasta=2026-11-30
```
**Respuesta real:** `422 Unprocessable Entity`, `error_code: "RANGO_NO_ALINEADO"`.
✅ Confirmado: `422` controlado (noviembre no es un período mensual cerrado de este titular en el
mismo formato que exige el rango).

### Caso 3 — Rango invertido (`desde > hasta`)

```
GET .../vista-previa/productores/901444215?desde=2026-10-31&hasta=2026-10-01
```
**Respuesta real:** `400 Bad Request`
```json
{"error_code": "PARAMETROS_INVALIDOS", "message": "..."}
```
✅ Confirmado: `400` controlado, **nunca 500**.

## Aserciones ejecutadas (todas en verde)

| # | Aserción | Resultado |
|---|---|---|
| 1 | `desde` no alineado → `422 RANGO_NO_ALINEADO` | ✅ |
| 2 | Período intermedio/final no cerrado → `422` (`RANGO_NO_ALINEADO` o `PERIODO_NO_CERRADO`) | ✅ |
| 3 | `desde > hasta` → `400 PARAMETROS_INVALIDOS`, nunca `500` | ✅ |

## Conclusión

Las tres validaciones de rango responden con códigos 4xx controlados y mensajes legibles, nunca
un error de servidor. No se pudo ejercitar en vivo el caso de periodicidad trimestral ni el de
"mes sin período abierto" (requieren un titular con esa configuración específica, no disponible
en esta sesión) — quedan sin verificar, no confirmados como fallidos ni como correctos.
