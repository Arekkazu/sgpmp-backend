# Matriz de verificaciones — TC-M06-G97

**Fecha:** 2026-11-14  
**Fuente de contrato:** `ConsultarDepreciacionUseCase` + router M06 en `origin/dev` (`4f3d4962`)  
**Ejecución funcional:** no realizada

---

## TC-M06-09 — Depreciación lineal consultable

| # | Paso | Solicitud / acción | Aserción | Estado preparación |
|---|---|---|---|---|
| 09-P0 | Auth | `POST /sesiones/` Contador | Token; permiso `valoracion_por_costo` R | Pendiente ejecución |
| 09-P1 | Precondición | Identificar activo al costo con `costos_adquisicion=12000000`, `vida_util_meses=72`, fecha adquisición conocida | Activo **real** en TEST (ID por confirmar; no inventar) | **PENDIENTE DE DATOS** |
| 09-B1 | Baseline | `GET /finanzas/activos/{id}` | `valoracion_costo` activa; anotar costo, vida, `depreciacion_acumulada` registrada, fecha adquisición | Pendiente |
| 09-E1 | Consulta | `GET /finanzas/activos/{id}/depreciacion?fecha={adquisicion+12m}` | HTTP **200** | Preparado (endpoint existe en OpenAPI TEST) |
| 09-A1 | Campos | Respuesta | `depreciacion_anual == 2000000` | Preparado |
| 09-A2 | Campos | Respuesta | `depreciacion_acumulada == 2000000` (a 12 meses) | Preparado |
| 09-A3 | Campos | Respuesta | `valor_contable == 10000000` (sin deterioro distinto) | Preparado |
| 09-A4 | Campos | Respuesta | `depreciacion_registrada` = valor ya contable en valoración (0 si no hubo cierres) | Preparado |
| 09-A5 | Coherencia | Respuesta | `vida_util_meses=72`, `meses_transcurridos=12`, `depreciacion_mensual≈166666.6667` | Preparado |
| 09-A6 | Side-effect | `GET /finanzas/activos/{id}` después | `depreciacion_acumulada` **persistida** sin cambio (consulta no registra) | Preparado |
| 09-N1 | Negativo | Activo a VR / sin valoración costo | 404 `VALORACION_COSTO_NO_ENCONTRADA` | Documentado en código |

**Payload GET:** sin body. Query `fecha=AAAA-MM-DD` (IANA vía `X-Zona-Horaria: America/Bogota`).

---

## TC-M06-08 — Vida útil obligatoria (dos caminos)

### Camino A — Reconocimiento al costo

| # | Paso | Acción | Aserción | Notas |
|---|---|---|---|---|
| 08A-P1 | Datos | Activo elegible a costo cuya **especie** no tenga `vida_util_meses` | Preparación **autorizada** (no alterar especies compartidas sin permiso) | PENDIENTE AUTORIZACIÓN / DATOS |
| 08A-E1 | Escritura* | Flujo de propuesta + `POST /finanzas/reconocimientos/{id}` (o use case confirmar) | HTTP **422** `VIDA_UTIL_NO_CONFIGURADA` | *Requiere autorización — no ejecutar en esta fase |
| 08A-V1 | Lectura | Propuesta previa | Puede mostrar bloqueo `VIDA_UTIL_NO_CONFIGURADA` | Solo lectura posible |

### Camino B — Consulta sobre registro histórico sin vida útil

| # | Paso | Acción | Aserción | Notas |
|---|---|---|---|---|
| 08B-P1 | Datos | Registro `valoraciones_por_costos.vida_util_meses` NULL **y** especie sin vida | Solo si existe fixture autorizado; el test de integración lo simula con SQL | PENDIENTE AUTORIZACIÓN / DATOS |
| 08B-E1 | Lectura | `GET .../depreciacion?fecha=…` | HTTP **422** `VIDA_UTIL_NO_CONFIGURADA` | Preparado en contrato |
| 08B-C1 | Cierre (opcional / no G97 core UI) | Prevalidar/cerrar período con ese activo | Bloqueo `VIDA_UTIL_NO_CONFIGURADA` → execute **422** `CIERRE_BLOQUEADO` | Escritura de cierre — autorización aparte |

---

## Precondiciones — clasificación

| Ítem | Clasificación |
|---|---|
| Endpoint en OpenAPI TEST | **Existente / verificado (lectura)** |
| Código en `origin/dev` y `origin/test` | **Existente / verificado (git)** |
| Código en workspace `laura` | **No disponible** (actualizar rama) |
| Activo 12M / 72 meses en TEST | **No verificado** → preparación o selección autorizada |
| Especie sin vida útil aislada | **Requiere autorización** |
| Histórico sin vida útil | **Requiere autorización** / puede no existir |
| GET autenticado TC-M06-09 | **Pendiente ejecución** (no es escritura) |
| POST reconocimiento TC-M06-08 | **Pendiente autorización** |

---

## Qué no es evidencia de aprobación

- Cierre de issue #1114.  
- Merge de #1121.  
- Presencia del path en OpenAPI.  
- Test de integración del PR (esquema local, no TEST compartido).
