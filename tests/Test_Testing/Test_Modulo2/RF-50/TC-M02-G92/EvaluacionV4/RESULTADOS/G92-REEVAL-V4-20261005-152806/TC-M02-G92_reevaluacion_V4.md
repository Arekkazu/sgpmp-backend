# TC-M02-G92 — CUARTA EVALUACIÓN (V4)

**Caso agrupado:** TC-M02-G92 — Consumo exitoso de datos analíticos e indicadores zootécnicos por módulos autorizados
**Casos originales:** TC-M02-154 — Consumir API interna con módulo autorizado · TC-M02-159 — Calcular Ganancia Diaria de Peso con datos suficientes
**Requerimientos:** RF-50 / RF-51 · **Caso de uso:** CU12 — Consultar indicadores y exponer datos
**Tipo:** Funcional · **Herramienta:** API / Postman / Newman · **Prioridad:** Alta
**Responsable QA:** Juan Esteban
**RUN_ID:** `G92-REEVAL-V4-20261005-152806`
**Fecha:** 2026-10-05 · **Ambiente decisorio:** TEST
**Incidencia en seguimiento:** INC-M02-90-G92 (#241)

---

## DECISIÓN GENERAL

### TC-M02-G92: APROBADO

### TC-M02-154: APROBADO
### TC-M02-159: APROBADO

Los dos subcasos se ejecutaron en esta V4 reproduciendo exactamente la prueba de V3 —mismo actor,
mismos endpoints, misma petición canónica, mismo fixture, mismos expected y las mismas 26
assertions— y ambos cumplen. **26 assertions, 0 failures.**

El resultado decisivo es el de TC-M02-154, que en V3 quedó BLOQUEADO: **la precondición de
provisión que lo bloqueaba está resuelta**. El rol técnico Integración M04 ahora tiene autorización
de lectura sobre `datos_analiticos_metricas`, de modo que la consulta completa de datos
consolidados —la que por contrato abarca todas las secciones— responde **HTTP 200** en 134 ms,
conforme al contrato y sin modificar nada del escenario.

| Caso | Resultado V4 | Evidencia decisiva |
| --- | --- | --- |
| TC-M02-154 | **APROBADO** | `tipo_dato=todos` → **200** en 134 ms · 16/16 campos del contrato · 7/7 assertions |
| TC-M02-159 | **APROBADO** | **200** en 114 ms · `ganancia_peso` = **0.9677 kg/día**, igual al recálculo independiente · 14/14 assertions |
| **Grupo** | **APROBADO** | Escenario A del paquete |

**Escrituras: 0.** 0 escrituras funcionales del caso, 0 escrituras de preparación, 0 SQL de
escritura, 0 cambios de RBAC, rol o scopes, 0 eventos o mediciones creados, 0 modificaciones del
activo. **No se modificó el RBAC para hacer pasar TC-M02-154**: el scope ya estaba concedido cuando
se ejecutó el preflight.

---

## RESUMEN DEL RESULTADO

| Elemento | Valor |
| --- | --- |
| Assertions totales | **26** |
| Failures | **0** |
| TC-M02-154 | 7 assertions · 0 fallidas |
| TC-M02-159 | 14 assertions · 0 fallidas |
| Login e identidad (pasos 00 y 01) | 5 assertions · 0 fallidas |
| Peticiones de la ejecución oficial | 4 (un POST de sesión y tres GET) |
| Escrituras funcionales | 0 |
| Ejecuciones oficiales creadas | 1 |

El conjunto de assertions coincide exactamente con la referencia de V3: 26 en total, de las cuales
14 corresponden a TC-M02-159. **No se redujo, relajó, eliminó ni añadió ninguna**, y el oráculo no
se adaptó al comportamiento del producto.

Lo que cambió entre V3 y V4 cabe en una línea: **el scope `datos_analiticos_metricas` pasó de
ausente a concedido**, y con eso el subcaso que llevaba tres evaluaciones sin poder verificarse
quedó aprobado.

| Precondición | V3 | V4 |
| --- | --- | --- |
| Identidad técnica M04 disponible y activa | sí | sí |
| Rol Integración M04 | sí | sí |
| READ sobre `activos_biologicos` | sí | sí |
| Alcance sobre el activo del fixture | sí (tras una preparación) | **sí, ya presente → 0 preparaciones** |
| Scope `datos_analiticos_eventos` | sí | sí |
| Scope `datos_analiticos_fases` | sí | sí |
| Scope `datos_analiticos_estado` | sí | sí |
| **Scope `datos_analiticos_metricas`** | **no** | **sí** |
| TC-M02-154 | 403 `SCOPE_TIPO_DATO_NO_AUTORIZADO` | **200** |
| TC-M02-159 | 200 · 0.9677 kg/día | **200 · 0.9677 kg/día** |

---

## ANTECEDENTES

| Evaluación | Ambiente | TC-M02-154 | TC-M02-159 | Grupo | Escrituras |
| --- | --- | --- | --- | --- | ---: |
| **V1** | TEST | BLOQUEADO — no ejecutado | BLOQUEADO — no ejecutado | **BLOQUEADO** — sin identidad técnica | 0 |
| **V2** | TEST | BLOQUEADO / no ejecutado | BLOQUEADO / no ejecutado | **BLOQUEADO** — identidad no provisionada | 0 |
| **V3** | TEST | **BLOQUEADO** — 403 `SCOPE_TIPO_DATO_NO_AUTORIZADO`: la consulta completa requería también autorización sobre `metricas` | **APROBADO** — 200 en 142 ms, `ganancia_peso` 0.9677 kg/día | **BLOQUEADO** a nivel de grupo | 1 de preparación (alcance de finca) |
| **V4** | TEST | **APROBADO** | **APROBADO** | **APROBADO** | **0** |

RUN de V3: `G92-REEVAL-V3-20260927-200452`. V1, V2 y V3 se conservan intactas y sus resultados no
se reescriben.

El bloqueo de V3 **no fue un defecto de RF-50** sino una precondición de provisión, y así quedó
registrado entonces. V4 confirma esa interpretación: en cuanto el scope se concedió, el endpoint
respondió 200 conforme al contrato sin ningún cambio de código ni de oráculo.

---

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Ambiente decisorio | **TEST** |
| URL TEST oficial adoptada | `https://api.inmero.co/back-sigab-test` |
| URL configurada en la colección V3 | `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| ¿Mismo despliegue? | **Sí** — `sha256` de `/openapi.json` idéntico (`faca4efba0499deb…`) |
| Ejecuciones contra ambos dominios | **No** — una sola ejecución oficial |
| `GET /health` | 200 |
| `GET /openapi.json` | 200, versión 1.0.0 |
| Rama QA (backend y frontend) | `qa/juan-esteban-cuarta-evaluacion-M09-y-M02` |
| HEAD backend | `0371f2ec1d97ddfe7f3f33526d0db071d016e6ea` (= `origin/test`, `0 0`) |
| HEAD frontend | `cd3af47c07302f7310b17e6800642aab2253f479` (`2 0` respecto de `origin/test`) |

Ambos dominios resuelven al mismo backend, de modo que **el cambio de dominio no altera la prueba**.
Se adoptó `api.inmero.co/back-sigab-test` como URL oficial única por ser la vigente, y es el único
ajuste que se hizo sobre la colección de V3. **DEV no se utilizó**: no es decisorio para este grupo.

Contrato verificado en TEST:

| Endpoint | Método | Presente |
| --- | --- | --- |
| `/activos-biologicos/{id_activo}/datos-consolidados` | `GET` | sí |
| `/activos-biologicos/{id_activo}/indicadores` | `GET` | sí |

`DatosConsolidadosResponse` declara los dieciséis campos que TC-M02-154 exige;
`IndicadorZootecnicoResponse` declara los ocho campos que TC-M02-159 exige.

---

## ACTOR / IDENTIDAD TÉCNICA

| Campo | Valor |
| --- | --- |
| Correo | `integracion.tes@gmail.com` |
| `id_usuario` | 111 |
| Rol | **Integración M04** (`id_rol` 78) |
| Estado de cuenta | **Activo** |
| Login | HTTP 200 |
| Es exactamente la identidad del caso | **sí** |
| Sustituida por otra identidad | **no** |
| Permisos activos del rol | 6 |
| Recursos con READ | 9, 29, 60, 61, 62, **63** |
| READ sobre `activos_biologicos` (29) | **sí** |
| Activos biológicos visibles | 29 |

### Scopes analíticos verificados en runtime

| Scope | Recurso | V3 | **V4** |
| --- | ---: | --- | --- |
| `datos_analiticos_eventos` | 60 | sí | **sí** |
| `datos_analiticos_fases` | 61 | sí | **sí** |
| `datos_analiticos_estado` | 62 | sí | **sí** |
| `datos_analiticos_metricas` | 63 | **no** | **sí** |

El permiso nuevo aparece en el rol como `integracion_m04_leer_datos_analiticos_metricas`
(recurso 63, acción 2). Esto es lo que resuelve la precondición histórica de TC-M02-154.

Los scopes se comprobaron con el token de la propia identidad técnica
(`GET /sesiones/me/permisos`), no a través de un observador administrativo.

La contraseña se tomó únicamente de una variable de entorno del proceso y se entregó a Newman como
variable de entorno de la ejecución. **No aparece en ningún artefacto.** No se persistieron JWT ni
encabezados `Authorization`.

**Hallazgo de seguridad saneado.** El reporte JSON de Newman conservaba la cabecera `Set-Cookie` de
la respuesta de login, con el valor de la cookie `refresh_token` (4 ocurrencias). Se detectó en el
escaneo previo al cierre y se redactó el valor de la cookie en el reporte antes de finalizar, sin
reejecutar el RUN y sin alterar la validez del JSON ni ninguna assertion. El saneador del runner se
corrigió para redactar los valores de cookie de origen en adelante. **Escaneo final: 0 ocurrencias
en los cuatro artefactos.**

---

## CONFIGURACIÓN UTILIZADA / FIXTURE

El fixture de V3 **se revalidó y se reutilizó sin cambios**. No se buscó ni se sustituyó por otro
activo.

| Campo | V3 | V4 (revalidado) | Coincide |
| --- | --- | --- | --- |
| `id_activo_biologico` | 295 | 295 | sí |
| Identificador | `QAJE-DAT-COMPL` | `QAJE-DAT-COMPL` | sí |
| Tipo | INDIVIDUAL | INDIVIDUAL | sí |
| Estado | ACTIVO | ACTIVO | sí |
| Infraestructura | 48 | 48 | sí |
| Visible para la identidad técnica | sí | sí | sí |

El fixture se leyó **con la propia identidad técnica**, no con una cuenta administrativa.

Mediciones de peso conservadas:

| `id_eventos` | Fecha | Valor | Unidad |
| ---: | --- | ---: | --- |
| 224 | 2026-07-15 | 200.00 | kg |
| 225 | 2026-08-15 | 230.00 | kg |

### Expected independiente (recalculado, no tomado de la API)

```
días transcurridos = 2026-08-15 − 2026-07-15 = 31
ganancia diaria    = (230.00 − 200.00) / 31 = 0.967741935…

por decimales:  2 → 0.97   3 → 0.968   4 → 0.9677   5 → 0.96774   6 → 0.967742
expected del oráculo (4 decimales) = 0.9677 kg/día
```

El cálculo se hizo con aritmética decimal exacta —escalado con enteros grandes, sin coma
flotante— **antes** de ejecutar el oráculo, y de forma independiente de lo que devuelva la API.
Total de mediciones: 2. Peso inicial: 200.00. Peso final: 230.00. Días: 31.

**Escrituras de preparación: 0.** La identidad ya tenía alcance sobre el activo del fixture, de modo
que la preparación que fue legítima en V3 no fue necesaria en V4. No se modificaron fincas, scopes
ni rol.

### Reutilización de la automatización

| Aspecto | Valor |
| --- | --- |
| Colección origen | `EvaluacionV3/test_tc_m02_g92_v3.json` |
| Colección V4 generada | **no** — se reutilizó la de V3 en memoria, en modo lectura |
| Único ajuste aplicado | host de las URLs: dominio `sslip.io` → `api.inmero.co/back-sigab-test` |
| Assertions declaradas en la colección | **26** |
| Assertions modificadas / eliminadas / añadidas | **0 / 0 / 0** |
| Orden de ejecución | 00 login · 01 identidad y rol · 02 TC-M02-154 · 03 TC-M02-159 |

Se verificó además que las variables de la colección V3 siguen coincidiendo con el fixture y los
expected descubiertos en el preflight —activo, identificador, fechas, expected de ganancia, pesos,
días, total de mediciones y el RNF de 5000 ms—: **las diez coherencias se cumplen**. Si alguna no
hubiera coincidido, la ejecución se habría detenido antes de abrir el RUN.

El runner `run-v4.cjs` existe por una razón concreta: la fase oficial de
`EvaluacionV3/run-newman.cjs` escribe dentro de `EvaluacionV3/RESULTADOS/` y reescribe su propia
colección, de modo que ejecutarla habría modificado V3. El runner V4 es el mínimo necesario para
evitarlo.

---

## TC-M02-154

**Resultado: APROBADO.**

Petición canónica, **sin modificar**:

```
GET /activos-biologicos/295/datos-consolidados?tipo_dato=todos&pagina=1&page_size=20
Actor: integracion.tes@gmail.com (Integración M04)
```

**No se sustituyó `tipo_dato=todos` por ningún tipo de dato parcial.** El escenario es el mismo que
el de V3: la consulta completa de datos consolidados.

| Comprobación | Esperado | Observado | Resultado |
| --- | --- | --- | --- |
| HTTP | 200 | **200** | CUMPLE |
| `Content-Type` | `application/json` | `application/json` | CUMPLE |
| Tiempo de respuesta | ≤ 5000 ms | **134 ms** | CUMPLE |
| Campos del contrato | 16 | **16 presentes, 0 ausentes** | CUMPLE |
| Corresponde al activo solicitado | activo 295 · `QAJE-DAT-COMPL` | coincide | CUMPLE |
| No expone datos de otros activos | 0 eventos ajenos | 0 | CUMPLE |
| Paginación coherente | página 1, 20 por página | `pagina_actual` 1 · `registros_por_pagina` 20 · `total_registros` 3 · `total_paginas` 1 | CUMPLE |

Campos del contrato verificados en la respuesta: `id_activo_biologico`, `identificador`,
`tipo_activo`, `especie`, `estado_actual`, `infraestructura_asociada`, `fase_productiva_activa`,
`historial_eventos`, `historial_fases`, `historico_estados`, `metricas_actuales`,
`total_registros`, `pagina_actual`, `total_paginas`, `registros_por_pagina`, `fecha_generacion`.

**7 de 7 assertions superadas:**

| Assertion | Resultado |
| --- | --- |
| HTTP 200 | CUMPLE |
| Respuesta en JSON | CUMPLE |
| Tiempo de respuesta dentro del RNF | CUMPLE |
| La respuesta cumple el contrato desplegado | CUMPLE |
| Los datos corresponden al activo solicitado | CUMPLE |
| No expone información de otros activos | CUMPLE |
| La paginación es coherente | CUMPLE |

El subcaso incluye `metricas_actuales` en la respuesta, que es precisamente la sección que el scope
recién concedido habilita. Ese es el cambio funcional observable respecto de V3.

---

## TC-M02-159

**Resultado: APROBADO.**

Petición, idéntica a la de V3:

```
GET /activos-biologicos/295/indicadores?tipo_indicador=CRECIMIENTO
    &fecha_inicio=2026-07-15&fecha_fin=2026-08-15
Actor: integracion.tes@gmail.com (Integración M04)
```

| Comprobación | Esperado | Observado | Resultado |
| --- | --- | --- | --- |
| HTTP | 200 | **200** | CUMPLE |
| Tiempo de respuesta | ≤ 5000 ms | **114 ms** | CUMPLE |
| Indicador presente | `ganancia_peso` | `ganancia_peso` | CUMPLE |
| `disponible` | `true` | `true` | CUMPLE |
| Unidad | `kg/dia` | `kg/dia` | CUMPLE |
| **Valor** | **0.9677** (recálculo independiente) | **0.9677** | CUMPLE |
| `periodo_inicio` / `periodo_fin` | 2026-07-15 / 2026-08-15 | 2026-07-15 / 2026-08-15 | CUMPLE |
| Campos del indicador | 8 | los 8 presentes | CUMPLE |

Indicador devuelto:

```json
{
  "tipo": "ganancia_peso",
  "valor": "0.9677",
  "unidad": "kg/dia",
  "disponible": true,
  "periodo_inicio": "2026-07-15",
  "periodo_fin": "2026-08-15",
  "fecha_calculo": "2026-10-05T15:30:26.561822Z",
  "variables_usadas": {
    "peso_inicial_kg": 200,
    "peso_final_kg": 230,
    "dias": 31,
    "total_mediciones": 2
  }
}
```

Las variables que el backend declara haber usado coinciden una por una con la verificación
independiente: peso inicial 200, peso final 230, días 31, total de mediciones 2. **El valor no se
aceptó por venir de la API**: se comparó contra el 0.9677 recalculado antes de la ejecución.

**14 de 14 assertions superadas**, incluidas las cuatro que comprueban las variables declaradas por
el backend contra el recálculo propio.

El resultado reproduce el de V3 (200, `ganancia_peso`, 0.9677 kg/día) con el mismo fixture, lo que
confirma que **no hay regresión en RF-51**.

---

## RESULTADO DEL ORÁCULO

| Elemento | Valor |
| --- | --- |
| RUN_ID | `G92-REEVAL-V4-20261005-152806` (único) |
| Ejecución oficial Newman | 1 · 1 iteración · 4 peticiones |
| Assertions totales | **26** |
| Failures | **0** |
| Assertions modificadas, reducidas o relajadas | **0** |
| Criterios funcionales añadidos | **0** |
| Oráculo adaptado al comportamiento del producto | **no** |
| Retries automáticos | **0** |
| Escrituras funcionales | **0** |
| Escrituras de preparación | **0** |
| SQL de escritura | **0** |
| Cambios de RBAC / rol / scopes | **0** |

Desglose por paso de la colección:

| Paso | Método | HTTP | Tiempo | Assertions | Fallidas |
| --- | --- | ---: | ---: | ---: | ---: |
| 00 — Login de la identidad técnica | POST | 200 | — | 1 | 0 |
| 01 — Identidad y rol del consumidor | GET | 200 | — | 4 | 0 |
| 02 — TC-M02-154 | GET | 200 | 134 ms | 7 | 0 |
| 03 — TC-M02-159 | GET | 200 | 114 ms | 14 | 0 |
| **Total** | | | | **26** | **0** |

No se añadieron peticiones innecesarias al RUN oficial: las comprobaciones administrativas y de
solo lectura quedaron en el preflight, fuera del RUN.

---

## COMPARACIÓN V1 VS V2 VS V3 VS V4

| Aspecto | V1 | V2 | V3 | **V4** |
| --- | --- | --- | --- | --- |
| TC-M02-154 | BLOQUEADO (no ejecutado) | BLOQUEADO (no ejecutado) | BLOQUEADO (403 por scope) | **APROBADO (200)** |
| TC-M02-159 | BLOQUEADO (no ejecutado) | BLOQUEADO (no ejecutado) | **APROBADO** (0.9677) | **APROBADO (0.9677)** |
| Grupo | BLOQUEADO | BLOQUEADO | BLOQUEADO | **APROBADO** |
| RUN oficial | — | ninguno | `G92-REEVAL-V3-20260927-200452` | `G92-REEVAL-V4-20261005-152806` |
| Identidad técnica disponible | No | No | Sí | **Sí** |
| Cuenta activa y rol de integración | — | — | Sí | **Sí** |
| READ sobre `activos_biologicos` | — | — | Sí | **Sí** |
| Alcance sobre el activo | — | — | Sí (tras 1 preparación) | **Sí, ya presente** |
| Scopes `eventos` / `fases` / `estado` | — | — | Sí / Sí / Sí | **Sí / Sí / Sí** |
| Scope `metricas` | — | — | **No** | **Sí** |
| Permisos del rol | — | — | 5 | **6** |
| TC-154: HTTP | — | — | 403 `SCOPE_TIPO_DATO_NO_AUTORIZADO` | **200 en 134 ms** |
| TC-159: HTTP y valor | — | — | 200 en 142 ms · 0.9677 | **200 en 114 ms · 0.9677** |
| Assertions ejecutadas | 0 | 0 | 26 (4 fallidas) | **26 (0 fallidas)** |
| Fixture | — | — | activo 295 | **el mismo, revalidado** |
| Escrituras | 0 | 0 | 1 de preparación | **0** |
| Factor limitante | Identidad inexistente | Identidad no provisionada | Scope de métricas | **ninguno** |

La serie se cierra limpiamente: V1 y V2 no tenían identidad técnica; V3 la obtuvo, verificó RF-51 y
dejó aislado el único elemento pendiente —un permiso de lectura—; V4 encuentra ese permiso
concedido y aprueba ambos subcasos con las mismas 26 assertions y sin ninguna falla.

---

## COMPARACIÓN TEST VS DEV

No aplica. TEST es el ambiente decisorio de este grupo y DEV no lo es. **DEV no se ejecutó**, ni
siquiera para completar esta sección.

---

## ORIGEN / INTERPRETACIÓN DEL RESULTADO

### El bloqueo de V3 era de provisión, y quedó resuelto

V3 clasificó TC-M02-154 como BLOQUEADO y dejó constancia de que el 403 **no era un defecto de
RF-50** sino una precondición de autorización ausente. V4 confirma esa lectura de la forma más
directa posible: sin tocar una línea de código, de oráculo ni de escenario, el mismo endpoint con
la misma petición canónica responde 200 en cuanto el rol recibe el scope que le faltaba.

El permiso concedido es `integracion_m04_leer_datos_analiticos_metricas` (recurso 63, acción 2), y
es exactamente el que la consulta `tipo_dato=todos` necesitaba por abarcar la sección
`metricas_actuales`.

### El comportamiento del control de scope era correcto

Conviene subrayarlo porque evita conclusiones equivocadas: el 403 de V3 era la respuesta **correcta**
del control de scope granular. El sistema rechazaba una consulta que incluía una sección para la
que el módulo no estaba autorizado. Que ahora devuelva 200 con el scope concedido demuestra que el
control discrimina por sección como debe, en ambos sentidos.

### RF-51 sin regresión

TC-M02-159 vuelve a aprobar con el mismo fixture y el mismo expected de V3 —0.9677 kg/día,
verificado con aritmética decimal exacta—, y el backend declara las mismas variables de cálculo
(200, 230, 31 días, 2 mediciones). No hay indicio de regresión.

### Qué no se hizo

- **No se modificó el RBAC.** El scope ya estaba concedido al llegar el preflight; QA no añadió
  permisos, no cambió el rol, no creó usuarios ni tocó fincas.
- **No se cambió el escenario.** La petición canónica siguió siendo `tipo_dato=todos`; no se
  sustituyó por un tipo de dato parcial para obtener un 200.
- **No se duplicó la colección.** Se reutilizó la de V3 en memoria, con un único ajuste de host.
- **No se ejecutó ninguna escritura**, ni funcional ni de preparación.

---

## INCIDENCIA

**INC-M02-90-G92 / GitHub #241.**

Estado tras V4: **CONDICIÓN PENDIENTE VERIFICADA COMO RESUELTA.**

| Alcance de la incidencia | Estado en V4 | Evidencia |
| --- | --- | --- |
| Identidad técnica M04 inexistente o no provisionada (bloqueo de V1–V2) | **Resuelto** | Autentica, activa, rol Integración M04, `id_usuario` 111 |
| READ sobre `activos_biologicos` | **Resuelto** | recurso 29, acción 2 |
| Alcance sobre el activo del fixture | **Resuelto y estable** | ya presente, sin necesidad de preparación |
| Consumo de RF-51 (indicadores) | **Funcional** | 200 · `ganancia_peso` 0.9677 kg/día · 14/14 assertions |
| Scope `datos_analiticos_metricas` para RF-50 completo | **Resuelto** | recurso 63 concedido; `tipo_dato=todos` → 200 · 7/7 assertions |

**No se creó ninguna incidencia nueva** y **no se modificó el issue de GitHub.** La condición
pendiente que V3 había observado queda **verificada como resuelta** por esta ejecución, con lo que
esta V4 aporta la evidencia funcional que faltaba para sustentar el cierre de INC-M02-90-G92. La
decisión de cerrarlo queda fuera de esta ejecución automática.

---

## CONCLUSIÓN

La cuarta evaluación de TC-M02-G92 cierra el grupo en **APROBADO**, con los dos subcasos ejecutados
en una única ejecución oficial, **26 assertions y 0 failures**, y **0 escrituras** de cualquier
clase.

**TC-M02-154 queda APROBADO**, y con ello se cierra el único hueco que quedaba en este grupo. La
consulta completa de datos consolidados —`tipo_dato=todos`, sin alterar el escenario— responde
**HTTP 200 en 134 ms**, con los dieciséis campos del contrato presentes, los datos correspondientes
al activo solicitado, sin exponer información de otros activos y con paginación coherente. El
bloqueo de V3 era una precondición de provisión, no un defecto, y **quedó resuelto**: el rol
Integración M04 ya tiene autorización de lectura sobre `datos_analiticos_metricas`.

**TC-M02-159 queda APROBADO**, reproduciendo el resultado de V3 con el mismo fixture: **200 en
114 ms** y `ganancia_peso` de **0.9677 kg/día**, idéntico al recálculo independiente hecho con
aritmética decimal exacta antes de ejecutar el oráculo. Las variables que el backend declara haber
usado coinciden una por una con las reales. **No hay regresión en RF-51.**

La prueba se reprodujo exactamente: mismo actor, mismos endpoints, misma petición canónica, mismo
fixture revalidado, mismos expected y las mismas 26 assertions de V3, reutilizadas sin modificar,
reducir ni relajar ninguna. El único ajuste fue apuntar la colección a la URL TEST vigente, que
sirve el mismo despliegue.

V1, V2 y V3 permanecen intactas, y sus resultados históricos no se reescriben.

---

### Artefactos de este RUN

`EvaluacionV4/RESULTADOS/G92-REEVAL-V4-20261005-152806/`

| Archivo | Contenido |
| --- | --- |
| `evidencia-g92-v4.json` | Evidencia consolidada: RUN_ID, fecha, ambiente y URL adoptada, Git inicial y final, contrato, actor con rol y scopes, alcance, fixture revalidado, expected independiente, detalle de la reutilización de la colección V3 con su comprobación de coherencia, resultado de Newman, TC-M02-154, TC-M02-159, tiempos, assertions, failures, escrituras y seguridad |
| `newman-g92-v4.json` | Reporte JSON de la ejecución oficial de Newman, saneado |
| `TC-M02-G92_reevaluacion_V4.md` | Este informe |

`EvaluacionV4/run-v4.cjs` es el runner mínimo. **No se generó colección V4**: se reutilizó
`EvaluacionV3/test_tc_m02_g92_v3.json` tal como está en disco, en memoria y en modo lectura. No se
crearon reportes HTML de Newman, `README`, `plan.json`, `preflight.json`, `git-final.json` ni
`seguridad.json`: esa información está consolidada en `evidencia-g92-v4.json`.
