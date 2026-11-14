# REEVALUACIÓN V2 — TC-M02-G94

**Proyecto:** SGPMP / SIGAB · **Módulo:** M02 · **RF:** RF-50 — Disponibilidad de datos para módulos analíticos · **CU:** CU12
**Subcasos:** TC-M02-158 (rate limiting) · TC-M02-164 (solo lectura) · TC-M02-165 (autenticación obligatoria)
**Responsable QA:** Juan Esteban · **Ambiente:** TEST · **Fecha:** 2026-09-20
**Incidentes asociados:** INC-M02-96-G94 (rate limit y contrato) · INC-M02-90-G92 (identidad técnica M04)

---

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| Caso | TC-M02-G94 |
| RF / CU | RF-50 / CU12 |
| Subcasos | TC-M02-158 · TC-M02-164 · TC-M02-165 |
| Estado V1 | ⛔ **BLOQUEADO** (por TC-M02-158; 164 y 165 aprobados) |
| Estado V2 | ⛔ **SIGUE BLOQUEADO** |
| TC-M02-158 | ⛔ **BLOQUEADO / NO EJECUTADO en esta V2** |
| TC-M02-164 | Antecedente: APROBADO en V1. **No se reejecuta en esta tarea** |
| TC-M02-165 | Antecedente: APROBADO en V1. **No se reejecuta en esta tarea** |
| Ejecución funcional V2 | **NINGUNA**: no se ejecutó k6, ni la ráfaga de 101 solicitudes, ni Newman, ni Postman, ni Pytest |
| Motivo del bloqueo | **CONFIGURACIÓN / PROVISIÓN DE IDENTIDADES TÉCNICAS DE MÓDULOS CONSUMIDORES EN TEST** |
| Naturaleza del bloqueo | No es ausencia del rate limiter · No es falta de datos · No es inexistencia del endpoint · No exige tener desarrolladas las aplicaciones M04/M06/M08 |
| Responsable de desbloqueo | DBA / administrador de TEST (provisión y credenciales); Desarrollo / responsable funcional (elegir el módulo de control) |
| **Veredicto** | ⛔ **BLOQUEADO** |

El grupo sigue bloqueado **únicamente** porque TC-M02-158 todavía no puede ejecutarse completamente. Desarrollo ya corrigió parte del problema original: el endpoint tiene rate limit y el contrato contempla 429. Lo que falta son las **dos identidades técnicas independientes** necesarias para demostrar que la cuota está aislada por módulo consumidor.

---

## 1. Motivo de la reevaluación

V1 cerró en BLOQUEADO con el subtipo `CREDENCIAL M04 NO DISPONIBLE` + `MÓDULO DE CONTROL NO DISPONIBLE`, y registró además OBS-G94-01 (el endpoint no aplicaba ningún limitador) y OBS-G94-02 (el contrato no declaraba 429 ni los esquemas de seguridad).

Desde entonces Desarrollo atendió INC-M02-96-G94. Esta reevaluación documenta **qué cambió**, **qué sigue bloqueado** y **qué hace falta para desbloquear**, sin ejecutar la prueba de carga.

Los resultados históricos de TC-M02-164 y TC-M02-165 se citan **solo como antecedente de V1**. No se reejecutaron en esta tarea y no se convierten en resultados de ejecución V2.

---

## 2. Estado actual de la corrección de Desarrollo

Verificado por lectura del código en el HEAD actual (`a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`) y del contrato:

| Elemento | Estado actual | Evidencia |
|---|---|---|
| Limitador conectado al endpoint | ✅ **Sí** | `activo_biologico_router.py`: `_LIMITE_DATOS_CONSOLIDADOS = rate_limit(100, 60, alcance="activos_datos_consolidados")`, declarado como dependencia de `GET /{id_activo}/datos-consolidados` |
| Cuota configurada | **100 solicitudes / 60 segundos** | mismo valor que exige RF-50 |
| `429` en el contrato | ✅ **Sí** | `responses={… 429: {'model': ErrorResponse}}`; el OpenAPI del despliegue declara `200, 400, 401, 403, 404, 422, 429` |
| Clave de cuota del limitador | **usuario autenticado**: `f"{alcance}:{usuario_actual.id_usuario}"` | `src/shared/rate_limit.py` |
| Aislamiento por módulo | Documentado como fuera de alcance de INC-M02-96-G94, a la espera de la identidad de INC-M02-90-G92 | nota del incidente |

**En esta V2 no se afirma ningún resultado empírico sobre el rate limiter**: no se emitió ninguna ráfaga, así que no se comprobó en vivo ni el corte en la solicitud 101, ni el 429, ni las cabeceras de cuota. Lo verificado es que el limitador está conectado y que el contrato lo declara.

Consecuencia para OBS-G94-01 y OBS-G94-02: la parte de "no hay limitador" y "el contrato no declara 429" **ya no se sostiene**. **Este documento no debe leerse como que el rate limiting esté ausente.** Su cierre formal queda pendiente de la comprobación empírica, que es justo lo que bloquea la falta de identidades.

---

## 3. Bloqueo actual de TC-M02-158

El subcaso exige demostrar que la cuota es **por módulo consumidor** y no global. Para eso hacen falta dos identidades técnicas independientes:

**A. Identidad técnica M04**, autenticable y autorizada. Puede ser la misma que se está provisionando para TC-M02-G92:

```text
Correo: integracion.m04.test@pecuaria.co
Rol:    Integración M04
```

**B. Una segunda identidad técnica independiente** que represente a otro módulo consumidor autorizado — **M06 o M08** —, con su propio rol, su propia cuenta y su propia credencial.

Escenario que permitirían ejecutar:

```text
1. M04 consume hasta superar el límite de 100/60 s.
2. La solicitud que supera el umbral devuelve HTTP 429.
3. Inmediatamente después, el segundo módulo consumidor realiza la misma consulta.
4. Ese segundo módulo debe seguir respondiendo con normalidad.
5. Queda demostrado que la cuota de M04 no afectó al resto de módulos.
```

### 3.1 Estado verificado hoy en TEST

Consulta de solo lectura a PostgreSQL TEST el **2026-09-20 22:20 UTC** (`member_qa` / `sgpmp_test` / `transaction_read_only = on`). No se leyeron contraseñas, hashes ni secretos.

| Verificación | Resultado |
|---|---|
| Usuario `integracion.m04.test@pecuaria.co` | **0 filas** — no existe |
| Usuarios con correo `%m04%`, `%m06%`, `%m08%` o `%integracion%` | **0 filas** |
| Roles con nombre `%integr%`, `%m04%`, `%m06%`, `%m08%` | **0 filas** |
| `modulo1.credenciales_servicio` | Solo `1 · broker_mqtt · activo` |
| Credenciales disponibles para QA | **Ninguna de las dos** |
| Activo de la prueba (279 `QAJE-CREC-OK`) | Existe, ACTIVO, infraestructura 48, finca 57 |

La identidad M04 está siendo gestionada por TC-M02-G92. **Falta además definir y provisionar la segunda identidad de control (M06 u M08)**, que hoy ni siquiera está decidida.

### 3.2 Clasificación del bloqueo

| Tipo de bloqueo | ¿Aplica? | Sustento |
|---|---|---|
| Falta de desarrollo funcional | **NO** | El endpoint existe, el limitador está conectado (100/60 s) y el contrato declara 429 |
| **Falta de configuración / provisión en TEST** | **SÍ** | Ninguna de las dos identidades técnicas existe en la base de TEST |
| Falta de datos | **NO** | El activo 279 y sus datos consolidados están disponibles |
| Falta de credenciales | **SÍ, derivada** | Aun creadas las identidades, QA necesita las dos contraseñas por canal seguro, y deben ser independientes entre sí |
| Dependencia de otro módulo | **NO en el sentido de aplicación** | No hace falta que M04, M06 u M08 estén desarrollados: el proyecto autoriza representarlos mediante identidades técnicas de integración (decisión de INC-M02-90-G92). Solo cambiaría si existiera una decisión funcional explícita y documentada que prohibiera usarlas, y no se ha registrado ninguna |

### 3.3 Situación técnica del limitador y por qué dos identidades bastan

La implementación actual usa como clave de cuota el **usuario autenticado** (`id_usuario`). Por tanto, cuando existan las dos identidades técnicas:

- M04 tendrá un `id_usuario`;
- el módulo de control (M06 u M08) tendrá otro `id_usuario`.

Con esas dos identidades será posible ejecutar empíricamente el escenario de §3 y comprobar si el comportamiento satisface el aislamiento que exige RF-50. **No se reutiliza el mismo usuario para M04 y para el control**: con una sola identidad las dos ráfagas compartirían contador y no se podría demostrar aislamiento entre consumidores.

---

## 4. Por qué no se ejecuta la prueba

**TC-M02-158 — BLOQUEADO / NO EJECUTADO.** No se ejecutó k6, ni la ráfaga de 101 solicitudes, ni Newman, ni Postman, ni Pytest. No se generó ningún reporte de k6: no se emite un artefacto vacío o simulado que aparente una ejecución.

Razones:

1. Sin las dos identidades no hay forma de demostrar el aislamiento por consumidor, que es el objeto del subcaso. El propio script `test_tc_m02_g94_rate_limit.js` aborta si no recibe `TOKEN_M04` y `TOKEN_CONTROL`.
2. Una ráfaga con una cuenta humana mediría, como mucho, el límite por usuario, y confundiría ese resultado con el límite por módulo que pide RF-50.
3. Cada GET exitoso del endpoint escribe una fila de auditoría: una ráfaga dejaría ~101 registros en un TEST compartido sin resolver el bloqueo.

**TC-M02-164 y TC-M02-165** no se reejecutan en esta tarea, que es documental. Su estado APROBADO pertenece a V1 y se cita solo como antecedente; en esta V2 no se les asigna ningún resultado de ejecución.

---

## 5. Qué se necesita para desbloquear

1. **Terminar de provisionar la identidad técnica M04 en TEST** (gestionada por TC-M02-G92): rol `Integración M04` resuelto por nombre con el id real de TEST, usuario `integracion.m04.test@pecuaria.co`, cuenta activa y verificada, permiso READ (recurso 29, acción 2) y alcance válido sobre el activo de prueba.
2. **Desarrollo / responsable funcional: confirmar qué módulo se usará como control**, M06 o M08.
3. **DBA / administrador: provisionar una segunda identidad técnica independiente** para ese módulo.
4. Esa identidad debe tener:
   - rol técnico propio;
   - cuenta activa y verificada;
   - permiso READ sobre el recurso que protege RF-50;
   - alcance válido sobre el mismo activo/finca de la prueba;
   - contraseña segura e independiente de la de M04.
5. **Entregar las dos credenciales a QA por canal seguro.** No se escriben en Git, ni en este Markdown, ni en la colección, ni en los scripts.
6. **QA — gate previo a la carga:**
   - login M04 → correcto;
   - GET base con M04 → HTTP 200;
   - login del módulo de control → correcto;
   - GET base con el módulo de control → HTTP 200.
7. **Solo después:** ejecutar k6, emitir el mínimo de solicitudes necesario para superar 100/minuto, comprobar el 429 en M04, comprobar que el segundo consumidor mantiene el acceso normal y registrar el resultado real.

---

## 6. Evolución V1 → V2

| Elemento | V1 | V2 | Evolución |
|---|---|---|---|
| TC-M02-158 | BLOQUEADO / no ejecutado | BLOQUEADO / no ejecutado | **SIGUE BLOQUEADO**, con el motivo cambiado (§6.1) |
| TC-M02-164 | APROBADO | No reejecutado en esta tarea | Antecedente V1 |
| TC-M02-165 | APROBADO | No reejecutado en esta tarea | Antecedente V1 |
| Rate limiter en el endpoint | Ausente (OBS-G94-01) | Conectado: 100/60 s, clave por `id_usuario` | **Implementado; pendiente de comprobación empírica** |
| `429` en el contrato | No declarado (OBS-G94-02) | Declarado | **Corregido en el contrato**; los `securitySchemes` siguen fuera de alcance según INC-M02-96-G94 |
| Identidad M04 | No existe | No provisionada en TEST (gestionada por G92) | **SIGUE BLOQUEADO** |
| Segundo módulo de control | No existe | Sin definir ni provisionar | **SIGUE BLOQUEADO** |
| Veredicto del caso | BLOQUEADO | BLOQUEADO | **SIGUE BLOQUEADO** |

### 6.1 El motivo del bloqueo evolucionó

```text
V1: no había rate limiter, el contrato no declaraba 429
    y no existían identidades de módulo consumidor.

V2: el rate limiter y el HTTP 429 ya fueron implementados;
    persiste la imposibilidad de ejecutar completamente el escenario
    por falta de las identidades técnicas requeridas en TEST.
```

---

## 7. Veredicto final

# ⛔ BLOQUEADO

**Evolución de TC-M02-158: BLOQUEADO (V1) → SIGUE BLOQUEADO (V2)**, con el motivo evolucionado según §6.1.

**Motivo actual: CONFIGURACIÓN / PROVISIÓN DE IDENTIDADES TÉCNICAS DE MÓDULOS CONSUMIDORES EN TEST** — la de M04, gestionada por TC-M02-G92, y una segunda identidad de control (M06 u M08) todavía sin definir.

No se atribuye a:

- falta de datos — el activo de prueba y sus datos consolidados están disponibles;
- inexistencia del endpoint — `GET /activos-biologicos/{id_activo}/datos-consolidados` está desplegado;
- ausencia actual del rate limiter — está conectado con 100/60 s y el contrato declara 429;
- necesidad de tener desarrolladas las aplicaciones completas M04, M06 u M08 — basta con identidades técnicas de integración.

El grupo TC-M02-G94 permanece BLOQUEADO únicamente porque TC-M02-158 todavía no puede ejecutarse completamente.

---

## 8. Integridad

- ✅ **V1 intacta:** no se modificaron `test_tc_m02_g94.json`, `construir_coleccion.cjs`, `test_tc_m02_g94_rate_limit.js`, `test_tc_m02_g94_security.py` ni `Resultados/`.
- ✅ **No se ejecutó carga:** sin k6, sin la ráfaga de 101 solicitudes y sin ningún reporte de k6 falso o vacío.
- ✅ **No se ejecutó Newman** ni Postman.
- ✅ **No se ejecutó Pytest.**
- ✅ **No se ejecutó SQL de escritura:** solo `SELECT` en sesión `transaction_read_only = on`. Sin INSERT, UPDATE, DELETE ni scripts de provisión; no se crearon roles, usuarios, cuentas ni permisos.
- ✅ **Ningún cambio de código** del producto.
- ✅ **Sin commit, push, merge, rebase ni deploy**, y sin cambio de rama (`qa/juan-esteban-re-evaluacion-m02`, HEAD `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`).
- ✅ No se usó ninguna cuenta humana como sustituto de un módulo consumidor y no se leyeron contraseñas ni secretos.
- ✅ **Único artefacto nuevo:** este documento (`EvaluacionV2/Resultados/TC-M02-G94_reevalucion_V2.md`).
