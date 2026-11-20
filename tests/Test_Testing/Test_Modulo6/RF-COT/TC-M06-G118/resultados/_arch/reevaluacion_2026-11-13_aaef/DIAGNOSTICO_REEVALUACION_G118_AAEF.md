# TC-M06-G118 — Diagnóstico de reevaluación AAEF (2026-11-13)

**Fase:** inspección y verificación de solo lectura  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Sesión:** Contador (`QA_CORREO` / `QA_CONTRASENA`)  
**Escrituras contables/admin:** no  
**Cierre de períodos:** no  
**Cotización TC-M06-50:** no  
**Commit/push:** no  

## 1. Contexto y alcance

G118 (RF-COT) prepara y valida la integridad alrededor de **TC-M06-50** (`POST /finanzas/cotizaciones` sobre activo **1571**) y la cadena AAEF (contrato, vista previa, canal externo).

Esta reevaluación se limita a:

1. Verificar las novedades reportadas por Samuel (contrato 2.1, titular QA, cliente externo).  
2. Ejecutar GET de lectura sobre contratos, anexos, períodos y vista previa.  
3. Documentar bloqueos reales (período 220, credencial de canal, RBAC clientes).  

**Fuera de alcance de esta fase:** POST de cotización, cierre del período 220, emisión de token de canal, rotación de secretos, modificación de contratos/clientes.

## 2. Estado inicial (antes de esta reevaluación)

| Fuente | Estado |
|---|---|
| `primera_evaluacion/` (2026-11-08) | BLOQUEADO — activo compartido 943; AAEF no consultado |
| `preparacion/` (2026-11-12/13) | PREPARADO_PENDIENTE_AUTORIZACION_POST — activo 1571; AAEF `CONTRATO_NO_ACTIVO` |
| `revalidacion_lectura_aaef_G118.*` | Contrato sin versión ACTIVO; canal sin credencial |

## 3. Novedades informadas por Samuel (no evidencia por sí solas)

- Contrato AAEF **2.1 / ID 3** ACTIVA desde 13/11/2026; anexo mapeo v2.0; transformador solo compras; 1.0 INACTIVA; 2.0 DEPRECADA.  
- Titular QA **900000003**, período **220** ABIERTO; vista previa debería pasar de `CONTRATO_NO_ACTIVO` a `PERIODO_NO_CERRADO`.  
- Referencia **900000002** con período noviembre cerrado → HTTP 200.  
- Cliente externo ID **5** `QA_M06_AAEF_CONSULTA`, canal `CONSULTA_AAEF`, 60/min, sin M2M; secreto temporal vía WhatsApp (**no usado ni reproducido**).

## 4. Verificaciones realizadas (evidencia API)

### 4.1 Contrato AAEF — **APROBADO**

`GET /integracion/contratos` + `GET /integracion/anexos`

| Esperado (Samuel) | Observado |
|---|---|
| Versión 2.1 | Sí |
| ID 3 | `id_version_contrato_aaef=3` |
| Estado ACTIVA | API: **ACTIVO** |
| Vigencia 13/11/2026 | `fecha_vigencia=2026-11-13` |
| Anexo mapeo v2.0 | `id_mapeo_anexo_aaef=2`, `version_anexo=2.0`, estado **APROBADO** |
| Solo transformador compras | `mapeadores=["COMPRAS"]` |
| 1.0 INACTIVA / 2.0 DEPRECADA | `INACTIVO` / `DEPRECADO` |
| Global (no por titular) | Sin campos de NIT/titular en la versión |

### 4.2 Cliente externo QA — **BLOQUEADO**

`GET /integracion/clientes` → **HTTP 403** con Contador (`clientes_externos` R no disponible en esta sesión).

No se pudo verificar por API: ID 5, código, canales efectivos, límite 60/min, ausencia de M2M ni vigencia 27/11/2026.

**Credencial de canal:** no hay `QA_AAEF_CLIENT_SECRET` / equivalentes en el entorno del agente. No se inventó ni se pegó el secreto de WhatsApp.  
`POST /integraciones/agrofusion/token` **no ejecutado**.

Prueba negativa segura: `GET /integracion/aaef/productores/900000003` sin token → **401** `NO_AUTENTICADO`.

### 4.3 Vista previa AAEF

Endpoint oficial: `GET /integracion/aaef/vista-previa/productores/{nit}?desde=&hasta=` (permiso `exportacion_contable` R).

| Titular | Período nov-2026 | HTTP | Código | Interpretación |
|---|---|---|---|---|
| 900000003 (QA) | 220 **ABIERTO** | 422 | `PERIODO_NO_CERRADO` | Desaparece `CONTRATO_NO_ACTIVO`; el bloqueo actual es el período. **No** implica paquete AAEF válido del titular QA. |
| 900000002 (ref.) | 219 **CERRADO** | 200 | — | Header `X-Version-Contrato-AAEF: 2.1`. Envelope con `metadata/summary/invoices/transactions` (0 invoices). **No** aprueba al titular QA. |

### 4.4 Transformación AAEF

| Tipo | Resultado |
|---|---|
| Configuración contrato (solo COMPRAS) | **APROBADO** |
| Estructura envelope (titular referencia, estática) | **APROBADO** (claves y versión 2.1) |
| Transformación funcional titular QA (compras/campos/anexo) | **BLOQUEADO** por `PERIODO_NO_CERRADO` |

No se inventaron campos del anexo: la validación integral de mapeo de compras del titular QA queda pendiente de período cerrado + evidencia de contenido.

## 5. Relación con TC-M06-50

La cotización **no** se ejecutó. Prerrequisitos pendientes:

1. Autorización expresa de `POST /finanzas/cotizaciones` (activo 1571).  
2. Si se exige AAEF del titular QA: autorización administrativa para **cerrar período 220** (no hecho aquí).  
3. Credencial de canal en variables de entorno seguras.  
4. Autorización de `POST /integraciones/agrofusion/token` solo para consulta.  
5. Sesión con `clientes_externos` R (o evidencia Admin) para cerrar verificación del cliente 5.

## 6. Bloqueos y riesgos

| ID | Impacto |
|---|---|
| PERIODO_220_ABIERTO | Impide paquete AAEF del titular QA |
| CREDENCIAL_CANAL_NO_DISPONIBLE | Impide RF-AE01 por canal |
| POST_TOKEN_CANAL_NO_AUTORIZADO | Emisión de token no ejecutada |
| CLIENTES_EXTERNOS_403 | Impide verificar permisos efectivos del cliente 5 |

**Riesgo de interpretación:** confundir HTTP 200 del NIT 900000002 con aprobación AAEF del titular QA / G118 completo.

## 7. Conclusión

**G118 no está APROBADO de forma completa.**

Lo verificado con evidencia:

- Contrato **2.1 / ID 3 ACTIVO**, anexo v2.0, solo COMPRAS.  
- Vista previa QA: **422 PERIODO_NO_CERRADO** (evolución correcta desde `CONTRATO_NO_ACTIVO`).  
- Vista previa referencia: **200** con contrato 2.1.

Lo pendiente/bloqueado:

- Permisos efectivos del cliente QA.  
- Autenticación de canal.  
- Transformación AAEF del titular QA.  
- Ejecución autorizada de TC-M06-50.

## 8. Evidencias de esta carpeta

- `evidencia_consultas_reevaluacion_G118.json`
- `estado_consolidado_G118.json`
- `matriz_trazabilidad_G118_aaef.md`
- `vista_previa_900000002_sanitizada.json`
- `INFORME_REEVALUACION_G118_AAEF.html`
- este diagnóstico
