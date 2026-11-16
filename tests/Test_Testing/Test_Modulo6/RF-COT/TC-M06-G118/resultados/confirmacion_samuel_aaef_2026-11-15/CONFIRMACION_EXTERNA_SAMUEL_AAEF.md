# Confirmación externa — Samuel / canal AAEF (G118)

**Fecha de registro documental:** 2026-11-15  
**Fuente:** comunicación de **Samuel** (no es una ejecución realizada por Cursor).  
**Grupo:** TC-M06-G118 · RF-COT / canal AAEF  
**Ambiente referido:** TEST (`api-sgpmp-test`)

> Esta carpeta documenta **confirmaciones externas**. No contiene capturas HTTP generadas por Cursor, ni secretos, ni enlaces de entrega de credenciales.

---

## 1. Rotación de credencial (reportado por Samuel)

| Campo | Valor confirmado |
|---|---|
| Cliente QA | `QA_M06_AAEF_CONSULTA` |
| ID cliente | `5` |
| Estado cliente | **ACTIVO** |
| Credenciales activas | **1** (única) |
| Secreto anterior (WhatsApp) | **Revocado** |
| Comportamiento del secreto anterior | `401 CREDENCIALES_INVALIDAS` |
| Vencimiento | **2026-11-27** |
| Canal único | `CONSULTA_AAEF` |
| Canal M2M | **No** |

### Variables locales (instrucción operativa)

Configurar **solo** en `.env` local (no versionar, no publicar):

- `QA_AAEF_CLIENT_ID`
- `QA_AAEF_CLIENT_SECRET`
- `QA_AAEF_EMAIL`

En esta sesión de Cursor las tres variables **no** estaban presentes en el entorno del proceso (`false` al inspeccionar presencia, sin leer valores). Eso no contradice la confirmación de Samuel: el `.env` local puede existir fuera del proceso.

---

## 2. Validaciones del canal externo (ejecutadas por Samuel)

### 2.1 Token

| Ítem | Reportado por Samuel |
|---|---|
| Método / ruta | `POST /integraciones/agrofusion/token` |
| Resultado | Token obtenido correctamente |
| `expires_in` | `900` |

### 2.2 Consulta positiva — NIT 901333217

| Ítem | Reportado por Samuel |
|---|---|
| Método / ruta | `GET /integracion/aaef/productores/901333217?desde=2026-11-01&hasta=2026-11-30` |
| HTTP | **200** |
| Documentos | **2** · tipo **02** |
| Document IDs | `COS-4476-20261114`, `COS-4477-20261114` |
| Total bruto / neto | **$530.000** |
| Transactions | **0** |

### 2.3 Consulta negativa — NIT 900000003 / período 220

| Ítem | Reportado por Samuel |
|---|---|
| Método / ruta | Mismo patrón GET para NIT `900000003` |
| HTTP | **422** |
| Código | `PERIODO_NO_CERRADO` |
| Período 220 | Continúa **ABIERTO** |

---

## 3. Contraste con evidencias Cursor previas (2026-11-15)

| Componente | Evidencia Cursor (reevaluación fixture) | Confirmación Samuel |
|---|---|---|
| Vista previa Contador 901333217 | HTTP 200 · 2 docs tipo 02 · COS-4476/4477 · $530.000 · tx 0 | Coherente (canal externo con mismos documentos/totales) |
| Negativo 900000003 / 220 | HTTP 422 `PERIODO_NO_CERRADO` · 220 ABIERTO | Coherente |
| Auth externa (token + GET productores) | **No ejecutada** por Cursor (env ausente / sin secreto WhatsApp) | **Confirmada por Samuel** con credencial rotada |
| TC-M06-50 | Pendiente de autorización | Sin cambio |

Fuentes Cursor previas (intactas):

- `../reevaluacion_fixture_aaef_2026-11-15/`
- `../preparacion/solicitud_post_preparada_G118.json`

---

## 4. Impacto en el dictamen G118

| Escenario | Estado tras esta confirmación |
|---|---|
| Fixture / vista previa Contador | Sigue **CUMPLE** (evidencia Cursor) |
| Auth externa AAEF | **CUMPLE por confirmación externa** (Samuel); no reejecutada aquí |
| Negativo período 220 | Sigue **CUMPLE** |
| TC-M06-50 | **PENDIENTE DE AUTORIZACIÓN** |
| G118 global | **NO APROBADO** (bloquea TC-M06-50) |

No se ejecutó POST de cotización. No se modificó el activo 1571 ni se cerró el período 220.
