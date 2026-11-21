# 10 — Diagnóstico G94 tras integrar `origin/test` en `laura`

Fecha: 2026-10-10.  
**HEAD:** `ad55f049` (`laura` = `origin/test`, fast-forward desde `37efcd26`).  
**G94 sigue RECHAZADO.** No Cypress, no PATCH/POST/DELETE a TEST, no commit/push.  
Evidencias rev4/rev5 y archivos untracked de G94 **no se tocaron**.

---

## 1. Archivos y funciones relevantes (código actual)

| Pieza | Ruta | Rol |
|---|---|---|
| GET/POST/PATCH identidad | `src/configuration/infrastructure/routers/identidad_visual_router.py` | FastAPI RF-26 |
| GET vacío | `obtener_identidad_visual` → `return None` si no hay entidad | HTTP **200** con JSON `null` |
| Caso de uso GET | `.../obtener_identidad_visual_use_case.py` | `obtener_por_finca` |
| Repositorio | `.../repositories/identidad_visual_repository.py` | última versión por `id_finca`; `bloquear=` en PATCH |
| PATCH ausente | `actualizar_identidad_visual_use_case.py` | **404** `IDENTIDAD_VISUAL_NO_ENCONTRADA` |
| POST duplicado | `guardar_identidad_visual_use_case.py` | **409** si `obtener_por_finca` ve fila |
| Auditoría | `consultar_auditoria_identidad_visual_use_case.py` | **404** mismo código si GET no ve fila |
| Contexto RF-25 | `obtener_contexto_use_case.py` | misma `obtener_por_finca` sobre la finca del usuario |
| RBAC | `src/shared/rbac.py` `require_permission(23, 2)` | recurso `identidad_visual`, acción leer; exige admin |
| Auth / RLS sesión | `src/identity_access/infrastructure/dependencies.py` `get_current_user` + `declarar_identidad` | JWT → `app.current_user_id` |
| RLS F5 | `alembic/versions/bd9cea80dea6_f5_para_el_modulo9.py` | SELECT identidad por `fn_fincas_del_usuario` |
| Fincas del usuario | `modulo9.fn_fincas_del_usuario` (`315eaa6c5dc1`) | solo `usuarios_fincas` activos; **sin** bypass Administrador |
| Contrato documentado | `anotaciones/modulo_9/curls_m09_cu06_personalizar_interfaz.md` | GET: 200 objeto o **200 null**; PATCH/auditoría: 404 si no hay registro |
| Alta QA | `tests/.../TC-M09-G85/test_tc_m09_g85_rev2.py` | POST en finca **sin** identidad; **no hay DELETE** |

---

## 2. Cambios de los 282 commits que importan a G94

Diff `37efcd26..HEAD` en RF-26/RF-25/auth (no es un rediseño del GET):

- **Router identidad:** solo docstrings Swagger (`f986a0c1`). El `response_model=Optional[...]` y el `return None` **ya existían** antes del merge.
- **Repositorio:** `bloquear=True` + `FOR UPDATE` en edición concurrente (`9f479187`). El GET no usa `bloquear`.
- **`get_current_user`:** declara identidad RLS **antes** de la primera consulta (`88663f6f` / F4). Reduce 401/filas vacías por token invisible; **no** explica por sí solo un GET 200 autenticado.
- **F5 RLS (`bd9cea80dea6`, 2026-10-09):** sustituye  
  `pol_identidad_visuales_select … USING (true)`  
  por  
  `USING (id_finca IN (SELECT … fn_fincas_del_usuario(usuario_actual)))`.  
  Las políticas de **`fincas`** sí tienen `OR rol = Administrador`; las de **`identidad_visuales` no**.
- Tema personal/global: mismos use cases de RF-27; G94-179 parchea tema **personal** del productor (no el global). Sin cambio de contrato GET tema en este diff puntual.

Rev4 (2026-09-25) GET identidad admin finca 1 **sí** devolvió `#1A6B3C`. F5 es **posterior**. Rev5 (2026-10-10) corre contra TEST ya posiblemente migrado F5.

---

## 3. Contrato del GET vs comportamiento demostrable

### Contrato

| Operación | Si no hay identidad visible | Fuente |
|---|---|---|
| `GET /configuracion/identidad-visual/{id}` | **200 `null`** | curls CU06 L112; router `Optional` + `return None`; OpenAPI 401/403, no 404 |
| `GET .../auditoria` | **404** `IDENTIDAD_VISUAL_NO_ENCONTRADA` | use case + curls |
| `PATCH .../{id}` | **404** mismo código | use case + curls L187 |
| `POST /identidad-visual` | **409** si el GET ve fila | use case |
| `GET /interfaz/contexto` | `identidad_visual: null` si no hay finca o no hay fila **visible** | schema + use case |

**200 null en GET es el diseño documentado del Flujo A**, no un accidente de FastAPI.  
**No es equivalente a “la finca no tiene marca”** si RLS oculta la fila: GET, PATCH y auditoría usan el mismo `obtener_por_finca` y no distinguen “no existe” de “existe y no la ves”.

### Comportamiento rev5 (TEST, pre-merge local, ambiente ya en producción TEST)

Confirmado entonces (no se reconsultó TEST en esta fase):

- Admin `GET /identidad-visual/1` → 200 `null`.
- Admin `GET .../1/auditoria` → 404.
- Productor `GET /interfaz/contexto` → finca 1, `primary_color=#1A6B3C`.

En el código **actual**, contexto y GET RF-26 llaman al **mismo** repositorio. La única forma coherente de ese par de respuestas es: **la fila es visible bajo la identidad RLS del productor (finca 1 en `usuarios_fincas`) y no visible bajo la del admin.**

---

## 4. Explicación de `200 null` (certeza)

| Hipótesis | Certeza | Notas |
|---|---|---|
| GET 200 null = contrato cuando `obtener_por_finca` devuelve `None` | **Confirmado por código y curls** | No hace falta F5 para este contrato |
| La marca de Remanso **existe** (contexto productor) | **Confirmado por evidencia rev5** | No es “TEST sin identidad en absoluto” |
| Admin no ve la fila por RLS F5 (`fn_fincas_del_usuario` sin bypass Administrador) | **Inferencia razonable, pendiente de verificar en TEST** | Encaja con F5 (10-09), rev4 OK (09-25), rev5 null (10-10), auditoría 404 |
| Fila físicamente borrada y contexto “inventa” colores | **Improbable con este HEAD** | Contexto no tiene fallback `#1A6B3C`; solo pinta lo que el repo devuelve |
| Spec usa mal el path o el id | **No sostenido** | Path y `FINCA=1` coinciden con contexto `id_finca=1` y con rev4 |
| Actor incorrecto en GET | **Parcial** | Recurso 23 es **solo Administrador** (documentado). El productor no puede GET RF-26 (403). El spec **debe** usar admin para PATCH; el problema es visibilidad RLS, no el verbo |
| `TOKEN_REVOCADO` / 401 rev4 | **Sigue sin body** | Rev5 ni siquiera llegó al restore; esta fase no añade evidencia |

No se declara defecto de contraste RF-27. No se declara “no hay registro en BD” como hecho.

---

## 5. Precondiciones G94 (179)

El spec rev5 exige, con **admin**, snapshot GET identidad finca 1 = `#1A6B3C` y luego PATCH. Con **productor**, finca 1 y `theme_mode=2`.

| Precondición | Estado |
|---|---|
| Productor finca 1 + marca en **contexto** | Cumplida en rev5 |
| Admin ve y versiona esa identidad por **GET RF-26** | **No cumplida** en rev5 (200 null) |
| PATCH restaurable (version + fila visible) | **No** — PATCH también 404 si GET es None |
| POST para “crear” en finca 1 | **Prohibido como atajo:** si la fila existe y RLS la oculta, el 409 no dispara y se puede **insertar otra versión**; la API **no tiene DELETE** (G85 lo documenta) |
| Tema personal productor | Independiente; no se llegó a PATCH tema en rev5 |

G85 es el mecanismo **oficial de alta**: POST multipart en una finca **sin** identidad (p. ej. preferida 123), y el dato **queda**. No sirve para Remanso (finca 1) ni ofrece restore por borrado.

---

## 6. Distinción de causas

| Capa | Qué es | Qué no es |
|---|---|---|
| Backend GET 200 null | Contrato RF-26 Flujo A | No es bug por devolver null en vacío **visible** |
| Backend F5 SELECT identidad sin `OR Administrador` | Posible **defecto o decisión de alcance** si el admin debe gestionar cualquier finca (RF-26 “solo Administrador”) | No verificado en BD TEST (`usuarios_fincas` del admin) |
| Datos TEST | La marca vive para el productor | No está “ausente” en el sentido de contexto |
| Spec G94 | Endpoint, finca 1 y admin son los de rev4; aserción `body no nulo` es correcta como precondición | El spec no puede completar 179 mientras admin no vea la fila; **no** debe POST sobre finca 1 |
| 401 restore rev4 | Arnés / token | No reabierto aquí |

---

## 7. Recomendación para continuar

**No ejecutar Cypress 179** hasta una ventana de **solo lectura** que confirme:

1. `GET /configuracion/identidad-visual/1` admin → ¿sigue `null`?
2. `GET /configuracion/interfaz/contexto` productor → ¿sigue `#1A6B3C`?
3. Si (1) null y (2) color: **no PATCH ni POST** en finca 1. Tratar G94-179 como **BLOQUEADO** por visibilidad RLS/admin, no como fallo de contraste.
4. Verificación de producto (fuera de G94 o con autorización): ¿`admin@pecuaria.co` está en `usuarios_fincas` para finca 1? ¿F5 está aplicada en TEST?

**Corrección posible de producto (no aplicada):** política SELECT/UPDATE de `identidad_visuales` alineada con `fincas` (`OR Administrador`), si RF-26 exige que el administrador gestione cualquier finca. Eso no se implementa en esta fase.

**Corrección de spec (solo si TEST demuestra que admin sí ve otra finca con identidad):** no usar Remanso compartido; usar finca donde admin esté en `usuarios_fincas` **y** ya exista identidad; snapshot + PATCH + restore; nunca POST en finca 1. No bajar aserciones de variante/contraste/restore.

**178:** sigue valiendo solo el dashboard rev2; no aprueba el grupo.

---

## 8. Conclusión

- **Causa del HTTP 200 `null` del GET:** en código, `obtener_por_finca` devolvió `None` y el Flujo A **debe** responder 200 null. **Confirmado.**
- **Por qué el contexto sí trae `#1A6B3C`:** la identidad de finca 1 es visible al **productor**. **Confirmado en rev5.** En este HEAD eso implica visibilidad distinta por sesión (RLS F5 es la explicación alineada con el historial). **Pendiente de prueba de lectura en TEST.**
- **401 rev4:** sigue **sin** `error_code`.
- **G94:** **RECHAZADO** históricamente; 179 **bloqueado** para una nueva ejecución de mutación hasta aclarar visibilidad admin/finca 1. No APROBADO.
