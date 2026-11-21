# TC-M07-G025 — Sección metadata (CA-4, 5.4)

**Estado:** Ejecutado en vivo. 7/7 aserciones en verde, **2 hallazgos confirmados** (documentados
como aserciones a favor del comportamiento real, no como fallos de prueba).
**Fecha:** 2026-11-17/18. **Entorno:** TEST.
**Evidencia completa:** colección compartida
`RF-97-Verificacion-Live/tc_m07_rf97_live.postman_collection.json` (carpeta "TC-M07-G025 -
Metadata (CA-4)"), reporte HTML en `RF-97-Verificacion-Live/resultados/resultado_live_rf97.html`.
**Re-ejecutado 2026-11-20** filtrando solo esta carpeta con Newman, reporte propio en
`resultados/resultado_TC-M07-G025.html`/`.json` (10/10 aserciones, mismo resultado).

## Petición real

```
GET {{base_url}}/integracion/aaef/vista-previa/productores/901444215?desde=2026-10-01&hasta=2026-10-31
```

## metadata real devuelta

```json
{
  "ExchangeId": "AF-SIGAB-2026-10-3972113",
  "GeneratedAt": "2026-11-18",
  "StandardVersion": "1.0",
  "RequestedPeriod": {"From": "2026-10-01", "To": "2026-10-31"},
  "SourceSystem": {"SystemId": "SGPMP", "SystemName": "SIGAB", "SystemNIT": "901444215", "Environment": "DEV"},
  "GeneratedBy": "contador@pecuaria.co"
}
```

## Aserciones ejecutadas

| # | Aserción | Resultado |
|---|---|---|
| 1 | `GeneratedAt` en `YYYY-MM-DD` sin hora | ✅ |
| 2 | `StandardVersion` es el texto `"1.0"` | ✅ |
| 3 | `RequestedPeriod.From`/`To` coinciden con lo consultado | ✅ |
| 4 | `SourceSystem.SystemNIT` igual al NIT solicitado | ✅ |
| 5 | `GeneratedBy` es el correo del usuario que consulta | ✅ |
| 6 | El `ExchangeId` (nonce) cambia entre dos consultas del mismo rango | ✅ |
| 7 | El hash de contenido es el mismo aunque el `ExchangeId` cambie (CA-9) | ✅ |

## Hallazgos confirmados

1. **ExchangeId no sigue el formato de la ficha.** RF-97 5.4/CA-4 piden
   `SGPMP-{NIT}-{desde}-{hasta}-{nonce de 7 dígitos}`. El real es
   `AF-SIGAB-{AAAA-MM}-{nonce de 7 dígitos}` — confirmado por el commit `4353483f` (2026-11-14): el
   formato lo exige SIGCON, no el que describe el RF. No requiere corrección de código; sí
   actualizar la ficha.
2. **`SourceSystem.Environment` dice `"DEV"` en TEST.** Reportado como Issue 4 en el reporte de
   bugs de M07 (bug de configuración de despliegue, no de código — `SGPMP_ENTORNO` del contenedor
   de TEST está mal puesto).

## Conclusión

La estructura y el contenido de `metadata` cumplen CA-4/5.4 salvo los dos puntos de arriba, ya
reportados como issues separados.
