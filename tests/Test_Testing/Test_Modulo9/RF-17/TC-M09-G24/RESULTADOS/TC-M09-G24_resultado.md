# TC-M09-G24 — RESULTADO

## DECISIÓN GENERAL

**DESAPROBADO**

G24 solo queda APROBADO si los tres originales quedan APROBADOS. TC-M09-52 y
TC-M09-53 quedaron **APROBADOS**: en ambos el producto rechazó la configuración
inválida con el código correcto, sin ID y sin persistir nada. TC-M09-54 quedó
DESAPROBADO por un defecto del producto: la creación válida devuelve HTTP 500 y
no persiste, reproduciendo el defecto conocido `QA-JE-G22-01`. Ese único caso
arrastra al grupo.

| Caso | Resultado | Motivo | ¿Reportar a Desarrollo? |
| --------- | ---------------------- | ------ | ----------------------- |
| TC-M09-52 | APROBADO | HTTP 400 `NIVEL_FUERA_DE_RANGO` en el primer y único POST; sin ID, sin estado de éxito y GET posterior sin persistencia | No |
| TC-M09-53 | APROBADO | El producto rechaza el solapamiento con `SOLAPAMIENTO_NIVELES`, identifica el intervalo en conflicto y no persiste. La expectativa de status de la prueba estaba desactualizada (400 frente al 422 real del contrato); se corrigió el archivo QA y el reintento cerró 8/8 | No |
| TC-M09-54 | DESAPROBADO — DEFECTO DEL PRODUCTO | Creación válida y continua rechazada con HTTP 500 `ERROR_INTERNO` en los dos intentos; sin persistencia. Reproducción de `QA-JE-G22-01` | Sí |

Responsable: Juan Esteban. M09 / RF-17 / CU-03. Prioridad alta. Técnica: pruebas
de validación. Actor: Administrador TEST. Herramienta principal Newman; Cypress
como evidencia visual complementaria. G22 y G23 no se ejecutaron ni se
modificaron. G25 no se inició.

---

## ORIGEN DE LOS FALLOS

### TC-M09-53 — fallo del primer intento, corregido; el caso quedó APROBADO

- **Producto:** No
- **Automatización/prueba:** Sí
- **Entorno:** No
- **Acción:** `CORREGIR AUTOMATIZACIÓN` — **hecho y verificado**. `NO REPORTAR A DESARROLLO`.

El fallo fue exclusivamente de la prueba y quedó resuelto dentro del único
reintento disponible: el archivo QA se corrigió y el reintento cerró con 8/8
assertions. Como no hay nada que reportar a Desarrollo y el comportamiento
esperado de RF-17 (rechazar el solapamiento sin persistir) se cumplió, el
original queda **APROBADO**.

Qué estaba mal: la assertion `HTTP exactamente 400` de `TC-M09-G24.postman_collection.json`.

Por qué: `SOLAPAMIENTO_NIVELES` se lanza como `BusinessRuleError`, que
`src/shared/errors.py` documenta como **HTTP 422** y `error_handlers.py` traduce
con ese status. El 400 solo lo produce `RequestValidationError` (Pydantic) o un
`ValidationError` de dominio, que no es el caso de esta regla.

Qué evidencia lo demuestra: el `openapi.json` **desplegado en TEST** declara para
`POST /configuracion/umbrales` los estados `201, 401, 403, 404, 409, 422`; 400 ni
siquiera figura. La respuesta real trae `error_code: SOLAPAMIENTO_NIVELES` e
identifica el intervalo exacto en conflicto, y el GET posterior confirma la
ausencia de persistencia. Es decir: el comportamiento de RF-17 es correcto y solo
el status esperado por la prueba estaba desactualizado.

Qué archivo QA se corrigió: `TC-M09-G24.postman_collection.json`, únicamente la
assertion de status del item `TC-M09-53` (400 → 422). No se tocó el payload, ni
las demás assertions, ni los items de TC-M09-52 y TC-M09-54, ni requisitos, ni
código funcional.

### TC-M09-54 — HTTP 500 en la creación válida

- **Producto:** Sí
- **Automatización/prueba:** No
- **Entorno:** No
- **Acción:** `REPORTAR A DESARROLLO` (como evidencia adicional de `QA-JE-G22-01`).

El payload es válido y continuo según el contrato revisado, la combinación estaba
libre, el descubrimiento se repitió antes del caso y los dos intentos usaron el
mismo payload. No hubo indisponibilidad de TEST: login, catálogos, `/health`,
`/openapi.json` y los GET posteriores respondieron 200 en las mismas ventanas.

### Fallo instrumental de un recorrido Cypress (no afecta la clasificación)

El primer recorrido de TC-M09-52 no pudo completar el formulario porque el input
`normal_sup` queda cubierto por `precaucion_inf`. Es un hallazgo de interfaz
(ver `QA-JE-G24-UI-01`), no un fallo de la regla probada. El segundo recorrido
obtuvo la evidencia completa sin `force:true`.

---

## Entorno

- Fecha: 2026-09-05. Newman entre 21:43 y 21:45 UTC; Cypress entre 21:53 y 22:00 UTC.
  Los JSON conservan sus timestamps exactos.
- Rama local verificada al inicio y al cierre en ambos repositorios: `qa/juan-esteban-m09`.
- Backend SHA local: `adc3932b9f0293a76ebec7e89ed877274791b6a1`.
- Frontend SHA local: `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`.
- **El SHA desplegado en TEST no está confirmado.** Los SHA anteriores son locales.
- Frontend: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`.
- Backend: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Preflight antes de cada ejecución Newman: `/login` del frontend, `/health` y
  `/openapi.json` del backend devolvieron 200, y se comprobó que OpenAPI contiene
  el POST de umbrales. Login real 200. Permisos del recurso 20 (crear y consultar)
  verificados en cada descubrimiento.
- Newman 6.2.2, reporter real `newman-reporter-htmlextra` 1.23.1, Cypress 13.17.0,
  Electron 118.0.5993.159 headless, Node 22.15.1, TypeScript 5.9.3, Python 3.13.13
  (venv del backend). Ninguna dependencia se instaló, actualizó ni modificó.
- Ubicación de los archivos QA: `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/`,
  según la estructura usada por TC-M09-G23 e indicación explícita de trabajar en el
  repositorio de backend.

## Datos reales

Descubrimiento dinámico antes de cada ejecución: permisos, especies activas,
variables activas y umbrales existentes. Ningún ID fijo en la automatización. La
combinación se consideró ocupada aunque el umbral estuviera inactivo.

Selección obtenida en los cinco descubrimientos (idéntica en todos): especie **4**
Cachama Blanca, activa; variable **9** Temperatura Ambiental, catálogo activo,
unidad **°C**, límites físicos **−50 a 100**. Antes de cada POST la especie 4 tenía
los umbrales **10** (variable 1) y **11** (variable 3) y **ninguno** para la
variable 9: combinación previa libre en los tres originales.

Rango padre común: **valor_min −20, valor_max 70**, dentro de los límites físicos.

| Caso | normal | precaucion | critico | Defecto intencional |
|---|---|---|---|---|
| TC-M09-52 | −20 a 10 | 10 a 40 | 40 a **85** | `critico` termina en 85, por encima de `valor_max`=70 |
| TC-M09-53 | −20 a 10 | 10 a 40 | **25** a 70 | `precaucion` y `critico` ocupan a la vez [25, 40] |
| TC-M09-54 | −20 a 10 | 10 a 40 | 40 a 70 | ninguno: cobertura continua y completa |

En los tres casos cada nivel cumple `inferior < superior`, hay exactamente tres
niveles, los nombres son los exigidos y no hay duplicado, especie inactiva ni
violación de límites físicos: el único defecto es el que cada original prueba.

---

## TC-M09-52 — APROBADO

- Endpoint: `POST /configuracion/umbrales`. Intentos: **1 POST**, sin reintento.
- HTTP **400**. Respuesta sanitizada real:

```json
{
  "error_code": "NIVEL_FUERA_DE_RANGO",
  "message": "El nivel 'critico' (40–85) cae fuera del rango general [-20, 70].",
  "fields": [],
  "timestamp": "2026-09-05T21:43:01.117803+00:00"
}
```

- Sin `id_umbral_ambiental`, sin `id`, sin `es_activo: true`, sin `success: true`,
  status distinto de 201.
- GET posterior `?id_especie=4`: **200**, total 2, IDs 10 y 11, **0 coincidencias**
  para la variable 9. Confirmado además por el GET de la colección, por el GET del
  runner y por la verificación final de cierre.
- 8/8 assertions PASS.

Evidencia: [HTML Newman](newman-TC-M09-52-intento1.html) ·
[JSON Newman](newman-TC-M09-52-intento1.json) ·
[datos y payload](datos-TC-M09-52-intento1.json).

## TC-M09-53 — APROBADO (tras corregir la expectativa de la prueba)

- Endpoint: `POST /configuracion/umbrales`. Intentos: **2 POST** (máximo permitido),
  sin tercero.
- Ambos intentos devolvieron **HTTP 422** con la misma respuesta sanitizada:

```json
{
  "error_code": "SOLAPAMIENTO_NIVELES",
  "message": "Los niveles de alerta deben ser contiguos sin huecos ni solapamientos. El nivel 'precaucion' termina en 40 pero el siguiente comienza en 25.",
  "fields": [],
  "timestamp": "2026-09-05T21:44:0…"
}
```

- Intento 1 (expectativa del caso, «HTTP exactamente 400»): **7 de 8 assertions
  PASS**. La única fallida fue el status: *expected response to have status code
  400 but got 422*. Todo lo demás pasó, incluida la identificación del
  solapamiento y la ausencia de persistencia.
- Intento 2, tras corregir sólo la assertion de status al contrato real:
  **8/8 PASS**.
- El rechazo corresponde a la regla que G24 pretende probar y no a otra: el
  `error_code` es el del solapamiento y el mensaje cita el intervalo exacto en
  conflicto ([25, 40]) entre `precaucion` y `critico`.
- Sin ID creado; GET posterior **200** con 0 coincidencias para la variable 9 en
  ambos intentos.

El caso queda **APROBADO**: el comportamiento esperado de RF-17 se cumplió —el
solapamiento se rechaza, con el código correcto y sin persistencia—, el único
fallo fue de la prueba y se corrigió dentro del reintento disponible. No hay nada
que reportar a Desarrollo y no se genera incidencia.

Evidencia: [HTML intento 1](newman-TC-M09-53-intento1.html) ·
[JSON intento 1](newman-TC-M09-53-intento1.json) ·
[HTML intento 2](newman-TC-M09-53-intento2.html) ·
[JSON intento 2](newman-TC-M09-53-intento2.json) ·
[datos intento 1](datos-TC-M09-53-intento1.json) ·
[datos intento 2](datos-TC-M09-53-intento2.json).

## TC-M09-54 — DESAPROBADO — DEFECTO DEL PRODUCTO — REPORTAR A DESARROLLO

- Endpoint: `POST /configuracion/umbrales`. Intentos: **2 POST**, el segundo
  autorizado tras verificar ausencia de persistencia y validez del payload. **No
  se hizo un tercer POST.**
- Ambos intentos: **HTTP 500**.

```json
{
  "error_code": "ERROR_INTERNO",
  "message": "Error inesperado en base de datos",
  "fields": [],
  "timestamp": "2026-09-05T21:45:23.594504+00:00"
}
```

- No se creó ID. GET posterior **200**, total 2, IDs 10 y 11, **0 coincidencias**
  para la variable 9 en los dos intentos y en la verificación final. Sin
  persistencia parcial detectable por API.
- Intento 1: 1 de 11 assertions PASS. Intento 2: 2 de 15 assertions PASS. Todas
  las fallidas derivan del 500: no hay 201, ni ID, ni cuerpo del umbral sobre el
  que evaluar continuidad.
- La verificación matemática de continuidad exigida por el caso (nivel1.inferior
  == valor_min, fronteras compartidas, nivel3.superior == valor_max, cada nivel
  con inferior < superior, ausencia de solapamiento y cobertura completa) está
  implementada y ejecutada en la colección, pero **no pudo evaluarse sobre datos
  reales** porque el registro nunca llegó a crearse.

Evidencia: [HTML intento 1](newman-TC-M09-54-intento1.html) ·
[JSON intento 1](newman-TC-M09-54-intento1.json) ·
[HTML intento 2](newman-TC-M09-54-intento2.html) ·
[JSON intento 2](newman-TC-M09-54-intento2.json) ·
[datos intento 1](datos-TC-M09-54-intento1.json) ·
[datos intento 2](datos-TC-M09-54-intento2.json).

---

## Newman

| Ejecución | Requests de colección | Assertions | Failures | POST | Resultado |
|---|---:|---:|---:|---|---|
| TC-M09-52 intento1 | 2 (POST + GET) | 8 | 0 | 400 | PASS |
| TC-M09-53 intento1 | 2 (POST + GET) | 8 | 1 | 422 | FAIL (expectativa de la prueba, corregida) |
| TC-M09-53 intento2 | 2 (POST + GET) | 8 | 0 | 422 | PASS |
| TC-M09-54 intento1 | 2 (POST + GET) | 11 | 10 | 500 | FAIL |
| TC-M09-54 intento2 | 2 (POST + GET) | 15 | 13 | 500 | FAIL |

Los conteos excluyen login, preflight, descubrimiento y el GET de comprobación del
runner. Una invocación ejecuta un único original mediante la variable `G24_CASE`.
Los HTML los generó el reporter `htmlextra` durante la ejecución real de Newman;
no son HTML manuales. El JSON es un resumen estructurado propio con payload,
respuesta, estadísticas y GET, sin volcar el entorno con credenciales.

En ningún POST hubo 201, 409 ni 412. El 500 no se aceptó como PASS en ningún caso.

Nota de automatización propia: el intento 1 de TC-M09-54 registró además un
`SyntaxError` en la última assertion del GET de la colección (`Identifier 'o' has
already been declared`). Era un defecto de la colección QA, no del producto; se
corrigió antes del único reintento y en el intento 2 esa assertion ya ejecuta. No
altera el resultado, porque el registro no existía en ninguno de los dos casos.

## Cypress

Configuración aplicada: `screenshotOnRunFailure: true`, `video: false`,
`retries: 0`, `trashAssetsBeforeRuns: false`, capturas en
`RESULTADOS/screenshots/<G24_RUN_ID>/`. Login y navegación reales contra TEST.
Los `cy.intercept` solo observaron tráfico; ninguna respuesta fue sustituida. Sin
mocks, sin `cy.wait` numéricos, sin pausas fijas y **sin `force:true`**.

| Run ID | Caso | Recorrido | Resultado | POST de umbral | Capturas |
|---|---|---|---|---:|---:|
| ui52-intento1 | TC-M09-52 | 1 | FAIL (actionability, ver `QA-JE-G24-UI-01`) | 0 | 1 |
| ui52-intento2 | TC-M09-52 | 2 | PASS | 0 | 3 |
| ui53-intento1 | TC-M09-53 | 1 | PASS | 0 | 2 |
| ui53-intento2 | TC-M09-53 | 2 | PASS | 0 | 3 |
| ui54-intento1 | TC-M09-54 | 1 | PASS | 0 | 1 |

Máximo de dos recorridos por original respetado. **Ningún recorrido emitió un POST
de umbral**: para TC52 y TC53 el frontend replica las reglas de RF-17 en
`src/configuration/lib/validarUmbral.ts` y bloquea el envío en cliente, lo que es
evidencia UI válida; Newman sigue siendo la evidencia de API. Para TC-M09-54,
Cypress **no intentó crear el umbral** que Newman no pudo crear: sólo documentó el
estado observable, sin POST adicional.

Mensajes visuales observados y capturados:

- TC-M09-52: `El nivel "critico" (40–85) cae fuera del rango general [-20, 70].`
- TC-M09-53: `Los niveles de alerta deben ser contiguos sin huecos ni solapamientos. El nivel "precaucion" termina en 40 pero el siguiente comienza en 25.`

Capturas principales:

- TC-M09-52: [datos inválidos](<screenshots/ui52-intento2/tc-m09-g24-niveles-alerta.cy.ts/TC-M09-52-datos-invalidos.png>) ·
  [niveles](<screenshots/ui52-intento2/tc-m09-g24-niveles-alerta.cy.ts/TC-M09-52-niveles.png>) ·
  [validación](<screenshots/ui52-intento2/tc-m09-g24-niveles-alerta.cy.ts/TC-M09-52-validacion.png>)
- TC-M09-53: [solapamiento](<screenshots/ui53-intento2/tc-m09-g24-niveles-alerta.cy.ts/TC-M09-53-solapamiento.png>) ·
  [niveles](<screenshots/ui53-intento2/tc-m09-g24-niveles-alerta.cy.ts/TC-M09-53-niveles.png>) ·
  [validación](<screenshots/ui53-intento2/tc-m09-g24-niveles-alerta.cy.ts/TC-M09-53-validacion.png>) ·
  [recorrido 1](<screenshots/ui53-intento1/tc-m09-g24-niveles-alerta.cy.ts/TC-M09-53-validacion.png>)
- TC-M09-54: [sin persistencia](<screenshots/ui54-intento1/tc-m09-g24-niveles-alerta.cy.ts/TC-M09-54-sin-persistencia.png>)
- Diagnóstico del defecto visual: [recorrido fallido TC-M09-52](<screenshots/ui52-intento1/tc-m09-g24-niveles-alerta.cy.ts/G24 - niveles de alerta fuera de rango, solapamiento y continuidad -- TC-M09-52 (failed).png>)

Resultados estructurados: [TC52 r1](cypress-TC-M09-52-ui52-intento1.json) ·
[TC52 r2](cypress-TC-M09-52-ui52-intento2.json) ·
[TC53 r1](cypress-TC-M09-53-ui53-intento1.json) ·
[TC53 r2](cypress-TC-M09-53-ui53-intento2.json) ·
[TC54 r1](cypress-TC-M09-54-ui54-intento1.json) · evidencia UI:
[TC52](ui-TC-M09-52-ui52-intento2.json) · [TC53](ui-TC-M09-53-ui53-intento2.json) ·
[TC54](ui-TC-M09-54-ui54-intento1.json).

Antes del primer recorrido hubo tres arranques de Cypress que fallaron por
herramientas, sin abrir el navegador ni tocar TEST: `ELECTRON_RUN_AS_NODE=1`
heredado del entorno (Cypress rechaza su propio bytecode), `typescript` no
resoluble desde el proyecto backend y ausencia de `tsconfig.json`. Se resolvieron
ajustando la invocación y añadiendo un `tsconfig.json` local del caso. No cuentan
como recorridos: no ejecutaron el spec.

## Persistencia

| Momento | Especie 4 — total | IDs | Umbrales de la variable 9 |
|---|---:|---|---:|
| Antes de cada POST (5 descubrimientos) | 2 | 10, 11 | 0 |
| Después de TC-M09-52 | 2 | 10, 11 | 0 |
| Después de TC-M09-53 (ambos intentos) | 2 | 10, 11 | 0 |
| Después de TC-M09-54 (ambos intentos) | 2 | 10, 11 | 0 |
| Verificación final de cierre | 2 | 10, 11 | 0 |

TC-M09-52 y TC-M09-53 no persistieron nada: correcto. TC-M09-54 tampoco creó
registro, que es justamente el defecto. **No se creó ningún umbral en TEST durante
G24**, por lo que no hay ID nuevo que conservar. No se eliminó ni desactivó ningún
dato: los umbrales 10 y 11 permanecen intactos. Comprobación final en
[verificacion-final-readonly.json](verificacion-final-readonly.json).

---

## Defectos

### QA-JE-G22-01 (reproducción, no es una incidencia nueva)

**Reproducción del defecto conocido `QA-JE-G22-01` mediante TC-M09-54.** No se
crean incidencias distintas: el comportamiento es el mismo defecto ya reportado,
con evidencia adicional.

- Caso: TC-M09-54. RF: RF-17. CU-03. Módulo 9.
- Título: POST de umbral válido devuelve HTTP 500 y no persiste el registro.
- Precondiciones verificadas por API: login 200; permisos del recurso 20 (crear y
  consultar); especie 4 Cachama Blanca activa; variable 9 Temperatura Ambiental
  activa, °C, límites −50 a 100; combinación (4, 9) libre incluyendo inactivos.
- Datos reales: `id_especie=4`, `id_variable_ambiental=9`, `valor_min=-20`,
  `valor_max=70`, niveles normal −20 a 10, precaucion 10 a 40, critico 40 a 70.
- Pasos: autenticar como Administrador TEST → consultar permisos y catálogos →
  comprobar combinación libre → `POST /configuracion/umbrales` con esos datos →
  `GET /configuracion/umbrales?id_especie=4`.
- Esperado: HTTP 201, ID positivo, especie y variable correctas, estado activo,
  rango y tres niveles continuos conservados en el GET.
- Obtenido: HTTP 500, `ERROR_INTERNO`, `"Error inesperado en base de datos"`.
- Endpoint / método / status: `POST /configuracion/umbrales` / POST / 500.
- Persistencia: ninguna, verificada por GET tras cada intento y al cierre.
- Intento 1: 2026-09-05T21:44:36.825Z. Intento 2: 2026-09-05T21:45:23.594Z. Mismo
  payload, mismo resultado.
- Evidencia Newman: `newman-TC-M09-54-intento1.html/.json`,
  `newman-TC-M09-54-intento2.html/.json`.
- Evidencia Cypress: `TC-M09-54-sin-persistencia.png` — la tabla de umbrales de
  Cachama Blanca muestra únicamente #10 y #11; no aparece Temperatura Ambiental.
- Severidad sugerida: **Alta** (impide la configuración válida probada).
- Equipo responsable: **Desarrollo**.
- Relación con defecto previo: **es el mismo `QA-JE-G22-01`**, ahora reproducido
  desde otro caso y con niveles distintos a los originales de G22 en su
  construcción, pero idéntico resultado. Aporta un dato nuevo: el 500 aparece con
  una configuración cuya continuidad es exacta, de modo que no depende de la
  cobertura de los niveles.
- No se investigó de nuevo la incompatibilidad ORM/enum de G22, no se tocó
  backend, ORM, enum ni migraciones, y no se consultó PostgreSQL: el API y el GET
  bastaron para demostrar la ausencia de persistencia.

### QA-JE-G24-UI-01 — Campos de niveles superpuestos en el modal (hallazgo de interfaz)

- Severidad sugerida: **Media**. Equipo: **Desarrollo**. Requiere revisión humana.
- Reproduce el hallazgo `QA-JE-G23-UI-01` de G23, ahora con viewport 1920×1400 y
  Electron 118: en `Nuevo umbral ambiental`, el input `normal_sup` queda **cubierto
  por** `precaucion_inf`, lo que impide interactuar con él por clic estándar.
- Evidencia: recorrido ui52-intento1, error de actionability de Cypress con ambos
  elementos identificados, y captura del fallo. En la captura se aprecia que los
  campos numéricos de las tarjetas de nivel desbordan su columna: a 560 px de
  ancho de modal las tres `NivelCard` se reparten en dos columnas y el desborde de
  una cae sobre el input de la siguiente.
- Con el ancho de PWA (440 px) las tarjetas se apilan en una sola columna, los seis
  campos son accesibles y el formulario se completa con normalidad; el desborde
  horizontal persiste dentro de la tarjeta pero ya no cubre otro campo. Así se
  obtuvo la evidencia visual definitiva, sin `force:true` y sin modificar el
  producto.
- No se afirma que la interacción por teclado sea imposible ni que afecte a todos
  los tamaños de pantalla. No es un fallo de las reglas de niveles probadas en G24:
  las validaciones se mostraron correctamente en ambos originales.

---

## Seguridad

- Contraseña usada sólo en memoria del proceso, vía `TEST_ADMIN_PASSWORD`. Token
  sólo en memoria. No se imprimió ni persistió ninguna credencial, JWT, refresh
  token, cookie ni cabecera `Authorization` completa.
- Reporter configurado con `omitHeaders`, `showEnvironmentData: false`,
  `showGlobalData: false` y `skipEnvironmentVars: ['token']`; además, sanitización
  posterior del HTML y de todo JSON escrito.
- Barrido automático de secretos sobre los 20 archivos de evidencia textual
  (HTML, JSON y este informe) antes de cerrar G24: **sin hallazgos**. Registrado en
  [seguridad-evidencias.json](seguridad-evidencias.json). Las 10 capturas usan
  blackout de correo y contraseña y se revisaron: no muestran secretos.
- **No se usó PostgreSQL, ni siquiera SELECT.** El API y los GET resolvieron toda
  la comprobación de persistencia. Ningún SQL de escritura, migración ni cambio
  de datos.
- No se modificó código funcional (backend `src/` ni frontend `src/`), DTO, modelo,
  router, servicio, repositorio, caso de uso, componente, hook, cliente de API,
  migraciones, seeds ni infraestructura. Sólo se leyeron para entender el contrato.
- No se modificaron dependencias ni `package.json`; no se ejecutó ningún instalador.
- No se tocó Dokploy, dominios, Docker, Nginx, contenedores ni variables de
  despliegue.
- No se creó, editó, desactivó ni eliminó ningún umbral ajeno. No se creó ningún
  umbral propio (el POST válido falló). No se probó RBAC ni se usaron otros
  actores: sólo Administrador.
- No se ejecutó G22 ni G23; no se modificaron sus archivos. G25 no se inició.
- No hubo `git commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `stash`, cambio
  de rama ni ninguna operación de escritura de Git.

## Git

Estado final verificado tras las ejecuciones.

Backend (`qa/juan-esteban-m09`, `adc3932b9f0293a76ebec7e89ed877274791b6a1`):
`git diff --stat` vacío — ningún archivo versionado modificado. `git status --short`:

```text
?? tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/RESULTADOS/
?? tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/TC-M09-G24.postman_collection.json
?? tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/cypress.config.cjs
?? tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/helpers.cjs
?? tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/run-newman.cjs
?? tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/tc-m09-g24-niveles-alerta.cy.ts
?? tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/tsconfig.json
?? tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/verificar-cierre.cjs
```

(`README.md` del caso se añade a esa misma lista.) Todo lo nuevo está dentro de
`TC-M09-G24/`; no se creó ni modificó nada fuera del caso.

Frontend (`qa/juan-esteban-m09`, `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`):
`git diff --stat` vacío y `git status --short` con exactamente los mismos ocho
archivos untracked preexistentes de G22 que había al comenzar. **G24 no escribió
nada en el repositorio de frontend.**

Resumen en [git-final.json](git-final.json).

---

## Estado de cierre

G24 queda ejecutado y detenido para revisión humana. TC-M09-52 APROBADO;
TC-M09-53 APROBADO tras corregir la expectativa de la prueba dentro del reintento
disponible; TC-M09-54 DESAPROBADO por defecto del producto, a reportar a
Desarrollo como evidencia de `QA-JE-G22-01`. El grupo queda DESAPROBADO por ese
único caso. No se inicia G25.
