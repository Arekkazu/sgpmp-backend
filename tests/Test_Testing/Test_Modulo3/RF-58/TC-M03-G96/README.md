# TC-M03-G96 — RF-58 / CU04

Caso original: TC-M03-187. Newman verifica que el dashboard expone para `estado_conectividad` solo valores del catálogo de RF-58: `ONLINE`, `OFFLINE` o `SIN_SEÑAL`.

La matriz pide preparar o simular las tres condiciones: conectado, desconectado y sin señal.

## Preparación de cada condición

| Condición | Cómo se obtiene |
| --- | --- |
| **ONLINE** (conectado) | Se construye en el sandbox: área QA, dispositivo sin gateway, sensor calibrado y una lectura válida con `estado_conectividad=true` por `POST /iot/telemetria`. El trigger `fn_actualizar_estado_sensor` registra ACTIVO. |
| **SIN_SEÑAL** y **OFFLINE** | Se descubren en solo lectura entre unidades del Productor. |

**Por qué SIN_SEÑAL y OFFLINE no se construyen.** RF-58 indica que esos estados provienen de RF-60, es decir, de la transición por ausencia de reportes. Esa transición la calcula una tarea periódica global que no ve el sandbox. Enviar `estado_conectividad=false` en una lectura que sí llega sería el estado que comunica el dispositivo, no la ausencia de reportes, por eso no se usa. Tampoco se escribe SQL.

**Consulta de descubrimiento.** Antes de cada consulta se declara la identidad de Administrador, porque las tablas de `modulo9` tienen RLS por rol.

**Si falta alguna condición:**
- se evalúan las condiciones disponibles;
- la colección omite las demás;
- el caso queda **BLOQUEADO**: no hay cobertura completa.

## Aislamiento y veredicto

- **Aislamiento:** el testigo es el INSERT del dispositivo en `auditoria.logs_dml` (tabla sin RLS). Se exige 1 dentro del RUN, 0 desde otra transacción y 0 después del rollback.
- **Veredicto:**
  - BLOQUEADO: fallos de entorno, de rollback, de `[PRE]` o errores de script.
  - RECHAZADO: un `[ASSERT]` incumplido con respuesta real, aunque falten condiciones.
  - APROBADO: solo con las tres condiciones verificadas.

## Autenticación del dispositivo

Hoy se usa `access_key = serial`. DEV-06 la sustituirá por un token de servicio cuyo contrato aún no está definido; la adaptación se concentra en `cuerpoLectura`. `QA_DEVICE_PREFIX` es opcional; si está vacío se usa `QAAUTO`.

## Uso

Validación local:

```
node ejecutar_tc_m03_g96.mjs --validar-local
```

Ejecución futura, solo con autorización de Desarrollo:

```
node ejecutar_tc_m03_g96.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

Cada RUN produce un informe Markdown y `evidencia.json`. V1 se guarda en `RESULTADOS`; V2 y siguientes, en `EvaluacionVN/RESULTADOS`.
