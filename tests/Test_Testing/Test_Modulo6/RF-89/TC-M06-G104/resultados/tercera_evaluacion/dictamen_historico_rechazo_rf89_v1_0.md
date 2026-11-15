# TC-M06-29 — Dictamen verificación lectura (Administrador)

> **Antecedente histórico (no borrado).**  
> Dictamen **vigente**: **APROBADO (alcance delimitado)** — `DICTAMEN_DEFINITIVO_TC_M06_29.md` · `../estado_oficial_G104.json`.  
> Este RECHAZADO corresponde a la evaluación con criterios **RF-89 v1.0** (`SIN_PRECIO_VIGENTE` y RF-88 / `PRECIO_REFERENCIA_VENCIDO`), **retirados por RFC-024 C24.5**.  
> CA-8 (aviso Contador) no estaba demostrado entonces ni ahora; quedó como validación complementaria pendiente.

## Resultado histórico: **RECHAZADO**

Las 4 GET del procedimiento cumplen (precio 492 VENCIDO sin reemplazo aplicado; activo 1644/rec 533; periodo 266 ABIERTO; simulacion SIN_PRECIO). No se declara APROBADO porque no hay evidencia del estado SIN_PRECIO_VIGENTE (no existe en API/RFC-024) ni de activacion automatica del flujo RF-88 / PRECIO_REFERENCIA_VENCIDO.

### Sesión
- Rol obtenido: **Administrador**
- Permisos lectura: {"cierre_periodo": true, "precios_mercado": true, "valoracion_activos": true}

### Consultas (procedimiento)

| # | Ruta | HTTP | Criterio procedimiento |
|---|---|---:|---|
| 1 | GET /finanzas/precios?id_especie=544 | 200 | True |
| 2 | GET /finanzas/activos/1644 | 200 | True |
| 3 | GET /finanzas/periodos?numero_id_tributaria=900000104 | 200 | True |
| 4 | GET /finanzas/activos/1644/simulacion | 200 | True |

### Hallazgos clave
- Precio 492: estado VENCIDO, vencimiento 2026-11-10, es_aplicado False
- Otros aplicados especie 544: []
- Simulación: motivo SIN_PRECIO, es_valido False
- SIN_PRECIO_VIGENTE: no existe en API
- Auditoría PRECIO_REFERENCIA_VENCIDO: HTTP 200, total 0
- Notificaciones relacionadas precio (página 1): 0

### G104 consolidado
| Subcaso | Estado |
|---|---|
| TC-M06-25 | APROBADO |
| TC-M06-26 | APROBADO |
| TC-M06-29 | RECHAZADO |
| Grupo | No aprobado completo |

Sin escritura funcional. Secretos no persistidos. Sin commit/push.
