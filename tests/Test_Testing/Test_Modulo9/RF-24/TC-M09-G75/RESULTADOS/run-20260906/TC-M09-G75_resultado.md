# TC-M09-G75 — RESULTADO

## DECISIÓN GENERAL

**APROBADO**

Los cuatro originales quedaron APROBADOS. El campo `valor_referencia` acepta
exactamente los límites técnicos inclusivos, rechaza con HTTP 400 los valores fuera
de rango y los valores vacíos o no numéricos, y en ningún caso inválido se creó
registro ni se alteró el historial. No hay defectos que reportar.

| Caso | Resultado | Motivo | Categoría de error | Equipo responsable | Acción |
| ---------- | --------- | ------ | ------------------ | ------------------ | ------ |
| TC-M09-142 | **APROBADO** | `valor_referencia = 0.0000` (mínimo técnico exacto) aceptado con HTTP 201, calibración **#10** persistida con trazabilidad completa y disponible como calibración vigente | — | — | Ninguna |
| TC-M09-143 | **APROBADO** | `valor_referencia = 45.0000` (máximo técnico exacto) aceptado con HTTP 201, calibración **#11** persistida; el histórico #10 se conservó, no se sustituyó | — | — | Ninguna |
| TC-M09-144 | **APROBADO** | `-0.0001` y `45.0001` rechazados con HTTP 400 `VALOR_FUERA_DE_RANGO`, sin persistencia y con la calibración válida anterior (#11) intacta y vigente | — | — | Ninguna |
| TC-M09-145 | **APROBADO** | `""` y `"abc"` rechazados con HTTP 400 `VALOR_CALIBRACION_INVALIDO` sobre `valor_referencia`, sin persistencia y con el historial intacto | — | — | Ninguna |

Responsable QA: Juan Esteban. M09 / RF-24 v1.0 / CU-05. Prioridad alta. Técnica:
pruebas de valores límite. Herramienta: Newman. Actor funcional:
**Ingeniero de campo**. Sin Cypress, sin mocks y sin PostgreSQL. G74 no se ejecutó.
No se avanzó a ningún otro grupo.

---

## DISCREPANCIA DOCUMENTAL TC-M09-144

`Matriz de pruebas: HTTP 422`

`RF-24 v1.0: HTTP 400 Bad Request — «Valor fuera de límites»`

`OpenAPI/contrato actual: HTTP 400` — el router declara explícitamente `400` entre
las respuestas de `POST /configuracion/sensores/{id_sensor}/calibrar`, y
`VALOR_FUERA_DE_RANGO` se lanza como `ValidationError`, que `src/shared/errors.py`
mapea a **400**.

`Oráculo utilizado: HTTP 400`

`Justificación:` RF-24 y el contrato implementado y publicado **coinciden** en 400.
El 422 aparece únicamente en la matriz de pruebas. No existe conflicto entre fuentes
normativas —el contrato no define 422 para esta regla—, así que no procede
`CONTRACT_REQUIREMENT_MISMATCH` ni bloqueo por oráculo contradictorio: se registra
como **`TEST_MATRIX_REQUIREMENT_MISMATCH`**, discrepancia documental de la matriz
frente al requisito y al contrato.

La discrepancia **no se convierte en un bug del producto**: el comportamiento
observado (400 con código específico de rango y sin persistencia) es exactamente el
que exige RF-24. **Recomendación para revisión humana:** actualizar el resultado
esperado de TC-M09-144 en la matriz de 422 a 400. QA no modificó la matriz.

Nota: el oráculo se resolvió **antes** del primer POST de TC-M09-144, como exige el
caso, y por tanto no se gastó ningún POST con una expectativa sin resolver.

TC-M09-145 no presenta esta discrepancia: RF-24, la matriz y el contrato coinciden
en 400. El DTO está diseñado explícitamente para ello —acepta `valor_referencia`
como `Decimal | str | None` para que Pydantic no responda 422 por tipo, y el caso de
uso convierte y devuelve 400 `VALOR_CALIBRACION_INVALIDO`—, con un comentario en el
código que cita ese flujo alterno de RF-24.

---

## RANGO TÉCNICO UTILIZADO

| Dato | Valor |
| ------------------- | ----- |
| Dispositivo | **3** — serial `IOT-ALE01-HLA-003`, activo |
| Sensor | **6** — «Sensor temperatura zona de incubación», activo |
| Tipo | `TEMPERATURA` |
| Área (infraestructura) | **3** — «Zona de incubación, profundidad 15 cm», asociación vigente (`fecha_finalizacion: null`) |
| Unidad | Categoría `TEMPERATURA` del catálogo de rangos |
| Mínimo técnico | **0.0000** |
| Máximo técnico | **45.0000** |
| Valor bajo inválido | **-0.0001** |
| Valor alto inválido | **45.0001** |

**Fuente del rango:** `GET /configuracion/sensores/rangos-calibracion`, que publica
los siete rangos de seguridad por categoría. No se supuso ningún límite: el catálogo
devolvió `TEMPERATURA 0.0000–45.0000`, y la verificación de cierre confirmó que el
rango **no cambió** durante la ejecución.

Los valores fuera de rango se construyeron con **aritmética decimal exacta** sobre
el límite publicado, usando el menor incremento representable por `numeric(10,4)`
(`0.0001`). No se usó coma flotante para derivarlos, y ambos siguen siendo
representables por el tipo: TC-M09-144 prueba el rango técnico, no un desbordamiento
del tipo.

El límite es **inclusivo** en el contrato (`valor_min <= valor <= valor_max` en
`RangoCalibracion.verificar`), coherente con que la matriz declare el mínimo y el
máximo como valores aceptados.

---

## Entorno

- Fecha: 2026-09-06 UTC. POST entre 04:22:49 y 04:23:41.
- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`
- Frontend TEST: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`
- Rama backend: `qa/juan-esteban-m09` · SHA local `adc3932b9f0293a76ebec7e89ed877274791b6a1`
- Rama frontend: `qa/juan-esteban-m09` · SHA local `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`
- **SHA desplegado en TEST no confirmado.** Los SHA anteriores son locales.
- Status Git inicial: backend con untracked de grupos anteriores de RF-17; frontend
  con untracked de TC-M09-G22 y TC-M09-G28. Ningún archivo versionado modificado.
- Preflight antes de cada ejecución: `/login` del frontend, `/health` y
  `/openapi.json` del backend en **200**, con verificación de que OpenAPI publica
  `POST /configuracion/sensores/{id_sensor}/calibrar`.
- Dependencias verificadas, ninguna instalada: Newman **6.2.2**,
  `newman-reporter-htmlextra` **1.23.1**.
- Ubicación de los archivos QA:
  `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G75/`, siguiendo la
  indicación explícita de trabajar en `RF-24/TC-M09-G75` del repositorio de backend.
  No se usó la carpeta de RF-17.

## Actor

Actor funcional de los seis POST: **Ingeniero de campo** (`ingeniero@pecuaria.co`),
autenticado realmente contra TEST. Permisos comprobados sobre el recurso 12
(sensores): **C=1, R=2, U=3**, coherentes con el RBAC que documenta el router. El
mismo actor realizó el descubrimiento: no hizo falta recurrir a Administrador para
las consultas.

**Incidencia de acceso durante la preparación:** el primer intento de autenticación
usó una contraseña que resultó no ser la del Ingeniero y devolvió 401. La respuesta
advierte que la cuenta se bloquea 15 minutos tras cinco intentos fallidos, así que
**se detuvo el ensayo tras un único intento** y se solicitó la credencial correcta
en lugar de seguir probando. La cuenta no llegó a bloquearse y el resto de la
ejecución transcurrió con normalidad.

## Revisión del contrato

Revisión enfocada y de solo lectura, realizada una sola vez antes del primer POST.

| Punto | Hallazgo |
|---|---|
| Endpoint de calibración | `POST /configuracion/sensores/{id_sensor}/calibrar` |
| Método y éxito | POST, `status_code=201` declarado en el router |
| Fuera de rango | `VALOR_FUERA_DE_RANGO` (`ValidationError`) → **400** |
| Vacío / no numérico | `VALOR_CALIBRACION_INVALIDO` (`ValidationError`) → **400** |
| Payload | `id_dispositivo_iot`, `id_infraestructura`, `valor_referencia`, `ganancia` (defecto 1.0), `offset` (defecto = `valor_referencia`), `fecha_calibracion`, `observaciones` |
| Rango técnico | `GET /configuracion/sensores/rangos-calibracion`, por categoría de sensor |
| Historial | `GET /configuracion/sensores/{id_sensor}/calibraciones` |
| Trazabilidad | La respuesta expone `id_usuario`, `fecha_calibracion` y `observaciones`; el caso de uso escribe además auditoría inmutable y hace rollback si la auditoría falla |
| Aplicación posterior | `CalibracionM09Adapter` (módulo de telemetría) selecciona la calibración **más reciente por `fecha_calibracion`** del par (sensor, dispositivo) y aplica `valor_ajustado = ganancia × crudo + offset` durante la ingesta |

Orden de validación en el caso de uso: dispositivo existe y activo → sensor existe y
pertenece al dispositivo → asociación de área vigente coincide con la enviada →
conversión decimal de `valor_referencia` → rango técnico por categoría → creación con
auditoría. Cada payload de G75 supera todas las validaciones previas para llegar
exactamente a la regla que su caso prueba.

---

## TC-M09-142 — APROBADO

Mínimo técnico exacto. **1 POST**, sin reintento.

- Valor enviado: `0.0000`, literal decimal exacto, idéntico al mínimo publicado.
- HTTP **201**. Calibración creada **#10**.
- Respuesta sanitizada:

```json
{
  "id_calibracion": 10,
  "id_dispositivo_iot": 3,
  "id_sensor": 6,
  "valor_referencia": "0.0000",
  "ganancia": "1.0000",
  "offset": "0.0000",
  "fecha_calibracion": "2026-09-06T04:22:49.008000Z",
  "id_usuario": 4,
  "observaciones": "QA TC-M09-142 G75 run-20260906"
}
```

- Dispositivo y sensor correctos; valor persistido idéntico al enviado; trazabilidad
  con responsable y fecha; observaciones correlacionables con la ejecución.
- Historial: **0 → 1**, con la calibración presente exactamente una vez.
- **17/17 assertions.**

## TC-M09-143 — APROBADO

Máximo técnico exacto. **1 POST**, sin reintento. Precondiciones reconfirmadas por
GET antes de ejecutar: dispositivo activo, sensor asociado y rango sin cambios.

- Valor enviado: `45.0000`, idéntico al máximo publicado.
- HTTP **201**. Calibración creada **#11**, `valor_referencia = "45.0000"`,
  `id_usuario = 4`, observaciones `QA TC-M09-143 G75 run-20260906`.
- Historial: **1 → 2**. **La calibración #10 de TC-M09-142 se conservó**: no hubo
  sustitución destructiva, sino historial, como exige RF-24.
- **17/17 assertions.**

## PROPAGACIÓN / APLICACIÓN POSTERIOR (TC-M09-142 y TC-M09-143)

`Creación aceptada: Sí` (ambos)

`Persistencia: Sí` (ambos, verificada por GET del historial)

`Mecanismo de aplicación posterior identificado: Sí` — `CalibracionM09Adapter` del
módulo de telemetría toma la calibración más reciente por `fecha_calibracion` para
el par (sensor, dispositivo) y la aplica en la ingesta como
`valor_ajustado = ganancia × crudo + offset`.

`Propagación/aplicación verificable: Parcialmente` — se verificó de forma
**observable y read-only** que la calibración registrada queda **disponible** para su
aplicación posterior: está en el historial y es la que el criterio documentado del
adaptador seleccionaría. Tras TC-M09-143 la vigente es **#11 (45.0000)**, confirmado
también en la verificación de cierre.

`Resultado observado:` la calibración queda disponible y es la seleccionable. **No se
verificó la aplicación de extremo a extremo sobre una medición real**: el módulo de
telemetría solo expone endpoints POST de ingesta, de modo que observarlo exigiría
ingerir telemetría, lo que crearía datos de medición ajenos al alcance de G75. No se
simuló ni se afirma nada no comprobado: se documenta la limitación. El criterio del
original —«disponible para su aplicación posterior»— sí quedó demostrado.

## CALIBRACIÓN VÁLIDA ANTERIOR

`LAST_VALID_CALIBRATION` capturada tras TC-M09-143:

| Dato | Valor |
|---|---|
| ID | **11** |
| Valor | `45.0000` |
| Sensor | 6 |
| Fecha | `2026-09-06T04:23:01.536000Z` |
| Estado | Vigente: es la más reciente del sensor |

Es la referencia contra la que se comprobaron TC-M09-144 y TC-M09-145.

---

## TC-M09-144 — APROBADO

Fuera de rango técnico. **2 POST**, uno por subescenario. **No hubo un tercero.**

| Variante | Valor | Esperado HTTP | Obtenido | Persistió | Calibración anterior intacta | Resultado |
| ------------ | ----: | ------------: | -------: | --------- | ---------------------------- | --------- |
| Bajo mínimo | `-0.0001` | 400 | **400** | **No** | **Sí** (#11, 45.0000, vigente) | APROBADO |
| Sobre máximo | `45.0001` | 400 | **400** | **No** | **Sí** (#11, 45.0000, vigente) | APROBADO |

Respuesta sanitizada del subescenario bajo mínimo:

```json
{
  "error_code": "VALOR_FUERA_DE_RANGO",
  "message": "El ajuste de -0.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.",
  "fields": [{ "field": "valor_referencia", "message": "El ajuste de -0.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado." }],
  "timestamp": "2026-09-06T04:23:19.207618+00:00"
}
```

El rechazo corresponde **específicamente** a la regla probada: el código es el del
rango técnico, el mensaje nombra la variable y cita los límites permitidos, y el
campo señalado es `valor_referencia`. Se comprobó explícitamente que **no** es
`DISPOSITIVO_NO_ENCONTRADO`, `DISPOSITIVO_INACTIVO`, `SENSOR_NO_ENCONTRADO`,
`SENSOR_DISPOSITIVO_INVALIDO`, `SENSOR_AREA_INVALIDA`, `VALOR_CALIBRACION_INVALIDO`
ni `ERROR_INTERNO`, y que el status no fue 201, 404, 422 ni 500.

Historial **2 → 2** en ambos: sin ID nuevo, sin calibración con el valor rechazado y
con los registros previos íntegros. **15/15 assertions** en cada variante.

## TC-M09-145 — APROBADO

Vacío y no numérico. **2 POST**, uno por subescenario. **No hubo un tercero.**

| Variante | Valor enviado | Esperado | Obtenido | Persistió | Resultado |
| ----------- | ------------- | -------- | -------- | --------- | --------- |
| Vacío | `""` (cadena vacía, tipo string) | HTTP 400 | **400** `VALOR_CALIBRACION_INVALIDO` | **No** | APROBADO |
| No numérico | `"abc"` | HTTP 400 | **400** `VALOR_CALIBRACION_INVALIDO` | **No** | APROBADO |

Se envió literalmente `""` por fidelidad con la matriz y con RF-24, sin sustituirlo
por `null` ni por la omisión del campo: el DTO admite `str`, de modo que el valor
llega hasta la validación de aplicación, que es donde RF-24 sitúa el rechazo. No hizo
falta ninguna adaptación.

Respuesta sanitizada, idéntica en ambas variantes salvo el contexto:

```json
{
  "error_code": "VALOR_CALIBRACION_INVALIDO",
  "message": "El valor de referencia debe ser un número decimal válido.",
  "fields": [{ "field": "valor_referencia", "message": "El valor de referencia debe ser un número decimal válido." }]
}
```

Historial **2 → 2** en ambos, con la calibración válida anterior (#11) intacta y
vigente. **La validación no se delegó a un 422 de framework**: el rechazo llega como
400 con código de negocio, tal como RF-24 exige.

### Incidencia de automatización en el subescenario vacío

El subescenario vacío ejecutó con **14 de 15 assertions** en verde. La única fallida
fue una **cadena de comparación mal escrita en la prueba**: se buscaba `numero
decimal` sin tilde mientras el mensaje real dice «número decimal válido». El
producto se comportó correctamente —400, código correcto, campo correcto y sin
persistencia—, y así consta en la evidencia.

**No se repitió el POST**: hacerlo habría consumido el segundo POST de TC-M09-145 y
habría dejado sin ejecutar el subescenario no numérico, que es obligatorio. Se
corrigió la aserción en el archivo QA para que compare una subcadena sin acentos y la
corrección quedó verificada en el subescenario no numérico, ejecutado después con
15/15. Es un `ERROR DE PRUEBA / AUTOMATIZACIÓN` ya resuelto, sin efecto sobre la
clasificación del original y **sin incidencia funcional que reportar**.

---

## HISTORIAL DE CALIBRACIONES

| Momento | Total | IDs | Observación |
|---|---:|---|---|
| `HISTORY_INITIAL` | **0** | — | Sensor 6 sin calibraciones previas |
| Después de TC-M09-142 | 1 | `[10]` | Nueva calibración `0.0000` |
| Después de TC-M09-143 | 2 | `[10, 11]` | Nueva `45.0000`; **#10 conservada** |
| Después de TC-M09-144-A | 2 | `[10, 11]` | Sin cambios |
| Después de TC-M09-144-B | 2 | `[10, 11]` | Sin cambios |
| Después de TC-M09-145-A | 2 | `[10, 11]` | Sin cambios |
| Después de TC-M09-145-B | 2 | `[10, 11]` | Sin cambios |
| Verificación de cierre | 2 | `[11, 10]` | Vigente **#11 (45.0000)**; rango técnico sin cambios |

**Ningún registro histórico fue sobrescrito, eliminado ni alterado.** Las dos
calibraciones creadas son las únicas escrituras de G75 y se conservan como evidencia
TEST: no se limpiaron ni se desactivaron.

## Newman

| Newman | Reporter | Caso | Subescenario | POST | Status | Error code | Assertions | Fallidas | HTML | JSON |
|---|---|---|---|---|---:|---|---:|---:|---|---|
| 6.2.2 | htmlextra 1.23.1 | TC-M09-142 | mínimo exacto | `POST .../6/calibrar` | 201 | — | 17 | 0 | `newman/newman-TC-M09-142-intento1.html` | `newman-TC-M09-142-intento1.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-143 | máximo exacto | `POST .../6/calibrar` | 201 | — | 17 | 0 | `newman/newman-TC-M09-143-intento1.html` | `newman-TC-M09-143-intento1.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-144 | bajo mínimo | `POST .../6/calibrar` | 400 | `VALOR_FUERA_DE_RANGO` | 15 | 0 | `newman/newman-TC-M09-144-bajo-minimo.html` | `newman-TC-M09-144-bajo-minimo.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-144 | sobre máximo | `POST .../6/calibrar` | 400 | `VALOR_FUERA_DE_RANGO` | 15 | 0 | `newman/newman-TC-M09-144-sobre-maximo.html` | `newman-TC-M09-144-sobre-maximo.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-145 | vacío | `POST .../6/calibrar` | 400 | `VALOR_CALIBRACION_INVALIDO` | 15 | 1 (aserción QA) | `newman/newman-TC-M09-145-vacio.html` | `newman-TC-M09-145-vacio.json` |
| 6.2.2 | htmlextra 1.23.1 | TC-M09-145 | no numérico | `POST .../6/calibrar` | 400 | `VALOR_CALIBRACION_INVALIDO` | 15 | 0 | `newman/newman-TC-M09-145-no-numerico.html` | `newman-TC-M09-145-no-numerico.json` |

**6 POST en total, el máximo ideal previsto: 1 + 1 + 2 + 2.** Ningún original usó
reintento y ninguno hizo un tercer POST; el runner lo impide por diseño y también
rechaza sobrescribir la evidencia de un subescenario ya ejecutado. Los archivos de
TC-M09-144 y TC-M09-145 se nombran por escenario (`bajo-minimo`, `sobre-maximo`,
`vacio`, `no-numerico`) y no como intentos, porque no son reintentos. Cada invocación
ejecuta un único subescenario mediante `G75_CASE`.

## ORIGEN DE LOS FALLOS

Ningún original quedó DESAPROBADO ni BLOCKED. La única incidencia de ejecución fue la
aserción del subescenario vacío:

- **Producto:** No — respondió 400 con el código y el campo correctos y sin persistir.
- **Automatización/prueba:** **Sí** — cadena de comparación mal escrita, ya corregida.
- **Entorno:** No — TEST accesible; preflight, login y todos los GET en 200.
- **Bloqueo:** No.
- **Categoría:** no aplica; no es un defecto del producto.
- **Equipo responsable:** QA (corrección interna ya aplicada).
- **Acción:** `NO REPORTAR A DESARROLLO`.

## DEFECTO DETECTADO

**Ninguno.** El comportamiento de `valor_referencia` cumple RF-24 en los cuatro
originales: límites inclusivos aceptados, valores fuera de rango y no numéricos
rechazados con 400 y código específico, sin persistencia, con trazabilidad y sin
alteración de históricos. No se propone ID de incidencia, no se asigna severidad y no
se creó ningún ticket en Taiga ni GitHub.

Queda una única recomendación documental, sin impacto funcional:
**actualizar el resultado esperado de TC-M09-144 en la matriz de 422 a 400**, para
alinearla con RF-24 y con el contrato. No es un defecto y no se enruta a Desarrollo.

## Seguridad

- No se modificó código funcional del backend ni del frontend, ni DTO, modelo,
  router, servicio, repositorio, caso de uso, migraciones o seeds. Solo se leyeron.
- No se modificó ningún dispositivo, sensor, asociación ni rango técnico. La
  verificación de cierre confirma que el rango `TEMPERATURA 0.0000–45.0000` sigue
  igual y que la asociación del sensor 6 sigue vigente.
- No se instalaron ni actualizaron dependencias. No se tocó infraestructura.
- **No se usó PostgreSQL, ni siquiera `SELECT`**: la API cubrió catálogo, rango,
  historial y persistencia. Ningún SQL de escritura.
- No se eliminaron ni desactivaron calibraciones. **Sin cleanup**: las calibraciones
  #10 y #11 se conservan como evidencia.
- Contraseña y token solo en memoria del proceso. Reporter con `omitHeaders`,
  `showEnvironmentData: false`, `showGlobalData: false` y
  `skipEnvironmentVars: ['token']`, más sanitización posterior de HTML y JSON.
- Escaneo final de secretos sobre los 23 artefactos del run buscando **valores** y no
  vocabulario: JWT, cabecera de autorización con token real, cabecera de cookie,
  tokens y credenciales en pares clave-valor, cadenas de conexión y el valor concreto
  de la contraseña del actor. **Sin hallazgos.** El correo del actor sí aparece en
  este informe: no es un secreto según el requisito —el propio caso lo publica— y se
  contabiliza aparte como identificador, no como fuga. Registrado en
  [seguridad-evidencias.json](seguridad-evidencias.json).
- No se ejecutó Cypress ni se usaron mocks: las seis peticiones fueron reales contra
  TEST.
- No hubo `git commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `clean`, `stash`,
  `checkout`, `switch`, creación o borrado de rama, tags ni PR.

## Git final

Backend (`qa/juan-esteban-m09`, `adc3932b9f0293a76ebec7e89ed877274791b6a1`):
`git diff --stat` vacío — ningún archivo versionado modificado. Lo nuevo son los
archivos QA de este grupo bajo `RF-24/TC-M09-G75/`, más los untracked previos de
otros grupos que ya existían al comenzar.

Frontend (`qa/juan-esteban-m09`, `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`):
untracked únicamente de grupos anteriores. **G75 no ejecutó ninguna operación sobre
el repositorio de frontend.**

### Hallazgo del estado del repositorio, fuera del alcance de G75

`git diff --stat` del frontend **no está vacío**: el archivo versionado
`testing/test_testing/Modulo9/RF-17/TC-M09-G22/.gitkeep` figura como **eliminado**
(`deleted file mode 100644`, contenido vacío). Pertenece a RF-17 / TC-M09-G22, un
grupo ajeno a G75, y G75 trabaja exclusivamente en el repositorio de backend bajo
`RF-24/TC-M09-G75/`.

Conforme a las reglas del caso, **no se revirtió, no se reseteó y no se restauró**:
solo se documenta. Queda para revisión humana determinar su origen y si debe
recuperarse. No afecta a ninguna de las comprobaciones de G75, que no leen ni
escriben en esa ruta.

Detalle en [git-final.json](git-final.json).

---

## Estado de cierre

G75 queda ejecutado y detenido para revisión humana. TC-M09-142, TC-M09-143,
TC-M09-144 y TC-M09-145 **APROBADOS**. Decisión general **APROBADO**. Sin defectos
que reportar a ningún equipo. Pendiente de decisión documental, sin impacto
funcional: la corrección del resultado esperado de TC-M09-144 en la matriz. No se
avanza a otro grupo.
