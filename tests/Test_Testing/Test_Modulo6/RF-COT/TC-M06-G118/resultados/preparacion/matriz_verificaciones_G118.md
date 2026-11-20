# TC-M06-G118 / TC-M06-50 — Matriz de verificaciones (preparacion)

Endpoint autorizado (pendiente): `POST /finanzas/cotizaciones` con activo **1571**.

| Verificacion | Esperado tras registro |
|---|---|
| Estado del activo 1571 | Continua ACTIVO |
| Valor razonable neto | Sin modificaciones |
| Fecha del calculo vigente | Sin modificaciones |
| Lineas contables periodo 220 | Sin nuevas lineas |
| Asientos contables | Sin nuevos asientos |
| Exportaciones AAEF | Sin nuevas exportaciones |
| Cotizacion | Registrada (HTTP 201, estado COTIZADO) |
| Auditoria comercial | Evento `COTIZACION_REGISTRADA` |
| Periodo 220 | Continua ABIERTO |
| Periodo 219 | Continua CERRADO |

**POST no ejecutado en preparacion.**
