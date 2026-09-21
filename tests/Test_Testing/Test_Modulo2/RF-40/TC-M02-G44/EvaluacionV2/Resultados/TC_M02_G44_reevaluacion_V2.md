# REEVALUACIÓN V2 — TC-M02-G44

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| Requerimiento | RF-40 — Registro de eventos de crecimiento |
| Caso agrupado | TC-M02-G44 (TC-M02-082, TC-M02-083-A, TC-M02-083-B, TC-M02-084) |
| Rama | `qa/juan-esteban-re-evaluacion-m02` |
| HEAD V2 | `7e1174d145b2785b331f8c63f49dc6f1b0989621` — *Reevaluaciones M09, RF-17 y RF-24* |
| Ambiente | TEST (HTTPS) — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/` |
| Herramienta | Postman / Newman |
| Colección ejecutada | `test_tc_m02_g44.json` |
| ¿Misma colección de V1? | **Sí.** El archivo es idéntico al versionado en `HEAD` y ambas ejecuciones tienen los mismos 34 ítems y las mismas 96 aserciones (§4) |
| Veredicto V1 | **APROBADO** |
| Veredicto V2 | **APROBADO** |
| Regresiones | **Ninguna** |
| Persistencia indebida | **NO**: Δ = 0 en las 12 verificaciones (3 actores × 4 escenarios) |

**En una frase:** la misma colección automatizada de V1 se volvió a ejecutar sin cambios. Las 12 peticiones negativas oficiales se rechazaron otra vez con `HTTP 400 / VAL_ENTRADA` para los tres actores, sin crear ningún evento de crecimiento, y Newman reporta **96/96 aserciones aprobadas**.

---

## 1. Objetivo de la reevaluación

Comprobar que RF-40 sigue rechazando, en el ambiente TEST actual, los mismos valores inválidos que se validaron en la evaluación original (V1):

- `valor_medicion` no numérico (`"abc"`);
- `valor_medicion` no positivo (`0` y `-5`);
- unidad incompatible con el tipo de medición (`PESO` + `cm`);

y que en ningún caso se crea un evento de crecimiento.

Para que V1 y V2 sean comparables, V2 **no define una prueba nueva**. Vuelve a ejecutar la misma colección `test_tc_m02_g44.json`, con los mismos actores, activos, payloads y criterios de aceptación.

---

## 2. Trazabilidad V1

| Dato | Valor V1 |
|---|---|
| Informe | `Resultados/TC-M02-G44_resultado.md` |
| Reportes | `Resultados/reporte_tc_m02_g44.json`, `Resultados/reporte_tc_m02_g44.html` |
| Fecha de la ejecución oficial | 2026-09-10, 08:00:56 → 08:01:09 UTC (12,6 s), según `run.timings` del reporte JSON |
| Rama V1 | `qa/juan-esteban-m02` |
| HEAD V1 | `41369ea4ab3948eacb1ab9b2d0549310e285eeae` |
| Veredicto V1 | **APROBADO** |
| Newman V1 | 34 peticiones · 96 aserciones · 0 fallos |
| Persistencia V1 | Δ = 0 en los tres activos (confirmado por Newman y por `SELECT` en BD) |

**Resultados principales de V1:**

| Subcaso | Productor | Veterinario | Ingeniero de campo | Resultado V1 |
|---|---:|---:|---:|---|
| TC-M02-082 (`"abc"`) | 400 | 400 | 400 | APROBADO |
| TC-M02-083-A (`0`) | 400 | 400 | 400 | APROBADO |
| TC-M02-083-B (`-5`) | 400 | 400 | 400 | APROBADO |
| TC-M02-084 (`PESO` + `cm`) | 400 | 400 | 400 | APROBADO |

**Particularidades documentadas en V1:**

- **OBS-G44-01 (Baja, no bloqueante):** en TC-M02-082, el mensaje del campo era el texto por defecto de Pydantic en inglés, *«Input should be a valid decimal»*.
- **Veterinario:** la credencial indicada en el paquete de instrucciones (`juan.carlos@email.com`) no existía. Se usó la cuenta vigente del mismo usuario, id 3 (`juan.carlos.qa133@sgpmp-test.com`).
- **Ajuste de aserciones en V1:** en una ejecución preliminar de V1, las aserciones de texto de TC-M02-082 y TC-M02-084 exigían coincidencia literal. Antes de la ejecución oficial se cambiaron a un criterio semántico: palabras clave de «valor no numérico» más atribución al campo `valor_medicion` en 082, y la cláusula «no corresponde al tipo de medición» en 084. Esa es la versión de la colección que está en `HEAD` y la que V2 reutiliza.

---

## 3. Identificación de V2

| Dato | Valor V2 |
|---|---|
| Fecha/hora de la ejecución | 2026-09-19, 04:48:30 → 04:48:39 UTC (9,0 s), según `run.timings` de `reporte_tc_m02_g44_v2.json`. En hora local del equipo corresponde al 2026-09-18, 23:48 (fecha de los archivos) |
| Rama | `qa/juan-esteban-re-evaluacion-m02` |
| HEAD V2 | `7e1174d145b2785b331f8c63f49dc6f1b0989621` |
| Estado del árbol | Único cambio: `EvaluacionV2/` sin seguimiento. No hay archivos rastreados modificados |
| Ambiente | TEST HTTPS, el mismo host que en V1 |
| Colección reutilizada | `test_tc_m02_g44.json` |
| Archivos generados | `EvaluacionV2/Resultados/reporte_tc_m02_g44_v2.json`, `EvaluacionV2/Resultados/reporte_tc_m02_g44_v2.html` y este informe |

**Validez del reporte V2:** el JSON se puede leer y corresponde a la colección *«TC-M02-G44 - RF-40 validacion de formato, signo y unidad»*. Contiene la ejecución completa: 1 iteración, 34/34 ítems y 34/34 peticiones sin pendientes. Incluye los tres logins, el SETUP de cada actor, las 12 peticiones principales con cuerpos de petición y respuesta, sus aserciones y las 12 verificaciones de no persistencia.

> El HEAD registrado corresponde al repositorio de QA desde el que se ejecutó la colección. No identifica la versión desplegada del backend en TEST, que no consta en la evidencia.

---

## 4. Evidencia de reutilización de la prueba

La Evaluación V2 reutilizó sin modificación la colección automatizada `test_tc_m02_g44.json` de la evaluación original. La nueva ejecución generó evidencia independiente en `EvaluacionV2/Resultados`.

Evidencia:

1. `git status` no muestra modificaciones en `test_tc_m02_g44.json`.
2. `git hash-object test_tc_m02_g44.json` = `4a882763e615ef658022c01c5b090c7e5ece117b`, que coincide con el blob versionado en `HEAD`. El último commit que tocó el archivo es `5defb7ae` (*Pruebas funcionales M02, RF-40, RF-48, RF-50, RF-51*), anterior a esta reevaluación.
3. Los 34 ítems de la colección, en su orden, coinciden exactamente con los ejecutados en V1 y en V2.
4. Los nombres de las 96 aserciones son idénticos en V1 y V2. Solo varían los conteos numéricos interpolados, como `4 -> 4`.
5. El `_postman_id` del reporte es distinto en V1 (`7fb98c01…`) y en V2 (`acb5c4c2…`). No indica un cambio en la colección: el archivo no define `_postman_id` y Newman genera uno nuevo en cada ejecución.

Hay que distinguir dos tipos de artefacto:

| Tipo | Archivo | Naturaleza |
|---|---|---|
| **Definición de la prueba** | `test_tc_m02_g44.json` | Colección Postman: peticiones, payloads y aserciones. Común a V1 y V2 |
| Generador | `construir_coleccion.cjs` | Script que produjo la colección. **No se ejecutó para V2** |
| **Resultado V1** | `Resultados/reporte_tc_m02_g44.json` / `.html` | Evidencia de la ejecución del 2026-09-10 |
| **Resultado V2** | `EvaluacionV2/Resultados/reporte_tc_m02_g44_v2.json` / `.html` | Evidencia de la ejecución del 2026-09-19 (UTC) |

---

## 5. Gate y SETUP

**Gate V2:** `GET /openapi.json` → **HTTP 200**. Aserciones aprobadas: el contrato declara `POST /activos-biologicos/{id_activo}/eventos/crecimiento`, y `tipo_medicion`, `valor_medicion` y `unidad_medida` son obligatorios.

| Actor | Login | Usuario/ID esperado | Activo | Acceso | Estado | Tipo | Resultado setup |
|---|---|---:|---:|---|---|---|---|
| Productor | HTTP 200 (`m2m.nuevo@ejemplo.com`) | 35 ✅ (`sub` del JWT) | 279 | `GET /activos-biologicos/279` → 200 | ACTIVO | INDIVIDUAL | ✅ Correcto. Conteo base = 4 |
| Veterinario | HTTP 200 (`juan.carlos.qa133@sgpmp-test.com`) | 3 ✅ (`sub` del JWT) | 311 | `GET /activos-biologicos/311` → 200 | ACTIVO | INDIVIDUAL | ✅ Correcto. Conteo base = 2 |
| Ingeniero de campo | HTTP 200 (`ingeniero@pecuaria.co`) | 4 ✅ (`sub` del JWT) | 312 | `GET /activos-biologicos/312` → 200 | ACTIVO | INDIVIDUAL | ✅ Correcto. Conteo base = 4 |

No hubo fallos de autenticación, fixture, autorización ni disponibilidad del endpoint. Los tres actores ejecutaron sus casos con precondiciones válidas. El SETUP de V2 es solo de lectura: logins y `GET`.

---

## 6. TC-M02-082 — valor no numérico

Payload: base válida (`PESO`, `kg`, `fecha 2026-09-10T08:30:00Z`) con `valor_medicion = "abc"`.

| Actor | Valor | HTTP V1 | HTTP V2 | Mensaje/campo V2 | Persistencia V2 | Resultado V2 | Evolución |
|---|---|---:|---:|---|---|---|---|
| Productor | `"abc"` | 400 | 400 | `valor_medicion`: *El valor ingresado no es un número decimal válido.* | NO (4 → 4) | APROBADO | SIN REGRESIÓN |
| Veterinario | `"abc"` | 400 | 400 | `valor_medicion`: *El valor ingresado no es un número decimal válido.* | NO (2 → 2) | APROBADO | SIN REGRESIÓN |
| Ingeniero de campo | `"abc"` | 400 | 400 | `valor_medicion`: *El valor ingresado no es un número decimal válido.* | NO (4 → 4) | APROBADO | SIN REGRESIÓN |

Con cada actor, las 5 aserciones de la petición pasaron:

- se rechazó la petición;
- el rechazo fue controlado (4xx);
- **HTTP 400** según la ficha;
- el mensaje corresponde a un valor no numérico;
- el error se atribuye al campo `valor_medicion`.

Además pasó la aserción de no persistencia posterior. `error_code = VAL_ENTRADA` en los tres casos.

**Cambio respecto a V1:** el mensaje del campo ya no es *«Input should be a valid decimal»* (inglés, V1), sino *«El valor ingresado no es un número decimal válido.»* (español). Ver §14.

---

## 7. TC-M02-083-A — valor igual a cero

Payload: base válida con `valor_medicion = 0`.

| Actor | Valor | HTTP V1 | HTTP V2 | Mensaje/campo V2 | Persistencia V2 | Resultado V2 | Evolución |
|---|---|---:|---:|---|---|---|---|
| Productor | `0` | 400 | 400 | `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO (4 → 4) | APROBADO | SIN REGRESIÓN |
| Veterinario | `0` | 400 | 400 | `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO (2 → 2) | APROBADO | SIN REGRESIÓN |
| Ingeniero de campo | `0` | 400 | 400 | `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO (4 → 4) | APROBADO | SIN REGRESIÓN |

Con cada actor pasaron las 3 aserciones de la petición:

- se rechazó la petición;
- el rechazo fue controlado (4xx, sin 5xx);
- el mensaje identifica un valor no positivo.

También pasó la aserción de no persistencia. La colección exige un 4xx controlado para este subcaso, y el código observado fue 400 en los tres actores.

---

## 8. TC-M02-083-B — valor negativo

Payload: base válida con `valor_medicion = -5`.

| Actor | Valor | HTTP V1 | HTTP V2 | Mensaje/campo V2 | Persistencia V2 | Resultado V2 | Evolución |
|---|---|---:|---:|---|---|---|---|
| Productor | `-5` | 400 | 400 | `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO (4 → 4) | APROBADO | SIN REGRESIÓN |
| Veterinario | `-5` | 400 | 400 | `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO (2 → 2) | APROBADO | SIN REGRESIÓN |
| Ingeniero de campo | `-5` | 400 | 400 | `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO (4 → 4) | APROBADO | SIN REGRESIÓN |

Con cada actor pasaron las 3 aserciones de la petición y la de no persistencia, igual que en TC-M02-083-A. El contrato OpenAPI admite `0` y negativos según V1 §2.1, así que el rechazo sigue viniendo de la regla de negocio `valor_medicion > 0`, que se mantiene.

---

## 9. TC-M02-084 — unidad incompatible

Payload: base válida con `tipo_medicion = PESO`, `valor_medicion = 250` y `unidad_medida = cm`.

| Actor | Valor | HTTP V1 | HTTP V2 | Mensaje/campo V2 | Persistencia V2 | Resultado V2 | Evolución |
|---|---|---:|---:|---|---|---|---|
| Productor | `PESO` + `cm` | 400 | 400 | campo `null`: *La unidad de medida 'cm' no corresponde al tipo de medición 'PESO'. Unidades permitidas para PESO: gr, kg, lb.* | NO (4 → 4) | APROBADO | SIN REGRESIÓN |
| Veterinario | `PESO` + `cm` | 400 | 400 | idéntico | NO (2 → 2) | APROBADO | SIN REGRESIÓN |
| Ingeniero de campo | `PESO` + `cm` | 400 | 400 | idéntico | NO (4 → 4) | APROBADO | SIN REGRESIÓN |

Con cada actor pasaron las 5 aserciones de la petición:

- se rechazó la petición;
- el rechazo fue controlado;
- **HTTP 400** según la ficha;
- el mensaje corresponde a una incompatibilidad entre unidad y tipo;
- el mensaje contiene la cláusula sustantiva de la ficha.

También pasó la aserción de no persistencia. El error se devuelve sin campo asociado (`field: null`), igual que en V1. Es una validación entre campos y no afecta a ningún criterio de la colección.

---

## 10. Verificación de no persistencia

La colección toma un conteo base (PRE) de los registros `categoria = 'CRECIMIENTO'` en `GET /activos-biologicos/{id}/historial?page_size=100`. Después de **cada** petición negativa vuelve a consultar el historial (POST) y afirma que el conteo es igual al base. Los valores provienen de las aserciones del reporte V2.

| Actor | Escenario | PRE | POST | Delta | Resultado |
|---|---|---:|---:|---:|---|
| Productor | TC-M02-082 (`"abc"`) | 4 | 4 | **0** | ✅ Sin persistencia |
| Productor | TC-M02-083-A (`0`) | 4 | 4 | **0** | ✅ Sin persistencia |
| Productor | TC-M02-083-B (`-5`) | 4 | 4 | **0** | ✅ Sin persistencia |
| Productor | TC-M02-084 (`PESO`+`cm`) | 4 | 4 | **0** | ✅ Sin persistencia |
| Veterinario | TC-M02-082 (`"abc"`) | 2 | 2 | **0** | ✅ Sin persistencia |
| Veterinario | TC-M02-083-A (`0`) | 2 | 2 | **0** | ✅ Sin persistencia |
| Veterinario | TC-M02-083-B (`-5`) | 2 | 2 | **0** | ✅ Sin persistencia |
| Veterinario | TC-M02-084 (`PESO`+`cm`) | 2 | 2 | **0** | ✅ Sin persistencia |
| Ingeniero de campo | TC-M02-082 (`"abc"`) | 4 | 4 | **0** | ✅ Sin persistencia |
| Ingeniero de campo | TC-M02-083-A (`0`) | 4 | 4 | **0** | ✅ Sin persistencia |
| Ingeniero de campo | TC-M02-083-B (`-5`) | 4 | 4 | **0** | ✅ Sin persistencia |
| Ingeniero de campo | TC-M02-084 (`PESO`+`cm`) | 4 | 4 | **0** | ✅ Sin persistencia |

**Delta = 0 en los 12 casos.** Ninguna petición de V2 creó un evento de crecimiento.

**Conteo base distinto al de V1:** en V1 el conteo base era 3 / 1 / 3 (activos 279 / 311 / 312). En V2 es 4 / 2 / 4, un evento más por activo. Esos eventos ya existían cuando empezó V2, porque son el conteo PRE. No los creó TC-M02-G44: la colección solo envía peticiones inválidas, y V1 demostró Δ = 0 en API y en BD. Su origen no se puede determinar con la evidencia disponible. V2 no incluye consultas `SELECT` a la BD, así que la no persistencia de V2 se demuestra solo mediante el historial expuesto por la API, igual que en las 12 verificaciones intermedias de V1.

---

## 11. Resultado de Newman V2

| Métrica | Valor |
|---|---:|
| Iteraciones | 1 (0 fallidas) |
| Ítems / peticiones | 34 / 34 (0 fallidas, 0 pendientes) |
| Scripts de test | 34 (0 fallidos) |
| Aserciones totales | **96** |
| Aserciones aprobadas | **96** |
| Aserciones fallidas | **0** |
| Errores de ejecución (`run.failures`) | 0 |
| Duración | 9,0 s |
| Tiempo de respuesta medio / mín / máx | 177,6 ms / 121 ms / 1005 ms (el máximo corresponde a `GET /openapi.json`) |

Distribución de las 96 aserciones:

- 3 del gate OpenAPI;
- 21 de SETUP (7 por actor);
- 48 de las peticiones principales (16 por actor: 5 + 3 + 3 + 5);
- 24 de no persistencia (2 por verificación × 12).

Las cifras son idénticas a las de la ejecución oficial de V1: 34 peticiones, 96 aserciones y 0 fallos.

---

## 12. Comparación consolidada V1 ↔ V2

| Subcaso | V1 | V2 | Evolución | Observación |
|---|---|---|---|---|
| TC-M02-082 | APROBADO (400 × 3, Δ 0) | APROBADO (400 × 3, Δ 0) | **SIN REGRESIÓN** | El mensaje del campo ahora está en español. OBS-G44-01 ya no se reproduce (§14) |
| TC-M02-083-A | APROBADO (400 × 3, Δ 0) | APROBADO (400 × 3, Δ 0) | **SIN REGRESIÓN** | Mismo mensaje sin el prefijo `Value error, ` |
| TC-M02-083-B | APROBADO (400 × 3, Δ 0) | APROBADO (400 × 3, Δ 0) | **SIN REGRESIÓN** | Mismo mensaje sin el prefijo `Value error, ` |
| TC-M02-084 | APROBADO (400 × 3, Δ 0) | APROBADO (400 × 3, Δ 0) | **SIN REGRESIÓN** | Mismo mensaje sin el prefijo `Value error, ` |

Desglose por actor:

| Actor | 082 V1 → V2 | 083-A V1 → V2 | 083-B V1 → V2 | 084 V1 → V2 | Evolución |
|---|---|---|---|---|---|
| Productor | 400 → 400 | 400 → 400 | 400 → 400 | 400 → 400 | SIN REGRESIÓN |
| Veterinario | 400 → 400 | 400 → 400 | 400 → 400 | 400 → 400 | SIN REGRESIÓN |
| Ingeniero de campo | 400 → 400 | 400 → 400 | 400 → 400 | 400 → 400 | SIN REGRESIÓN |

---

## 13. Regresiones

No se identificaron regresiones funcionales en la reevaluación V2.

Ninguna aserción falló, así que no hay que atribuir fallos a credenciales, fixtures, autorización, disponibilidad del endpoint, respuesta funcional incorrecta ni persistencia indebida. No hay defectos que registrar ni bloqueos.

---

## 14. Observaciones

1. **OBS-G44-01 ya no se reproduce.** En V1, TC-M02-082 devolvía el mensaje por defecto de Pydantic en inglés, *«Input should be a valid decimal»*. En V2 devuelve *«El valor ingresado no es un número decimal válido.»* con los tres actores. El código HTTP, el `error_code` y el campo señalado no cambiaron. Según la evidencia de ejecución, la observación queda subsanada en el ambiente TEST. Su cierre formal en el Registro de Errores queda fuera del alcance de esta tarea. No se revisó el cambio de código que lo produjo.
2. **Se eliminó el prefijo `Value error, `.** En V1, los mensajes de 083-A, 083-B y 084 llevaban el prefijo técnico `Value error, ` de Pydantic. En V2 aparece solo el texto de negocio. Es una mejora cosmética y no afecta a ninguna aserción.
3. **Conteo base diferente** (3/1/3 → 4/2/4). Los eventos ya existían antes de la ejecución V2 y no los generó G44 (§10). No afecta al criterio, que se evalúa con el delta dentro de la misma ejecución.
4. **Credencial del Veterinario.** V2 usó otra vez la cuenta vigente del usuario id 3 (`juan.carlos.qa133@sgpmp-test.com`), igual que V1. La recomendación de V1 de actualizar la credencial en el paquete de instrucciones sigue vigente.
5. **V2 no incluye evidencia de BD.** A diferencia de V1, V2 no incluye consultas `SELECT` a PostgreSQL. La no persistencia se sustenta en las 12 aserciones PRE/POST sobre el historial de la API, que V1 ya validó contra las mismas tablas.

Ninguna de estas observaciones es un defecto funcional.

---

## 15. Veredicto final

# ✅ APROBADO

- Los cuatro escenarios obligatorios (082, 083-A, 083-B y 084) se rechazaron con **HTTP 400 / VAL_ENTRADA** con los **tres actores**, sin ningún 5xx, 401 ni 403.
- En cada caso, el mensaje y el campo corresponden a la regla evaluada.
- **No hay persistencia indebida:** delta = 0 en las 12 verificaciones.
- **96/96 aserciones aprobadas**, 0 errores de ejecución.
- No hay escenarios bloqueados ni incumplimientos funcionales.

---

## 16. Conclusión V1 ↔ V2

- **V1 (2026-09-10):** la colección `test_tc_m02_g44.json` demostró que RF-40 rechaza los valores `"abc"`, `0` y `-5`, y la combinación `PESO` + `cm`, con HTTP 400 y sin persistir eventos, para Productor, Veterinario e Ingeniero de campo. Veredicto APROBADO, con una observación de localización (OBS-G44-01).
- **V2 (2026-09-19 UTC):** la **misma colección, sin modificaciones**, produjo los mismos códigos HTTP, los mismos rechazos y el mismo delta 0 para los tres actores. Pasaron las 96 aserciones.
- **El comportamiento validado se mantiene.** No hay regresión. La única diferencia observable es que ahora todos los mensajes de validación están en español y sin prefijos técnicos, lo que resuelve OBS-G44-01.
- Como V2 reutilizó la misma prueba automatizada, cualquier diferencia se debe al sistema bajo prueba y no a un cambio en la prueba.

---

## 17. Declaración de integridad

- ✅ **No se modificó la Evaluación V1.** `Resultados/TC-M02-G44_resultado.md`, `reporte_tc_m02_g44.json` y `reporte_tc_m02_g44.html` solo se leyeron.
- ✅ **`test_tc_m02_g44.json` no se modificó para V2.** Su hash coincide con el blob de `HEAD` y `git status` no muestra cambios.
- ✅ **`construir_coleccion.cjs` no se ejecutó ni se modificó** para crear una prueba distinta.
- ✅ **V2 generó evidencia independiente** en `EvaluacionV2/Resultados/`.
- ✅ Durante esta documentación no se volvió a ejecutar Newman ni Postman. El análisis se hizo solo sobre los reportes existentes.
- ✅ **No se modificó código productivo.**
- ✅ **No se hicieron commits.**
- ✅ **No se hizo push.**
- ✅ **No se hizo deploy.**
- ✅ No se cambió de rama, no se creó ningún ticket en Taiga ni ningún Issue en GitHub, y no se modificó el Registro de Errores.
