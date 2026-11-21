# TC-M07-G026 — Sección summary (CA-8, 5.4)

**Estado:** Ejecutado en vivo, confirmado correcto, sin hallazgos.
**Fecha:** 2026-11-17/18. **Entorno:** TEST.
**Evidencia completa:** colección compartida
`RF-97-Verificacion-Live/tc_m07_rf97_live.postman_collection.json` (carpeta "TC-M07-G026 -
Summary (CA-8)"), reporte HTML en `RF-97-Verificacion-Live/resultados/resultado_live_rf97.html`.
**Re-ejecutado 2026-11-20** filtrando solo esta carpeta con Newman, reporte propio en
`resultados/resultado_TC-M07-G026.html`/`.json` (6/6 aserciones, mismo resultado).

## Petición real

```
GET {{base_url}}/integracion/aaef/vista-previa/productores/901444215?desde=2026-10-01&hasta=2026-10-31
```

## summary real devuelto (NIT 901444215, período 627, octubre 2026)

```json
{
  "TotalDocuments": 3,
  "TotalInvoices": 3,
  "TotalTransactions": 0,
  "TotalGrossAmount": 740000.0,
  "TotalNet": 740000.0,
  "Currency": "COP"
}
```

Los 3 documentos reales que lo componen: `COS-4485-20261008` (380.000), `COS-4486-20261021`
(210.000), `COS-4487-20261027` (150.000) — suma real: 740.000.

## Aserciones ejecutadas (todas en verde)

| # | Aserción | Resultado |
|---|---|---|
| 1 | `TotalDocuments = TotalInvoices = len(invoices)` (3) | ✅ |
| 2 | `TotalTransactions` siempre 0 | ✅ |
| 3 | `TotalGrossAmount = Σ Totals.Subtotal` de los 3 documentos reales (740.000) | ✅ |
| 4 | `TotalNet = TotalGrossAmount` (RF-96 fija `TotalPayment = Subtotal`) | ✅ |
| 5 | `Currency = "COP"` | ✅ |

## Conclusión

El resumen cuadra exactamente con los documentos reales del período, sin error de redondeo
(verificado con aritmética decimal, no de punto flotante, sobre los 3 montos reales). CA-8 se
cumple sin hallazgos.
