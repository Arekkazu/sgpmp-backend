# TC-M03-G104 — RF-58 / CU04 (RNF-06)

Caso original: **TC-M03-204**. La vista `/telemetria/monitoreo` debe permanecer usable a **360 px** de ancho mínimo, con sensores en VERDE, AMARILLO, ROJO y GRIS. Deben seguir visibles y utilizables el valor, la unidad, el semáforo, las alertas y los controles principales, sin superposición ni recorte de información crítica.

Herramienta: **Cypress**, porque la matriz solo pide interfaz; no hay colección Newman. El actor es el **Ingeniero de Campo** (actor de CU04). El Productor no lee `modulo9.sensores` por RLS.

## Preparación de los cuatro estados

| Estado | Origen | Mecanismo |
| --- | --- | --- |
| VERDE | Construido en el sandbox | Sensor registrado, asociado y calibrado, con una lectura válida (RF-53) |
| AMARILLO | Construido en el sandbox | Lectura válida y alerta activa **MODERADO** por `POST /iot/alertas` (RF-57) |
| ROJO | Construido en el sandbox | Lectura válida y alerta activa **CRITICO** por `POST /iot/alertas` (RF-57) |
| GRIS | Descubierto en solo lectura | Sensor en GRIS con valor y unidad, buscado en el dashboard del propio Ingeniero |

- **AMARILLO y ROJO:** el trigger `fn_sincronizar_alerta_en_sensor` lleva el semáforo a AMARILLO o ROJO, y la alerta activa también es criterio del caso.
- **GRIS:** solo lo produce la **transición de RF-60** por ausencia de reportes, una tarea periódica global sin disparador aislado. No se simula ni se escribe SQL. Si no se descubre un sensor apto, la variante GRIS queda BLOQUEADA y el caso no puede aprobarse.
- **Comprobación previa:** antes de abrir la interfaz, cada estado se verifica por API como `[PRE]` de su variante (semáforo, valor, unidad y alerta). Un estado que no quede preparado se bloquea; nunca se rechaza.

## Aserciones

A 360 × 740 px (decisorio), para cada estado preparado:

| ID | Comprobación |
| --- | --- |
| UI-204-01 | La página no tiene desplazamiento horizontal. Los controles principales de la vista (filtro, refresco automático y refresco manual) son visibles y utilizables. |
| UI-204-02 | El valor, la unidad y el semáforo de la tarjeta son visibles y no se superponen. |
| UI-204-03 | La alerta activa es visible sin recorte ni superposición (en AMARILLO y ROJO). |
| UI-204-04 | La tarjeta abre su detalle, el detalle cabe en el ancho y se puede cerrar (en VERDE). |

- **«Visible y utilizable»** significa, para cada elemento:
  - tiene tamaño y visibilidad;
  - queda dentro del ancho de la pantalla;
  - no lo recorta ningún contenedor con `overflow`;
  - no queda tapado por otro elemento (comprobado con `elementFromPoint` en su centro).
- **Resoluciones superiores** (768 × 1024 y 1366 × 768): repiten las comprobaciones como **INFO**, no decisorias. El resultado esperado de la matriz solo fija el criterio a 360 px.
- **Localización de elementos:** por contenido visible (nombre del sensor, número, unidad, etiqueta del semáforo y `aria-label` de la alerta), no por la estructura interna de los componentes.

## Aislamiento, rollback y veredicto

- **Aislamiento:** el testigo es el INSERT del dispositivo en `auditoria.logs_dml`. Se exige 1 dentro del RUN, 0 fuera y 0 tras el rollback. Una consulta fallida es «no verificable» y detiene el RUN.
- **Tráfico:** Cypress serializa sus peticiones en el `intercept` y verifica el eco del sandbox. No hay respuestas simuladas ni relojes falsos.
- **Veredicto:**
  - RECHAZADO: un `[ASSERT]` a 360 px incumplido en una variante bien preparada. Se conserva aunque otra variante, por ejemplo GRIS, esté bloqueada.
  - BLOQUEADO: falta un estado, una precondición o el login (hook), o hay fallos de entorno, rollback o automatización.
  - APROBADO: solo con los cuatro estados verificados.

## Dependencias de Desarrollo

- **RF-60:** disparador aislado de la transición por ausencia de reportes, para construir GRIS dentro del sandbox.
- **DEV-06:** la credencial del dispositivo está concentrada en `cuerpoLectura` y `cuerpoAlerta` (`monitoreo_lib.mjs`).
- **DEV-11, DEV-12 y DEV-13:** si cambia el contrato de alertas, se adapta en `cuerpoAlerta`.
- **DEV-05:** si el estado actual pasa a post-commit, el `[PRE]` lo detecta y bloquea.

## Uso

```
node ejecutar_tc_m03_g104.mjs --validar-local
node --test validar_local_g104.mjs
node ejecutar_tc_m03_g104.mjs --verificar-spec
node ejecutar_tc_m03_g104.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

**`--verificar-spec`:** descubre el spec con Cypress aislado de la red.
- Usa `cypress.verificacion.config.cjs`, que solo tiene destinos de loopback, nunca el `cypress.config.cjs` raíz.
- Antes de lanzar comprueba que no quede ningún destino remoto y bloquea la salida con un proxy de loopback inexistente.
- Pasa una variante local ficticia para que el spec registre pruebas y su `before` se detenga en `BLOQUEO_G104`.

**En ejecución autorizada (`opcionesCypress`):**
- `baseUrl` es el frontend de TEST, distinto del API (`env.API_BASE`).
- Las anulaciones van dentro de `e2e`, porque el bloque `e2e` raíz (con `baseUrl` `https://api.inmero.co`) prevalecía.
- El reporter es de consola y el proceso no hereda `ELECTRON_RUN_AS_NODE`.

La ejecución solo procede con autorización de Desarrollo y `QA_AUTORIZADO=SI`. V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`. Cada RUN produce un informe Markdown, `evidencia.json` y, solo si falla una prueba, capturas.
