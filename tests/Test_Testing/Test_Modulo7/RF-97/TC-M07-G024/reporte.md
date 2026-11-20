# TC-M07-G024 — Generación del envelope y estructura (CA-1, 5.4, RNF-97.4)

**Estado:** Ejecutado en vivo, confirmado correcto.
**Fecha:** 2026-11-17/18. **Entorno:** TEST.
**Evidencia completa:** la petición y el script de prueba viven en la colección compartida
`tests/Test_Testing/Test_Modulo7/RF-97-Verificacion-Live/tc_m07_rf97_live.postman_collection.json`
(carpeta "TC-M07-G024 - Estructura del envelope (CA-1)"), con el reporte HTML completo en
`RF-97-Verificacion-Live/resultados/resultado_live_rf97.html`. Este archivo extrae la parte
específica de G024 para que quede evidencia también en esta carpeta.

## Petición real

```
GET {{base_url}}/integracion/aaef/vista-previa/productores/901444215?desde=2026-10-01&hasta=2026-10-31
Authorization: Bearer <token del Contador>
```

## Respuesta real (200 OK, recortada)

```json
{
  "metadata": { "ExchangeId": "AF-SIGAB-2026-10-3972113", "GeneratedAt": "2026-11-18", "...": "..." },
  "summary": { "TotalDocuments": 3, "TotalInvoices": 3, "TotalTransactions": 0, "...": "..." },
  "invoices": [ "...3 documentos, ver TC-M07-G014/G018..." ],
  "transactions": []
}
```

Headers de respuesta confirmados: `X-Content-SHA256` y `X-Version-Contrato-AAEF: 2.1` presentes.

## Aserciones ejecutadas (todas en verde)

| # | Aserción | Resultado |
|---|---|---|
| 1 | `200 OK` | ✅ |
| 2 | `X-Content-SHA256` presente | ✅ |
| 3 | `X-Version-Contrato-AAEF` presente | ✅ |
| 4 | Exactamente las 4 secciones: `metadata`, `summary`, `invoices`, `transactions` (sin claves adicionales) | ✅ |
| 5 | `transactions` es siempre lista vacía | ✅ |
| 6 | `metadata` tiene exactamente las claves sensibles a mayúsculas de 5.4 (`ExchangeId`, `GeneratedAt`, `GeneratedBy`, `RequestedPeriod`, `SourceSystem`, `StandardVersion`) | ✅ |
| 7 | `Description` conserva tildes/eñes sin corrupción (`Activo biológico`, no `Activo biolÃ³gico`) | ✅ |

## Conclusión

CA-1 y 5.4 se cumplen con datos reales de TEST (NIT 901444215, período 627). El envelope es JSON
UTF-8 válido, con el esquema exacto de 4 secciones, sin campos adicionales residuales de la v2.0
(paginación, estados). RF-95 recibe correctamente envelope, hash, ExchangeId, versión aplicada y
request_id (confirmado por lectura de `gateway_aaef._cabeceras()`).

Sin hallazgos en este TCG.
