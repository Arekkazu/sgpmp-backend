# REEVALUACIÓN V2 — TC-M02-G79

**Proyecto:** SGPMP / SIGAB · **Módulo:** M02 · **RF:** RF-48 — Transferencia Interna de Activos Biológicos · **CU:** CU10 / CU10C
**Subcaso:** TC-M02-133 — Transferir activo INDIVIDUAL a infraestructura compatible
**Responsable QA:** Juan Esteban · **Ambiente:** TEST · **Fecha:** 2026-09-19

---

## 0. Resumen ejecutivo

| Dimensión | Resultado |
|---|---|
| **VEREDICTO V2** | **APROBADO — CRITERIO QA CORREGIDO / SIN REGRESIÓN** |
| Criterio de éxito | **HTTP 201**: contrato OpenAPI y router. RF-48 no fija código HTTP |
| Productor (usuario 35) | Activo 292, 48 → 51: 201, V1–V17 correctas |
| Administrador (usuario 1) | Activo 294, 51 → 48: 201, V1–V17 correctas |
| QA-G79-H1 (200 vs 201) | **RESUELTO POR CORRECCIÓN DEL CRITERIO QA**. No fue un defecto del Backend |
| QA-G79-H2 (GET disponibles) | **CORREGIDO**: los destinos devueltos coinciden exactamente con el conjunto elegible calculado en BD |
| Newman | Ejecución única: 23 requests, **75 assertions, 75 passed, 0 failed** |
| Escrituras de QA | Solo los 2 POST oficiales. SQL de QA solo lectura |
| Persistencia parcial | NO |

Todo lo que RF-48 exige para el camino exitoso se cumplió para los dos actores: validaciones previas, asociación exclusiva al destino, cierre de la asociación anterior, movimiento registrado, historial conservado, ocupación de origen −1 y de destino +1, y auditoría. La V1 se rechazó únicamente por una expectativa de la matriz (HTTP 200) que la documentación oficial no respalda.

---

## 1. Fuente de verdad y criterio

### 1.1 Requisito funcional oficial (RF-48)

Según el paquete de reevaluación, alineado a la especificación oficial, la transferencia exitosa exige: activo existente y ACTIVO; destino existente, activo, distinto del origen y de la misma finca; C1 especie, C2 tipo de infraestructura, C3 capacidad; fecha no futura; sin transferencia concurrente. Resultado esperado: el activo queda asociado exclusivamente al destino, baja la ocupación del origen, sube la del destino y se conservan el historial y la trazabilidad. **RF-48 no fija un código HTTP para el camino exitoso.**

### 1.2 Contrato técnico (OpenAPI TEST, 2026-09-19)

| Operación | Respuestas declaradas |
|---|---|
| `GET /activos-biologicos/{id_activo}/transferencias/disponibles` | 200, 401, 403, 404, 422 |
| `POST /activos-biologicos/{id_activo}/transferencias` | **201**, 401, 403, 404, 409, 422, 500 (no declara 200) |

`RegistrarTransferenciaDTO.required` = `infraestructura_origen_id`, `infraestructura_destino_id`, `fecha_transferencia`, `motivo_transferencia`. El router (`activo_biologico_router.py`, decorador `@router.post('/{id_activo}/transferencias', ..., status_code=201)`) coincide con el contrato.

### 1.3 Error histórico de la matriz QA

La ficha y matriz de TC-M02-133 exigían **HTTP 200**. Ese valor no proviene de RF-48 ni de CU10, y contradice el contrato vigente. La colección V1 incluía a la vez `V1 ficha: HTTP 200` y `Contrato: HTTP 201`, dos aserciones incompatibles. Por eso V1 quedó con 2 fallos aunque la transferencia se ejecutó completa. **Backend ya respondía 201 correctamente en V1**: no hubo corrección de Desarrollo sobre el código HTTP.

### 1.4 Criterio V2

- Éxito = **HTTP 201 exclusivamente** (no se acepta cualquier 2xx). La aserción de 200 se eliminó.
- Se mantienen todas las exigencias funcionales de RF-48 (V2–V17).
- Actores: **Productor + Administrador**, la misma cobertura que V1.

Nota documental: el documento de diseño CU10 también menciona al Ingeniero de Campo como actor. Esa diferencia queda registrada, pero TC-M02-133 no se amplió en esta reevaluación, según el §6 del paquete.

### 1.5 Texto que debe quedar en la matriz para TC-M02-133

> La transferencia se registra exitosamente (HTTP 201 según el contrato técnico vigente). El activo queda asociado exclusivamente a la infraestructura destino, se registra el movimiento/evento manteniendo la trazabilidad, se conserva el historial previo y se actualizan correctamente los contadores de ocupación de origen y destino.

No debe volver a documentarse HTTP 200 para este camino feliz, salvo que una nueva versión oficial del contrato o del requerimiento lo establezca.

---

## 2. Gate técnico

| Verificación | Resultado |
|---|---|
| Rama | `qa/juan-esteban-re-evaluacion-m02` ✅ |
| HEAD | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c` ✅ |
| `git fetch origin` + `HEAD...origin/test` | `0 0` ✅ (el fetch trajo solo ramas ajenas: `fix/tc-m09-158-…`, `test-JuanSG`) |
| `git status --short` | solo carpetas `EvaluacionV2/` no versionadas |
| OpenAPI | 200; GET disponibles y POST transferencias presentes; POST declara 201 ✅ |
| BD | `member_qa / sgpmp_test / transaction_read_only = on` ✅; `current_date = 2026-09-19` |
| Actores | Usuario 35 (Productor, rol 2, cuenta Activa, dueño de la finca 57); usuario 1 (Administrador, rol 1, cuenta Activa) |
| Permiso del endpoint | `require_permission_m02(29, 5, rf_origen='RF48')`: rol 1 → permiso 173 activo; rol 2 → permiso 174 activo |

### Código vigente (HEAD)

- `RegistrarTransferenciaUseCase._execute`: E-01 concurrencia, E-02 existencia, E-03 ACTIVO, E-04 asociación de origen, E-05 destino activo, E-06 destino ≠ origen, E-07 C1, E-07b C2, E-08 misma finca, E-09 C3, E-10 fecha no futura. Después cierra la asociación, abre la nueva, actualiza `id_infraestructura`, inserta el movimiento, hace commit y audita `TRANSFERENCIA_REGISTRADA`.
- `listar_infraestructuras_disponibles`: excluye el origen y filtra por finca del origen, C1, C2 (`es_tipo_compatible`) y C3 (ocupación + cantidad ≤ capacidad).

---

## 3. Fixtures frescos

No había activos nuevos dedicados a transferencias en TEST. Los INDIVIDUAL ACTIVO de la finca 57 son fixtures de otros casos (CREC, DAT, IND, G47). Los únicos dedicados a RF-48 son **292 `QAJE-TRF-OK`** y **294 `QAJE-TRF-REGLAS`**. No se reutilizaron a ciegas: se volvieron a verificar por SQL y API el 2026-09-19 (21:2xZ). Se evitó la infraestructura 47 como destino porque es el fixture de capacidad de otros casos (49/50).

| Actor | Activo | Tipo / estado | Especie | Asociación vigente (única) | Origen | Destino | Finca | C1 | C2 | C3 (PRE inmediato) |
|---|---|---|---|---|---|---|---|---|---|---|
| Productor (35) | 292 QAJE-TRF-OK | INDIVIDUAL / ACTIVO | 40 | historial 290 → 48 | 48 Corral QA JE Origen | **51** Corral QA JE Destino OK (sp 40, cap 200) | 57 / 57 | 40 = 40 ✅ | Corral, filtrado por el producto ✅ | 1 + 1 ≤ 200 ✅ |
| Administrador (1) | 294 QAJE-TRF-REGLAS | INDIVIDUAL / ACTIVO | 40 | historial 291 → 51 | 51 Corral QA JE Destino OK | **48** Corral QA JE Origen (sin restricción de especie, cap 1000) | 57 / 57 | sin restricción ✅ | Corral, filtrado por el producto ✅ | 250 + 1 ≤ 1000 ✅ |

- Destino activo y distinto del origen en ambos casos. Fecha 2026-09-19, no futura (`current_date` BD = 2026-09-19).
- **Concurrencia:** `pg_locks` sin locks de escritura sobre `activos_biologicos` ni `movimientos` en las capturas previas. El producto usa `FOR UPDATE NOWAIT`.
- **Limitación C2:** `member_qa` no tiene permiso `SELECT` sobre `modulo9.compatibilidades_tipo_area_especie` ni sobre `modulo9.tipos_area` (`has_table_privilege = false`), así que C2 no pudo leerse directamente en BD. Evidencia indirecta: el GET disponibles aplica `es_tipo_compatible` e incluye el destino elegido mientras excluye 52 (Estanque); el POST vuelve a validar C2 (E-07b) y aceptó la transferencia; V1 ya había transferido especie 40 a Corral.
- No se fabricaron datos: 0 SQL de escritura y ningún activo reubicado para preparar el escenario.

---

## 4. GET disponibles (QA-G79-H2)

| Actor | Origen | Devueltos | Esperado por BD (finca 57, activo, ≠ origen, C1, C2, C3) | Resultado |
|---|---|---|---|---|
| Productor (292) | 48 | **[47, 51]** | 47 (Corral sp40, 49/50 → cabe 1), 51 (Corral sp40, 1/200) | ✅ idéntico |
| Administrador (294) | 51 | **[47, 48]** | 47 (Corral sp40, 49/50), 48 (Corral sin sp, 250/1000) | ✅ idéntico |

Descartados correctamente, frente a lo que devolvía V1:

| Infra | Motivo de exclusión | V1 | V2 |
|---|---|---|---|
| 1 Estanque-01 | otra finca (1) | aparecía | **no aparece** ✅ |
| 52 Estanque QA JE Piscicola | tipo incompatible (C2) | aparecía | **no aparece** ✅ |
| 53 Galpón QA JE Aves | especie 41 (C1) | aparecía | **no aparece** ✅ |
| Origen actual (48 / 51) | origen excluido | excluido | **excluido** ✅ |
| 49, 50 | inactivas | — | no aparecen ✅ |
| 47 | V1: aparecía llena (50/50) | aparecía sin capacidad | hoy 49/50 → **elegible** para 1 individuo; su aparición es correcta |

Todos los destinos devueltos son de la finca 57, están activos, tienen especie null o 40 y cumplen C3. El conjunto coincide exactamente con el esperado: no falta ningún elegible ni sobra ninguno.

- **Límite de la prueba:** hoy no hay en la finca 57 ninguna infraestructura activa y compatible sin capacidad, así que la exclusión por C3 no pudo observarse en vivo. El código (`ocupacion_actual + cantidad > capacidad_maxima → continue`) y el caso 47 al límite (49 + 1 = 50, incluida) son coherentes con la regla.

**QA-G79-H2 → CORREGIDO.**

---

## 5. POST oficial y resultado — Productor

- **Captura PRE:** 21:31:43.383Z · **POST** · **Captura POST:** 21:31:46.266Z.
- `POST /activos-biologicos/292/transferencias`

```json
{"infraestructura_origen_id": 48, "infraestructura_destino_id": 51, "fecha_transferencia": "2026-09-19",
 "motivo_transferencia": "TC-M02-G79 V2 TC-M02-133 productor 20260919 individual compatible 292 48 a 51"}
```

**HTTP 201**

```json
{"id_movimiento":37,"id_activo_biologico":292,"infraestructura_origen":"Corral QA JE Origen",
 "infraestructura_destino":"Corral QA JE Destino OK","fecha_transferencia":"2026-09-19T00:00:00Z",
 "motivo_transferencia":"TC-M02-G79 V2 TC-M02-133 productor 20260919 individual compatible 292 48 a 51",
 "mensaje":"Transferencia registrada exitosamente. El activo fue transferido a Corral QA JE Destino OK en fecha 2026-09-19."}
```

| Evidencia | PRE | POST |
|---|---|---|
| Ubicación activo | 48 | **51** |
| Ocupación origen 48 | 251 | **250** (−1) |
| Ocupación destino 51 | 1 | **2** (+1) |
| Movimientos del activo | 2 (23, 29) | 3 (+ **37**) |
| Asociación vigente | 290 (48) | **422** (51); 290 cerrada |
| Auditoría RF48 nueva | — | **3337** `TRANSFERENCIA_REGISTRADA`, usuario 35 |

## 6. POST oficial y resultado — Administrador

- **Captura PRE:** 21:31:51.677Z. Ya incorpora la transferencia del Productor. · **POST** · **Captura POST:** 21:31:55.403Z.
- `POST /activos-biologicos/294/transferencias`

```json
{"infraestructura_origen_id": 51, "infraestructura_destino_id": 48, "fecha_transferencia": "2026-09-19",
 "motivo_transferencia": "TC-M02-G79 V2 TC-M02-133 admin 20260919 individual compatible 294 51 a 48"}
```

**HTTP 201**

```json
{"id_movimiento":38,"id_activo_biologico":294,"infraestructura_origen":"Corral QA JE Destino OK",
 "infraestructura_destino":"Corral QA JE Origen","fecha_transferencia":"2026-09-19T00:00:00Z",
 "motivo_transferencia":"TC-M02-G79 V2 TC-M02-133 admin 20260919 individual compatible 294 51 a 48",
 "mensaje":"Transferencia registrada exitosamente. El activo fue transferido a Corral QA JE Origen en fecha 2026-09-19."}
```

| Evidencia | PRE | POST |
|---|---|---|
| Ubicación activo | 51 | **48** |
| Ocupación origen 51 | 2 | **1** (−1) |
| Ocupación destino 48 | 250 | **251** (+1) |
| Movimientos del activo | 3 (24, 28, 30) | 4 (+ **38**) |
| Asociación vigente | 291 (51) | **423** (48); 291 cerrada |
| Auditoría RF48 nueva | — | **3344** `TRANSFERENCIA_REGISTRADA`, usuario 1 |

## 7. Assertions V1–V17 por actor

Las columnas combinan la aserción Newman sobre la API con la comprobación sobre las capturas SQL tomadas inmediatamente antes y después de cada POST.

| # | Verificación | Productor | Admin | Fuente |
|---|---|---|---|---|
| V1 | HTTP 201 | ✅ | ✅ | Newman |
| V2 | id_activo correcto | ✅ 292 | ✅ 294 | Newman |
| V3 | id_movimiento válido | ✅ 37 | ✅ 38 | Newman + BD (única fila nueva, mismo id) |
| V4 | mensaje de transferencia exitosa | ✅ | ✅ | Newman |
| V5 | motivo correcto | ✅ | ✅ | Newman + BD (`movimientos.motivo_transferencia`) |
| V6 | origen/destino correctos | ✅ 48→51 | ✅ 51→48 | Newman (nombres, fecha) + BD (ids, `id_usuario`) |
| V7 | activo asociado al destino | ✅ | ✅ | Newman (`GET activo`) + BD |
| V8 | asociación anterior cerrada | ✅ 290 | ✅ 291 | Newman + BD (`fecha_fin` asignada) |
| V9 | nueva asociación vigente única | ✅ 422 | ✅ 423 | Newman + BD (1 sola fila abierta, `id_usuario_registro` del actor) |
| V10 | movimientos +1 | ✅ | ✅ | Newman (historial +1) + BD (activo y global +1) |
| V11 | historial previo conservado | ✅ | ✅ | Newman (`deep.include` de todos los registros previos) + BD (movimientos idénticos; historiales cerrados idénticos; al abierto solo se le asigna `fecha_fin`) |
| V12 | evento nuevo trazable | ✅ | ✅ | Newman (categoría TRANSFERENCIA, motivo, origen/destino) + BD |
| V13 | auditoría RF48 nueva | ✅ 3337 | ✅ 3344 | Newman (exactamente 1 nueva, detalle origen/destino/motivo) + BD (global RF48 +1) |
| V14 | usuario responsable correcto | ✅ 35 | ✅ 1 | Newman + BD |
| V15 | ocupación origen PRE − 1 | ✅ 251→250 | ✅ 2→1 | BD (fórmula de `calcular_ocupacion`) |
| V16 | ocupación destino PRE + 1 | ✅ 1→2 | ✅ 250→251 | BD |
| V17 | sin inconsistencia parcial | ✅ | ✅ | BD: V7–V10 y V13 simultáneos; `activos_biologicos` sin filas nuevas; historial +1; infraestructuras y detalles poblacionales sin cambios |

---

## 8. Newman

| Métrica | Valor |
|---|---|
| Colección | `EvaluacionV2/test_tc_m02_g79_v2.json` (blob `--no-filters` `698eefc8fc38c7d4e6649d541f4b2c18d516f0d2`) |
| Ventana | 2026-09-19 21:31:39.890Z – 21:31:58.055Z (una sola ejecución) |
| Requests | 23 (0 fallidas): 1 OpenAPI + 11 por actor |
| Assertions | **75 · 75 passed · 0 failed** |
| Reportes | `reporte_tc_m02_g79_v2.json`, `reporte_tc_m02_g79_v2.html` (secretos redactados) |
| Evidencia BD | `evidencia_bd_g79_v2.json` (gate, capturas PRE/POST por actor y evaluación) |

### Cambios respecto a la colección V1

| V1 | V2 |
|---|---|
| `V1 ficha: HTTP 200` + `Contrato: HTTP 201`, incompatibles | Solo `Transferencia creada: HTTP 201` |
| Fixtures 292 (51→48) y 294 (47→51) de 2026-09-10 | Fixtures reverificados: 292 (48→51) y 294 (51→48), fecha 2026-09-19, motivos V2 únicos |
| GET disponibles: solo "destino disponible" | + origen excluido, sin 1/52/53, especie compatible (H2) |
| Historial: V4/V5/V6 | V10/V11/V12 con origen y destino del evento |
| Auditoría: solo HTTP 200 al final | V13/V14 por actor: exactamente 1 evento nuevo, usuario y detalle |
| — | V7/V8/V9 por API (`GET activo`, `GET infraestructura`) |
| Gate `bd_gate` único | `bd_gate_<actor>` + `acceso_<actor>` + `disponible_<actor>`; el POST se omite si falta alguno |

La ejecución se hizo con un runner Node (`newman.run`, auxiliar no versionado) que llama de forma síncrona a un script Python read-only inmediatamente antes (`beforeRequest`) y después (`request`) de cada POST, igual que el hook de V1. La contraseña se inyectó con `envVar` y la colección no contiene credenciales.

---

## 9. Persistencia y escrituras

- **Escrituras de QA:** exactamente **2 POST oficiales** (uno por actor). No hubo POST de reintento, preparación ni diagnóstico. SQL de QA: solo `SELECT` con `default_transaction_read_only = on`.
- **Cambios de dominio (esperados, producidos por el producto a raíz de los 2 POST):** 2 filas en `modulo2.movimientos` (37, 38); 2 filas nuevas en `historial_infraestructura_activo` (422, 423) y 2 cerradas (290, 291); `activos_biologicos.id_infraestructura` de 292 (48→51) y 294 (51→48); 2 registros `TRANSFERENCIA_REGISTRADA` (3337, 3344). Hubo además la auditoría DML del trigger `trg_auditoria` sobre movimientos.
- **Sin cambios:** `modulo9.infraestructuras` y detalles poblacionales (hash PRE = POST); ningún activo nuevo.
- **Escrituras técnicas:** lecturas auditadas por el producto (RF34/RF46 en infraestructura e historial) y `ultimo_acceso` por los 2 logins.
- **Estado final:** 292 queda en 51 y 294 en 48. Es la posición inversa a la de V1, que dejó 292 en 48 y 294 en 51. La ocupación final coincide con la inicial: 48 pasó de 251 a 250 y volvió a 251, y 51 pasó de 1 a 2 y volvió a 1, porque 292 salió de 48 hacia 51 y 294 salió de 51 hacia 48. No se revirtió nada: las transferencias son el resultado oficial del caso.

---

## 10. Hallazgos V1

| Hallazgo | Relación | V1 | V2 | Evolución |
|---|---|---|---|---|
| QA-G79-H1 | Criterio QA / documentación | Abierto: 201 obtenido frente a 200 de la ficha | La V2 espera 201 según el contrato; RF-48 no fija código; el Backend responde 201 como en V1 | **RESUELTO POR CORRECCIÓN DEL CRITERIO QA** (no es un defecto del Backend; queda pendiente actualizar la matriz, §1.5) |
| QA-G79-H2 | Directo, GET disponibles | Abierto: incluía otra finca (1), tipo incompatible (52), especie incompatible (53) y sin capacidad (47 lleno) | Devueltos = conjunto elegible exacto por BD; 1, 52 y 53 excluidos | **CORREGIDO** |

Hallazgos formales V1 sin reevaluar: **NINGUNO**.

Observaciones documentales (no son defectos):
- La matriz de TC-M02-133 debe cambiar "HTTP 200" por "HTTP 201 CREATED" (§1.5).
- CU10 menciona al Ingeniero de Campo como actor; TC-M02-133 cubre Productor y Administrador (§1.4).

## 11. Regresiones

**Ninguna.** Los dos actores completan la transferencia con la misma calidad funcional que en V1 (V2–V10 de V1 equivalen a V2–V17 de V2) y sin persistencia parcial.

## 12. Veredicto final

# ✅ APROBADO — CRITERIO QA CORREGIDO / SIN REGRESIÓN

El veredicto se basa en RF-48: todas las exigencias funcionales se cumplieron para Productor y Administrador. El 201 obtenido es el código de éxito del contrato vigente, y RF-48 no respalda el 200 exigido por la matriz. Evolución: **RECHAZADO (V1, por criterio QA erróneo) → APROBADO (V2)**. QA-G79-H1: RESUELTO POR CORRECCIÓN DEL CRITERIO QA. QA-G79-H2: CORREGIDO.

## 13. Integridad

- V1 intacta: `test_tc_m02_g79.json` (blob `5ac8b4276f5d2358f673f1894acaf25e044e3b32`, igual a HEAD) y `Resultados/` sin cambios; `git diff HEAD` vacío en la carpeta del caso.
- Se reutilizó la carpeta `EvaluacionV2/`, que ya existía vacía desde el 2026-09-15.
- Una sola ejecución Newman; no se repitió.
- Secretos: JSON de Newman con 20 JWT, 3 contraseñas y 2 buffers de login redactados; HTML con 22 JWT y 2 contraseñas redactados. Verificación posterior: 0 restantes en ambos reportes, en la colección V2 y en `evidencia_bd_g79_v2.json`.
- Sin commit, push, merge, rebase ni deploy, y sin cambio de rama. No se modificó código del producto, no se crearon tickets ni se usó DEV.

### Artefactos

```text
TC-M02-G79/EvaluacionV2/
├── test_tc_m02_g79_v2.json               colección V2 (criterio 201, H2, V1–V14 por API)
└── Resultados/
    ├── reporte_tc_m02_g79_v2.json        Newman 23 req · 75/75 (secretos redactados)
    ├── reporte_tc_m02_g79_v2.html        htmlextra (secretos redactados)
    ├── evidencia_bd_g79_v2.json          gate + capturas SQL PRE/POST por actor + evaluación V1–V17/H2
    └── TC_M02_G79_reevaluacion_V2.md     este informe
```
