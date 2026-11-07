<!--
| Fecha      | Nombre   | Que se hizo |
|------------|----------|-------------|
| 2026-11-06 | Arekkazu | M07 RF-AE02: Anexo de Mapeo AAEF v3.0 (forma 1) |
-->
# Anexo de Mapeo AAEF v3.0 — SGPMP → AgroFusion → SIGCON

**Código del anexo:** `AAEF-ANEXO-3.0` · **Versión:** 3.0 · **Estado:** BORRADOR (la aprobación vive en el sistema, RF-AE02 5.8)
**Contratos que lo usan:** 3.0 (solo facturas de compra `02`) y 3.1 (agrega el comprobante NIC 41 `06`).

Este documento es la forma 1 del anexo (RF-AE02). La forma 2 es su registro en el sistema
(`POST /integracion/anexos`) con el SHA-256 de este archivo:

```bash
sha256sum docs/integracion/anexo_aaef_v3.0.md
```

Cualquier cambio a este archivo es una versión nueva del anexo: cambia el hash y hay que registrarlo de nuevo.

## 1. Reglas generales

| Regla | Valor |
|---|---|
| Consulta | `GET /integracion/aaef/productores/{NIT}?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` con el token de canal |
| Rango | Empieza el primer día y termina el último día de períodos contables **cerrados** del titular |
| Documentos | Solo `02` (factura de compra) y, con el contrato 3.1, `06` (comprobante NIC 41). Nunca `01`, `03`, `04` ni `05` |
| Fechas | `AAAA-MM-DD`, sin hora |
| Importes | 2 decimales por truncamiento (sin redondeo); números JSON |
| Estado | `Header.Status = "ACTIVE"` siempre; las correcciones son hechos de ajuste en un período abierto |
| Impuestos | `Taxes = []`; `TotalVAT`, `TotalWithholdings` y `TotalDiscounts` = 0 |
| Cuadre | `TotalPayment = Subtotal = Σ Lines[].Value` con diferencia 0,00 |
| `transactions` | Siempre `[]`: SGPMP no registra pagos, anticipos ni reembolsos |
| Integridad | `X-Content-SHA256` = SHA-256 de `{"invoices", "transactions"}` canónico (claves ordenadas, importes como texto de 2 decimales, `invoices` por `DocumentId`) |
| Tamaño | Máximo 20 MB (límite de SIGCON por lote); si se supera, consultar un rango menor |

## 2. `metadata` y `summary`

| Campo | Origen / regla |
|---|---|
| `metadata.ExchangeId` | `SGPMP-{NIT}-{desde AAAAMMDD}-{hasta AAAAMMDD}-{7 dígitos}`; AgroFusion reemplaza el último segmento |
| `metadata.GeneratedAt` | Fecha de generación (UTC) |
| `metadata.StandardVersion` | `"1.0"` (estándar AAEF que acepta SIGCON; no es la versión del contrato) |
| `metadata.RequestedPeriod.From` / `.To` | `desde` / `hasta` |
| `metadata.SourceSystem.SystemId` / `.SystemName` | `"SGPMP"` / `"SIGAB"` |
| `metadata.SourceSystem.SystemNIT` | NIT del titular, sin dígito de verificación (SIGCON lo usa para elegir la empresa) |
| `metadata.SourceSystem.Environment` | `DEV`, `TEST` o `PROD` (variable `SGPMP_ENTORNO`) |
| `metadata.GeneratedBy` | Correo del usuario que consulta |
| `summary.TotalDocuments` = `summary.TotalInvoices` | `len(invoices)` |
| `summary.TotalTransactions` | `0` |
| `summary.TotalGrossAmount` / `summary.TotalNet` | `Σ Totals.Subtotal` / `Σ Totals.TotalPayment` |
| `summary.Currency` | `"COP"` |

## 3. Tipo `02` — Factura de compra

**Origen:** costos de Finanzas con proveedor (`origen_costo` COMPRA_PROVEEDOR o SERVICIO_TERCERO), naturaleza
mantenimiento o inversión, estado registrado, sin reversos, cuyo **período contable** está en el rango.

**Un documento por factura** (NIT del proveedor + prefijo + número) y **una línea por registro**: cuando un costo se
reparte entre varios activos, M06 guarda un registro por activo con la misma factura, y SIGCON rechaza una segunda
factura con el mismo número de proveedor en la empresa.

| Campo | Origen / regla |
|---|---|
| `Header.DocumentId` | `COS-{menor id de registro de la factura}-{fecha de la factura AAAAMMDD}` |
| `Header.Prefix` / `Header.Serial` | Prefijo / número de la factura del proveedor. Sin prefijo, `Prefix = ""` (SIGCON usa solo el número) |
| `Header.Type` | `{"Code": "02", "Name": "Factura de compra"}` |
| `Header.IssueDate` = `Header.UpdatedAt` | Fecha de la factura |
| `Header.DueDate` | Vencimiento de la factura (igual a la emisión si es de contado) |
| `ThirdParty.NIT` / `.Name` | NIT (sin DV) y razón social del proveedor; SIGCON lo crea si no existe |
| `Totals.Subtotal` = `TotalPayment` = `OutstandingBalance` | Suma de las líneas |
| `Lines[i].Code` = `.LineType` | Subtipo del costo (`ALIMENTO`, `VETERINARIO`, …) |
| `Lines[i].Name` / `.Description` | Nombre del subtipo / `Activo biológico {identificador}` |
| `Lines[i].accounting_account` | `[cuenta débito]` — 1 elemento, de la matriz contable; la cuenta crédito (proveedores) la fija SIGCON |
| `Lines[i].Quantity` / `.UnitPrice` / `.Value` | `1` / monto del registro / monto del registro |

## 4. Tipo `06` — Comprobante contable NIC 41 (solo contrato 3.1)

**Origen:** comprobantes del cierre del período (uno por titular × tipo de hecho × especie) cuya fecha cae en el rango.
**Condición externa:** SIGCON debe aceptar el tipo `06`; hoy solo acepta `01`–`05`.

| Campo | Origen / regla |
|---|---|
| `Header.DocumentId` | `NIC-{NIT}-{AAAAMM}-{TIPO_HECHO}-{id de especie}` (código del comprobante) |
| `Header.Prefix` / `Header.Serial` | `"NIC"` / `{AAAAMM}-{TIPO_HECHO}-{id de especie}` |
| `Header.Type` | `{"Code": "06", "Name": "Comprobante contable NIC 41"}` |
| `Header.IssueDate` = `DueDate` = `UpdatedAt` | Último día del período |
| `ThirdParty.NIT` / `.Name` | NIT y razón social del propio titular |
| `Totals.Subtotal` = `TotalPayment` | Suma de las líneas; `OutstandingBalance = 0` |
| `Lines[i]` | Una por par de cuentas distinto: `Code` = `LineType` = tipo de hecho, `Name` = nombre del hecho, `Description` = especie y período |
| `Lines[i].accounting_account` | `[cuenta débito, cuenta crédito]` — 2 elementos; `Value > 0` (el sentido lo dan las cuentas) |

## 5. Tipos y documentos excluidos

SGPMP no genera `01` (ventas), `03` (honorarios), `04` (nota crédito) ni `05` (nota débito), ni envía el estado de
resultados, las revelaciones NIC 41 ni las cotizaciones de venta: SIGCON contabiliza todo documento que recibe.

## 6. Aprobación (RF-AE02 5.9–5.11)

1. **Borrador:** el Administrador registra el anexo con la ruta y el SHA-256 de este archivo.
2. **En revisión:** el Contador lo aprueba; el sistema corre antes la validación automática con datos de prueba
   (estructura contra el esquema de AgroFusion, cuadre, número de cuentas y formato de fechas).
3. **Aprobado:** tras la prueba en TEST — AgroFusion consulta sin error 502, el usuario transfiere a SIGCON, el ACK
   acepta el 100 % de los documentos y el Contador revisa los asientos — el Administrador registra la evidencia
   (`ExchangeId`, ACK, observaciones). Fuera de producción, un contrato puede activarse con el anexo en revisión para
   poder hacer esa prueba.
