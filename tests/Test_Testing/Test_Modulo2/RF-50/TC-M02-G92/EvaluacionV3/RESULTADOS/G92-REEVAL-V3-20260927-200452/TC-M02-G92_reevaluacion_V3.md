# TC-M02-G92 — TERCERA EVALUACIÓN (V3)

**Caso agrupado:** TC-M02-G92 — Consumo exitoso de datos analíticos e indicadores zootécnicos por módulos autorizados
**Casos originales:** TC-M02-154 — Consumir API interna con módulo autorizado · TC-M02-159 — Calcular Ganancia Diaria de Peso con datos suficientes
**Requerimientos:** RF-50 / RF-51
**Caso de uso:** CU12 — Consultar indicadores y exponer datos
**Responsable QA:** Juan Esteban
**RUN_ID:** `G92-REEVAL-V3-20260927-200452`
**Fecha:** 2026-09-27
**Ambiente decisorio:** TEST
**Incidencia en seguimiento:** INC-M02-90-G92 (#241)

---

## DECISIÓN GENERAL

### TC-M02-G92: BLOQUEADO

### TC-M02-154: BLOQUEADO
### TC-M02-159: APROBADO

La tercera evaluación se ejecutó funcionalmente por primera vez: la identidad técnica M04 autentica,
es reconocida con su rol de integración y consume RF-51 correctamente. **TC-M02-159 queda APROBADO**,
con el indicador de ganancia diaria de peso disponible y con el valor recalculado de forma
independiente.

**TC-M02-154 queda BLOQUEADO** por una precondición de provisión distinta de la histórica: el rol
técnico no está autorizado para el tipo de dato `metricas`, y la consulta de datos consolidados —que
por contrato abarca todas las secciones— es rechazada con 403 por el control de scope granular. No se
modificó el RBAC para sortearlo.

Al no poder verificarse uno de los dos subcasos por falta de precondición legítima, el grupo queda
BLOQUEADO, mostrando el resultado individual de ambos.

---

## RESUMEN DEL RESULTADO

| Caso | Esperado | Obtenido | Resultado |
|---|---|---|---|
| TC-M02-154 | HTTP 200 con datos consolidados conforme al contrato en ≤ 5 s | 403 `SCOPE_TIPO_DATO_NO_AUTORIZADO`: el módulo no está autorizado para el tipo de dato `metricas`, incluido en la consulta completa | **BLOQUEADO** |
| TC-M02-159 | HTTP 200 con el indicador de ganancia diaria de peso disponible y correcto | 200 en 142 ms, `ganancia_peso` disponible, 0.9677 kg/día, con las variables y el período correctos | **APROBADO** |

Ejecución automatizada: 26 assertions, 4 fallidas —todas correspondientes al subcaso bloqueado—.
TC-M02-159 superó sus catorce verificaciones.

---

## ANTECEDENTES

**V1 — BLOQUEADO.** La identidad técnica M04 no estaba disponible para QA; ambos subcasos quedaron sin
ejecutar.

**V2 — SIGUE BLOQUEADO.** Se confirmó que la identidad histórica no estaba provisionada en TEST y que
el alcance de finca quedaba pendiente. También se confirmó que RF-50 y RF-51 estaban implementados,
que el fixture existía y que no era necesario tener M04 completo para ejecutar el caso. V2 dejó como
referencia el activo 295 con dos mediciones de peso y una ganancia esperada de 0.9677 kg/día.

**Issue #241 · INC-M02-90-G92.** Definir la identidad M04 para el consumo de los endpoints analíticos
en TEST. Desarrollo indicó que el bloqueo era de provisión/identidad y no un defecto funcional de
RF-50/RF-51.

**PR #275.** Definió el patrón de la identidad: usuario técnico, rol de integración M04 y permiso READ
sobre `activos_biologicos`.

**V3.** Determinar si ese bloqueo quedó resuelto en TEST con la identidad técnica suministrada.

---

## ENTORNO

| Ambiente | Uso |
|---|---|
| TEST | Ambiente decisorio; ejecución funcional V3 |
| DEV | No verificable por credencial: no se dispone de una identidad técnica DEV conocida y autorizada, y no se ensayaron credenciales |

`/health` y `/openapi.json` respondieron 200. El contrato define los dos endpoints del caso con sus
esquemas de respuesta completos: la consulta de datos consolidados con sus sedecim campos y el
indicador zootécnico con `tipo`, `valor`, `unidad`, `periodo_inicio`, `periodo_fin`,
`variables_usadas`, `fecha_calculo` y `disponible`.

Tiempos de respuesta observados: 131 ms y 142 ms, muy por debajo del límite de 5 s.

---

## ACTOR / IDENTIDAD TÉCNICA

Consumidor utilizado: la identidad técnica suministrada para esta evaluación, sin sustituirla por
identidades históricas ni por cuentas humanas.

| Verificación | Estado |
|---|---|
| Autentica | **sí** |
| Cuenta activa | sí |
| Rol | `Integración M04` — identidad técnica de integración, no una cuenta humana |
| Permiso READ sobre `activos_biologicos` | sí |
| Alcance sobre la finca del fixture | sí, tras la preparación |
| Activos visibles | 29 |
| Scope `datos_analiticos_eventos` | sí |
| Scope `datos_analiticos_fases` | sí |
| Scope `datos_analiticos_estado` | sí |
| Scope `datos_analiticos_metricas` | **no** |

El rol dispone además de lectura sobre el recurso de fincas, que no otorga alcance global porque éste
se concede a quien puede gestionarlas, no a quien solo las consulta.

**Diferencia decisiva respecto de V1 y V2:** la identidad ya existe, autentica y es reconocida con su
rol técnico. El bloqueo histórico de identidad quedó superado. Lo que ahora falta es un único permiso
de scope.

---

## CONFIGURACIÓN UTILIZADA / FIXTURE

| Elemento | Valor |
|---|---|
| Activo biológico | 295 |
| Identificador | `QAJE-DAT-COMPL` |
| Tipo | INDIVIDUAL |
| Estado | ACTIVO |
| Infraestructura | 48 |
| Finca | 57 |

Mediciones de peso revalidadas:

| Fecha | Valor | Unidad |
|---|---|---|
| 2026-07-15 | 200.00 | kg |
| 2026-08-15 | 230.00 | kg |

El fixture coincide exactamente con el de referencia de V2 y sigue siendo válido. Recálculo
independiente del indicador, sin aceptar el valor devuelto como bueno:

```
(230.00 − 200.00) / 31 días = 0.967741935…
Esperado a cuatro decimales: 0.9677 kg/día
```

**Preparación de precondiciones.** La identidad técnica requería alcance sobre la finca del fixture.
La finca correspondiente fue asignada mediante el endpoint oficial `PUT /usuarios/{id_usuario}/fincas`
antes de iniciar la ejecución oficial, enviando el conjunto completo de fincas que debían quedar
asignadas y preservando cualquier asignación activa preexistente (no había ninguna). La operación fue
ejecutada por una cuenta autorizada para actualizar usuarios, cuyo permiso se confirmó previamente, y
nunca por la propia identidad técnica. Tras la asignación, la identidad pasó de ver 0 activos a ver 29.

No se modificó el rol técnico, ni el permiso READ, ni ningún scope, ni se crearon eventos de
crecimiento. No se ejecutó ninguna sentencia directa contra la base de datos. Esta preparación no forma
parte del oráculo.

---

## TC-M02-154

**Resultado: BLOQUEADO.**

Petición del caso: consulta de datos consolidados del activo con la identidad técnica. Por contrato, la
consulta sin filtro de sección abarca todas las secciones de datos.

Respuesta obtenida: **403** con `error_code` `SCOPE_TIPO_DATO_NO_AUTORIZADO` y el mensaje «Acceso
denegado: El módulo solicitante no tiene autorización para consumir datos de tipo metricas».

El origen del rechazo está identificado con precisión y no es una falta de alcance ni de permiso
general:

| Consulta con la misma identidad y el mismo activo | Respuesta |
|---|---|
| Consulta completa (todas las secciones) | 403 — scope de `metricas` no autorizado |
| Sección `metricas` | 403 — mismo motivo |
| Sección `eventos` | **200** |
| Indicadores zootécnicos (RF-51) | **200** |

Que las consultas de `eventos` e indicadores devuelvan 200 demuestra que la identidad está
autenticada, tiene permiso general, tiene alcance sobre el activo y el activo es visible. El 403 se
debe exclusivamente a que el rol no incluye el scope `datos_analiticos_metricas`, que la consulta
completa exige junto con los otros tres.

Por tanto el comportamiento observado **no es un defecto de RF-50**: es el control de scope granular
funcionando como se especificó. Lo que falta es la autorización del módulo sobre ese tipo de dato, es
decir una precondición de provisión. Conforme al criterio del caso, un rechazo por falta de scope
clasifica el subcaso como BLOQUEADO, no como desaprobado, y no se modificó el RBAC para forzar el 200.

---

## TC-M02-159

**Resultado: APROBADO.**

Petición del caso: indicadores zootécnicos del activo, con indicador de crecimiento y el rango que
incluye las dos mediciones (2026-07-15 → 2026-08-15).

| Verificación | Resultado |
|---|---|
| HTTP 200 | CUMPLE |
| Tiempo de respuesta dentro del límite | CUMPLE — 142 ms |
| Respuesta conforme al contrato desplegado | CUMPLE |
| Indicador `ganancia_peso` presente | CUMPLE |
| `disponible = true` | CUMPLE |
| Campos del contrato en el indicador | CUMPLE |
| Unidad `kg/dia` | CUMPLE |
| Valor igual al recálculo independiente | CUMPLE — **0.9677** |
| Período coherente con el rango de las mediciones | CUMPLE — 2026-07-15 → 2026-08-15 |
| Variables utilizadas declaradas | CUMPLE |
| Peso inicial correcto | CUMPLE — 200 |
| Peso final correcto | CUMPLE — 230 |
| Días transcurridos correctos | CUMPLE — 31 |
| Total de mediciones correcto | CUMPLE — 2 |

El indicador se calculó con las dos mediciones reales del activo y su valor coincide con el esperado
recalculado de forma independiente. La respuesta no incluyó advertencias.

---

## RESULTADO DEL ORÁCULO

| Verificación | Resultado |
|---|---|
| Contrato de RF-50 y RF-51 desplegado | CUMPLE |
| Identidad técnica autentica, activa y con rol de integración | CUMPLE |
| Permiso READ sobre `activos_biologicos` | CUMPLE |
| Alcance sobre la finca del fixture | CUMPLE |
| Activo del fixture alcanzable y visible | CUMPLE |
| Fixture con dos mediciones de peso en fechas distintas | CUMPLE |
| Valor esperado del indicador recalculado de forma independiente | CUMPLE |
| Scope del módulo sobre el tipo de dato `metricas` | NO CUMPLE |
| TC-M02-154: datos consolidados con 200 y contrato correcto | NO OBSERVADO — 403 por scope |
| TC-M02-159: indicador de ganancia diaria de peso correcto | CUMPLE |
| RNF de tiempo de respuesta | CUMPLE en las dos consultas realizadas |

**Newman: 26 assertions, 4 fallidas** (todas del subcaso bloqueado).

---

## COMPARACIÓN V1 VS V2 VS V3

| Aspecto | V1 | V2 | V3 |
|---|---|---|---|
| TC-M02-G92 | BLOQUEADO | BLOQUEADO | **BLOQUEADO** (por scope, no por identidad) |
| TC-M02-154 | BLOQUEADO / no ejecutado | BLOQUEADO / no ejecutado | **BLOQUEADO** — ejecutado y rechazado por falta de scope |
| TC-M02-159 | BLOQUEADO / no ejecutado | BLOQUEADO / no ejecutado | **APROBADO** |
| Identidad técnica M04 | No disponible | No provisionada en TEST | **Provisionada, activa y con rol de integración** |
| Login técnico | No ejecutado | No ejecutado | **Exitoso** |
| RBAC READ sobre `activos_biologicos` | No verificable | No disponible | **Confirmado** |
| Scope sobre el activo | No verificable | Pendiente | **Resuelto**: finca asignada por endpoint oficial, 29 activos visibles |
| Scope por tipo de dato | No aplicable | No aplicable | **3 de 4 concedidos; falta `metricas`** |
| Fixture con 2 pesos | Disponible | Disponible | **Disponible y revalidado (200.00 → 230.00 kg, 31 días)** |
| RF-50 ejecutado | No | No | **Sí** — respondió 403 por scope |
| RF-51 ejecutado | No | No | **Sí** — respondió 200 y verificado |
| Issue #241 | Abierto / bloqueo | Gap de provisión documentado | **Bloqueo de identidad superado; queda un gap de scope** |

### Evolución

**V1** no tenía identidad técnica alguna y ninguno de los dos subcasos pudo ejecutarse.

**V2** acotó la causa a la provisión en TEST y descartó el fixture y la implementación de RF-50/RF-51
como motivos del bloqueo, pero tampoco pudo ejecutar.

**V3** ejecuta por primera vez. El bloqueo histórico —ausencia de identidad técnica— quedó **resuelto**:
la identidad autentica, es reconocida con su rol y consume RF-51 con resultado correcto. Lo que queda
es un obstáculo distinto y mucho más acotado: el rol técnico tiene tres de los cuatro permisos de scope
por tipo de dato, y la consulta completa de datos consolidados exige los cuatro. El grupo sigue
BLOQUEADO, pero por un motivo diferente, con un subcaso ya aprobado y con una acción concreta
pendiente.

---

## COMPARACIÓN TEST VS DEV

| Ambiente | Resultado |
|---|---|
| TEST | Ejecución funcional V3: TC-M02-159 APROBADO, TC-M02-154 BLOQUEADO por scope |
| DEV | `DEV_NO_VERIFICABLE_POR_CREDENCIAL` — sin identidad técnica DEV conocida y autorizada; el contraste se limita al contrato, que declara los mismos endpoints |

No se reutilizaron identificadores ni credenciales de TEST en DEV, ni se usó ninguna cuenta humana como
sustituto del módulo.

---

## ORIGEN / INTERPRETACIÓN DEL RESULTADO

El resultado tiene dos lecturas complementarias y ninguna de ellas es un defecto funcional.

**RF-51 funciona.** El cálculo de la ganancia diaria de peso es correcto, está expuesto con su unidad,
su período y las variables empleadas, y coincide con el recálculo independiente hecho a partir de las
mediciones reales del activo. Esto se comprueba por primera vez en la historia del grupo.

**RF-50 no llegó a observarse en su escenario positivo.** La consulta completa de datos consolidados
abarca las cuatro secciones y el control de scope granular exige autorización sobre todas ellas. El rol
técnico tiene `eventos`, `fases` y `estado`, pero no `metricas`, de modo que la consulta completa se
rechaza. Ese rechazo es el comportamiento especificado del control de scope, no una falla: el mismo
control, evaluado como escenario negativo, es precisamente lo que otro grupo de pruebas verifica.

Para desbloquear TC-M02-154 basta una decisión de provisión: conceder al rol de integración M04 el
permiso de lectura sobre el recurso `datos_analiticos_metricas`, de forma coherente con los otros tres
que ya tiene. Es la misma familia de gap que #241 describía —provisión, no funcionalidad— y no requiere
ningún cambio de código. QA no modificó el RBAC porque hacerlo habría falseado tanto este caso como el
escenario negativo que lo acompaña.

Queda además una observación de diseño, ajena al oráculo: un consumidor de servicio como este módulo
depende hoy de asignaciones de finca propias de usuarios operativos, y su lectura sobre el recurso de
fincas no le otorga alcance global. Si se prevé que consuma datos de varias fincas, conviene decidir si
los roles de integración deben tratarse como de alcance global. Es una decisión de diseño, no un
defecto.

---

## INCIDENCIA

### INC-M02-90-G92 (#241)

**Estado V3: BLOQUEO DE IDENTIDAD RESUELTO; PENDIENTE UN ELEMENTO DE PROVISIÓN DE SCOPE.**

El bloqueo que originó la incidencia —la ausencia de una identidad técnica M04 consumible por QA en
TEST— quedó superado y verificado: la identidad existe, autentica, tiene rol de integración, permiso
READ y alcance sobre el fixture, y con ella se consumió RF-51 con resultado correcto.

La incidencia **no se reabre como defecto funcional**, porque RF-50 y RF-51 no incumplieron: uno se
verificó correcto y el otro aplicó su control de autorización tal como está especificado. Lo que resta
es conceder al rol técnico el permiso de scope sobre el tipo de dato `metricas` para completar la
verificación de TC-M02-154.

No se crea ninguna incidencia adicional.

---

## CONCLUSIÓN

**TC-M02-G92 queda BLOQUEADO.**

De sus dos casos originales, **TC-M02-159 queda APROBADO** y **TC-M02-154 queda BLOQUEADO**.

La tercera evaluación es la primera que ejecuta el grupo funcionalmente, y demuestra que el obstáculo
histórico ya no existe: la identidad técnica M04 está provisionada, autentica y consume los endpoints
analíticos de M02. RF-51 quedó verificado de extremo a extremo, con el indicador de ganancia diaria de
peso calculado correctamente sobre las mediciones reales del activo.

TC-M02-154 no pudo verificarse porque el rol técnico carece del permiso de scope sobre una de las
cuatro secciones que la consulta completa de datos consolidados abarca. Es una precondición de
provisión, no un defecto del requerimiento, y se resuelve concediendo ese permiso.

TC-M02-154 deberá reejecutarse cuando el rol de integración disponga del scope sobre el tipo de dato
`metricas`. El fixture, los rangos y la automatización quedan verificados y listos para esa
reejecución.

---

La evaluación se realizó sin modificar código productivo, sin escrituras directas en la base de datos,
sin alterar roles ni permisos y sin sustituir la identidad técnica del caso. La única escritura fue la
asignación de la finca del fixture a la identidad técnica, mediante el endpoint oficial y como
preparación de precondiciones. Las evidencias técnicas se conservan en la carpeta del RUN_ID
correspondiente.
