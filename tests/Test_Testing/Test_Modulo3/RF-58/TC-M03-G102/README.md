# TC-M03-G102 — RF-58 / CU04

Casos originales: **TC-M03-201, TC-M03-202 y TC-M03-213** (límite de 50 sensores por vista, soporte de hasta 200 mediante segmentación y resistencia del límite ante tamaños excesivos, OWASP API4).

- **Newman** valida el contrato de `GET /iot/monitoreo/dashboard`.
- **Cypress** valida el renderizado real de la vista `/telemetria/monitoreo` (casos 201 y 202).

## Escenario construido en el sandbox (APIs oficiales)

No depende de datos preexistentes.

| Unidad | Sensores activos | Casos |
| --- | --- | --- |
| U50 | 50 | 201 |
| U51 | 51 | 201 |
| U200 | 200 | 202 y 213 |

- **Cada sensor**: se registra, se asocia al área, se calibra y recibe una lectura válida (RF-53). La lectura crea su estado actual, que es lo que lista el dashboard.
- **Un dispositivo sin gateway por unidad**: sin MQTT y dentro del límite de registro de dispositivos (10/min).
- **Finca**: compartida por la cuenta de preparación y el Ingeniero o, si no existe, creada con `id_usuario` del Ingeniero. No se modifican sus asignaciones previas.
- **Actor del dashboard: Ingeniero de Campo** (actor de CU04). La matriz no fija actor. El Productor no tiene lectura sobre `modulo9.sensores` por RLS (solo Administrador e Ingeniero), así que no vería sensores en ninguna vista.

**Precondiciones `[PRE]`** (si fallan, la unidad afectada queda BLOQUEADA, nunca RECHAZADA):
- alcance del Ingeniero sobre cada unidad;
- acceso al dashboard;
- los N sensores de cada unidad tienen estado actual dentro del sandbox. Se cuenta en `modulo3.estados_actuales_sensores`, que no tiene RLS.

## Aserciones

| Caso | API (Newman) | Interfaz (Cypress) |
| --- | --- | --- |
| 201 | API-201-01/02: `por_pagina=50` → 200 y los 50 de U50 · API-201-03: U51 entrega como máximo 50 · API-201-04: el segmento 2 entrega el restante (51 sin duplicados ni omisiones) · API-201-05: `por_pagina=51` → **422** | UI-201-01: con 50 se renderizan todos · UI-201-02: con 51 no más de 50 a la vez · UI-201-03: la segmentación permite consultar el sensor 51 |
| 202 | API-202-01: cada segmento → 200, como máximo 50, todos de la unidad · API-202-02: los 200 sin duplicados ni omisiones · API-202-03: sin sensores de otras unidades | UI-202-01: ningún segmento renderiza más de 50 · UI-202-02: recorriendo la segmentación se consultan los 200 |
| 213 | API-213-01/02/03: `por_pagina` = 51, 500 y 100000 nunca entregan más de 50 sensores. El código HTTP de cada uno se registra como INFO (la matriz no exige uno concreto) | — |

**Detección de la segmentación en la interfaz.** No depende de una implementación concreta: sirve cualquier control visible tipo «siguiente», «cargar más» o «ver más». La matriz anticipa que hoy la vista pide `por_pagina=50` sin paginación (fallo esperado en la capa cliente, caso 201). Si no hay control, UI-201-03 y UI-202-02 lo registran como incumplimiento con evidencia.

**k6.** La matriz menciona k6 para carga con distintos tamaños de `por_pagina`, pero ningún resultado esperado exige un criterio de carga. k6 no está instalado y el sandbox serializa todas las peticiones del RUN en una sola sesión, así que una prueba de carga ahí no sería representativa. Los criterios funcionales de 202 y 213 se cubren con Newman. **REQUIERE DECISIÓN QA** si se quiere una prueba de carga fuera del sandbox.

## Aislamiento, rollback y veredicto

- **Aislamiento:** el testigo es el INSERT del primer dispositivo en `auditoria.logs_dml` (sin RLS). Se exige 1 dentro del RUN, 0 desde otra transacción y 0 tras el rollback. Una consulta fallida es «no verificable» y detiene el RUN.
- **Peticiones** siempre secuenciales (sesión única del sandbox). Cypress serializa las suyas en el `intercept`.
- **Veredicto por caso:**
  - RECHAZADO: un `[ASSERT]` incumplido con respuesta real y sin `[PRE]` fallido en su unidad.
  - BLOQUEADO: entorno, rollback, precondiciones, hooks de Cypress (login), errores de script o cobertura incompleta.
  - APROBADO: solo con todas las aserciones requeridas verificadas.
  - INFO nunca decide.

## Dependencias de Desarrollo

- **DEV-06:** la credencial del dispositivo (`access_key = serial`) está concentrada en `cuerpoLectura` (`monitoreo_lib.mjs`). El contrato del token de servicio no se inventa.
- **DEV-05:** si la actualización del estado actual pasa a post-commit, deja de verse dentro del sandbox. El `[PRE]` de estados actuales lo detecta y bloquea; no rechaza.

## Uso

Validación local, sin red:

```
node ejecutar_tc_m03_g102.mjs --validar-local
node --test validar_local_g102.mjs
```

Descubrimiento del spec con Cypress, aislado de la red:

```
node ejecutar_tc_m03_g102.mjs --verificar-spec
```

- Usa `cypress.verificacion.config.cjs`, que solo tiene destinos de loopback, y **nunca** el `cypress.config.cjs` raíz, cuyo `baseUrl` es remoto.
- Antes de lanzar Cypress comprueba que no quede ningún destino remoto (configuración, anulaciones, `cypress.env.json`, variables `CYPRESS_*`) y bloquea la salida con un proxy de loopback inexistente. Si algo falla, Cypress no se ejecuta.
- Exige cuatro cosas: el spec descubierto, la barrera `BLOQUEO_G102` en el `before`, que prevalezcan las anulaciones de `e2e` y ningún artefacto nuevo.

**Configuración de Cypress en ejecución autorizada (`opcionesCypress`):**
- `baseUrl` = frontend de TEST (`SIGAB_FRONT_TEST_URL`), distinto del API (`env.API_BASE`). La barrera rechaza que coincidan.
- Las anulaciones van dentro de `e2e`. El bloque `e2e` del `cypress.config.cjs` raíz (con `baseUrl` `https://api.inmero.co`, mochawesome y capturas) prevalecía sobre las de nivel superior.
- El reporter es de consola y el proceso hijo no hereda `ELECTRON_RUN_AS_NODE`.

Ejecución futura, solo con autorización de Desarrollo y `QA_AUTORIZADO=SI`:

```
node ejecutar_tc_m03_g102.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

- `--tipo reintento` conserva la versión.
- V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`.
- Cada RUN produce un informe Markdown, `evidencia.json` y, solo si falla una prueba de interfaz, capturas.
- La construcción de 301 sensores supone unas 1.200 peticiones secuenciales dentro del sandbox. El timeout de inactividad de 180 s se renueva con cada petición.
