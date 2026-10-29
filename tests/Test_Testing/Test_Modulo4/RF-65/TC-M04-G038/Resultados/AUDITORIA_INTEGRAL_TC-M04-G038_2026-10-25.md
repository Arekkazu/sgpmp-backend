# Auditoría integral TC-M04-G038 — RF-65

Fecha: 2026-10-25. Rama `laura` @ `f0ca7248`. Sin commit ni push. Sin cambios a `src/` ni a los scripts de prueba.

**Conclusión del grupo: no APROBADO.** Estado propuesto del grupo: **RECHAZADO** (criterio HTTP 409 de TC-M04-027 no cumplido en código ni en el handler HTTP) con **BLOQUEADO** en el nivel API/PostgreSQL exigido por una validación integral.

Los 5 ítems de pytest PASSED **no** equivalen a aprobación del grupo.

---

## Trazabilidad de identificadores

La matriz original citada para esta auditoría usa **TC-M04-035** (estado ACTIVO) y **TC-M04-027** (contrato de entrada / HTTP 409).

En este repositorio **no existe** un archivo de matriz oficial que contenga `TC-M04-035`. Búsqueda en el workspace: cero coincidencias de `TC-M04-035`. `TC-M04-027` aparece en **G046 RF-70** (`test_tc_m04_g046.py`, modos INMEDIATO/PROGRAMADO/LOTES), no como caso de RF-65.

El script de G038 (`test_tc_m04_g038.py`, líneas 1–6 y nombres de función) declara subcasos **TC-M04-005** y **TC-M04-021**. La `MATRIZ_EJECUCION_G037_G048.md` (19-oct-2026, generada en el cierre G037–G048, **no es la matriz original**) copia esos IDs.

Correspondencia **funcional** (tema), no de ID oficial:

| ID matriz original (esta solicitud) | ID en script G038 | ¿Equivalente por nombre de archivo? |
|---|---|---|
| TC-M04-035 | `test_tc_m04_005_*` | No. Mismo tema (gate ACTIVO). IDs distintos. |
| TC-M04-027 | `test_tc_m04_021_incompatibilidad_es_422_no_409` | No. Mismo tema (incompatibilidad). Colisión: TC-M04-027 también es G046/RF-70. |

Los reportes `Resultados/TC-M04-005/` y `TC-M04-021/` del 25-oct **heredan el error de ID** del script. Esta auditoría usa los IDs originales 035 y 027.

Ficha RF-65 versionada: **ausente** en el repo. Fuentes Dev: `curls_m04_cu02_configurar_motor_ia.md` (FA-03 → 412 `MODELO_NO_ACTIVO`), `curls_m04_rfc009_taxonomia_paradigma.md` (4.e → **422** `VERSION_MODELO_INCOMPATIBLE`), `motor_ia_router.py` (OpenAPI 412 y 422, **sin 409**).

---

## Tabla de criterios (estados: APROBADO / RECHAZADO / BLOQUEADO)

| ID original | Criterio verificado | Evidencia concreta | Resultado observado | Cumple el esperado | Nivel de prueba | Estado propuesto |
|---|---|---|---|---|---|---|
| TC-M04-035 | Rechazo estado APROBADO | `test_tc_m04_g038.py:23-36` param `APROBADO`; use case `configurar_motor_use_case.py:203-211`; pytest 2026-10-25 PASSED | `PreconditionFailedError` `MODELO_NO_ACTIVO`, `status_code==412`; repo memoria `id_version_modelo_activa is None`, `config_version==1` | Parcial (dominio sí; HTTP/BD no) | Unitario (dobles `VersionPortFijo`) | **BLOQUEADO** |
| TC-M04-035 | Rechazo DEPRECADO | mismo test param `DEPRECADO`; evidencias `.../TC-M04-005/evidencias/reeval-2026-10-25/test_tc_m04_005_rechaza_modelo_no_activo_DEPRECADO_.*` y `auditoria-2026-10-25/g038-unitario.txt` | Igual: 412 lógico, vigente intacta en memoria | Parcial | Unitario | **BLOQUEADO** |
| TC-M04-035 | Rechazo RECHAZADO | param `RECHAZADO` | Igual | Parcial | Unitario | **BLOQUEADO** |
| TC-M04-035 | ACTIVO válido continúa | `test_tc_m04_005_acepta_modelo_activo` L39-45 | Vincula `id_version_modelo_activa==20` en memoria | Parcial | Unitario | **BLOQUEADO** |
| TC-M04-035 | HTTP 412 real en POST `/prediccion/motor-ia` | Router L40-71 no captura excepciones; OpenAPI declara 412. Probe handler: `auditoria-2026-10-25/http-handler-probe.txt` → POST sintético 412 `MODELO_NO_ACTIVO`. **No** se ejecutó POST del router con JWT, RBAC ni `VersionModeloAdapter` SQL | 412 en atributo de error y en handler global; **sin** respuesta HTTP del endpoint de motor | No verificado al nivel API | Código estático + probe del handler (no es el endpoint) | **BLOQUEADO** |
| TC-M04-035 | Mensaje identifica causa | Use case L206-209 incluye estado actual y «Solo se pueden vincular modelos en estado ACTIVO» | Presente en la excepción; curls FA-03 coinciden | Sí en dominio | Unitario / código | (cubre parte de 035) |
| TC-M04-035 | Configuración previa intacta / sin escritura parcial | Test: auditoría `len==1` (solo CREADA previa); `ConfigRepoMemoria` con `deepcopy`. SQLAlchemy **no** ejecutado | Intacta en doble en memoria | No en PostgreSQL | Unitario | **BLOQUEADO** |
| TC-M04-035 | Lógica real, no respuesta inventada | `_validar_version` compara `estado != "ACTIVO"` y lanza; el test llama `uc.execute` | Ejecuta el use case con puerto falso, no el adapter SQL | Lógica de dominio sí; integración no | Unitario | **BLOQUEADO** |
| TC-M04-035 | Estados no cubiertos | No hay nodo `EN_VALIDACION` | Hueco de parametrización | No exigido explícitamente en la solicitud | — | documentado |
| TC-M04-027 | Compara config vs contrato de entrada del modelo | `_validar_version` L212: solo `(tipo_modelo, componente)` vs llave de versión. No lee esquema de variables ni `ventana_temporal` del artefacto | Incompatibilidad de **llave RFC-009 4.e**, no contrato de features completo | Parcial vs enunciado de matriz | Unitario | **BLOQUEADO** / cobertura incompleta |
| TC-M04-027 | HTTP **409** | `BusinessRuleError.status_code = 422` (`errors.py:88-96`); raise L213; handler `exc.status_code` (`error_handlers.py:95-96`); OpenAPI POST sin 409 (`motor_ia_router.py:43-51`); RFC-009 curls: **422**; probe: 422 `VERSION_MODELO_INCOMPATIBLE`; `ConflictError` sí da 409 pero **no** se usa aquí | HTTP efectivo del contrato Dev: **422**, no 409 | **No** | Código + probe handler | **RECHAZADO** |
| TC-M04-027 | Error identifica incompatibilidad | Mensaje L215-218: tipos/componente de la versión vs los pedidos | Sí en dominio | Sí (mensaje) | Unitario | — |
| TC-M04-027 | Configuración previa intacta | Test L59-61 | En memoria sí | PostgreSQL no | Unitario | **BLOQUEADO** (persistencia) |
| TC-M04-027 | Más de un escenario de incompatibilidad | Un solo caso: `MODELO_AVES`/`DETECTOR` vs `MODELO_ESPECIES_GRANDES`/`None`. No hay componente distinto mismo tipo, ni POBLACIONAL `versiones_activas_por_componente` | Un escenario | Insuficiente si la matriz exige varios | Unitario | **BLOQUEADO** |
| TC-M04-027 | Caso válido no rechazado indebidamente | Cubierto por ACTIVO mismo tipo en 035 (`test_tc_m04_005_acepta_modelo_activo`), no en el test 021 | Indirecto | Parcial | Unitario | — |
| TC-M04-027 | API / Postman / BD | No hay test HTTP de incompatibilidad. Adapter real: SQL `modulo4.versiones_modelos` (`version_modelo_adapter.py:25-33`) | No ejecutado (sin escrituras a BD compartida) | No | — | **BLOQUEADO** |

---

## Inventario de evidencias

Consultadas (no modificadas salvo carpeta de auditoría nueva):

- `tests/Test_Testing/Test_Modulo4/RF-65/TC-M04-G038/test_tc_m04_g038.py`
- `tests/Test_Testing/Test_Modulo4/rf65_dobles.py`
- `tests/Test_Testing/Test_Modulo4/Resultados/MATRIZ_EJECUCION_G037_G048.md`
- `tests/Test_Testing/Test_Modulo4/Resultados/pytest-g037-g048.txt` (19-oct)
- `src/prediction/application/use_cases/motor_ia/configurar_motor_use_case.py`
- `src/prediction/infrastructure/routers/motor_ia_router.py`
- `src/prediction/infrastructure/adapters/version_modelo_adapter.py`
- `src/shared/errors.py`, `src/shared/error_handlers.py`
- `anotaciones/modulo_4/curls_m04_cu02_configurar_motor_ia.md`
- `anotaciones/modulo_4/curls_m04_rfc009_taxonomia_paradigma.md`
- `tests/Test_Testing/Test_Modulo4/RF-70/TC-M04-G046/test_tc_m04_g046.py` (colisión ID 027)
- Reportes 25-oct con ID incorrecto: `Resultados/TC-M04-005/`, `Resultados/TC-M04-021/`

Generadas en esta auditoría:

- `Resultados/auditoria-2026-10-25/g038-unitario.txt|.html|.xml`
- `Resultados/auditoria-2026-10-25/http-handler-probe.txt`
- este archivo

---

## Ejecución 2026-10-25 (auditoría)

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  --junitxml=.../auditoria-2026-10-25/g038-unitario.xml
  --html=.../auditoria-2026-10-25/g038-unitario.html --self-contained-html
  tests/Test_Testing/Test_Modulo4/RF-65/TC-M04-G038/test_tc_m04_g038.py
```

EXIT=0. **5 passed, 0 failed, 0 skipped.** Nodos: tres rechazos no ACTIVO, un ACTIVO, un 422≠409.

Probe TestClient (rutas sintéticas `/probe/412` y `/probe/422`, **no** `/prediccion/motor-ia`): 412 `MODELO_NO_ACTIVO`; 422 `VERSION_MODELO_INCOMPATIBLE`; `ConflictError` → 409. OpenAPI POST motor: claves 200, 201, 401, 403, 404, **412**, **422**.

No ejecutado: Postman, PostgreSQL, JWT, RBAC, `VersionModeloAdapter`.

---

## HTTP 422 vs 409

No es un código interno que el endpoint traduzca a 409.

1. `VERSION_MODELO_INCOMPATIBLE` se lanza como `BusinessRuleError`.
2. Esa clase tiene `status_code = 422`.
3. `ConflictError` (409) no se usa en `_validar_version`.
4. El handler HTTP copia `exc.status_code`.
5. El POST de motor declara 422, no 409.
6. RFC-009 Dev documenta 422 para este código.
7. El test G038 **afirma** 422 y `!= 409` (caracteriza Dev; no valida la matriz 409).

Conclusión: **discrepancia real** entre matriz original (409) y contrato Dev implementado (422). No resuelta.

---

## Defectos / riesgos

1. Criterio obligatorio 409 de TC-M04-027 **no cumplido** (422).
2. IDs 005/021 en scripts y reportes ≠ 035/027; TC-M04-027 duplicado en G046.
3. Nivel de prueba insuficiente para APROBADO de matriz API: solo unitario con dobles.
4. Contrato de entrada reducido a `(tipo_modelo, componente)`.
5. Un solo escenario de incompatibilidad; sin POBLACIONAL.
6. Ficha RF-65 no está en el repositorio.

Pasos: (a) fijar IDs oficiales; (b) decisión de analista 409 vs 422; (c) si se exige 409, cambiar el tipo de error o el mapeo (fuera de esta auditoría); (d) pruebas HTTP in-process o aisladas + persistencia autorizada.

---

## Estado recomendado G038

**No APROBADO en su totalidad.**

- **TC-M04-035:** **BLOQUEADO** (dominio cubierto en memoria; falta HTTP del endpoint y PostgreSQL).
- **TC-M04-027:** **RECHAZADO** en el criterio HTTP 409; **BLOQUEADO** en API, BD y amplitud de escenarios.

El grupo queda **RECHAZADO** respecto de la matriz original, no APROBADO.
