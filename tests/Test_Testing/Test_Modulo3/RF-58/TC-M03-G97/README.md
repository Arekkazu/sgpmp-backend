# TC-M03-G97 — RF-58 / CU04

Casos originales: TC-M03-188, 189, 190 y 210 (vistas y payloads diferenciados por rol).

- **Newman** compara el JSON crudo que reciben Productor, Ingeniero y Veterinario sobre la misma unidad.
- **Cypress** comprueba la vista de cada rol con su propia sesión.

## Escenario construido en el sandbox (APIs oficiales)

Ya no depende de encontrar una unidad preexistente.

1. **Finca:**
   - Si existe, se usa una finca compartida por los cuatro actores (Administrador de preparación, Productor, Ingeniero y Veterinario).
   - Si no, se crea con acceso del Productor y se agrega de forma **aditiva** al Ingeniero y al Veterinario.
   - La asignación solo se aplica si las fincas que ve cada usuario coinciden exactamente con sus asignaciones activas en `usuarios_fincas`.
   - Después se verifica que el conjunto final sea exactamente el previo más la finca nueva.
   - Si no puede garantizarse, se bloquean solo los casos de ese rol.
2. **Área y activo:** un área QA con un **único activo biológico INDIVIDUAL**. RF-61 lo exige para VINCULAR la lectura.
3. **Dispositivo y sensor:** dispositivo sin gateway y sensor calibrado.
4. **Lectura:** `TEMPERATURA_CORPORAL` (38.6 °C) con batería, RSSI y SNR. Se comprueba que quede VINCULADA al activo; si no, se bloquea TC-M03-190.
5. **Alerta:** alerta activa por `POST /iot/alertas`, sobre esa lectura.

**Límite del contrato.** Ninguna API oficial asocia explícitamente una alerta a un activo: `POST /iot/alertas` y `/iot/eventos-edge` no reciben `id_activo_biologico`. La alerta se crea para el sensor vinculado. Que el sistema la muestre con el contexto clínico del activo es lo que evalúa API-190-03; no se fuerza.

## Ejecución, aislamiento y veredicto

- **Peticiones secuenciales:** el ejecutor y las colecciones no lanzan peticiones en paralelo, porque el sandbox comparte una sola sesión de base de datos.
- **Aislamiento:** el testigo es el INSERT del dispositivo en `auditoria.logs_dml`. Se exige 1 dentro del RUN, 0 desde otra transacción y 0 después del rollback.
- **Veredicto por caso:**
  - BLOQUEADO: fallos de entorno, de rollback, de precondición, del hook de Cypress (login) o errores de script.
  - RECHAZADO: solo un `[ASSERT]` incumplido con respuesta real.

## Autenticación del dispositivo

Hoy se usa `access_key = serial` (`cuerpoDispositivo`). DEV-06 la sustituirá por un token de servicio aún no definido.

## Uso

Validación local:

```
node ejecutar_tc_m03_g97.mjs --validar-local
node --test validar_local_g97.mjs
```

Descubrimiento local del spec, sin red:
- Usa `cypress.verificacion.config.cjs`, que solo tiene destinos de loopback, y nunca el `cypress.config.cjs` raíz.
- Antes de lanzar Cypress comprueba que no quede ningún destino remoto (configuración, anulaciones, `cypress.env.json`, variables `CYPRESS_*`) y bloquea la salida con un proxy de loopback inexistente. Si algo falla, Cypress no se ejecuta.
- Sin `baseUrl` y sin autorización, el `before` se detiene en `BLOQUEO_G97`.
- Exige además que prevalezcan las anulaciones en `e2e` y que no aparezcan artefactos nuevos.

```
node ejecutar_tc_m03_g97.mjs --verificar-spec
```

**Configuración de Cypress (`opcionesCypress`):**
- El proyecto es la raíz del repositorio y `specPattern` es la ruta relativa del spec. Con solo el nombre del archivo, Cypress no lo encontraba.
- Las anulaciones van dentro de `e2e`, porque el bloque `e2e` del `cypress.config.cjs` raíz prevalece sobre las de nivel superior.
- El proceso hijo no hereda `ELECTRON_RUN_AS_NODE`, que impide arrancar Cypress desde la terminal de VS Code.

**UI-188-01:** el semáforo se valida por correspondencia. La tarjeta debe mostrar un único indicador visible cuyo estado (la etiqueta de la interfaz, «Normal», «Advertencia», «Fuera de rango» o «Sin señal», o el nombre del estado) coincida con el `estado_semaforo` que el dashboard entrega para ese sensor.

Ejecución futura, solo con autorización de Desarrollo y QA:

```
node ejecutar_tc_m03_g97.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

Cada RUN produce un informe con el resultado por caso y `evidencia.json`. V1 se guarda en `RESULTADOS`; V2 y siguientes, en `EvaluacionVN/RESULTADOS`.
